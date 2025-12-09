from src.commands.base_command import BaseCommand, CommandResult
from src.core.events import Event
from src.services.db_service import DatabaseService
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CreateEventCommand(BaseCommand):
    """
    Command to create a new event.
    """

    def __init__(self, event_data: dict = None):
        super().__init__()
        if event_data:
            # We would need to ensure 'id' is generated if not provided,
            # likely the helper factories or Event post_init handles it.
            # Event dataclass auto-generates ID if missing.
            self.event = Event(**event_data)
        else:
            # Default Event
            self.event = Event(name="New Event", lore_date=0.0)

        self._previous_state = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to insert the event into the database.
        """
        try:
            logger.info(f"Executing CreateEvent: {self.event.name}")
            db_service.insert_event(self.event)
            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Event '{self.event.name}' created.",
                command_name="CreateEventCommand",
            )
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create event: {e}",
                command_name="CreateEventCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        if not self._is_executed:
            return

        logger.info(f"Undoing CreateEvent: {self.event.name}")
        db_service.delete_event(self.event.id)
        self._is_executed = False


class UpdateEventCommand(BaseCommand):
    """
    Command to update an existing event.
    Accepts a dictionary of changes to apply to the existing event.
    Snapshots the clean state before update for undo.
    """

    def __init__(self, event_id: str, update_data: dict):
        """
        Initializes the Update command.

        Args:
            event_id (str): The ID of the event to update.
            update_data (dict): Dictionary of fields to update.
        """
        super().__init__()
        self.event_id = event_id
        self.update_data = update_data
        self._previous_event: Optional[Event] = None
        self._new_event: Optional[Event] = None  # Store result for logs/UI

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the update.
        """
        # 1. Snapshot current state from DB
        current = db_service.get_event(self.event_id)
        if not current:
            return CommandResult(
                success=False,
                message=f"Cannot update event {self.event_id}: Not found",
                command_name="UpdateEventCommand",
            )

        self._previous_event = current

        # 2. Apply Updates
        try:
            # Validation
            if "name" in self.update_data:
                new_name = self.update_data["name"]
                if not new_name or not new_name.strip():
                    return CommandResult(
                        success=False,
                        message="Event name cannot be empty.",
                        command_name="UpdateEventCommand",
                    )

            import dataclasses

            valid_fields = {f.name for f in dataclasses.fields(Event)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_event = dataclasses.replace(current, **clean_data)
            self._new_event.modified_at = __import__("time").time()

            logger.info(f"Executing UpdateEvent: {self._new_event.name}")
            db_service.insert_event(self._new_event)
            self._is_executed = True

            return CommandResult(
                success=True,
                message="Event updated successfully.",
                command_name="UpdateEventCommand",
            )
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to update event: {e}",
                command_name="UpdateEventCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the update by restoring the previous state of the event.
        """
        if self._is_executed and self._previous_event:
            logger.info(
                f"Undoing UpdateEvent: Reverting to {self._previous_event.name}"
            )
            db_service.insert_event(self._previous_event)
            self._is_executed = False


class DeleteEventCommand(BaseCommand):
    """
    Command to delete an event, storing its state for undo.
    """

    def __init__(self, event_id: str):
        super().__init__()
        self.event_id = event_id
        self._backup_event: Optional[Event] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to delete the event.
        """
        # Backup before delete
        self._backup_event = db_service.get_event(self.event_id)
        if not self._backup_event:
            logger.warning(f"Cannot delete event {self.event_id}: Not found")
            return CommandResult(
                success=False,
                message=f"Cannot delete event {self.event_id}: Not found",
                command_name="DeleteEventCommand",
            )

        try:
            db_service.delete_event(self.event_id)
            self._is_executed = True
            return CommandResult(
                success=True,
                message="Event deleted.",
                command_name="DeleteEventCommand",
            )
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to delete event: {e}",
                command_name="DeleteEventCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        if self._is_executed and self._backup_event:
            logger.info(f"Undoing DeleteEvent: Restoring {self._backup_event.name}")
            db_service.insert_event(self._backup_event)
            self._is_executed = False
