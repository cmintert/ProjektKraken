"""Tests for session context-tag state, recovery, and controls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, QSettings

from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
from src.app.coordinators.editor_coordinator import EditorCoordinator
from src.commands.base_command import CommandResult
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand, UpdateEntityCommand
from src.commands.event_commands import CreateEventCommand, UpdateEventCommand
from src.gui.dialogs.context_tag_dialogs import (
    ContextReviewModel,
    ContextTagEditorDialog,
)
from src.gui.widgets.context_tag_bar import ContextTagBar


class FakeWindow(QObject):
    def __init__(self, world_id: str = "world-a") -> None:
        super().__init__()
        self.current_world = SimpleNamespace(id=world_id)
        self.event_editor = MagicMock()
        self.entity_editor = MagicMock()
        self.event_editor._current_event_id = None
        self.entity_editor._current_entity_id = None
        self.event_editor.has_unsaved_changes.return_value = False
        self.entity_editor.has_unsaved_changes.return_value = False
        self.navigation_coordinator = MagicMock()


@pytest.fixture
def context_settings(tmp_path):
    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    settings.clear()
    return settings


@pytest.fixture
def context(qapp, context_settings):
    return ContextTagCoordinator(FakeWindow(), context_settings)


def finish(command, *, success=True):
    return CommandResult(
        success=success,
        command_name=command.__class__.__name__,
        data={"command_id": command.command_id},
    )


def test_inactive_set_is_remembered_but_not_applied(context):
    context.save_tags(["Foggenburg", "Adventure"], activate=False)

    command = context.create_entity_command({"name": "Gate", "type": "Location"})

    assert context.remembered_tags == ["Foggenburg", "Adventure"]
    assert not context.is_active
    assert command._entity.tags == []


def test_active_set_appends_tags_without_case_folding_or_duplicates(context):
    context.save_tags(["Foggenburg", "adventure"], activate=True)

    command = context.create_entity_command(
        {
            "name": "Gate",
            "type": "Location",
            "attributes": {"_tags": ["Foggenburg", "Adventure"]},
        }
    )

    assert command._entity.tags == ["Foggenburg", "Adventure", "adventure"]


def test_pending_command_keeps_submission_set_after_context_changes(context):
    context.save_tags(["Old Context"], activate=True)
    command = context.create_event_command({"name": "Arrival", "lore_date": 0.0})
    context.save_tags(["New Context"], activate=True)

    context.on_command_finished(finish(command))
    context.reconcile([command.event], [])

    assert context.review_records()[0]["tags"] == ["Old Context"]


def test_failed_creation_does_not_enter_recovery(context):
    context.save_tags(["Context"], activate=True)
    command = context.create_event_command({"name": "Arrival", "lore_date": 0.0})

    context.on_command_finished(finish(command, success=False))
    context.reconcile([command.event], [])

    assert context.review_records() == []
    assert context.snapshot()["affected_count"] == 0


def test_recovery_and_remembered_set_persist_but_activation_does_not(
    context_settings,
):
    first = ContextTagCoordinator(FakeWindow(), context_settings)
    first.save_tags(["City"], activate=True)
    command = first.create_entity_command({"name": "Inn", "type": "Location"})
    first.on_command_finished(finish(command))

    restored = ContextTagCoordinator(FakeWindow(), context_settings)
    restored.reconcile([], [command._entity])

    assert restored.remembered_tags == ["City"]
    assert not restored.is_active
    assert restored.snapshot()["affected_count"] == 1


def test_settings_are_isolated_by_world(context_settings):
    first = ContextTagCoordinator(FakeWindow("world-a"), context_settings)
    first.save_tags(["City A"], activate=False)

    second = ContextTagCoordinator(FakeWindow("world-b"), context_settings)

    assert second.remembered_tags == []


def test_malformed_settings_fall_back_safely(context_settings):
    context_settings.setValue("worlds/world-a/context_tags/v1/last_tags", "not-json")
    context_settings.setValue(
        "worlds/world-a/context_tags/v1/recovery_ledger", "{broken"
    )

    restored = ContextTagCoordinator(FakeWindow(), context_settings)

    assert restored.remembered_tags == []
    assert restored.review_records() == []


def test_reconciliation_tracks_present_resolved_and_unavailable(context):
    context.save_tags(["City"], activate=True)
    command = context.create_entity_command({"name": "Inn", "type": "Location"})
    context.on_command_finished(finish(command))

    context.reconcile([], [command._entity])
    assert context.snapshot()["affected_count"] == 1

    command._entity.tags = []
    context.reconcile([], [command._entity])
    assert context.snapshot()["affected_count"] == 0

    command._entity.tags = ["City"]
    context.reconcile([], [command._entity])
    assert context.snapshot()["affected_count"] == 1

    context.reconcile([], [])
    assert context.snapshot()["affected_count"] == 0


def test_cleanup_is_one_composite_and_preserves_other_tags(context):
    context.save_tags(["City", "Adventure"], activate=True)
    entity_command = context.create_entity_command(
        {
            "name": "Inn",
            "type": "Location",
            "attributes": {"_tags": ["Keep"]},
        }
    )
    event_command = context.create_event_command(
        {
            "name": "Arrival",
            "lore_date": 0.0,
            "attributes": {"_tags": ["Later"]},
        }
    )
    context.on_command_finished(finish(entity_command))
    context.on_command_finished(finish(event_command))
    context.reconcile([event_command.event], [entity_command._entity])

    cleanup = context.build_cleanup_command(
        [("entity", entity_command._entity.id), ("event", event_command.event.id)]
    )

    assert isinstance(cleanup, CompositeCommand)
    assert isinstance(cleanup.commands[0], UpdateEntityCommand)
    assert isinstance(cleanup.commands[1], UpdateEventCommand)
    assert cleanup.commands[0].update_data["attributes"]["_tags"] == ["Keep"]
    assert cleanup.commands[1].update_data["attributes"]["_tags"] == ["Later"]


def test_dirty_selected_inspector_blocks_cleanup(context):
    context.main_window.entity_editor._current_entity_id = "entity-1"
    context.main_window.entity_editor.has_unsaved_changes.return_value = True

    with patch("src.app.coordinators.context_tag_coordinator.QMessageBox.information"):
        assert not context.request_cleanup([("entity", "entity-1")])


def test_editor_creation_and_map_creation_use_context_factory(qapp):
    window = FakeWindow()
    context = MagicMock()
    context.create_entity_command.side_effect = CreateEntityCommand
    context.create_event_command.side_effect = CreateEventCommand
    window.app_coordinator = SimpleNamespace(context_tags=context)
    window.command_requested = MagicMock()
    coordinator = EditorCoordinator(window)

    with patch(
        "src.app.coordinators.editor_coordinator.QInputDialog.getText",
        return_value=("Created", True),
    ):
        coordinator.create_entity()
        coordinator.create_event()
    coordinator.on_map_create_entity("map-entity", "Map Entity")
    coordinator.on_map_create_event("map-event", "Map Event")

    assert context.create_entity_command.call_count == 2
    assert context.create_event_command.call_count == 2


def test_context_bar_renders_inactive_active_and_review_states(qtbot):
    bar = ContextTagBar()
    qtbot.addWidget(bar)

    bar.set_state({"tags": [], "active": False, "affected_count": 0})
    assert bar.lbl_state.text() == "Context Tags: Off"
    assert bar.btn_edit.text() == "Set…"

    bar.set_state(
        {
            "tags": ["City", "Adventure"],
            "active": True,
            "affected_count": 3,
            "history_count": 3,
        }
    )
    assert bar.lbl_state.text() == "Context Tags Active"
    assert bar.btn_disable.isVisibleTo(bar)
    assert bar.btn_review.text() == "Review (3)"


def test_context_editor_reuses_tag_autocomplete(qtbot):
    dialog = ContextTagEditorDialog(
        ["City"],
        ["City", "Adventure"],
        active=False,
    )
    qtbot.addWidget(dialog)

    assert dialog.tag_editor._completer_model.stringList() == ["Adventure"]
    dialog.tag_editor._on_completion_activated("Adventure")
    assert dialog.tags() == ["City", "Adventure"]


def test_review_model_selection_is_record_based():
    records = [
        {
            "item_type": "entity",
            "item_id": "one",
            "name": "One",
            "tags": ["City"],
            "created_at": 1.0,
        },
        {
            "item_type": "event",
            "item_id": "two",
            "name": "Two",
            "tags": ["Adventure"],
            "created_at": 2.0,
        },
    ]
    model = ContextReviewModel(records)

    model.set_all_checked(False)
    assert model.selected_keys() == []
    model.set_all_checked(True)
    assert model.selected_keys() == [("entity", "one"), ("event", "two")]
