from src.commands.base_command import BaseCommand
from src.core.events import Event
from src.services.db_service import DatabaseService
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CreateEventCommand(BaseCommand):
    """
    Command to create a new event.
    """

    def __init__(self, event: Event):
        super().__init__()
        self.event = event
        self._previous_state = None  # Not needed for creation, but good practice

    def execute(self, db_service: DatabaseService) -> bool:
        """
        Executes the command to insert the event into the database.

        Returns:
            bool: True if successful, False if an error occurred.
        """
        try:
            logger.info(f"Executing CreateEvent: {self.event.name}")
            db_service.insert_event(self.event)
            self._is_executed = True
            return True
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return False

    def undo(self, db_service: DatabaseService) -> None:
        if not self._is_executed:
            return

        logger.info(f"Undoing CreateEvent: {self.event.name}")
        db_service.delete_event(self.event.id)
        self._is_executed = False


class UpdateEventCommand(BaseCommand):
    """
    Command to update an existing event.
    Snapshots the clean state before update for undo.
    """

    def __init__(self, event: Event):
        """
        Initializes the Update command.

        Args:
            event (Event): The event object with updated values (but same ID).
        """
        super().__init__()
        self.new_event = event
        self._previous_event: Optional[Event] = None

    def execute(self, db_service: DatabaseService) -> bool:
        """
        Executes the update. Validates that the event exists first.

        Returns:
            bool: True if successful, False if event not found or error.
        """
        # 1. Snapshot current state from DB
        current = db_service.get_event(self.new_event.id)
        if not current:
            logger.warning(f"Cannot update event {self.new_event.id}: Not found")
            return False

        self._previous_event = current

        # 2. Apply Update
        try:
            logger.info(f"Executing UpdateEvent: {self.new_event.name}")
            db_service.insert_event(self.new_event)  # insert_event is an upsert
            self._is_executed = True
            return True
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return False

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

    def execute(self, db_service: DatabaseService) -> bool:
        """
        Executes the command to delete the event.

        Saves the current state of the event for undo purposes.

        Returns:
            bool: True if successful, False if event not found or error.
        """
        # Backup before delete
        self._backup_event = db_service.get_event(self.event_id)
        if not self._backup_event:
            logger.warning(f"Cannot delete event {self.event_id}: Not found")
            return False

        try:
            db_service.delete_event(self.event_id)
            self._is_executed = True
            return True
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    def undo(self, db_service: DatabaseService) -> None:
        if self._is_executed and self._backup_event:
            logger.info(f"Undoing DeleteEvent: Restoring {self._backup_event.name}")
            db_service.insert_event(self._backup_event)
            self._is_executed = False
