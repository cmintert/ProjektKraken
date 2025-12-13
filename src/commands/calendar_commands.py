"""
Calendar Commands Module.

Implements the Command pattern for calendar configuration operations.
All commands support undo/redo functionality.

Classes:
    CreateCalendarConfigCommand: Creates a new calendar configuration.
    UpdateCalendarConfigCommand: Updates an existing calendar configuration.
    DeleteCalendarConfigCommand: Deletes a calendar configuration.
    SetActiveCalendarCommand: Sets a calendar as the active one.
"""

from typing import Optional, Union
import logging

from src.commands.base_command import BaseCommand, CommandResult
from src.services.db_service import DatabaseService
from src.core.calendar import CalendarConfig

logger = logging.getLogger(__name__)


class CreateCalendarConfigCommand(BaseCommand):
    """
    Creates a new calendar configuration.

    Supports undo by deleting the created configuration.
    """

    def __init__(self, config: CalendarConfig):
        """
        Initializes the command.

        Args:
            config: The calendar configuration to create.
        """
        super().__init__()
        self._config = config

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Creates the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.
        """
        try:
            db_service.insert_calendar_config(self._config)
            self._is_executed = True
            logger.info(f"Created calendar config: {self._config.id}")
            return CommandResult(
                success=True,
                message=f"Created calendar '{self._config.name}'",
                data={"id": self._config.id},
                command_name="CreateCalendarConfigCommand",
            )
        except Exception as e:
            logger.error(f"Failed to create calendar config: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="CreateCalendarConfigCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undoes the creation by deleting the config.

        Args:
            db_service: The database service to use.
        """
        if self._is_executed:
            db_service.delete_calendar_config(self._config.id)
            self._is_executed = False
            logger.info(f"Undid creation of calendar config: {self._config.id}")


class UpdateCalendarConfigCommand(BaseCommand):
    """
    Updates an existing calendar configuration.

    Stores the original config for undo support.
    """

    def __init__(self, config: CalendarConfig):
        """
        Initializes the command.

        Args:
            config: The updated calendar configuration.
        """
        super().__init__()
        self._config = config
        self._original_config: Optional[CalendarConfig] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Updates the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.
        """
        try:
            # Store original for undo
            self._original_config = db_service.get_calendar_config(self._config.id)

            db_service.insert_calendar_config(self._config)
            self._is_executed = True
            logger.info(f"Updated calendar config: {self._config.id}")
            return CommandResult(
                success=True,
                message=f"Updated calendar '{self._config.name}'",
                data={"id": self._config.id},
                command_name="UpdateCalendarConfigCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update calendar config: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="UpdateCalendarConfigCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undoes the update by restoring the original config.

        Args:
            db_service: The database service to use.
        """
        if self._is_executed and self._original_config:
            db_service.insert_calendar_config(self._original_config)
            self._is_executed = False
            logger.info(f"Undid update of calendar config: {self._config.id}")


class DeleteCalendarConfigCommand(BaseCommand):
    """
    Deletes a calendar configuration.

    Stores the deleted config for undo support.
    """

    def __init__(self, config_id: str):
        """
        Initializes the command.

        Args:
            config_id: The ID of the calendar configuration to delete.
        """
        super().__init__()
        self._config_id = config_id
        self._deleted_config: Optional[CalendarConfig] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Deletes the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.
        """
        try:
            # Store for undo
            self._deleted_config = db_service.get_calendar_config(self._config_id)

            db_service.delete_calendar_config(self._config_id)
            self._is_executed = True
            logger.info(f"Deleted calendar config: {self._config_id}")
            return CommandResult(
                success=True,
                message="Deleted calendar configuration",
                data={"id": self._config_id},
                command_name="DeleteCalendarConfigCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete calendar config: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="DeleteCalendarConfigCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undoes the deletion by restoring the config.

        Args:
            db_service: The database service to use.
        """
        if self._is_executed and self._deleted_config:
            db_service.insert_calendar_config(self._deleted_config)
            self._is_executed = False
            logger.info(f"Undid deletion of calendar config: {self._config_id}")


class SetActiveCalendarCommand(BaseCommand):
    """
    Sets a calendar configuration as the active one.

    Stores the previously active config ID for undo support.
    """

    def __init__(self, config_id: str):
        """
        Initializes the command.

        Args:
            config_id: The ID of the calendar to set as active.
        """
        super().__init__()
        self._config_id = config_id
        self._previous_active_id: Optional[str] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Sets the calendar as active.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.
        """
        try:
            # Store previous active for undo
            previous = db_service.get_active_calendar_config()
            self._previous_active_id = previous.id if previous else None

            db_service.set_active_calendar_config(self._config_id)
            self._is_executed = True
            logger.info(f"Set active calendar config: {self._config_id}")
            return CommandResult(
                success=True,
                message="Set active calendar",
                data={"id": self._config_id},
                command_name="SetActiveCalendarCommand",
            )
        except Exception as e:
            logger.error(f"Failed to set active calendar: {e}")
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetActiveCalendarCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Undoes by restoring the previously active calendar.

        Args:
            db_service: The database service to use.
        """
        if self._is_executed and self._previous_active_id:
            db_service.set_active_calendar_config(self._previous_active_id)
            self._is_executed = False
            logger.info(f"Undid set active, restored: {self._previous_active_id}")
