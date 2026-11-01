"""Batch dialog and queued preview retain checked identities and local intent."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QDialog, QWidget

from src.app.coordinators.app_coordinator import AppCoordinator
from src.app.coordinators.batch_metadata_coordinator import BatchMetadataCoordinator
from src.commands.batch_metadata_command import BatchMetadataCommand
from src.core.command import CommandResult
from src.gui.dialogs.batch_metadata_dialog import BatchMetadataDialog
from src.services.batch_metadata_worker import BatchMetadataWorker

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def feature(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    thread = QThread()
    world = ["world-a"]
    dirty = [""]
    commands, refreshes, indices = [], [], []
    coordinator = BatchMetadataCoordinator(
        parent,
        thread,
        lambda: None,
        lambda: world[0],
        lambda: [("entity", "person"), ("event", "council")],
        lambda _: dirty[0],
        lambda: ["existing"],
        commands.append,
        refreshes.append,
        lambda *identity: indices.append(identity),
    )
    # Keep replies under test control; exercise actual queued delivery separately.
    coordinator.preview_requested.disconnect()
    thread.start()
    yield coordinator, world, dirty, commands, refreshes, indices
    coordinator.cancel()
    thread.quit()
    assert thread.wait(3000)


def preview(coordinator, qtbot):
    coordinator.show()
    dialog = coordinator.dialog
    qtbot.addWidget(dialog)
    dialog.tags.tag_input.setText("new")
    dialog.preview_button.click()
    assert not dialog.apply_button.isEnabled()
    coordinator._preview_ready(
        {
            "job": coordinator._job,
            "world": coordinator._world_id,
            "success": True,
            "preview": {"changed": 2, "unchanged": 0, "overwritten": 0, "rows": []},
        }
    )
    return dialog


def test_dialog_validates_number_and_retains_pending_tag(qtbot):
    dialog = BatchMetadataDialog(2, ["existing"])
    qtbot.addWidget(dialog)
    intents = []
    dialog.preview_requested.connect(intents.append)
    dialog.tags.tag_input.setText("pending")
    dialog.preview_button.click()
    assert intents[-1]["tags"] == ["pending"]
    dialog.action.setCurrentIndex(2)
    dialog.key.setText("score")
    dialog.value_type.setCurrentText("Number")
    dialog.value.setText("invalid")
    dialog.preview_button.click()
    assert "valid number" in dialog.status.text()
    assert not dialog.apply_button.isEnabled()
    dialog.value_type.setCurrentText("Boolean")
    dialog.boolean.setChecked(True)
    dialog.preview_button.click()
    assert intents[-1]["value"] is True


def test_preview_and_input_change_gate_apply(feature, qtbot):
    coordinator, _, _, commands, _, _ = feature
    dialog = preview(coordinator, qtbot)
    assert dialog.apply_button.isEnabled()
    dialog.tags.tag_input.setText("different")
    assert not dialog.apply_button.isEnabled()
    coordinator._apply()
    assert not commands
    assert coordinator._preview is None


def test_noop_preview_disabled(feature, qtbot):
    coordinator = feature[0]
    dialog = preview(coordinator, qtbot)
    dialog.show_preview({"changed": 0, "unchanged": 2, "overwritten": 0})
    assert not dialog.apply_button.isEnabled()
    assert "Unchanged: 2" in dialog.status.text()


def test_affected_draft_and_world_change_block_apply(feature, qtbot):
    coordinator, world, dirty, commands, _, _ = feature
    dialog = preview(coordinator, qtbot)
    dirty[0] = "Save or discard affected draft first"
    dialog.apply_button.click()
    assert not commands and "draft" in dialog.status.text()
    assert dialog.tags.tag_input.text() == "new"
    dirty[0] = ""
    dialog.preview_button.click()
    job = coordinator._job
    world[0] = "world-b"
    coordinator._preview_ready({"job": job, "success": True})
    assert "world changed" in dialog.status.text()
    assert coordinator._preview is None


def test_apply_one_command_failure_retry_and_ack(feature, qtbot):
    coordinator, _, _, commands, refreshes, _ = feature
    dialog = preview(coordinator, qtbot)
    dialog.apply_button.click()
    coordinator._apply()
    assert len(commands) == 1 and isinstance(commands[0], BatchMetadataCommand)
    assert commands[0].targets == [("entity", "person"), ("event", "council")]
    dialog.reject()
    assert coordinator.dialog is dialog
    coordinator.on_command_finished(
        CommandResult(
            False,
            "Stale preview",
            command_name="BatchMetadataCommand",
            data={"command_id": commands[0].command_id},
        )
    )
    assert "Stale" in dialog.status.text() and not dialog.apply_button.isEnabled()
    assert dialog.tags.tag_input.text() == "new"
    dialog.preview_button.click()
    coordinator._preview_ready(
        {
            "job": coordinator._job,
            "success": True,
            "preview": {"changed": 2, "unchanged": 0, "overwritten": 0, "rows": []},
        }
    )
    dialog.apply_button.click()
    coordinator.on_command_finished(
        CommandResult(
            True,
            command_name="BatchMetadataCommand",
            data={"command_id": commands[-1].command_id},
        )
    )
    assert coordinator.dialog is None and dialog.result() == QDialog.DialogCode.Accepted
    assert refreshes == []  # No fabricated effects are delivered.


def test_cancelled_preview_cannot_repopulate_dialog(feature, qtbot):
    coordinator = feature[0]
    coordinator.show()
    dialog = coordinator.dialog
    qtbot.addWidget(dialog)
    dialog.tags.tag_input.setText("new")
    dialog.preview_button.click()
    job = coordinator._job
    dialog.reject()
    coordinator._preview_ready({"job": job, "success": True})
    assert coordinator.dialog is None


def test_undo_redo_index_every_changed_record(feature):
    coordinator, _, _, _, refreshes, indices = feature
    effects = [
        {
            "object_type": "entity",
            "object_id": "person",
            "operation": "upsert",
            "snapshot": {"id": "person", "name": "Person", "type": "character"},
            "relations_changed": False,
        },
        {
            "object_type": "event",
            "object_id": "council",
            "operation": "upsert",
            "snapshot": {"id": "council", "name": "Council", "lore_date": 1},
            "relations_changed": False,
        },
    ]
    for prefix in ("Undo_", "Redo_"):
        coordinator.on_command_finished(
            CommandResult(
                True,
                command_name=prefix + "BatchMetadataCommand",
                data={"lore_effects": effects},
            )
        )
    assert len(refreshes) == 2
    assert indices == [("entity", "person"), ("event", "council")] * 2


def test_worker_provider_runs_on_database_thread(qtbot):
    class Requests(QObject):
        requested = Signal(dict)

    thread = QThread()
    observed = []

    def provider():
        observed.append(QThread.currentThread())
        return None

    adapter = BatchMetadataWorker(provider)
    adapter.moveToThread(thread)
    thread.finished.connect(adapter.deleteLater)
    requests = Requests()
    requests.requested.connect(adapter.preview, Qt.ConnectionType.QueuedConnection)
    thread.start()
    try:
        with qtbot.waitSignal(adapter.completed, timeout=3000) as reply:
            requests.requested.emit({"job": "test", "world": "world"})
        assert observed == [thread]
        assert not reply.args[0]["success"]
    finally:
        thread.quit()
        assert thread.wait(3000)


@pytest.mark.parametrize("pending", ["dirty", "save", "temporal", "preparing"])
def test_composition_draft_guard_only_blocks_affected_object(pending):
    editor = SimpleNamespace(
        current_entity_id="person",
        has_unsaved_changes=lambda: pending == "dirty",
        save_pending=pending == "save",
        _temporal_save_pending=pending == "temporal",
        _temporal_preparing=pending == "preparing",
    )
    owner = SimpleNamespace(
        main_window=SimpleNamespace(
            entity_editor=editor,
            event_editor=SimpleNamespace(current_event_id=None),
        )
    )
    assert AppCoordinator._batch_draft_warning(owner, [("entity", "person")])
    assert AppCoordinator._batch_draft_warning(owner, [("entity", "other")]) == ""


def test_composition_refreshes_clean_active_inspector_without_navigation():
    owner = SimpleNamespace(
        navigation=SimpleNamespace(selected_type="entity", selected_id="person"),
        data=SimpleNamespace(load_completer_data=Mock(), load_entity_details=Mock()),
        _batch_draft_warning=lambda _: "",
    )
    AppCoordinator._refresh_batch_metadata(
        owner, [{"object_type": "entity", "object_id": "person"}]
    )
    owner.data.load_entity_details.assert_called_once_with("person")
    owner.data.load_completer_data.assert_called_once()


def test_batch_dialog_theme_focus_and_narrow_labels(qtbot, init_theme_manager):
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    from src.core.theme_manager import ThemeManager
    from src.gui.utils.action_label_metrics import action_label_geometry

    manager = ThemeManager()
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))
    original = manager.current_theme_name
    dialog = BatchMetadataDialog(20, ["existing"])
    qtbot.addWidget(dialog)
    base_font = QFont(dialog.font())
    dialog.show()
    try:
        for theme in manager.themes:
            manager.set_theme(theme, persist=False)
            for factor in (1.0, 1.25, 1.5, 2.0):
                font = QFont(base_font)
                font.setPointSizeF(base_font.pointSizeF() * factor)
                dialog.setFont(font)
                for width in (360, 560):
                    dialog.resize(width, 680)
                    dialog.action.setCurrentIndex(3)
                    dialog.show_preview(
                        {"changed": 4, "unchanged": 16, "overwritten": 2}
                    )
                    dialog.preview_button.setFocus()
                    qtbot.wait(1)
                    assert dialog.width() <= width
                    assert dialog.preview_button.hasFocus()
                    for button in (
                        dialog.preview_button,
                        dialog.apply_button,
                        dialog.cancel_button,
                    ):
                        geometry = action_label_geometry(button)
                        assert geometry.fits
                        assert dialog.rect().contains(
                            button.mapTo(dialog, button.rect().topLeft())
                        )
                        assert dialog.rect().contains(
                            button.mapTo(dialog, button.rect().bottomRight())
                        )
    finally:
        manager.set_theme(original, persist=False)
