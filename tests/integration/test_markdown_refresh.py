"""Integration tests for Markdown import refresh behaviour.

Verifies that after a Markdown import finishes the full data-refresh
pipeline is triggered so that the Unified List, open editors, and
timeline all receive updated data without a manual reload.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class FakeMainWindow(QObject):
    """Minimal fake MainWindow for testing import refresh."""

    command_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.worker = MagicMock()
        self.status_bar = MagicMock()
        self.data_coordinator = MagicMock()
        self._import_progress_dialog = None


@pytest.fixture
def qapp():
    """Provide a QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def fake_window(qapp):
    """Create a FakeMainWindow for testing."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(fake_window):
    """Create an ImportCoordinator with a fake MainWindow."""
    from src.app.coordinators.import_coordinator import ImportCoordinator

    return ImportCoordinator(fake_window)


class TestMarkdownImportRefresh:
    """Verify that the full GUI refresh is triggered after import."""

    def test_successful_import_calls_load_data(
        self, coordinator, fake_window
    ):
        """DataCoordinator.load_data() must be called on success."""
        result = MagicMock()
        result.success = True
        result.created_entities = ["e1"]
        result.created_events = []
        result.created_relations = []
        result.warnings = []

        coordinator._import_progress_dialog = MagicMock()

        with patch(
            "src.app.coordinators.import_coordinator.QMessageBox"
        ):
            coordinator.on_import_finished(result)

        fake_window.data_coordinator.load_data.assert_called_once()

    def test_failed_import_does_not_refresh(
        self, coordinator, fake_window
    ):
        """DataCoordinator.load_data() must NOT be called on failure."""
        result = MagicMock()
        result.success = False
        result.errors = ["some error"]

        coordinator._import_progress_dialog = MagicMock()

        with patch(
            "src.app.coordinators.import_coordinator.QMessageBox"
        ):
            coordinator.on_import_finished(result)

        fake_window.data_coordinator.load_data.assert_not_called()


class TestWorkerRefreshDepth:
    """Verify that the worker refreshes the correct data after import."""

    def test_refresh_after_import_calls_core_loaders(self):
        """_refresh_after_import must call events, entities, calendar."""
        from src.services.worker import DatabaseWorker

        worker = DatabaseWorker.__new__(DatabaseWorker)
        worker.db_service = MagicMock()

        worker.load_events = MagicMock()
        worker.load_entities = MagicMock()
        worker.load_calendar_config = MagicMock()

        worker._refresh_after_import()

        worker.load_events.assert_called_once()
        worker.load_entities.assert_called_once()
        worker.load_calendar_config.assert_called_once()

    def test_refresh_after_import_does_not_call_longform(self):
        """_refresh_after_import must NOT call load_longform_sequence.

        load_longform_sequence requires a doc_id that the worker does
        not have. Longform refresh is handled by DataCoordinator.load_data()
        on the UI thread via LongformManager.
        """
        from src.services.worker import DatabaseWorker

        worker = DatabaseWorker.__new__(DatabaseWorker)
        worker.db_service = MagicMock()

        worker.load_events = MagicMock()
        worker.load_entities = MagicMock()
        worker.load_calendar_config = MagicMock()
        worker.load_longform_sequence = MagicMock()

        worker._refresh_after_import()

        worker.load_longform_sequence.assert_not_called()
