"""Scope persistence and presentation without canonical history changes."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from src.app.coordinators.app_coordinator import AppCoordinator
from src.app.coordinators.authoring_scope_coordinator import AuthoringScopeCoordinator
from src.app.coordinators.context_tag_coordinator import ContextTagCoordinator
from src.app.coordinators.graph_authoring import (
    GraphAuthoring,
    GraphSubmission,
    SavedGraphConnection,
)
from src.app.coordinators.scoped_history import ScopedHistory
from src.core.authoring_scope import AuthoringScope
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.timeline_grouping import build_group_metadata, events_for_group
from src.gui.dialogs.graph_connection_dialog import GraphConnectionDialog
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

pytestmark = pytest.mark.ci_fast


def test_any_requires_explicit_default_and_all_uses_all_tags():
    with pytest.raises(ValueError, match="creation tags"):
        AuthoringScope(("a", "b"))
    any_scope = AuthoringScope(("a", "b"), "any", ("a",))
    all_scope = AuthoringScope(("a", "b"), "all")
    assert any_scope.matches(["b"])
    assert not any_scope.matches(["B"])
    assert not all_scope.matches(["b"])
    assert all_scope.matches(["a", "b"])
    assert all_scope.creation_tags == ("a", "b")
    assert AuthoringScope.from_dict(any_scope.to_dict()) == any_scope


def test_scope_restores_per_world_and_clear_keeps_other_world_settings(
    qtbot, tmp_path, monkeypatch
):
    settings = QSettings(str(tmp_path / "scope.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        "src.app.coordinators.authoring_scope_coordinator.QSettings",
        lambda *_args: settings,
    )
    window = QWidget()
    qtbot.addWidget(window)

    def catalog():
        return ["Adventure", "Faction"]

    one = AuthoringScopeCoordinator("one", catalog, window)
    two = AuthoringScopeCoordinator("two", catalog, window)
    selected = AuthoringScope(("Adventure", "Faction"), "any", ("Adventure",))
    one.set_scope(selected)
    two.set_scope(AuthoringScope(("Faction",)))
    restored = AuthoringScopeCoordinator("one", catalog, window)
    assert restored.scope == selected
    restored.set_scope(AuthoringScope())
    assert AuthoringScopeCoordinator("one", catalog, window).scope == AuthoringScope()
    assert AuthoringScopeCoordinator("two", catalog, window).scope == two.scope


def test_follow_scope_and_explicit_custom_survive_reopen(tmp_path):
    owner = QObject()
    owner.current_world = SimpleNamespace(id="scope")
    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    tags = ContextTagCoordinator(owner, settings)
    tags.set_available_tags(["Adventure"])
    tags.set_scope_defaults(("Adventure",))
    tags.follow_scope()
    assert tags.graph_creation("entity", {"name": "Scout", "type": "Character"})[1] == [
        "Adventure"
    ]
    tags.save_tags(["Custom"])
    tags.enable()
    restored = ContextTagCoordinator(owner, settings)
    restored.set_scope_defaults(("Adventure",))
    assert restored.snapshot()["policy"] == "custom"
    assert restored.graph_creation("entity", {"name": "Scout", "type": "Character"})[
        1
    ] == ["Custom"]
    restored.follow_scope()
    assert not restored.is_active
    restored.set_available_tags(["Adventure"])
    assert restored.is_active


def test_context_tags_bind_after_world_selection(tmp_path):
    owner = QObject()
    owner.current_world = None
    settings = QSettings(str(tmp_path / "context.ini"), QSettings.Format.IniFormat)
    settings.setValue("worlds/default/context_tags/v1/policy", "custom")
    settings.setValue("worlds/default/context_tags/v1/custom_active", True)
    settings.setValue("worlds/default/context_tags/v1/last_tags", '["Wrong world"]')

    tags = ContextTagCoordinator(owner, settings)
    assert not tags.is_active
    tags.bind_world("one")
    tags.set_scope_defaults(("Scope One",))
    tags.set_available_tags(["Scope One"])
    assert tags.snapshot()["tags"] == ["Scope One"]
    tags.save_tags(["Custom One"])
    tags.enable()

    tags.bind_world("two")
    tags.set_scope_defaults(("Scope Two",))
    tags.set_available_tags(["Scope Two"])
    assert tags.snapshot()["policy"] == "follow"
    assert tags.snapshot()["tags"] == ["Scope Two"]

    restored = ContextTagCoordinator(owner, settings)
    restored.bind_world("one")
    assert restored.snapshot()["policy"] == "custom"
    assert restored.snapshot()["tags"] == ["Custom One"]
    assert restored.is_active


def test_explorer_intersects_local_search_and_preserves_active_pin(qtbot):
    explorer = UnifiedListWidget()
    qtbot.addWidget(explorer)
    scoped = Entity("Scout", "Character", attributes={"_tags": ["Adventure"]})
    outside = Entity("Anchor", "Location")
    explorer.set_data([], [scoped, outside])
    explorer.set_active_item("entity", outside.id)
    explorer.set_authoring_scope(AuthoringScope(("Adventure",)))
    assert explorer._proxy_model.rowCount() == 2
    explorer._proxy_model.set_search_term("missing")
    assert explorer._proxy_model.rowCount() == 1
    explorer.set_authoring_scope(AuthoringScope())
    assert explorer._proxy_model.rowCount() == 1


def test_timeline_reveals_only_relevant_events_with_full_context(qtbot):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    visible = Event("Council", 50.0, attributes={"_tags": ["Adventure"]})
    related = Event("Foundation", 12.0, attributes={"_tags": ["City"]})
    unrelated = Event("Other", 1.0, attributes={"_tags": ["City"]})
    visible.tags = ["Adventure", "City"]
    events = [unrelated, related, visible]
    view = timeline.view
    view.set_temporal_context(TemporalResolutionContext.build(events, None))
    view.set_playhead_time(41.0)
    view.set_data_provider(
        SimpleNamespace(
            get_group_metadata=lambda tag_order, date_range: build_group_metadata(
                view.scoped_events(events), tag_order, {}, (0.0, 100.0)
            ),
            get_events_for_group=lambda tag_name, date_range=None: events_for_group(
                view.scoped_events(events), tag_name, date_range
            ),
        )
    )
    view.set_grouping_config(["City"])
    band = view._band_manager.get_band("City")
    band.collapse_requested.emit("City")
    assert band.count == 3
    assert band.is_collapsed
    history = ScopedHistory(timeline, lambda: events)
    history.scope_changed(AuthoringScope(("Adventure",)))
    history.selected("entity", "scout", "selected")
    history.relations(
        "entity",
        "scout",
        [{"source_id": related.id, "target_id": "scout", "rel_type": "related"}],
    )
    assert [event.id for event in timeline.view.events] == [visible.id]
    assert band.count == 1
    assert band.earliest_date == band.latest_date == 50.0
    assert len(band.presentations) == 1
    history.toggle()
    assert [event.id for event in timeline.view.events] == [related.id, visible.id]
    assert band.count == 2
    assert timeline.get_playhead_time() == 41.0
    assert len(timeline.view._temporal_context.events()) == 3
    history.selected("event", visible.id, "selected")
    assert [event.id for event in timeline.view.events] == [visible.id]
    assert band.count == 1
    history.scope_changed(AuthoringScope(("No matches",)))
    assert band.count == 0
    assert not band.presentations
    assert band.is_collapsed
    assert view._band_manager.get_band("City") is band


def test_connection_dialog_preserves_pending_input_and_protects_mentions(qtbot):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    dialog = GraphConnectionDialog("Scout", ["mentions", "member_of"], timeline)
    qtbot.addWidget(dialog)
    dialog.set_target("Faction", awaiting_relations=True)
    dialog.type_field.setCurrentText("related")
    assert not dialog.save.isEnabled()
    dialog.pair_ready([("read-only", {"rel_type": "mentions"})])
    dialog.existing.setCurrentIndex(1)
    assert not dialog.edit_button.isEnabled()
    assert dialog.save.isEnabled()
    assert [
        dialog.direction.itemData(index) for index in range(dialog.direction.count())
    ] == ["forward", "reverse"]
    dialog.resize(380, 420)
    dialog.show()
    dialog.direction.setCurrentIndex(1)
    dialog.save.setFocus()
    with qtbot.waitSignal(dialog.save_requested) as submitted:
        qtbot.keyClick(dialog.save, Qt.Key.Key_Space)
    assert submitted.args == ["related", "reverse", False]
    dialog.set_pending(True)
    dialog.set_pending(False, "Rejected")
    assert dialog.save.isEnabled()
    assert dialog.type_field.currentText() == "related"


class _GraphSignals(QObject):
    changed = Signal(object)
    graph_command_finished = Signal(object)
    navigation_result = Signal(str, str, str)
    history_loaded = Signal(dict)


@pytest.fixture
def graph_authoring(qtbot):
    graph = GraphWidget()
    qtbot.addWidget(graph)
    signals = _GraphSignals(graph)
    source = Entity("Scout", "Character", attributes={"_tags": ["Scope"]})
    target = Event("Outside", 1.0)
    graph.display_graph([{"id": source.id, "name": source.name}], [])
    data = SimpleNamespace(
        cached_entities=[source], cached_events=[target], cached_tags=["Scope"]
    )
    scope = SimpleNamespace(
        scope=AuthoringScope(("Scope",)), revision=1, changed=signals.changed
    )
    event_editor = SimpleNamespace(
        current_event_id=target.id,
        has_unsaved_changes=MagicMock(return_value=False),
        save_pending=False,
    )
    entity_editor = SimpleNamespace(current_entity_id=None)
    window = SimpleNamespace(event_editor=event_editor, entity_editor=entity_editor)
    app = SimpleNamespace(main_window=window)
    commands = SimpleNamespace(
        graph_command_finished=signals.graph_command_finished,
        execute_command=MagicMock(),
    )
    coordinator = GraphAuthoring(
        graph,
        data,
        scope,
        SimpleNamespace(restore_graph_recovery=MagicMock()),
        commands,
        signals,
        signals,
        lambda: "world",
        lambda: 0.0,
        lambda: None,
        lambda targets: AppCoordinator._batch_draft_warning(app, targets),
    )
    coordinator.pair_requested.disconnect()
    return coordinator, source, target, commands, event_editor


def test_cancelled_pair_reply_cannot_populate_new_draft(graph_authoring):
    coordinator, source, target, *_ = graph_authoring
    coordinator.begin({"source": source.id, "target": target.id})
    obsolete = coordinator._pair_requests["draft"]
    coordinator._dialog.reject()
    coordinator.begin({"source": source.id})
    current = coordinator._dialog
    current.set_target("New entry")

    coordinator._on_pair({"request": obsolete, "rows": [{}]})

    assert current.existing.count() == 1
    assert not current.edit_button.isEnabled()
    assert not coordinator._pair_requests


def test_failed_pair_lookup_retries_in_place(graph_authoring, qtbot, theme_delivery):
    coordinator, source, target, *_ = graph_authoring
    coordinator.begin({"source": source.id, "target": target.id})
    dialog = coordinator._dialog
    dialog.resize(380, dialog.height())
    dialog.type_field.setCurrentText("related")
    dialog.direction.setCurrentIndex(1)
    request = coordinator._pair_requests["draft"]
    coordinator._on_pair({"request": request, "error": "Could not load."})
    assert dialog.retry.isVisible()
    assert dialog.focusWidget() is dialog.retry
    assert not dialog.save.isEnabled()
    assert not dialog.edit_button.isEnabled()

    with qtbot.waitSignal(coordinator.pair_requested) as emitted:
        qtbot.keyClick(dialog.focusWidget(), Qt.Key.Key_Return)
    (retry,) = emitted.args
    assert retry["id"] != request["id"]
    assert (retry["source"], retry["target"]) == (source.id, target.id)
    assert not dialog.retry.isVisible()
    assert not dialog.save.isEnabled()
    coordinator._on_pair({"request": request, "error": "Obsolete failure."})
    assert not dialog.retry.isVisible()
    coordinator._on_pair({"request": retry, "rows": []})
    assert dialog.save.isEnabled()
    assert dialog.type_field.currentText() == "related"
    assert dialog.direction.currentData() == "reverse"
    assert dialog.error.text() == ""


def test_tag_scope_membership_checks_editor_before_and_after_confirmation(
    graph_authoring, monkeypatch
):
    coordinator, source, target, commands, editor = graph_authoring
    submission = GraphSubmission(
        "connection", coordinator._context(), source.id, target.id, None, None
    )
    coordinator._feedback = SavedGraphConnection(submission, frozenset(), target.id)
    confirm = MagicMock()
    monkeypatch.setattr(QMessageBox, "question", confirm)
    editor.has_unsaved_changes.return_value = True
    coordinator.add_to_tag_scope()
    confirm.assert_not_called()
    commands.execute_command.assert_not_called()
    assert "Event Editor" in coordinator._view.feedback.caption.text()

    def start_save(*_args):
        editor.save_pending = True
        return QMessageBox.StandardButton.Yes

    editor.has_unsaved_changes.return_value = False
    confirm.side_effect = start_save
    coordinator.add_to_tag_scope()
    confirm.assert_called_once()
    commands.execute_command.assert_not_called()
    assert coordinator._feedback.outside == target.id

    editor.save_pending = False
    confirm.side_effect = None
    confirm.return_value = QMessageBox.StandardButton.Yes
    coordinator.add_to_tag_scope()
    commands.execute_command.assert_called_once()


def test_graph_reveal_respects_world_scope_and_temporal_presentation(qtbot):
    graph = GraphWidget()
    qtbot.addWidget(graph)
    graph.set_authoring_scope(AuthoringScope(("Adventure",)))
    graph._advanced_filter_config["rel_types"] = {"include": ["member_of"]}
    nodes = [
        {"id": "scout", "name": "Scout", "tags": ["Adventure"]},
        {"id": "faction", "name": "Faction", "tags": ["Adventure"]},
        {"id": "outside", "name": "Outside", "tags": ["Other"]},
    ]
    edges = [
        {
            "id": "saved",
            "source_id": "scout",
            "target_id": "faction",
            "rel_type": "related",
        },
        {
            "id": "external",
            "source_id": "scout",
            "target_id": "outside",
            "rel_type": "related",
        },
        {
            "id": "possible",
            "source_id": "scout",
            "target_id": "faction",
            "rel_type": "related",
            "validity_status": "possible",
        },
    ]
    graph.display_graph(nodes, edges)
    assert not graph.visible_node_ids
    local, excluded = graph.show_saved_relations(
        frozenset({"saved", "external", "possible"})
    )
    assert local == ("relation type",) and excluded == 2
    assert graph.visible_node_ids == {"scout", "faction"}
    graph.authoring_context_changed()
    assert not graph.visible_node_ids
    assert graph.get_filter_config()["rel_types"] == ["member_of"]
