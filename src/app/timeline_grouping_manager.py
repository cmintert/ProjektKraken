"""
TimelineGroupingManager - Handles timeline grouping operations for MainWindow.

This module contains all timeline grouping-related functionality extracted from
MainWindow to reduce its size and improve maintainability.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import QColorDialog

from src.commands.timeline_grouping_commands import (
    ClearTimelineGroupingCommand,
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class TimelineGroupingManager:
    """
    Manages timeline grouping operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Loading and applying timeline grouping configurations
    - Opening and handling the grouping configuration dialog
    - Updating tag colors
    - Adding/removing tags from grouping
    - Clearing grouping configuration
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """
        Initialize the TimelineGroupingManager.

        Args:
            main_window: Reference to the MainWindow instance.
        """
        self.window = main_window

    def request_grouping_config(self) -> None:
        """Requests loading of the timeline grouping configuration."""
        try:
            # Load from GUI db_service (thread-safe main thread usage)
            if hasattr(self.window, "gui_db_service"):
                config = self.window.gui_db_service.get_timeline_grouping_config()
                self.on_grouping_config_loaded(config)
        except Exception as e:
            logger.warning(f"Failed to load grouping config: {e}")

    def on_grouping_config_loaded(self, config: dict) -> None:
        """
        Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.
        """
        if config:
            tag_order = config.get("tag_order", [])
            mode = config.get("mode", "DUPLICATE")
            if tag_order:
                # Apply grouping (db_service is already set in on_db_initialized)
                self.window.timeline.set_grouping_config(tag_order, mode)
                logger.info(
                    f"Auto-loaded grouping: {len(tag_order)} tags in {mode} mode"
                )
        else:
            logger.debug("No grouping configuration found")

    def on_configure_grouping_requested(self) -> None:
        """Opens grouping configuration dialog by requesting data from worker thread."""
        # Request data from worker thread (thread-safe)
        QMetaObject.invokeMethod(
            self.window.worker,
            "load_grouping_dialog_data",
            Qt.ConnectionType.QueuedConnection,
        )

    @Slot(list, object)
    def on_grouping_dialog_data_loaded(
        self, tags_data: list, current_config: dict
    ) -> None:
        """
        Handler for grouping dialog data loaded from worker.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.
        """
        from src.gui.dialogs.grouping_config_dialog import GroupingConfigDialog

        try:
            # Create dialog with pre-loaded data
            dialog = GroupingConfigDialog(
                tags_data,
                current_config,
                self.window.command_coordinator,
                self.window,
            )
            dialog.grouping_applied.connect(self.on_grouping_applied)
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to open grouping dialog: {e}")
            self.window.show_error_message(f"Failed to open grouping dialog: {e}")

    @Slot(list, str)
    def on_grouping_applied(self, tag_order: list, mode: str) -> None:
        """
        Handle grouping applied from dialog.

        Args:
            tag_order: List of tag names in order.
            mode: Grouping mode (DUPLICATE or FIRST_MATCH).
        """
        # Update timeline view
        self.window.timeline.set_grouping_config(tag_order, mode)
        logger.info(f"Grouping applied: {len(tag_order)} tags in {mode} mode")

    def on_clear_grouping_requested(self) -> None:
        """Clears timeline grouping."""
        cmd = ClearTimelineGroupingCommand()
        self.window.command_requested.emit(cmd)
        # Also clear UI
        self.window.timeline.clear_grouping()
        logger.info("Timeline grouping cleared")

    @Slot(str)
    def on_tag_color_change_requested(self, tag_name: str) -> None:
        """
        Handle tag color change from band context menu.

        Args:
            tag_name: The name of the tag to change color for.
        """
        color = QColorDialog.getColor()
        if color.isValid():
            cmd = UpdateTagColorCommand(tag_name, color.name())
            self.window.command_requested.emit(cmd)
            logger.debug(f"Tag color changed: {tag_name} -> {color.name()}")

    @Slot(str)
    def on_remove_from_grouping_requested(self, tag_name: str) -> None:
        """
        Remove a tag from current grouping.

        Args:
            tag_name: The name of the tag to remove.
        """
        # Get current config from GUI thread's db_service (thread-safe)
        current_config = self.window.gui_db_service.get_timeline_grouping_config()
        if current_config:
            tag_order = current_config["tag_order"]
            if tag_name in tag_order:
                tag_order.remove(tag_name)
                cmd = SetTimelineGroupingCommand(tag_order, current_config["mode"])
                self.window.command_requested.emit(cmd)
                self.window.timeline.set_grouping_config(tag_order, current_config["mode"])
                logger.info(f"Removed '{tag_name}' from grouping")
