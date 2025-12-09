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

    def execute(self, db_service: DatabaseService) -> bool:
        """
        Executes the update.
        1. Fetches existing event.
        2. Snapshots it.
        3. Applies updates from dictionary.
        4. Saves.

        Returns:
            bool: True if successful, False if event not found or error.
        """
        # 1. Snapshot current state from DB
        current = db_service.get_event(self.event_id)
        if not current:
            logger.warning(f"Cannot update event {self.event_id}: Not found")
            return False

        self._previous_event = current

        # 2. Apply Updates
        # We manually update fields available in the dict.
        # This acts as validation/mapping layer too.
        try:
            # Create a copy or modify the object?
            # It's safer to rely on dataclass helper or manual set
            # Since Event is a dataclass, we can't just obj.__dict__.update safely if we want strictness,
            # but for now we iterate keys.
            import dataclasses

            # Create a mutable copy effectively by replacing fields
            # Note: dataclasses.replace returns a NEW object
            # Filter update_data to only known fields to avoid errors?
            # Or assume UI sends correct keys. Let's filter for safety.
            valid_fields = {f.name for f in dataclasses.fields(Event)}
            clean_data = {
                k: v for k, v in self.update_data.items() if k in valid_fields
            }

            self._new_event = dataclasses.replace(current, **clean_data)
            self._new_event.modified_at = __import__("time").time()

            logger.info(f"Executing UpdateEvent: {self._new_event.name}")
            db_service.insert_event(self._new_event)
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
