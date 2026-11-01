"""Import Coordinator Module.

Manages import operations and database manager dialog, extracted from
MainWindow to reduce its responsibilities.

Handles:
- JSON file import workflow (file selection, preview, worker dispatch)
- Import result handling (success/failure display)
- Database manager dialog
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox
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

    prepare_obsidian_export_requested = Signal(str, str)
    run_obsidian_export_requested = Signal(str, str, str)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the import coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(main_window)
        self._transfer: Any = None

    def transfer_coordinator(self) -> Any:
        """Return the feature coordinator, creating its worker adapter lazily."""
        if self._transfer is None:
            from src.app.coordinators.transfer_coordinator import (
                create_transfer_coordinator,
            )

            self._transfer = create_transfer_coordinator(self.main_window)
        return self._transfer

    @Slot()
    def show_transfer(self) -> None:
        """Open the unified format chooser."""
        self.transfer_coordinator().show()

    @Slot()
    def import_item_requested(self) -> None:
        """Open the shared file, folder and pasted-lore import workflow."""
        self.transfer_coordinator().show(tab=0)

    @Slot()
    def import_pasted_json_requested(self) -> None:
        """Open the same import workflow with pasted JSON available."""
        self.transfer_coordinator().show(tab=0)

    @Slot()
    def show_database_manager(self) -> None:
        """Shows the Database Manager dialog."""
        dialog = DatabaseManagerDialog(self.main_window)

        def protect_world_change(reason: str, continuation: Callable[[], None]) -> None:
            self.main_window.app_coordinator.settings.request_world_transition(
                lambda: self.main_window.app_coordinator.map_edits.request_transition(
                    reason, continuation
                )
            )

        dialog.edit_transition_handler = protect_world_change
        if dialog.exec() == QDialog.DialogCode.Accepted:
            pass

    @Slot(str, str)
    def export_single_obsidian(self, item_type: str, item_id: str) -> None:
        """Open the shared note export with the contextual record selected."""
        if item_type in {"entity", "event"}:
            self.transfer_coordinator().show(
                tab=1, format_key="notes", selected=[item_id]
            )

    @Slot(dict)
    def on_obsidian_export_prepared(self, snapshot: ObsidianExportPreparation) -> None:
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
    def on_obsidian_export_finished(self, snapshot: ObsidianExportCompletion) -> None:
        """Present the result of a worker-thread Obsidian export.

        Args:
            snapshot: Serializable export completion snapshot.

        """
        if snapshot["success"]:
            message = f"Exported '{snapshot['item_name']}' to {snapshot['file_path']}"
            self.main_window.status_bar.showMessage(message, 5000)
            popup = AutoClosingMessageBox(
                "Obsidian Export Complete",
                message,
                1500,
                QMessageBox.Icon.Information,
                parent=self.main_window,
            )
            popup.exec()
            logger.info(
                "Exported %s '%s' to %s",
                snapshot["item_type"],
                snapshot["item_name"],
                snapshot["file_path"],
            )
            return

        self.main_window.status_bar.showMessage("Export failed", 3000)
        popup = AutoClosingMessageBox(
            "Obsidian Export Failed",
            f"Failed to export '{snapshot['item_name']}': {snapshot['error']}",
            1500,
            QMessageBox.Icon.Critical,
            parent=self.main_window,
        )
        popup.exec()
