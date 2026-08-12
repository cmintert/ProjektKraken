"""TimelineGroupingManager - Handles timeline grouping operations for MainWindow.

This module contains all timeline grouping-related functionality extracted from
MainWindow to reduce its size and improve maintainability.
"""

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QColorDialog

from src.app.qt_invocation import invoke_queued
from src.commands.timeline_grouping_commands import (
    ClearTimelineGroupingCommand,
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)
from src.core.logging_config import get_logger

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = get_logger(__name__)


class TimelineGroupingManager(QObject):
    """Manages timeline grouping operations for the MainWindow.

    This class encapsulates all functionality related to:
    - Loading and applying timeline grouping configurations
    - Opening and handling the grouping configuration dialog
    - Updating tag colors
    - Adding/removing tags from grouping
    - Clearing grouping configuration
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the TimelineGroupingManager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        super().__init__()
        self.window = main_window
        self._current_config: dict[str, Any] | None = None
        self._tag_colors: dict[str, str] = {}

    @property
    def current_config(self) -> dict[str, Any] | None:
        """Return a defensive copy of the cached grouping configuration."""
        return dict(self._current_config) if self._current_config else None

    @property
    def tag_colors(self) -> dict[str, str]:
        """Return a defensive copy of worker-loaded tag colors."""
        return dict(self._tag_colors)

    def color_for_tag(self, tag_name: str) -> str | None:
        """Return the cached display color for a grouping tag."""
        return self._tag_colors.get(tag_name)

    def request_grouping_config(self) -> None:
        """Requests loading of the timeline grouping configuration."""
        self.window.worker_manager.load_timeline_grouping_requested.emit()

    @Slot(object)
    def on_grouping_snapshot_loaded(self, payload: object) -> None:
        """Cache and apply grouping configuration loaded by the DB worker."""
        if not isinstance(payload, dict):
            self._current_config = None
            self._tag_colors = {}
            self.on_grouping_config_loaded(None)
            return
        config = payload.get("config")
        colors = payload.get("colors", {})
        self._tag_colors = (
            {str(key): str(value) for key, value in colors.items()}
            if isinstance(colors, dict)
            else {}
        )
        typed_config = config if isinstance(config, dict) else None
        self.on_grouping_config_loaded(typed_config)

    def on_grouping_config_loaded(self, config: dict[str, Any] | None) -> None:
        """Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.

        """
        self._current_config = dict(config) if config else None
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
        invoke_queued(
            self.window.worker,
            "load_grouping_dialog_data",
        )

    @Slot(list, object)
    def on_grouping_dialog_data_loaded(
        self, tags_data: list, current_config: dict[str, Any] | None
    ) -> None:
        """Handler for grouping dialog data loaded from worker.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.

        """
        from src.gui.dialogs.grouping_config_dialog import GroupingConfigDialog

        try:
            self._tag_colors.update(
                {
                    str(tag["name"]): str(tag["color"])
                    for tag in tags_data
                    if isinstance(tag, dict) and tag.get("name") and tag.get("color")
                }
            )
            # Create dialog with pre-loaded data
            command_coordinator = getattr(self.window, "command_coordinator")
            dialog = GroupingConfigDialog(
                tags_data,
                current_config,
                command_coordinator,
                self.window,
            )
            dialog.grouping_applied.connect(self.on_grouping_applied)
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to open grouping dialog: {e}")
            self.window.show_error_message(f"Failed to open grouping dialog: {e}")

    @Slot(list, str)
    def on_grouping_applied(self, tag_order: list, mode: str) -> None:
        """Handle grouping applied from dialog.

        Args:
            tag_order: List of tag names in order.
            mode: Grouping mode (DUPLICATE or FIRST_MATCH).

        """
        self._current_config = {"tag_order": list(tag_order), "mode": mode}
        self.window.timeline.set_grouping_config(tag_order, mode)
        logger.info(f"Grouping applied: {len(tag_order)} tags in {mode} mode")

    def on_clear_grouping_requested(self) -> None:
        """Clears timeline grouping."""
        cmd = ClearTimelineGroupingCommand()
        self.window.command_requested.emit(cmd)
        self._current_config = None
        self._tag_colors = {}
        # Also clear UI
        self.window.timeline.clear_grouping()
        logger.info("Timeline grouping cleared")

    @Slot(str)
    def on_tag_color_change_requested(self, tag_name: str) -> None:
        """Handle tag color change from band context menu.

        Args:
            tag_name: The name of the tag to change color for.

        """
        color = QColorDialog.getColor()
        if color.isValid():
            color_name = color.name()
            cmd = UpdateTagColorCommand(tag_name, color_name)
            self.window.command_requested.emit(cmd)
            self._tag_colors[tag_name] = color_name
            logger.debug(f"Tag color changed: {tag_name} -> {color_name}")

    @Slot(str)
    def on_remove_from_grouping_requested(self, tag_name: str) -> None:
        """Remove a tag from current grouping.

        Args:
            tag_name: The name of the tag to remove.

        """
        current_config = self.current_config
        if current_config:
            tag_order = list(current_config["tag_order"])
            if tag_name in tag_order:
                tag_order.remove(tag_name)
                cmd = SetTimelineGroupingCommand(tag_order, current_config["mode"])
                self.window.command_requested.emit(cmd)
                self._current_config = {
                    "tag_order": tag_order,
                    "mode": current_config["mode"],
                }
                self.window.timeline.set_grouping_config(
                    tag_order, current_config["mode"]
                )
                logger.info(f"Removed '{tag_name}' from grouping")
