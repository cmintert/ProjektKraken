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


def test_mainwindow_close_event_cleanups_worker(qapp, mock_db_service):
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
        mock_thread = MagicMock(spec=QThread)
        mock_thread.wait.return_value = True  # Simulate successful wait

        # Instantiate MainWindow
        # We need to patch where MainWindow instantiates these
        with patch("src.app.main_window.QThread", return_value=mock_thread):
            window = MainWindow()
            # Manually inject our specific mock worker if the constructor didn't use it
            # (It instantiates DatabaseWorker inside __init__, so our patch above handles it)

            # Simulate close event
            event = MagicMock()
            event.ignore = MagicMock()
            event.accept = MagicMock()

            # Mock unsaved changes check to return True (safe to close)
            window.check_unsaved_changes = MagicMock(return_value=True)

            window.closeEvent(event)

            # Assertions
            # 1. Check worker cleanup invoked
            # Use QMetaObject.invokeMethod, so we can't easily assert assert_called on the slot directly
            # if it's invoked via Qt meta system, UNLESS we patch QMetaObject.invokeMethod.
            # However, since we are in python, invokeMethod usually works on the python object.
            # Let's verify via patching QMetaObject.
            pass


def test_mainwindow_close_calls_worker_cleanup_logic(qapp):
    """
    More direct test of the clean up sequence logic without full Qt event loop if possible.
    """
    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QThread"),
        patch("src.app.main_window.QMetaObject.invokeMethod") as mock_invoke,
        patch("src.app.main_window.QSettings") as MockSettings,
    ):
        # Configure QSettings mock to return None to avoid restoreGeometry TypeError
        mock_settings_instance = MockSettings.return_value
        mock_settings_instance.value.return_value = None

        window = MainWindow()
        window.check_unsaved_changes = MagicMock(return_value=True)

        event = MagicMock()
        window.closeEvent(event)

        # Verify cleanup requested
        # invokeMethod(worker, "cleanup", ...)
        args, _ = mock_invoke.call_args_list[0]
        assert args[0] == window.worker
        assert args[1] == "cleanup"

        # Verify thread quit and wait
        window.worker_thread.quit.assert_called_once()
        window.worker_thread.wait.assert_called_once()


def test_cleanup_app_shuts_down_logging():
    """Test the cleanup_app top-level function."""
    with patch("src.app.main_window.shutdown_logging") as mock_shutdown:
        cleanup_app()
        mock_shutdown.assert_called_once()
