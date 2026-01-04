"""
Event Commands Module.

Provides command classes for managing events in the timeline:
- CreateEventCommand: Create new events with default or custom data
- UpdateEventCommand: Modify existing events with validation
- DeleteEventCommand: Remove events with backup for undo

All commands support undo/redo operations and return CommandResult objects.
"""

import logging
from typing import Optional

from src.commands.base_command import BaseCommand, CommandResult
from src.core.events import Event
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class CreateEventCommand(BaseCommand):
    """
    Command to create a new event.
    """

    def __init__(self, event_data: Optional[dict] = None) -> None:
        """
        Initializes the CreateEventCommand.

        Args:
            event_data (dict, optional): Dictionary containing event data.
                                         If None, default values are used.
        """
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

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or failure.
        """
        try:
            logger.info(f"Executing CreateEvent: {self.event.name}")
            db_service.insert_event(self.event)

            # Sync tags to normalized tables
            tags = self.event.tags
            if tags:
                for tag_name in tags:
                    try:
                        db_service.assign_tag_to_event(self.event.id, tag_name)
                    except Exception as e:
                        logger.warning(f"Failed to assign tag '{tag_name}': {e}")

            self._is_executed = True
            return CommandResult(
                success=True,
                message=f"Event '{self.event.name}' created.",
                command_name="CreateEventCommand",
                data={"id": self.event.id},
            )
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return CommandResult(
                success=False,
                message=f"Failed to create event: {e}",
                command_name="CreateEventCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """
        Reverts the event creation by deleting it from the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
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

    def __init__(self, event_id: str, update_data: dict) -> None:
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

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object containing success status and messages.
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

            # Sync tags to normalized tables
            # First, get current normalized tags
            current_tags = set(
                t["name"] for t in db_service.get_tags_for_event(self.event_id)
            )
            # Get new tags from event
            new_tags = set(self._new_event.tags)

            # Remove tags that are no longer present
            for tag_name in current_tags - new_tags:
                try:
                    db_service.remove_tag_from_event(self.event_id, tag_name)
                except Exception as e:
                    logger.warning(f"Failed to remove tag '{tag_name}': {e}")

            # Add new tags
            for tag_name in new_tags - current_tags:
                try:
                    db_service.assign_tag_to_event(self.event_id, tag_name)
                except Exception as e:
                    logger.warning(f"Failed to assign tag '{tag_name}': {e}")

            self._is_executed = True

            return CommandResult(
                success=True,
                message="Event updated successfully.",
                command_name="UpdateEventCommand",
                data={
                    "id": self._new_event.id,
                    "name": self._new_event.name,
                    "type": "event",
                    "icon": self._new_event.attributes.get("icon"),
                    "color": self._new_event.attributes.get("color"),
                },
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

    def __init__(self, event_id: str) -> None:
        """
        Initializes the DeleteEventCommand.

        Args:
            event_id (str): The ID of the event to delete.
        """
        super().__init__()
        self.event_id = event_id
        self._backup_event: Optional[Event] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """
        Executes the command to delete the event.

        Args:
            db_service (DatabaseService): The database service to use.

        Returns:
            CommandResult: Result object indicating success or fail (e.g. not found).
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
        """
        Reverts the event deletion by restoring it to the database.

        Args:
            db_service (DatabaseService): The database service to operate on.
        """
        if self._is_executed and self._backup_event:
            logger.info(f"Undoing DeleteEvent: Restoring {self._backup_event.name}")
            db_service.insert_event(self._backup_event)
            self._is_executed = False
