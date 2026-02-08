"""LongformManager - Handles longform document operations for MainWindow.

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
    RemoveLongformEntryCommand,
)
from src.core.logging_config import get_logger
from src.services.longform_builder import DEFAULT_POSITION_GAP

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class LongformManager(QObject):
    """Manages longform document operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Loading longform sequences
    - Filtering longform content
    - Promoting/demoting/moving entries
    - Exporting longform documents to Markdown
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the LongformManager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window

    def load_longform_sequence(self) -> None:
        """Loads the longform sequence, applying active filters if any."""
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
        """Handler for when longform sequence is loaded."""
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
        """Promotes a longform entry by reducing its depth.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to promote.
            old_meta: Previous longform metadata for undo.

        """
        cmd = PromoteLongformEntryCommand(table, row_id, old_meta)
        self.window.command_requested.emit(cmd)

    def demote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Demotes a longform entry by increasing its depth.

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
        """Moves a longform entry to a new position.

        Args:
            table: Table name.
            row_id: ID.
            old_meta: Old metadata.
            new_meta: New metadata with position/parent/depth.

        """
        cmd = MoveLongformEntryCommand(table, row_id, old_meta, new_meta)
        self.window.command_requested.emit(cmd)

    def remove_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Remove a longform entry from the document.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to remove.
            old_meta: Previous longform metadata for undo.

        """
        cmd = RemoveLongformEntryCommand(table, row_id, old_meta)
        self.window.command_requested.emit(cmd)

    def move_up_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Move a longform entry up in its sibling list.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to move up.
            old_meta: Previous longform metadata for undo.

        """
        # Calculate new position - between previous sibling and the one before it
        sequence = self.window._cached_longform_sequence
        
        # Find current item in sequence
        current_idx = None
        for idx, item in enumerate(sequence):
            if item["table"] == table and item["id"] == row_id:
                current_idx = idx
                break
        
        if current_idx is None:
            logger.warning(
                f"Cannot move up: item {table}.{row_id} not found in sequence"
            )
            return
        
        if current_idx == 0:
            logger.debug(f"Cannot move up: item {table}.{row_id} is already at top")
            return  # Item not found or already at top
        
        # Get parent_id and depth from old_meta
        parent_id = old_meta.get("parent_id")
        depth = old_meta.get("depth", 0)
        
        # Find the previous sibling (same parent and depth)
        prev_idx = None
        for idx in range(current_idx - 1, -1, -1):
            item = sequence[idx]
            if item["meta"].get("parent_id") == parent_id and item["meta"].get("depth", 0) == depth:
                prev_idx = idx
                break
        
        if prev_idx is None:
            return  # No previous sibling
        
        # Calculate new position between prev_sibling's predecessor and prev_sibling
        prev_item = sequence[prev_idx]
        prev_pos = prev_item["meta"].get("position", 0.0)
        
        # Find predecessor of prev_sibling
        before_prev_idx = None
        for idx in range(prev_idx - 1, -1, -1):
            item = sequence[idx]
            if item["meta"].get("parent_id") == parent_id and item["meta"].get("depth", 0) == depth:
                before_prev_idx = idx
                break
        
        if before_prev_idx is not None:
            before_prev_pos = sequence[before_prev_idx]["meta"].get("position", 0.0)
            new_pos = (before_prev_pos + prev_pos) / 2.0
        else:
            new_pos = prev_pos - DEFAULT_POSITION_GAP
        
        # Create new metadata
        new_meta = old_meta.copy()
        new_meta["position"] = new_pos
        
        cmd = MoveLongformEntryCommand(table, row_id, old_meta, new_meta)
        self.window.command_requested.emit(cmd)

    def move_down_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Move a longform entry down in its sibling list.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to move down.
            old_meta: Previous longform metadata for undo.

        """
        # Calculate new position - between next sibling and the one after it
        sequence = self.window._cached_longform_sequence
        
        # Find current item in sequence
        current_idx = None
        for idx, item in enumerate(sequence):
            if item["table"] == table and item["id"] == row_id:
                current_idx = idx
                break
        
        if current_idx is None:
            logger.warning(
                f"Cannot move down: item {table}.{row_id} not found in sequence"
            )
            return
        
        if current_idx >= len(sequence) - 1:
            logger.debug(f"Cannot move down: item {table}.{row_id} is already at bottom")
            return  # Item not found or already at bottom
        
        # Get parent_id and depth from old_meta
        parent_id = old_meta.get("parent_id")
        depth = old_meta.get("depth", 0)
        
        # Find the next sibling (same parent and depth)
        next_idx = None
        for idx in range(current_idx + 1, len(sequence)):
            item = sequence[idx]
            if item["meta"].get("parent_id") == parent_id and item["meta"].get("depth", 0) == depth:
                next_idx = idx
                break
        
        if next_idx is None:
            return  # No next sibling
        
        # Calculate new position between next_sibling and its successor
        next_item = sequence[next_idx]
        next_pos = next_item["meta"].get("position", 0.0)
        
        # Find successor of next_sibling
        after_next_idx = None
        for idx in range(next_idx + 1, len(sequence)):
            item = sequence[idx]
            if item["meta"].get("parent_id") == parent_id and item["meta"].get("depth", 0) == depth:
                after_next_idx = idx
                break
        
        if after_next_idx is not None:
            after_next_pos = sequence[after_next_idx]["meta"].get("position", 0.0)
            new_pos = (next_pos + after_next_pos) / 2.0
        else:
            new_pos = next_pos + DEFAULT_POSITION_GAP
        
        # Create new metadata
        new_meta = old_meta.copy()
        new_meta["position"] = new_pos
        
        cmd = MoveLongformEntryCommand(table, row_id, old_meta, new_meta)
        self.window.command_requested.emit(cmd)

    def export_longform_document(self) -> None:
        """Exports the current longform document to Markdown.

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

    def export_as_vault(self) -> None:
        """Exports entities and events as individual Obsidian-compatible .md files.

        Opens a folder dialog for the user to choose export location. Each entity/event
        becomes a separate file with YAML frontmatter.
        """
        from pathlib import Path

        from src.services.obsidian_exporter import ObsidianExporter

        # Get output directory from user
        output_dir = QFileDialog.getExistingDirectory(
            self.window,
            "Select Export Folder for Vault",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )

        if not output_dir:
            return

        if not self.window.gui_db_service:
            self.window.status_bar.showMessage("No database connection", 3000)
            return

        try:
            exporter = ObsidianExporter(self.window.gui_db_service)
            result = exporter.export_to_folder(
                output_dir=Path(output_dir),
                include_relations=True,
            )

            if result.success:
                self.window.status_bar.showMessage(
                    f"Exported {result.files_created} files to {output_dir}", 5000
                )
                logger.info(f"Vault export complete: {result.files_created} files")
            else:
                error_summary = "; ".join(result.errors[:3])
                self.window.status_bar.showMessage(
                    f"Export completed with errors: {error_summary}", 5000
                )
                logger.warning(f"Vault export errors: {result.errors}")

        except Exception as e:
            logger.error(f"Failed to export vault: {e}")
            self.window.status_bar.showMessage(f"Export failed: {e}", 5000)
