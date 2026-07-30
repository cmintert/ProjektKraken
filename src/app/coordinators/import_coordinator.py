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

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog
from src.gui.dialogs.import_preview_dialog import ImportPreviewDialog
from src.gui.dialogs.paste_json_import_dialog import PasteJsonImportDialog
from src.gui.dialogs.progress_dialog import ProgressDialog
from src.services.import_service import ImportResult, ImportService
from src.services.obsidian_exporter import (
    ObsidianExportCompletion,
    ObsidianExportPreparation,
)

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class ImportCoordinator(BaseCoordinator):
    """Coordinates import operations and database management.

    Handles the full import workflow: file selection, parsing, preview,
    and dispatching to the worker thread for database operations.
    """

    run_import_requested = Signal(str, str)
    run_markdown_import_requested = Signal(str, str)
    run_markdown_batch_import_requested = Signal(str, str)
    prepare_obsidian_export_requested = Signal(str, str)
    run_obsidian_export_requested = Signal(str, str, str)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the import coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(main_window)
        self._import_progress_dialog: Optional[ProgressDialog] = None

    @Slot()
    def import_item_requested(self) -> None:
        """Handles the request to import items from JSON or Markdown files.

        This method:
        1. Opens a file dialog to select one or more JSON/Markdown files
        2. For a single file: parses, previews, and dispatches as before
        3. For multiple .md files: collects contents and dispatches a batch
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window,
            "Import Item",
            "",
            "All Supported (*.json *.md);;JSON Files (*.json);;"
            "Markdown Files (*.md);;All Files (*)",
        )

        if not file_paths:
            return

        try:
            # Batch path: multiple Markdown files
            md_paths = [p for p in file_paths if p.lower().endswith(".md")]
            if len(file_paths) > 1 and len(md_paths) == len(file_paths):
                self._import_markdown_batch(md_paths)
                return

            # Single-file path (original behaviour)
            file_path = file_paths[0]
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            is_markdown = file_path.lower().endswith(".md")

            if is_markdown:
                from pathlib import Path

                filename_stem = Path(file_path).stem
                parsed_data = ImportService.parse_markdown_file(
                    content, fallback_title=filename_stem
                )
            else:
                parsed_data = ImportService.parse_only(content)

            dialog = ImportPreviewDialog(self.main_window, parsed_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                import json

                options = dialog.get_options()
                # Extracted filename stem for fallback title
                from pathlib import Path

                filename_stem = Path(file_path).stem
                options["filename"] = filename_stem
                options_json = json.dumps(options)

                if is_markdown:
                    self.run_markdown_import_requested.emit(content, options_json)
                else:
                    parsed_json = json.dumps(parsed_data)
                    self.run_import_requested.emit(parsed_json, options_json)

                self._show_import_progress()

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

    @Slot()
    def import_pasted_json_requested(self) -> None:
        """Import JSON data entered directly in a text dialog."""
        dialog = PasteJsonImportDialog(self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        json_text = dialog.get_json_text().strip()
        if not json_text:
            return

        try:
            parsed_data = ImportService.parse_only(json_text)

            preview = ImportPreviewDialog(self.main_window, parsed_data)
            if preview.exec() != QDialog.DialogCode.Accepted:
                return

            import json

            options = preview.get_options()
            options_json = json.dumps(options)
            parsed_json = json.dumps(parsed_data)

            self.run_import_requested.emit(parsed_json, options_json)

            self._show_import_progress()

        except ValueError as e:
            QMessageBox.critical(
                self.main_window,
                "Invalid JSON",
                f"Failed to parse pasted JSON: {e}",
            )
        except Exception as e:
            logger.exception("Pasted JSON import error")
            QMessageBox.critical(
                self.main_window,
                "Import Error",
                f"An unexpected error occurred during pasted JSON import: {e}",
            )

    def _import_markdown_batch(self, file_paths: list[str]) -> None:
        """Read multiple Markdown files and dispatch a batch import.

        Args:
            file_paths: List of absolute paths to .md files.

        """
        import json

        contents = []
        for fp in file_paths:
            with open(fp, "r", encoding="utf-8") as f:
                contents.append(f.read())

        contents_json = json.dumps(contents)
        options_json = json.dumps({})

        self.run_markdown_batch_import_requested.emit(contents_json, options_json)

        self._show_import_progress()

    def _show_import_progress(self) -> None:
        """Display a non-cancellable progress dialog during import."""
        self._import_progress_dialog = ProgressDialog(
            "Importing data...\n\nThis may take a moment for large files.",
            parent=self.main_window,
            cancelable=False,
            title="Import in Progress",
        )
        self.main_window.status_bar.showMessage("Importing...", 0)

    @Slot(object)
    def on_import_finished(self, result: ImportResult) -> None:
        """Handles the completion of an import operation.

        Args:
            result: ImportResult from the worker thread.

        """
        if self._import_progress_dialog:
            self._import_progress_dialog.finish()
            self._import_progress_dialog = None

        self.main_window.status_bar.clearMessage()

        if result.success:
            # Trigger a full GUI refresh so editors, timeline, etc. update
            self.main_window.data_coordinator.load_data()

            msg = (
                "Import Successful!\n\n"
                f"Entities: {len(result.created_entities)}\n"
                f"Events: {len(result.created_events)}\n"
                f"Relations: {len(result.created_relations)}"
            )
            if result.ambiguous_items:
                msg += f"\n\nAmbiguous items skipped: {len(result.ambiguous_items)}"
                for item in result.ambiguous_items[:3]:
                    msg += (
                        f"\n  \u2022 {item['type'].title()} '{item['name']}': "
                        f"{len(item['candidates'])} matches"
                    )
                if len(result.ambiguous_items) > 3:
                    msg += f"\n  ...and {len(result.ambiguous_items) - 3} more."
            if result.unparsed_date_count > 0:
                msg += (
                    f"\n\nEvents with unparsed dates (defaulted to 0.0): "
                    f"{result.unparsed_date_count}"
                )
            if result.warnings:
                msg += "\n\nWarnings:\n" + "\n".join(result.warnings[:5])
                if len(result.warnings) > 5:
                    msg += f"\n...and {len(result.warnings) - 5} more."

            QMessageBox.information(self.main_window, "Import Complete", msg)
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

    @Slot(str, str)
    def export_single_obsidian(self, item_type: str, item_id: str) -> None:
        """Export a single entity or event as an Obsidian Markdown file.

        Args:
            item_type: "event" or "entity".
            item_id: The ID of the item to export.

        """
        if item_type not in {"entity", "event"}:
            logger.warning("Unsupported Obsidian export item type: %s", item_type)
            self.main_window.status_bar.showMessage(
                f"Cannot export unsupported item type '{item_type}'", 3000
            )
            return

        self.prepare_obsidian_export_requested.emit(item_type, item_id)
        self.main_window.status_bar.showMessage("Preparing export...", 0)

    @Slot(dict)
    def on_obsidian_export_prepared(
        self, snapshot: ObsidianExportPreparation
    ) -> None:
        """Choose the output path after the worker resolves the item.

        Args:
            snapshot: Serializable item identity snapshot from the database worker.

        """
        error = snapshot["error"]
        if error:
            self.main_window.status_bar.showMessage(
                error,
                3000,
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export to Obsidian Markdown",
            f"{snapshot['item_name']}.md",
            "Markdown Files (*.md);;All Files (*)",
        )

        if not file_path:
            self.main_window.status_bar.clearMessage()
            return

        self.run_obsidian_export_requested.emit(
            snapshot["item_type"],
            snapshot["item_id"],
            file_path,
        )
        self.main_window.status_bar.showMessage("Exporting...", 0)

    @Slot(dict)
    def on_obsidian_export_finished(
        self, snapshot: ObsidianExportCompletion
    ) -> None:
        """Present the result of a worker-thread Obsidian export.

        Args:
            snapshot: Serializable export completion snapshot.

        """
        if snapshot["success"]:
            self.main_window.status_bar.showMessage(
                f"Exported '{snapshot['item_name']}' to {snapshot['file_path']}",
                5000,
            )
            logger.info(
                "Exported %s '%s' to %s",
                snapshot["item_type"],
                snapshot["item_name"],
                snapshot["file_path"],
            )
            return

        self.main_window.status_bar.showMessage("Export failed", 3000)
        QMessageBox.critical(
            self.main_window,
            "Export Error",
            f"Failed to export '{snapshot['item_name']}': {snapshot['error']}",
        )
