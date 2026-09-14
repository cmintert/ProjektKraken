"""Unit tests for ImportCoordinator.

Tests import workflow and database manager dialog extracted from MainWindow.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox


class FakeMainWindow(QObject):
    """Minimal fake MainWindow for testing ImportCoordinator."""

    command_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.worker = MagicMock()
        self.status_bar = MagicMock()
        self.data_coordinator = MagicMock()
        self._import_progress_dialog = None


@pytest.fixture
def fake_window(qapp):
    """Create a FakeMainWindow for testing."""
    return FakeMainWindow()


@pytest.fixture
def coordinator(fake_window):
    """Create an ImportCoordinator with a fake MainWindow."""
    from src.app.coordinators.import_coordinator import ImportCoordinator

    return ImportCoordinator(fake_window)


class TestImportFinished:
    """Tests for import completion handling."""

    def test_on_import_finished_success(self, coordinator, fake_window):
        """Successful import should show information message."""
        result = MagicMock()
        result.success = True
        result.created_entities = ["e1"]
        result.created_events = ["ev1"]
        result.created_relations = ["r1"]
        result.warnings = []
        result.ambiguous_items = []
        result.unparsed_date_count = 0

        # Set up progress dialog
        coordinator._import_progress_dialog = MagicMock()
        progress_dialog = coordinator._import_progress_dialog

        with patch("src.app.coordinators.import_coordinator.QMessageBox") as mock_box:
            coordinator.on_import_finished(result)
            mock_box.information.assert_called_once()

        # Progress dialog should be cleaned up
        progress_dialog.finish.assert_called_once()
        assert coordinator._import_progress_dialog is None

    def test_on_import_finished_failure(self, coordinator, fake_window):
        """Failed import should show critical message."""
        result = MagicMock()
        result.success = False
        result.errors = ["Error 1", "Error 2"]

        coordinator._import_progress_dialog = MagicMock()

        with patch("src.app.coordinators.import_coordinator.QMessageBox") as mock_box:
            coordinator.on_import_finished(result)
            mock_box.critical.assert_called_once()

    def test_on_import_finished_clears_status(self, coordinator, fake_window):
        """Import finish should clear status bar."""
        result = MagicMock()
        result.success = True
        result.created_entities = []
        result.created_events = []
        result.created_relations = []
        result.warnings = []
        result.ambiguous_items = []
        result.unparsed_date_count = 0

        with patch("src.app.coordinators.import_coordinator.QMessageBox"):
            coordinator.on_import_finished(result)
            fake_window.status_bar.clearMessage.assert_called_once()

    def test_on_import_finished_success_calls_load_data(self, coordinator, fake_window):
        """Successful import should trigger data_coordinator.load_data()."""
        result = MagicMock()
        result.success = True
        result.created_entities = ["e1"]
        result.created_events = []
        result.created_relations = []
        result.warnings = []
        result.ambiguous_items = []
        result.unparsed_date_count = 0

        with patch("src.app.coordinators.import_coordinator.QMessageBox"):
            coordinator.on_import_finished(result)

        fake_window.data_coordinator.load_data.assert_called_once()

    def test_on_import_finished_failure_skips_load_data(self, coordinator, fake_window):
        """Failed import should NOT trigger data_coordinator.load_data()."""
        result = MagicMock()
        result.success = False
        result.errors = ["Error"]

        coordinator._import_progress_dialog = MagicMock()

        with patch("src.app.coordinators.import_coordinator.QMessageBox"):
            coordinator.on_import_finished(result)

        fake_window.data_coordinator.load_data.assert_not_called()


class TestDatabaseManager:
    """Tests for database manager dialog."""

    @patch("src.app.coordinators.import_coordinator.DatabaseManagerDialog")
    def test_show_database_manager(self, mock_dialog_class, coordinator, fake_window):
        """show_database_manager should create and show the dialog."""
        mock_dialog = MagicMock()
        mock_dialog_class.return_value = mock_dialog
        coordinator.show_database_manager()
        mock_dialog.exec.assert_called_once()


class TestSingleObsidianExport:
    """Tests for worker-backed single-item Obsidian exports."""

    def test_contextual_export_opens_shared_review(self, coordinator):
        coordinator._transfer = MagicMock()
        coordinator.export_single_obsidian("entity", "entity-id")
        coordinator._transfer.show.assert_called_once_with(
            tab=1, format_key="notes", selected=["entity-id"]
        )

    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    def test_prepared_export_selects_path_and_dispatches_worker(
        self, mock_dialog, coordinator
    ):
        """A prepared snapshot should lead to a worker export request."""
        requests = []
        coordinator.run_obsidian_export_requested.connect(
            lambda item_type, item_id, path: requests.append(
                (item_type, item_id, path)
            )
        )
        mock_dialog.getSaveFileName.return_value = (
            "C:/tmp/Chosen Name.md",
            "Markdown Files (*.md)",
        )

        coordinator.on_obsidian_export_prepared(
            {
                "item_type": "entity",
                "item_id": "entity-1",
                "item_name": "The Kraken",
                "error": "",
            }
        )

        assert requests == [
            ("entity", "entity-1", "C:/tmp/Chosen Name.md")
        ]

    @patch("src.app.coordinators.import_coordinator.AutoClosingMessageBox")
    def test_successful_export_shows_transient_result(
        self, mock_message_box, coordinator, fake_window
    ):
        """Successful exports should use the shared transient result modal."""
        coordinator.on_obsidian_export_finished(
            {
                "success": True,
                "item_type": "entity",
                "item_id": "entity-1",
                "item_name": "The Kraken",
                "file_path": "C:/tmp/The Kraken.md",
                "error": "",
            }
        )

        message = "Exported 'The Kraken' to C:/tmp/The Kraken.md"
        fake_window.status_bar.showMessage.assert_called_once_with(message, 5000)
        mock_message_box.assert_called_once_with(
            "Obsidian Export Complete",
            message,
            1500,
            QMessageBox.Icon.Information,
            parent=fake_window,
        )
        mock_message_box.return_value.exec.assert_called_once_with()

    @patch("src.app.coordinators.import_coordinator.AutoClosingMessageBox")
    def test_failed_export_reports_worker_error(
        self, mock_message_box, coordinator, fake_window
    ):
        """Worker export failures should be presented by the coordinator."""
        coordinator.on_obsidian_export_finished(
            {
                "success": False,
                "item_type": "entity",
                "item_id": "entity-1",
                "item_name": "The Kraken",
                "file_path": "C:/tmp/The Kraken.md",
                "error": "disk full",
            }
        )

        fake_window.status_bar.showMessage.assert_called_with(
            "Export failed", 3000
        )
        mock_message_box.assert_called_once_with(
            "Obsidian Export Failed",
            "Failed to export 'The Kraken': disk full",
            1500,
            QMessageBox.Icon.Critical,
            parent=fake_window,
        )
        mock_message_box.return_value.exec.assert_called_once_with()


@pytest.mark.parametrize(
    "entrypoint",
    ["show_transfer", "import_item_requested", "import_pasted_json_requested"],
)
def test_import_entrypoints_open_shared_workflow(coordinator, entrypoint):
    coordinator._transfer = MagicMock()
    getattr(coordinator, entrypoint)()
    assert coordinator._transfer.show.call_count == 1
