"""LongformManager - Handles longform document operations for MainWindow.

This module contains all longform document-related functionality extracted from
MainWindow to reduce its size and improve maintainability.
"""

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Q_ARG, QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from src.app.qt_invocation import invoke_queued
from src.commands.entity_commands import DeleteEntityCommand
from src.commands.event_commands import DeleteEventCommand
from src.commands.longform_commands import (
    DemoteLongformEntryCommand,
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
)
from src.core.logging_config import get_logger
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox
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

    export_vault_requested = Signal(str)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the LongformManager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window
        self._revision = 0
        self._request_revision: int | None = None
        self._snapshot_revision: int | None = None
        self._pending_sequence: list | None = None
        self._load_in_flight = False
        self._dirty = True
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(100)
        self._reload_timer.timeout.connect(self._request_if_needed)

    def load_longform_sequence(self) -> None:
        """Explicitly refresh the active Longform sequence."""
        self._revision += 1
        self._dirty = True
        self._request_if_needed()

    def mark_dirty(self) -> None:
        """Invalidate Longform data and refresh only when its panel is active."""
        self._revision += 1
        self._dirty = True
        if self._is_active():
            self._reload_timer.start()

    @Slot(str)
    def on_panel_activated(self, panel_id: str) -> None:
        """Render or load Longform content when its panel becomes active."""
        if panel_id != "longform":
            return
        if (
            not self._dirty
            and self._pending_sequence is not None
            and self._snapshot_revision == self._revision
        ):
            self.window.longform_editor.load_sequence(self._pending_sequence)
            return
        self._reload_timer.start(0)

    def _request_if_needed(self) -> None:
        """Submit the latest Longform revision if it still needs hydration."""
        if self._load_in_flight or not self._dirty or not self._is_active():
            return
        # PySide6 cross-thread signal/slot type issues.
        filter_json = (
            json.dumps(self.window.longform_filter_config)
            if self.window.longform_filter_config
            else ""
        )

        self._load_in_flight = True
        self._request_revision = self._revision
        invoke_queued(
            self.window.worker,
            "load_longform_sequence",
            Q_ARG(str, "default"),
            Q_ARG(str, filter_json),
        )

    @Slot(list)
    def on_longform_sequence_loaded(self, sequence: list) -> None:
        """Handler for when longform sequence is loaded."""
        request_revision = self._request_revision
        self._load_in_flight = False
        self._request_revision = None
        if request_revision is None:
            request_revision = self._revision
        self._pending_sequence = sequence
        self._snapshot_revision = request_revision
        if request_revision != self._revision:
            if self._is_active():
                self._reload_timer.start(0)
            return
        self._dirty = False
        self.window.data_coordinator.cached_longform_sequence = sequence
        if self._is_active():
            self.window.longform_editor.load_sequence(sequence)

    def on_command_finished_reload_longform(self) -> None:
        """Handler to reload longform sequence after command completion."""
        self.mark_dirty()

    def _is_active(self) -> bool:
        """Return whether Longform is the visible tab in its workspace zone."""
        workspace = self.window.workspace
        if "longform" not in workspace.panel_ids():
            return False
        zone = workspace.panel_zone("longform")
        return (
            workspace.zone_visible(zone)
            and workspace.active_panel(zone) == "longform"
        )

    def show_longform_filter_dialog(self) -> None:
        """Shows filter dialog for the Longform editor (independent state)."""
        from src.gui.dialogs.filter_dialog import FilterDialog

        dialog = FilterDialog(
            self.window,
            available_tags=self.window.data_coordinator.cached_tags,
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

    def delete_longform_item(self, table: str, row_id: str) -> None:
        """Delete an item completely (Event or Entity).

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to delete.

        """
        command: DeleteEventCommand | DeleteEntityCommand
        if table == "events":
            command = DeleteEventCommand(row_id)
        elif table == "entities":
            command = DeleteEntityCommand(row_id)
        else:
            logger.error(f"Unknown table type for deletion: {table}")
            return

        self.window.command_requested.emit(command)

    def move_up_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Move a longform entry up in its sibling list.

        Args:
            table: Table name ("events" or "entities").
            row_id: ID of the item to move up.
            old_meta: Previous longform metadata for undo.

        """
        # Calculate new position - between previous sibling and the one before it
        sequence = self.window.data_coordinator.cached_longform_sequence

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
            return  # Already at top

        # Get parent_id and depth from old_meta
        parent_id = old_meta.get("parent_id")
        depth = old_meta.get("depth", 0)

        # Find the previous sibling (same parent and depth)
        prev_idx = None
        for idx in range(current_idx - 1, -1, -1):
            item = sequence[idx]
            if (
                item["meta"].get("parent_id") == parent_id
                and item["meta"].get("depth", 0) == depth
            ):
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
            if (
                item["meta"].get("parent_id") == parent_id
                and item["meta"].get("depth", 0) == depth
            ):
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
        sequence = self.window.data_coordinator.cached_longform_sequence

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
            logger.debug(
                f"Cannot move down: item {table}.{row_id} is already at bottom"
            )
            return  # Already at bottom

        # Get parent_id and depth from old_meta
        parent_id = old_meta.get("parent_id")
        depth = old_meta.get("depth", 0)

        # Find the next sibling (same parent and depth)
        next_idx = None
        for idx in range(current_idx + 1, len(sequence)):
            item = sequence[idx]
            if (
                item["meta"].get("parent_id") == parent_id
                and item["meta"].get("depth", 0) == depth
            ):
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
            if (
                item["meta"].get("parent_id") == parent_id
                and item["meta"].get("depth", 0) == depth
            ):
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
        """Open the shared publishing workflow with Markdown selected."""
        self.window.import_coordinator.transfer_coordinator().show(
            tab=1, format_key="markdown"
        )

    def export_as_vault(self) -> None:
        """Open the shared note export workflow."""
        self.window.import_coordinator.transfer_coordinator().show(
            tab=1, format_key="notes"
        )

    @Slot(dict)
    def on_vault_export_finished(self, result: dict[str, object]) -> None:
        """Present the result of a worker-thread vault export.

        Args:
            result: Serializable export-result snapshot from ``DatabaseWorker``.

        """
        files_created_value = result.get("files_created", 0)
        files_created = (
            int(files_created_value)
            if isinstance(files_created_value, (int, float, str))
            else 0
        )
        output_dir = str(result.get("output_dir", ""))
        errors_value = result.get("errors", [])
        errors = (
            [str(error) for error in errors_value]
            if isinstance(errors_value, list)
            else []
        )
        if bool(result.get("success", False)):
            message = f"Exported {files_created} files to {output_dir}"
            self.window.status_bar.showMessage(message, 5000)
            popup = AutoClosingMessageBox(
                "Obsidian Export Complete",
                message,
                1500,
                QMessageBox.Icon.Information,
                parent=self.window,
            )
            popup.exec()
            logger.info("Vault export complete: %d files", files_created)
            return
        error_summary = "; ".join(errors[:3]) or "Unknown export error"
        message = f"Export completed with errors: {error_summary}"
        self.window.status_bar.showMessage(message, 5000)
        popup = AutoClosingMessageBox(
            "Obsidian Export Failed",
            f"Vault export failed: {error_summary}",
            1500,
            QMessageBox.Icon.Critical,
            parent=self.window,
        )
        popup.exec()
        logger.warning("Vault export errors: %s", errors)
