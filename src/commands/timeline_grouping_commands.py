"""
Timeline Grouping Commands Module.

Provides command classes for managing timeline grouping configurations:
- SetTimelineGroupingCommand: Set or update tag order and mode
- ClearTimelineGroupingCommand: Clear grouping configuration
- UpdateTagColorCommand: Update tag color with undo/redo support

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
from typing import List

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class SetTimelineGroupingCommand(BaseCommand):
    """
    Command to set or update timeline grouping configuration.
    """

    def __init__(self, tag_order: List[str], mode: str = "DUPLICATE"):
        """
        Initializes the SetTimelineGroupingCommand.

        Args:
            tag_order: List of tag names defining groups and their order.
            mode: Grouping mode - "DUPLICATE" (default) or "FIRST_MATCH".
        """
        super().__init__()
        self.tag_order = tag_order
        self.mode = mode
        self._previous_config = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to set timeline grouping configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Validate mode
            if self.mode not in ("DUPLICATE", "FIRST_MATCH"):
                return CommandResult(
                    success=False,
                    message=f"Invalid mode: {self.mode}. Must be DUPLICATE or FIRST_MATCH",
                    command_name="SetTimelineGroupingCommand",
                )

            # Save previous configuration for undo
            self._previous_config = db_service.get_timeline_grouping_config()

            # Set new configuration
            db_service.set_timeline_grouping_config(
                tag_order=self.tag_order, mode=self.mode
            )

            self._is_executed = True
            logger.info(
                f"Set timeline grouping: {len(self.tag_order)} tags, mode={self.mode}"
            )

            return CommandResult(
                success=True,
                message=f"Timeline grouping set with {len(self.tag_order)} tags",
                command_name="SetTimelineGroupingCommand",
                data={"tag_order": self.tag_order, "mode": self.mode},
            )
        except Exception as e:
            logger.error(f"Failed to set timeline grouping: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to set timeline grouping: {e}",
                command_name="SetTimelineGroupingCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts timeline grouping configuration to previous state.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        logger.info("Undoing SetTimelineGroupingCommand")

        if self._previous_config:
            # Restore previous configuration
            db_service.set_timeline_grouping_config(
                tag_order=self._previous_config["tag_order"],
                mode=self._previous_config["mode"],
            )
        else:
            # Clear configuration if there was none before
            db_service.clear_timeline_grouping_config()

        self._is_executed = False


class ClearTimelineGroupingCommand(BaseCommand):
    """
    Command to clear timeline grouping configuration.
    """

    def __init__(self):
        """
        Initializes the ClearTimelineGroupingCommand.
        """
        super().__init__()
        self._previous_config = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to clear timeline grouping configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Save previous configuration for undo
            self._previous_config = db_service.get_timeline_grouping_config()

            # Clear configuration
            db_service.clear_timeline_grouping_config()

            self._is_executed = True
            logger.info("Cleared timeline grouping configuration")

            return CommandResult(
                success=True,
                message="Timeline grouping cleared",
                command_name="ClearTimelineGroupingCommand",
            )
        except Exception as e:
            logger.error(f"Failed to clear timeline grouping: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to clear timeline grouping: {e}",
                command_name="ClearTimelineGroupingCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts clearing by restoring previous configuration.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        logger.info("Undoing ClearTimelineGroupingCommand")

        if self._previous_config:
            # Restore previous configuration
            db_service.set_timeline_grouping_config(
                tag_order=self._previous_config["tag_order"],
                mode=self._previous_config["mode"],
            )

        self._is_executed = False


class UpdateTagColorCommand(BaseCommand):
    """
    Command to update a tag's color.
    """

    def __init__(self, tag_name: str, color: str):
        """
        Initializes the UpdateTagColorCommand.

        Args:
            tag_name: The name of the tag to update.
            color: Hex color string (e.g., "#FF0000").
        """
        super().__init__()
        self.tag_name = tag_name
        self.color = color
        self._previous_color = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to update tag color.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            # Get or create tag and save previous color
            tag = db_service.get_tag_by_name(self.tag_name)
            if tag:
                self._previous_color = tag.get("color")
            else:
                # Create tag if it doesn't exist
                db_service.create_tag(self.tag_name)
                self._previous_color = None

            # Set new color (this validates the format)
            db_service.set_tag_color(self.tag_name, self.color)

            self._is_executed = True
            logger.info(f"Updated color for tag '{self.tag_name}' to {self.color}")

            return CommandResult(
                success=True,
                message=f"Tag color updated to {self.color}",
                command_name="UpdateTagColorCommand",
                data={"tag_name": self.tag_name, "color": self.color},
            )
        except ValueError as e:
            # Color validation failed
            logger.error(f"Invalid color format: {e}")
            return CommandResult(
                success=False,
                message=f"Invalid color format: {e}",
                command_name="UpdateTagColorCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update tag color: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update tag color: {e}",
                command_name="UpdateTagColorCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts tag color to previous value.

        Args:
            db_service: The database service to operate on.
        """
        if not self._is_executed:
            return

        logger.info(f"Undoing UpdateTagColorCommand for tag '{self.tag_name}'")

        if self._previous_color:
            # Restore previous color
            db_service.set_tag_color(self.tag_name, self._previous_color)
        else:
            # Clear color by setting to None (using SQL directly)
            if db_service._connection:
                cursor = db_service._connection.execute(
                    "SELECT id FROM tags WHERE name = ?", (self.tag_name.strip(),)
                )
                result = cursor.fetchone()
                if result:
                    with db_service.transaction() as conn:
                        conn.execute(
                            "UPDATE tags SET color = NULL WHERE id = ?",
                            (result["id"],),
                        )

        self._is_executed = False
