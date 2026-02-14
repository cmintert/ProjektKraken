"""Import Coordinator Module.

Manages import operations and database manager dialog, extracted from
MainWindow to reduce its responsibilities.

Handles:
- JSON file import workflow (file selection, preview, worker dispatch)
- Import result handling (success/failure display)
- Database manager dialog
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QProgressDialog

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog
from src.gui.dialogs.import_preview_dialog import ImportPreviewDialog
from src.services.import_service import ImportService

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class ImportCoordinator(BaseCoordinator):
    """Coordinates import operations and database management.

    Handles the full import workflow: file selection, parsing, preview,
    and dispatching to the worker thread for database operations.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the import coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(main_window)
        self._import_progress_dialog: Optional[QProgressDialog] = None

    @Slot()
    def import_item_requested(self) -> None:
        """Handles the request to import an item from a JSON file.

        This method:
        1. Opens a file dialog to select a JSON file
        2. Parses the JSON content (no DB access needed)
        3. Shows a preview dialog
        4. If confirmed, sends the parsed data to the worker thread for import
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Import Item",
            "",
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = f.read()

            parsed_data = ImportService.parse_only(json_content)

            dialog = ImportPreviewDialog(self.main_window, parsed_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                import json

                parsed_json = json.dumps(parsed_data)
                options = dialog.get_options()
                options_json = json.dumps(options)

                QMetaObject.invokeMethod(
                    self.main_window.worker,
                    "run_import",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, parsed_json),
                    Q_ARG(str, options_json),
                )

                from src.gui.dialogs.progress_dialog import ProgressDialog

                self._import_progress_dialog = ProgressDialog(
                    "Importing data...\n\n"
                    "This may take a moment for large files.",
                    parent=self.main_window,
                    cancelable=False,
                    title="Import in Progress",
                )
                self.main_window.status_bar.showMessage("Importing...", 0)

        except Exception as e:
            logger.exception("Import error")
            QMessageBox.critical(
                self.main_window,
                "Import Error",
                f"An unexpected error occurred during import: {e}\n\n"
                "Your existing data is safe and unchanged.\n\n"
                "Possible causes:\n"
                "• Invalid file format or corrupted data\n"
                "• Unsupported import format\n"
                "• File encoding issues (try UTF-8)\n\n"
                "To fix:\n"
                "1. Check that the file is a valid import format\n"
                "2. Verify file is not corrupted\n"
                "3. Check application logs for detailed error\n"
                "4. Try exporting and re-importing a small test dataset",
            )

    @Slot(object)
    def on_import_finished(self, result: object) -> None:
        """Handles the completion of an import operation.

        Args:
            result: ImportResult from the worker thread.

        """
        if self._import_progress_dialog:
            self._import_progress_dialog.finish()
            self._import_progress_dialog = None

        self.main_window.status_bar.clearMessage()

        if result.success:
            msg = (
                "Import Successful!\n\n"
                f"Entities: {len(result.created_entities)}\n"
                f"Events: {len(result.created_events)}\n"
                f"Relations: {len(result.created_relations)}"
            )
            if result.warnings:
                msg += "\n\nWarnings:\n" + "\n".join(result.warnings[:5])
                if len(result.warnings) > 5:
                    msg += f"\n...and {len(result.warnings) - 5} more."

            QMessageBox.information(
                self.main_window, "Import Complete", msg
            )
        else:
            err_msg = "\n".join(result.errors[:10])
            if len(result.errors) > 10:
                err_msg += f"\n...and {len(result.errors) - 10} more errors."

            QMessageBox.critical(
                self.main_window,
                "Import Failed",
                f"Import completed with errors. No data was imported.\n\n"
                f"Errors ({len(result.errors)} total):\n{err_msg}\n\n"
                "What to do:\n"
                "1. Fix the errors in your source file\n"
                "2. Check file format matches expected structure\n"
                "3. Try importing a smaller subset first\n"
                "4. Consult documentation for import format details",
            )

    @Slot()
    def show_database_manager(self) -> None:
        """Shows the Database Manager dialog."""
        dialog = DatabaseManagerDialog(self.main_window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pass
