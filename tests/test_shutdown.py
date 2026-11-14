from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QThread

from src.app.main import MainWindow, cleanup_app
from src.core.logging_config import shutdown_logging
from src.services.worker import DatabaseWorker


# Mock the database service to avoid real connections
@pytest.fixture
def mock_db_service():
    with patch("src.services.worker.DatabaseService") as MockService:
        instance = MockService.return_value
        instance.close = MagicMock()
        yield instance


def test_database_worker_cleanup(mock_db_service):
    """Test that DatabaseWorker.cleanup calls db_service.close()."""
    worker = DatabaseWorker(":memory:")
    worker.db_service = mock_db_service

    worker.cleanup()

    mock_db_service.close.assert_called_once()


def test_logging_shutdown():
    """Test that shutdown_logging calls logging.shutdown()."""
    with patch("logging.shutdown") as mock_shutdown:
        shutdown_logging()
        mock_shutdown.assert_called_once()


def test_mainwindow_close_waits_for_worker_confirmation(qapp, qtbot, mock_db_service):
    """
    Test that MainWindow.closeEvent triggers worker cleanup and thread quit.
    Note: We need the 'qapp' fixture (pytest-qt) or a manual generic setup.
    """
    # Setup mocks
    with patch("src.app.worker_manager.DatabaseWorker") as MockWorkerClass:
        # Configure the mock worker
        mock_worker = MockWorkerClass.return_value
        mock_worker.cleanup = MagicMock()

        # Configure the thread to simulate running
        mock_thread = QThread()
        mock_thread.start = MagicMock()
        mock_thread.quit = MagicMock(wraps=mock_thread.quit)
        mock_thread.wait = MagicMock()
        mock_thread.wait.return_value = True  # Simulate successful wait

        # Instantiate MainWindow
        # We need to patch where MainWindow instantiates these
        with (
            patch("src.app.worker_manager.QThread", return_value=mock_thread),
            patch("src.app.main_window.QTimer"),
        ):
            window = MainWindow()
            qtbot.addWidget(window)
            # Manually inject our specific mock worker if the constructor didn't use it
            # (It instantiates DatabaseWorker inside __init__, so our patch above handles it)

            # Simulate close event
            event = MagicMock()
            event.ignore = MagicMock()
            event.accept = MagicMock()

            # Mock unsaved changes check to return True (safe to close)
            window.check_unsaved_changes = MagicMock(return_value=True)
            shutdown = MagicMock(pending=False, complete=False)
            window._shutdown_coordinator = shutdown
            window.command_coordinator = MagicMock()

            window.closeEvent(event)

            event.ignore.assert_called_once()
            event.accept.assert_not_called()
            shutdown.start.assert_called_once()
            assert window.command_coordinator.mutations_suspended
            assert not window.isEnabled()
            mock_thread.quit.assert_not_called()
            mock_thread.wait.assert_not_called()

            # Repeated close attempts must not submit cleanup twice.
            shutdown.pending = True
            window.closeEvent(MagicMock())
            shutdown.start.assert_called_once()

            shutdown.complete = True
            shutdown.pending = False
            event = MagicMock()
            window.closeEvent(event)
            event.accept.assert_called_once()


def test_mainwindow_close_calls_worker_cleanup_logic(qapp, qtbot):
    """
    More direct test of cleanup logic without full Qt event loop if possible.
    """
    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QThread.start"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.QSettings") as MockSettings,
    ):
        # Configure QSettings mock to return None to avoid restoreGeometry TypeError
        mock_settings_instance = MockSettings.return_value

        def settings_value_side_effect(key, default=None, **kwargs):
            if key == "active_world":
                return "Default World"
            return None

        mock_settings_instance.value.side_effect = settings_value_side_effect

        window = MainWindow()
        qtbot.addWidget(window)
        window.check_unsaved_changes = MagicMock(return_value=True)
        window.worker_thread.quit = MagicMock(wraps=window.worker_thread.quit)
        window.worker_thread.wait = MagicMock(wraps=window.worker_thread.wait)
        shutdown = MagicMock(pending=False, complete=False)
        window._shutdown_coordinator = shutdown

        event = MagicMock()
        window.closeEvent(event)

        shutdown.start.assert_called_once()
        window.worker_thread.quit.assert_not_called()
        window.worker_thread.wait.assert_not_called()

        # The final close reports a failed cleanup rather than silently accepting it.
        with (
            patch("src.app.main_window.QMessageBox.warning") as warning,
            patch.object(window, "close") as close,
        ):
            window._on_shutdown_finished({"success": False, "error": "close failed"})
            assert "close failed" in warning.call_args.args[2]
            close.assert_called_once()
            window.setProperty("krakenInternalExit", True)
            warning.reset_mock()
            window._on_shutdown_finished({"success": False, "error": "close failed"})
            warning.assert_not_called()
        shutdown.complete = True


def test_cleanup_app_shuts_down_logging():
    """Test the cleanup_app top-level function."""
    with patch("src.app.entry.shutdown_logging") as mock_shutdown:
        cleanup_app()
        mock_shutdown.assert_called_once()
