"""
LongformManager - Handles longform document operations for MainWindow.

This module contains all longform document-related functionality extracted from
MainWindow to reduce its size and improve maintainability.
"""

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Slot
from PySide6.QtWidgets import QDialog, QFileDialog

from src.commands.longform_commands import (
    DemoteLongformEntryCommand,
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
)
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class LongformManager(QObject):
    """
    Manages longform document operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Loading longform sequences
    - Filtering longform content
    - Promoting/demoting/moving entries
    - Exporting longform documents to Markdown
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """
        Initialize the LongformManager.

        Args:
            main_window: Reference to the MainWindow instance.
        """
        super().__init__()
        self.window = main_window

    def load_longform_sequence(self) -> None:
        """
        Loads the longform sequence, applying active filters if any.
        """
        # PySide6 cross-thread signal/slot type issues.
        filter_json = (
            json.dumps(self.window.longform_filter_config)
            if self.window.longform_filter_config
            else ""
        )

        QMetaObject.invokeMethod(
            self.window.worker,
            "load_longform_sequence",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, "default"),
            Q_ARG(str, filter_json),
        )

    @Slot(list)
    def on_longform_sequence_loaded(self, sequence: list) -> None:
        """
        Handler for when longform sequence is loaded.
        """
        self.window.longform_editor.load_sequence(sequence)
        self.window._cached_longform_sequence = sequence

    def on_command_finished_reload_longform(self) -> None:
        """Handler to reload longform sequence after command completion."""
        self.load_longform_sequence()

    def show_longform_filter_dialog(self) -> None:
        """Shows filter dialog for the Longform editor (independent state)."""
        from src.gui.dialogs.filter_dialog import FilterDialog

        tags = []
        if self.window.gui_db_service:
            tag_dicts = self.window.gui_db_service.get_active_tags()
            tags = [t["name"] for t in tag_dicts]

        dialog = FilterDialog(
            self.window,
            available_tags=tags,
            current_config=self.window.longform_filter_config,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_filter_config()
            self.window.longform_filter_config = config

            logger.info(f"Applying longform filter: {config}")
            # Refresh longform view with new filter
            self.load_longform_sequence()

    @Slot()
    def clear_longform_filter(self) -> None:
        """Clears the longform filter and reloads the longform view."""
        logger.info("Clearing longform filters")
        self.window.longform_filter_config = {}
        self.load_longform_sequence()

    def promote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """
        Promotes a longform entry by reducing its depth.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to promote.
            old_meta: Previous longform metadata for undo.
        """
        cmd = PromoteLongformEntryCommand(table, row_id, old_meta)
        self.window.command_requested.emit(cmd)

    def demote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """
        Demotes a longform entry by increasing its depth.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to demote.
            old_meta: Previous longform metadata for undo.
        """
        cmd = DemoteLongformEntryCommand(table, row_id, old_meta)
        self.window.command_requested.emit(cmd)

    def move_longform_entry(
        self, table: str, row_id: str, old_meta: dict, new_meta: dict
    ) -> None:
        """
        Moves a longform entry to a new position.

        Args:
            table: Table name.
            row_id: ID.
            old_meta: Old metadata.
            new_meta: New metadata with position/parent/depth.
        """
        cmd = MoveLongformEntryCommand(table, row_id, old_meta, new_meta)
        self.window.command_requested.emit(cmd)

    def export_longform_document(self) -> None:
        """
        Exports the current longform document to Markdown.
        Opens a file dialog for the user to choose save location.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export Longform Document",
            "longform_document.md",
            "Markdown Files (*.md);;All Files (*)",
        )

        if file_path:
            try:
                lines = []
                for item in self.window._cached_longform_sequence:
                    heading_level = item["heading_level"]
                    title = item["meta"].get("title_override") or item["name"]
                    heading = "#" * heading_level + " " + title
                    lines.append(heading)
                    lines.append("")

                    content = item.get("content", "").strip()
                    if content:
                        lines.append(content)
                        lines.append("")
                    lines.append("")

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                self.window.status_bar.showMessage(f"Exported to {file_path}", 3000)
            except Exception as e:
                logger.error(f"Failed to export longform document: {e}")
                self.window.status_bar.showMessage(f"Export failed: {e}", 5000)
