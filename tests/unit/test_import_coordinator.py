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


class TestDatabaseManager:
    """Tests for database manager dialog."""

    @patch("src.app.coordinators.import_coordinator.DatabaseManagerDialog")
    def test_show_database_manager(self, mock_dialog_class, coordinator, fake_window):
        """show_database_manager should create and show the dialog."""
        mock_dialog = MagicMock()
        mock_dialog_class.return_value = mock_dialog
        fake_window.app_coordinator = MagicMock()
        coordinator.show_database_manager()
        mock_dialog.exec.assert_called_once()
        continuation = MagicMock()
        mock_dialog.edit_transition_handler("change world", continuation)
        settings = fake_window.app_coordinator.settings
        settings.request_world_transition.assert_called_once()
        fake_window.app_coordinator.map_edits.request_transition.assert_not_called()
        settings.request_world_transition.call_args.args[0]()
        fake_window.app_coordinator.map_edits.request_transition.assert_called_once_with(
            "change world", continuation
        )


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
            lambda item_type, item_id, path: requests.append((item_type, item_id, path))
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

        assert requests == [("entity", "entity-1", "C:/tmp/Chosen Name.md")]

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

        fake_window.status_bar.showMessage.assert_called_with("Export failed", 3000)
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
