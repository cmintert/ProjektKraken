"""Calendar Commands Module.

Implements the Command pattern for calendar configuration operations.
All commands support undo/redo functionality.

Classes:
    CreateCalendarConfigCommand: Creates a new calendar configuration.
    UpdateCalendarConfigCommand: Updates an existing calendar configuration.
    DeleteCalendarConfigCommand: Deletes a calendar configuration.
    SetActiveCalendarCommand: Sets a calendar as the active one.
"""

import logging
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.calendar import CalendarConfig
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class CreateCalendarConfigCommand(BaseCommand):
    """Creates a new calendar configuration.

    Supports undo by deleting the created configuration.
    """

    def __init__(self, config: CalendarConfig) -> None:
        """Initializes the command.

        Args:
            config: The calendar configuration to create.

        """
        super().__init__()
        self._config = config
        self._recorded_history = False
        self._previous_active_id: str | None = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Creates the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.

        """
        try:
            if self._config.is_active or self._recorded_history:
                from src.services.event_timing.guards import require_world_plan

                rejected = require_world_plan(
                    db_service,
                    {"kind": "config", "id": self._config.id, "config": None}
                    if self._recorded_history
                    else None,
                )
                if rejected is not None:
                    return rejected
            previous = db_service.get_active_calendar_config()
            self._previous_active_id = previous.id if previous else None
            db_service.insert_calendar_config(self._config)
            self._is_executed = True
            self._recorded_history = True
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
        """Undoes the creation by deleting the config.

        Args:
            db_service: The database service to use.

        """
        if self._is_executed:
            db_service.delete_calendar_config(self._config.id)
            if self._config.is_active and self._previous_active_id:
                db_service.set_active_calendar_config(self._previous_active_id)
            self._is_executed = False
            logger.info(f"Undid creation of calendar config: {self._config.id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            dict: Command data for persistence.

        """
        return {
            "config": self._config.to_dict(),
            "is_executed": self._is_executed,
            "recorded_history": self._recorded_history,
            "previous_active_id": self._previous_active_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreateCalendarConfigCommand":
        """Deserialize command from dictionary.

        Args:
            data: Command data from persistence.

        Returns:
            CreateCalendarConfigCommand: Reconstructed command.

        """
        config = CalendarConfig.from_dict(data["config"])
        cmd = cls(config)
        cmd._is_executed = data.get("is_executed", False)
        cmd._recorded_history = data.get("recorded_history", cmd._is_executed)
        cmd._previous_active_id = data.get("previous_active_id")
        return cmd


class UpdateCalendarConfigCommand(BaseCommand):
    """Updates an existing calendar configuration.

    Stores the original config for undo support.
    """

    def __init__(self, config: CalendarConfig) -> None:
        """Initializes the command.

        Args:
            config: The updated calendar configuration.

        """
        super().__init__()
        self._config = config
        self._original_config: Optional[CalendarConfig] = None
        self._recorded_history = False
        self._previous_active_id: str | None = None
        self._has_active_snapshot = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Updates the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.

        """
        try:
            from src.services.event_timing.guards import require_world_plan

            recorded = (
                {
                    "kind": "config",
                    "id": self._config.id,
                    "config": self._original_config.to_dict()
                    if self._original_config
                    else None,
                }
                if self._recorded_history
                else None
            )
            rejected = require_world_plan(db_service, recorded)
            if rejected is not None:
                return rejected
            # Store original for undo
            self._original_config = db_service.get_calendar_config(self._config.id)
            active = db_service.get_active_calendar_config()
            self._previous_active_id = active.id if active else None
            self._has_active_snapshot = True

            db_service.insert_calendar_config(self._config)
            self._is_executed = True
            self._recorded_history = True
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
        """Undoes the update by restoring the original config.

        Args:
            db_service: The database service to use.

        """
        if self._is_executed and self._original_config:
            db_service.insert_calendar_config(self._original_config)
            if self._has_active_snapshot:
                if self._previous_active_id:
                    db_service.set_active_calendar_config(self._previous_active_id)
                else:
                    db_service._calendar_repo.clear_active()
            self._is_executed = False
            logger.info(f"Undid update of calendar config: {self._config.id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            dict: Command data for persistence.

        """
        result = {
            "config": self._config.to_dict(),
            "is_executed": self._is_executed,
        }
        if self._original_config:
            result["original_config"] = self._original_config.to_dict()
        if self._has_active_snapshot:
            result["previous_active_id"] = self._previous_active_id
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateCalendarConfigCommand":
        """Deserialize command from dictionary.

        Args:
            data: Command data from persistence.

        Returns:
            UpdateCalendarConfigCommand: Reconstructed command.

        """
        config = CalendarConfig.from_dict(data["config"])
        cmd = cls(config)
        cmd._is_executed = data.get("is_executed", False)
        if "original_config" in data:
            cmd._original_config = CalendarConfig.from_dict(data["original_config"])
            cmd._recorded_history = True
        cmd._has_active_snapshot = "previous_active_id" in data
        cmd._previous_active_id = data.get("previous_active_id")
        return cmd


class DeleteCalendarConfigCommand(BaseCommand):
    """Deletes a calendar configuration.

    Stores the deleted config for undo support.
    """

    def __init__(self, config_id: str) -> None:
        """Initializes the command.

        Args:
            config_id: The ID of the calendar configuration to delete.

        """
        super().__init__()
        self._config_id = config_id
        self._deleted_config: Optional[CalendarConfig] = None
        self._recorded_history = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Deletes the calendar configuration.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.

        """
        try:
            from src.services.event_timing.guards import require_world_plan

            recorded = (
                {
                    "kind": "config",
                    "id": self._config_id,
                    "config": self._deleted_config.to_dict()
                    if self._deleted_config
                    else None,
                }
                if self._recorded_history
                else None
            )
            rejected = require_world_plan(db_service, recorded)
            if rejected is not None:
                return rejected
            # Store for undo
            self._deleted_config = db_service.get_calendar_config(self._config_id)

            db_service.delete_calendar_config(self._config_id)
            self._is_executed = True
            self._recorded_history = True
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
        """Undoes the deletion by restoring the config.

        Args:
            db_service: The database service to use.

        """
        if self._is_executed and self._deleted_config:
            db_service.insert_calendar_config(self._deleted_config)
            self._is_executed = False
            logger.info(f"Undid deletion of calendar config: {self._config_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            dict: Command data for persistence.

        """
        result = {
            "config_id": self._config_id,
            "is_executed": self._is_executed,
        }
        if self._deleted_config:
            result["deleted_config"] = self._deleted_config.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "DeleteCalendarConfigCommand":
        """Deserialize command from dictionary.

        Args:
            data: Command data from persistence.

        Returns:
            DeleteCalendarConfigCommand: Reconstructed command.

        """
        cmd = cls(data["config_id"])
        cmd._is_executed = data.get("is_executed", False)
        if "deleted_config" in data:
            cmd._deleted_config = CalendarConfig.from_dict(data["deleted_config"])
            cmd._recorded_history = True
        return cmd


class SetActiveCalendarCommand(BaseCommand):
    """Sets a calendar configuration as the active one.

    Stores the previously active config ID for undo support.
    """

    def __init__(self, config_id: str) -> None:
        """Initializes the command.

        Args:
            config_id: The ID of the calendar to set as active.

        """
        super().__init__()
        self._config_id = config_id
        self._previous_active_id: Optional[str] = None
        self._recorded_history = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Sets the calendar as active.

        Args:
            db_service: The database service to use.

        Returns:
            CommandResult: Success result with config ID in data.

        """
        try:
            from src.services.event_timing.guards import require_world_plan

            recorded = (
                {"kind": "active", "id": self._previous_active_id}
                if self._recorded_history
                else None
            )
            rejected = require_world_plan(db_service, recorded)
            if rejected is not None:
                return rejected
            # Store previous active for undo
            previous = db_service.get_active_calendar_config()
            self._previous_active_id = previous.id if previous else None
            if db_service.get_calendar_config(self._config_id) is None:
                raise ValueError("The selected calendar is unavailable")

            db_service.set_active_calendar_config(self._config_id)
            self._is_executed = True
            self._recorded_history = True
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
        """Undoes by restoring the previously active calendar.

        Args:
            db_service: The database service to use.

        """
        if self._is_executed:
            from src.services.repositories.calendar_repository import CalendarRepository

            if self._previous_active_id is not None:
                db_service.set_active_calendar_config(self._previous_active_id)
            else:
                CalendarRepository(db_service.get_connection()).clear_active()
            self._is_executed = False
            logger.info(f"Undid set active, restored: {self._previous_active_id}")

    def to_dict(self) -> dict:
        """Serialize command to dictionary.

        Returns:
            dict: Command data for persistence.

        """
        return {
            "config_id": self._config_id,
            "previous_active_id": self._previous_active_id,
            "is_executed": self._is_executed,
            "recorded_history": self._recorded_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SetActiveCalendarCommand":
        """Deserialize command from dictionary.

        Args:
            data: Command data from persistence.

        Returns:
            SetActiveCalendarCommand: Reconstructed command.

        """
        cmd = cls(data["config_id"])
        cmd._is_executed = data.get("is_executed", False)
        cmd._previous_active_id = data.get("previous_active_id")
        cmd._recorded_history = data.get(
            "recorded_history", cmd._is_executed or cmd._previous_active_id is not None
        )
        return cmd
