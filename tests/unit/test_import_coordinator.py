"""Unit tests for ImportCoordinator.

Tests import workflow and database manager dialog extracted from MainWindow.
"""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox


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
def qapp():
    """Fixture to provide QApplication instance."""
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


class TestImportWorkflow:
    """Tests for import item workflow."""

    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    def test_import_cancelled_when_no_file(self, mock_dialog, coordinator, fake_window):
        """Import should be cancelled when no file is selected."""
        mock_dialog.getOpenFileNames.return_value = ([], "")
        coordinator.import_item_requested()
        # Worker should not be invoked
        fake_window.worker.run_import.assert_not_called()

    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    @patch("src.app.coordinators.import_coordinator.ImportPreviewDialog")
    @patch("src.app.coordinators.import_coordinator.ImportService")
    @patch("builtins.open", mock_open(read_data='{"type": "entity"}'))
    def test_import_preview_rejected(
        self, mock_service, mock_preview, mock_dialog, coordinator
    ):
        """Import should be cancelled when preview dialog is rejected."""
        from PySide6.QtWidgets import QDialog

        mock_dialog.getOpenFileNames.return_value = (["/test/file.json"], "")
        mock_service.parse_only.return_value = {"type": "entity"}
        mock_preview_instance = MagicMock()
        mock_preview_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_preview.return_value = mock_preview_instance

        coordinator.import_item_requested()
        # Worker should not be invoked since dialog was rejected
        coordinator.main_window.worker.run_import.assert_not_called()

    @patch("src.app.coordinators.import_coordinator.QMessageBox")
    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    def test_import_error_shows_message(self, mock_dialog, mock_box, coordinator):
        """Import errors should show a critical message."""
        mock_dialog.getOpenFileNames.return_value = (["/nonexistent.json"], "")
        coordinator.import_item_requested()
        mock_box.critical.assert_called_once()


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


class TestMarkdownBatchImport:
    """Tests for multi-file Markdown batch import."""

    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    @patch("builtins.open", mock_open(read_data="# File A"))
    @patch(
        "src.app.coordinators.import_coordinator.ImportCoordinator._show_import_progress"
    )
    def test_batch_import_multiple_md_files(
        self, mock_progress, mock_dialog, coordinator, fake_window
    ):
        """Multiple .md files should trigger run_markdown_batch_import."""
        requests = []
        coordinator.run_markdown_batch_import_requested.connect(
            lambda contents, options: requests.append((contents, options))
        )
        mock_dialog.getOpenFileNames.return_value = (
            ["/tmp/a.md", "/tmp/b.md"],
            "",
        )

        coordinator.import_item_requested()

        # Should NOT invoke the single-file methods
        fake_window.worker.run_markdown_import.assert_not_called()
        fake_window.worker.run_import.assert_not_called()
        assert len(requests) == 1

    @patch("src.app.coordinators.import_coordinator.QFileDialog")
    def test_empty_selection_is_noop(self, mock_dialog, coordinator, fake_window):
        """Empty file selection should do nothing."""
        mock_dialog.getOpenFileNames.return_value = ([], "")
        coordinator.import_item_requested()
        fake_window.worker.run_import.assert_not_called()
        fake_window.worker.run_markdown_import.assert_not_called()


class TestDatabaseManager:
    """Tests for database manager dialog."""

    @patch("src.app.coordinators.import_coordinator.DatabaseManagerDialog")
    def test_show_database_manager(self, mock_dialog_class, coordinator, fake_window):
        """show_database_manager should create and show the dialog."""
        mock_dialog = MagicMock()
        mock_dialog_class.return_value = mock_dialog
        coordinator.show_database_manager()
        mock_dialog.exec.assert_called_once()


class TestPastedJsonImport:
    """Tests for pasted JSON import workflow."""

    @patch("src.app.coordinators.import_coordinator.PasteJsonImportDialog")
    def test_import_pasted_json_cancelled(self, mock_paste_dialog, coordinator):
        """Cancelling the paste dialog should not start import."""
        from PySide6.QtWidgets import QDialog

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Rejected
        mock_paste_dialog.return_value = dialog

        coordinator.import_pasted_json_requested()
        coordinator.main_window.worker.run_import.assert_not_called()

    @patch("src.app.coordinators.import_coordinator.QMessageBox")
    @patch("src.app.coordinators.import_coordinator.ImportService")
    @patch("src.app.coordinators.import_coordinator.PasteJsonImportDialog")
    def test_import_pasted_json_invalid_json(
        self,
        mock_paste_dialog,
        mock_import_service,
        mock_message_box,
        coordinator,
    ):
        """Invalid pasted JSON should show an error."""
        from PySide6.QtWidgets import QDialog

        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.get_json_text.return_value = "not json"
        mock_paste_dialog.return_value = dialog
        mock_import_service.parse_only.side_effect = ValueError("bad json")

        coordinator.import_pasted_json_requested()

        mock_message_box.critical.assert_called_once()

    @patch("src.app.coordinators.import_coordinator.ImportPreviewDialog")
    @patch("src.app.coordinators.import_coordinator.ImportService")
    @patch("src.app.coordinators.import_coordinator.PasteJsonImportDialog")
    @patch(
        "src.app.coordinators.import_coordinator.ImportCoordinator._show_import_progress"
    )
    def test_import_pasted_json_valid_dispatches_worker(
        self,
        mock_show_progress,
        mock_paste_dialog,
        mock_import_service,
        mock_preview_dialog,
        coordinator,
    ):
        """Valid pasted JSON should follow preview and dispatch to worker."""
        from PySide6.QtWidgets import QDialog

        requests = []
        coordinator.run_import_requested.connect(
            lambda parsed, options: requests.append((parsed, options))
        )
        paste_dialog = MagicMock()
        paste_dialog.exec.return_value = QDialog.DialogCode.Accepted
        paste_dialog.get_json_text.return_value = "{}"
        mock_paste_dialog.return_value = paste_dialog

        parsed_data = {"entities": [{"name": "E1"}], "events": [], "relations": []}
        mock_import_service.parse_only.return_value = parsed_data

        preview = MagicMock()
        preview.exec.return_value = QDialog.DialogCode.Accepted
        preview.get_options.return_value = {
            "source_name": "manual_import",
            "mode": "update",
            "dry_run": False,
        }
        mock_preview_dialog.return_value = preview

        coordinator.import_pasted_json_requested()

        assert len(requests) == 1
        mock_show_progress.assert_called_once()

    @patch("src.app.coordinators.import_coordinator.ImportPreviewDialog")
    @patch("src.app.coordinators.import_coordinator.ImportService")
    @patch("src.app.coordinators.import_coordinator.PasteJsonImportDialog")
    def test_import_pasted_json_preview_rejected(
        self,
        mock_paste_dialog,
        mock_import_service,
        mock_preview_dialog,
        coordinator,
    ):
        """Rejecting the preview should not dispatch worker import."""
        from PySide6.QtWidgets import QDialog

        requests = []
        coordinator.run_import_requested.connect(
            lambda parsed, options: requests.append((parsed, options))
        )
        paste_dialog = MagicMock()
        paste_dialog.exec.return_value = QDialog.DialogCode.Accepted
        paste_dialog.get_json_text.return_value = "{}"
        mock_paste_dialog.return_value = paste_dialog

        mock_import_service.parse_only.return_value = {
            "entities": [],
            "events": [],
            "relations": [],
        }

        preview = MagicMock()
        preview.exec.return_value = QDialog.DialogCode.Rejected
        mock_preview_dialog.return_value = preview

        coordinator.import_pasted_json_requested()

        assert requests == []


class TestSingleObsidianExport:
    """Tests for worker-backed single-item Obsidian exports."""

    def test_export_request_is_dispatched_without_gui_database(
        self, coordinator, fake_window
    ):
        """The coordinator should request worker preparation using item identity."""
        requests = []
        coordinator.prepare_obsidian_export_requested.connect(
            lambda item_type, item_id: requests.append((item_type, item_id))
        )

        coordinator.export_single_obsidian("entity", "entity-1")

        assert requests == [("entity", "entity-1")]
        fake_window.status_bar.showMessage.assert_called_with(
            "Preparing export...", 0
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
