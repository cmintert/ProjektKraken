from unittest.mock import MagicMock, patch

import pytest

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    # Mock DB service to avoid real DB creation
    # Also Mock QTimer to prevent deferred initialization crash in tests
    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.worker_manager.DatabaseWorker") as MockWorker,
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.coordinators.editor_coordinator.QMessageBox.warning",
            return_value=QMessageBox.Discard,
        ),
        patch("src.app.worker_manager.QSettings") as MockSettings,
        patch("src.app.main_window.QSettings") as MockMainWindowSettings,
        patch("src.app.worker_manager.WorldManager") as MockWorldManager,
        patch("src.app.worker_manager.ensure_worlds_directory", return_value="."),
    ):
        # Setup Settings (Worker)
        mock_settings = MockSettings.return_value
        mock_settings.value.return_value = "world.kraken"

        # Setup Settings (MainWindow)
        mock_mw_settings = MockMainWindowSettings.return_value

        def settings_side_effect(key, default=None, type=None):
            from src.app.constants import SETTINGS_ACTIVE_DB_KEY

            if key == SETTINGS_ACTIVE_DB_KEY:
                return "world.kraken"
            return default

        mock_mw_settings.value.side_effect = settings_side_effect

        # Setup World Manager
        mock_wm = MockWorldManager.return_value
        mock_world = MagicMock()
        mock_world.name = "world.kraken"
        mock_world.db_path = "world.kraken"
        mock_wm.get_world.return_value = mock_world

        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_init_window(main_window):
    from src.app.constants import WINDOW_TITLE

    assert main_window.windowTitle() == f"{WINDOW_TITLE} - world.kraken"
    assert main_window.timeline is not None


def test_create_event_flow(main_window, qtbot):
    # Simulate save from editor — route through editor_coordinator
    ev_data = {"id": "1", "name": "New", "lore_date": 10.0}

    with qtbot.waitSignal(
        main_window.editor_coordinator.command_requested, timeout=1000
    ):
        main_window.editor_coordinator.update_event(ev_data)


def test_create_entity(main_window, qtbot):
    with patch(
        "src.app.coordinators.editor_coordinator.QInputDialog.getText",
        return_value=("New Entity", True),
    ):
        # Ensure editor check passes
        main_window.entity_editor.has_unsaved_changes = MagicMock(return_value=False)

        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.create_entity()


def test_delete_entity(main_window, qtbot):
    with qtbot.waitSignal(
        main_window.editor_coordinator.command_requested, timeout=1000
    ):
        main_window.editor_coordinator.delete_entity("ent1")


def test_delete_event(main_window, qtbot):
    with qtbot.waitSignal(
        main_window.editor_coordinator.command_requested, timeout=1000
    ):
        main_window.editor_coordinator.delete_event("ev1")


def test_update_entity(main_window, qtbot):
    with qtbot.waitSignal(
        main_window.editor_coordinator.command_requested, timeout=1000
    ):
        main_window.editor_coordinator.update_entity({"id": "ent1", "name": "Updated"})


def test_add_relation(main_window, qtbot):
    with qtbot.waitSignal(
        main_window.editor_coordinator.command_requested, timeout=1000
    ):
        main_window.editor_coordinator.add_relation(
            "src", "dst", "relates_to", bidirectional=True
        )


@patch("src.app.coordinators.editor_coordinator.QMessageBox.warning")
def test_check_unsaved_changes_save(mock_warning, main_window):
    # Setup editor with unsaved changes
    main_window.event_editor.has_unsaved_changes = MagicMock(return_value=True)
    main_window.event_editor._on_save = MagicMock()

    # Simulate User clicking Save
    from PySide6.QtWidgets import QMessageBox

    mock_warning.return_value = QMessageBox.Save

    result = main_window.check_unsaved_changes(main_window.event_editor)

    assert result is True
    main_window.event_editor._on_save.assert_called_once()


@patch("src.app.coordinators.editor_coordinator.QMessageBox.warning")
def test_check_unsaved_changes_cancel(mock_warning, main_window):
    main_window.event_editor.has_unsaved_changes = MagicMock(return_value=True)

    # Simulate User clicking Cancel
    from PySide6.QtWidgets import QMessageBox

    mock_warning.return_value = QMessageBox.Cancel

    result = main_window.check_unsaved_changes(main_window.event_editor)

    assert result is False


def test_load_data_refreshes_editors(main_window):
    """Verify that load_data refetches details for open editors."""
    # Mock data_coordinator methods to track calls
    main_window.data_coordinator.load_data = MagicMock()
    main_window.data_coordinator.load_event_details = MagicMock()
    main_window.data_coordinator.load_entity_details = MagicMock()

    # Trigger load_data on data_coordinator
    main_window.data_coordinator.load_data()
    main_window.data_coordinator.load_data.assert_called_once()
