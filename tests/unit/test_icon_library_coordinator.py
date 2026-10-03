"""Icon management entry points, queued requests and consumer refresh."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import shiboken6
from PIL import Image
from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QThread
from PySide6.QtWidgets import QLabel, QMenuBar

from src.app.command_coordinator import CommandCoordinator
from src.app.coordinators.icon_library_coordinator import IconLibraryCoordinator
from src.app.ui_manager import UIManager
from src.commands.registry import get_command_types
from src.gui.dialogs.icon_metadata_dialog import IconMetadataDialog
from src.gui.dialogs.icon_picker_dialog import IconPickerDialog, ProjectIconCard
from src.gui.dialogs.lexicon_editor_dialog import LexiconEditorDialog
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.services.marker_icon_catalog import MarkerIconCatalog
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.real_qt_invoke, pytest.mark.ci_fast]


def source_icon(tmp_path, name="Watchtower.png", color="red"):
    source = tmp_path / name
    Image.new("RGBA", (32, 64), color).save(source)
    return source


@pytest.fixture
def queued_library(qapp, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    window = SimpleNamespace(data_coordinator=MagicMock())
    commands = CommandCoordinator(window)
    worker = DatabaseWorker(
        str(tmp_path / "world.kraken"), get_command_types(), world_root=tmp_path
    )
    thread = QThread()
    worker.moveToThread(thread)
    commands.command_requested.connect(
        worker.run_command, Qt.ConnectionType.QueuedConnection
    )
    commands.undo_requested.connect(worker.run_undo, Qt.ConnectionType.QueuedConnection)
    commands.redo_requested.connect(worker.run_redo, Qt.ConnectionType.QueuedConnection)
    worker.command_finished.connect(
        commands.on_command_result, Qt.ConnectionType.QueuedConnection
    )
    worker.history_loaded.connect(
        commands.load_history_payloads, Qt.ConnectionType.QueuedConnection
    )
    refreshes = []
    coordinator = IconLibraryCoordinator(
        commands.execute_command, lambda: ("world", str(tmp_path)), refreshes.append
    )
    commands.command_preparing.connect(coordinator.prepare_command)
    worker.command_finished.connect(
        coordinator.on_command_finished, Qt.ConnectionType.QueuedConnection
    )
    thread.started.connect(worker.initialize_db)
    with qtbot.waitSignal(worker.initialized, timeout=5000) as signal:
        thread.start()
    assert signal.args == [True]
    with qtbot.waitSignal(worker.history_loaded, timeout=5000):
        QMetaObject.invokeMethod(
            worker,
            "initialize_history",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, "world"),
        )
    yield coordinator, commands, worker, refreshes
    with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
        QMetaObject.invokeMethod(worker, "cleanup", Qt.ConnectionType.QueuedConnection)
    thread.quit()
    assert thread.wait(5000)


def open_picker(qtbot, coordinator, tmp_path, *, manage_only=False):
    picker = IconPickerDialog(world_root=str(tmp_path), manage_only=manage_only)
    qtbot.addWidget(picker)
    picker.show()
    coordinator.attach_picker(picker)
    qtbot.waitUntil(lambda: not picker._pending)
    return picker


def import_source(qtbot, picker, source):
    with patch(
        "src.gui.dialogs.icon_picker_dialog.QFileDialog.getOpenFileNames",
        return_value=([str(source)], ""),
    ):
        picker._on_import_clicked()
    qtbot.waitUntil(lambda: not picker._pending)
    assert picker._catalog.custom()
    return picker._catalog.custom()[0]


def test_queued_batch_remains_open_and_survives_parent_cancel(
    queued_library, qtbot, tmp_path
):
    coordinator, commands, worker, refreshes = queued_library
    picker = open_picker(qtbot, coordinator, tmp_path)
    source = source_icon(tmp_path)
    definition = import_source(qtbot, picker, source)
    assert picker.isVisible() and picker.selected_definition is None
    assert "Added 1" in picker._status.toPlainText()
    assert len(commands.undo_stack) == 1
    assert isinstance(refreshes[-1]["icon_library"], dict)
    picker.reject()
    new_picker = open_picker(qtbot, coordinator, tmp_path)
    assert new_picker._catalog.resolve_id(definition.id).name == "Watchtower"
    source.unlink()
    commands.undo()
    qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert not new_picker._catalog.custom()
    commands.redo()
    qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert new_picker._catalog.resolve_id(definition.id) == definition
    with qtbot.waitSignal(worker.history_loaded, timeout=5000):
        QMetaObject.invokeMethod(
            worker,
            "initialize_history",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, "world"),
        )
    assert len(commands.undo_stack) == 1
    commands.undo()
    qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert not new_picker._catalog.custom()


def test_picker_search_category_and_independent_manager(
    queued_library, qtbot, tmp_path
):
    coordinator, _, _, _ = queued_library
    picker = open_picker(qtbot, coordinator, tmp_path, manage_only=True)
    definition = import_source(qtbot, picker, source_icon(tmp_path))
    picker._request(
        {
            "operation": "edit",
            "icon_id": definition.id,
            "changes": {
                "name": "Lookout",
                "category": "Fortifications",
            },
        }
    )
    qtbot.waitUntil(lambda: not picker._pending)
    picker._search.setText("WATCHTOWER")
    cards = picker._project_tab_container.findChildren(ProjectIconCard)
    assert any(
        card._icon_btn.toolTip() == "Lookout" and not card.isHidden() for card in cards
    )
    picker._search.setText("harbour")
    assert (
        "No matching" in picker._project_tab_container.findChildren(QLabel)[-1].text()
    )
    picker._search.clear()
    picker._category.setCurrentIndex(picker._category.findData("Fortifications"))
    updated = picker._catalog.resolve_id(definition.id)
    with patch.object(picker, "_on_edit_project_icon") as edit:
        picker._on_definition_selected(updated)
    edit.assert_called_once_with(updated)
    assert picker.isVisible() and picker.selected_definition is None


def test_open_lexicon_draft_blocks_import_undo(queued_library, qtbot, tmp_path):
    coordinator, commands, _, _ = queued_library
    picker = open_picker(qtbot, coordinator, tmp_path)
    definition = import_source(qtbot, picker, source_icon(tmp_path))
    draft = LexiconEditorDialog(
        entity_types=["Tower"],
        current_config={
            "nodes": {"Tower": {"icon_id": definition.id}},
            "edges": {},
        },
    )
    qtbot.addWidget(draft)
    draft.show()
    coordinator.attach_draft(draft)
    with patch.object(commands, "_show_error") as error:
        commands.undo()
        qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert "Open Visual Lexicon draft: Tower" in error.call_args.args[0]
    assert len(commands.undo_stack) == 1 and not commands.redo_stack
    assert picker._catalog.resolve_id(definition.id)
    draft.reject()
    commands.undo()
    qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert not picker._catalog.custom()


def test_late_results_after_destroy_and_stale_world_requests(qapp, qtbot, tmp_path):
    submitted, refreshes = [], []
    context = ["world", str(tmp_path)]
    coordinator = IconLibraryCoordinator(
        submitted.append, lambda: tuple(context), refreshes.append
    )
    picker = IconPickerDialog(world_root=str(tmp_path))
    picker.show()
    coordinator.attach_picker(picker)
    first = submitted[-1]
    context[:] = ["other", str(tmp_path / "other")]
    picker._request({"operation": "import", "source_paths": []})
    # An old picker is rejected even if it emits intent after switching worlds.
    picker.library_requested.emit({"operation": "import", "source_paths": []})
    assert submitted == [first]
    from src.core.command import CommandResult

    result = CommandResult(
        True,
        command_name="IconLibraryCommand",
        data={
            "command_id": first.command_id,
            "world_id": "world",
            "world_root": str(tmp_path),
            "icon_library": {"metadata": {}, "icons": []},
        },
    )
    shiboken6.delete(picker)
    coordinator.on_command_finished(result)
    assert not refreshes


def test_file_menu_has_independent_icon_library_action(qapp):
    window = MagicMock()
    bar = QMenuBar()
    manager = UIManager(window)
    manager.create_file_menu(bar)
    file_menu = manager._file_menu
    action = next(a for a in file_menu.actions() if a.text() == "Icon Library...")
    action.trigger()
    window.app_coordinator.show_icon_library.assert_called_once()


def test_same_id_metadata_refresh_reaches_existing_markers(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    view.set_world_root(str(tmp_path))
    view.load_map(str(source_icon(tmp_path, "Map.png")))
    icon = tmp_path / "assets/images" / ("icon_" + "a" * 32 + ".png")
    icon.parent.mkdir(parents=True)
    icon.write_bytes(source_icon(tmp_path).read_bytes())
    icon_id = "custom." + "a" * 32
    view.marker_icon_catalog = MarkerIconCatalog.load(tmp_path)
    view.add_marker(
        "point",
        "entity",
        "Tower",
        0.5,
        0.5,
        visual_attributes={"_v_marker_icon_id": icon_id},
    )
    definition = view.marker_icon_catalog.resolve_id(icon_id)
    metadata = definition.to_dict()
    metadata.update({"name": "Lookout", "anchor": {"x": 0.5, "y": 1}})
    view.apply_icon_library_snapshot(
        {
            "world_root": str(tmp_path),
            "icon_library": {"metadata": {icon_id: metadata}},
        }
    )
    marker = view._marker_manager.markers["point"]
    assert marker._icon_definition.name == "Lookout"
    assert marker._resolved_icon_anchor().y == 1
    view.set_world_root(str(tmp_path))
    assert view.marker_icon_catalog.resolve_id(icon_id).name == "Lookout"
    view.close()


def test_edit_dialog_anchor_preview_and_empty_name_validation(qapp, qtbot, tmp_path):
    source = source_icon(tmp_path)
    from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource

    definition = MarkerIconDefinition(
        "custom.a", "Tower", "assets/images/icon_a.png", MarkerIconSource.CUSTOM
    )
    dialog = IconMetadataDialog(definition, str(source))
    qtbot.addWidget(dialog)
    dialog.anchor_y.setValue(1)
    assert dialog.preview.anchor_y == 1
    assert dialog.changes()["anchor"] == {"x": 0.5, "y": 1}
    dialog.name_edit.setText(" ")
    from PySide6.QtWidgets import QDialogButtonBox

    assert (
        not dialog.findChild(QDialogButtonBox)
        .button(QDialogButtonBox.StandardButton.Save)
        .isEnabled()
    )


def test_late_current_world_result_refreshes_without_destroyed_owner(qapp, tmp_path):
    from src.core.command import CommandResult

    submitted, refreshes = [], []
    coordinator = IconLibraryCoordinator(
        submitted.append, lambda: ("world", str(tmp_path)), refreshes.append
    )
    picker = IconPickerDialog(world_root=str(tmp_path))
    coordinator.attach_picker(picker)
    request = submitted[-1]
    shiboken6.delete(picker)
    snapshot = {"metadata": {}, "icons": []}
    coordinator.on_command_finished(
        CommandResult(
            True,
            command_name="IconLibraryCommand",
            data={
                "command_id": request.command_id,
                "world_id": "world",
                "world_root": str(tmp_path),
                "icon_library": snapshot,
            },
        )
    )
    assert refreshes[-1]["icon_library"] == snapshot
    assert not coordinator._pending


def test_graph_snapshot_preserves_draft_and_refreshes_image(qapp, qtbot, tmp_path):
    icon = tmp_path / "assets/images" / ("icon_" + "a" * 32 + ".png")
    icon.parent.mkdir(parents=True)
    icon.write_bytes(source_icon(tmp_path).read_bytes())
    icon_id = "custom." + "a" * 32
    graph = GraphWidget()
    qtbot.addWidget(graph)
    graph._refresh_display_locally = MagicMock()
    saved = {"nodes": {"Tower": {"color": "#111111"}}, "edges": {}}
    draft = LexiconEditorDialog(
        entity_types=["Tower"],
        current_config={
            "nodes": {"Tower": {"color": "#123456", "icon_id": icon_id}},
            "edges": {},
        },
    )
    qtbot.addWidget(draft)
    draft.show()
    graph._lexicon_editor = draft
    before = draft.get_lexicon_config()
    graph.apply_icon_library_snapshot(
        {
            "world_root": str(tmp_path),
            "icon_library": {"metadata": {}},
        }
    )
    assert draft.get_lexicon_config() == before
    assert graph._raw_lexicon == before
    assert graph._resolved_lexicon["nodes"]["Tower"]["image"].startswith("data:")
    graph.set_lexicon_config(saved, saved)
    assert graph._raw_lexicon == before
    graph._refresh_display_locally.assert_called()


def test_large_batch_report_stays_bounded(qapp, qtbot, tmp_path):
    picker = IconPickerDialog(world_root=str(tmp_path), manage_only=True)
    qtbot.addWidget(picker)
    picker.show()
    failures = [{"file": f"Artwork {n}.png", "error": "Unreadable"} for n in range(100)]
    picker.finish_library_request(
        True, "", {"operation": "import", "report": {"failed": failures}}
    )
    qapp.processEvents()
    assert picker.height() == 540
    assert "Artwork 99.png" in picker._status.toPlainText()
    assert picker._status.height() <= 110
    assert picker.isVisible()


def test_library_requests_and_undo_cannot_overlap(queued_library, qtbot, tmp_path):
    coordinator, commands, _, _ = queued_library
    picker = open_picker(qtbot, coordinator, tmp_path)
    import_source(qtbot, picker, source_icon(tmp_path))
    picker._request(
        {
            "operation": "import",
            "source_paths": [str(source_icon(tmp_path, "Harbour.png", "blue"))],
        }
    )
    commands.undo()
    assert not commands._undo_redo_in_progress
    qtbot.waitUntil(lambda: not picker._pending)
    assert len(commands.undo_stack) == 2
    commands.undo()
    assert picker._pending and not picker._import_btn.isEnabled()
    assert not picker._tabs.isEnabled()
    qtbot.waitUntil(lambda: not commands._undo_redo_in_progress)
    assert not picker._pending and len(picker._catalog.custom()) == 1
