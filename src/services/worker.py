"""
Database Worker Module.
Handles asynchronous database operations to keep the UI responsive.
"""

import logging
import traceback
from PySide6.QtCore import QObject, Signal, Slot
from src.services.db_service import DatabaseService
from src.commands.base_command import BaseCommand, CommandResult


logger = logging.getLogger(__name__)


class DatabaseWorker(QObject):
    """
    Worker object that executes database operations in a separate thread.
    Owns the DatabaseService instance to ensure thread affinity.
    """

    # Signals
    initialized = Signal(bool)  # Success/Fail
    events_loaded = Signal(list)  # List[Event]
    entities_loaded = Signal(list)  # List[Entity]

    # Details signals
    event_details_loaded = Signal(object, list, list)  # Event, relations, incoming
    entity_details_loaded = Signal(object, list, list)  # Entity, relations, incoming

    command_finished = Signal(object)  # CommandResult object
    error_occurred = Signal(str)

    # Status signals for UI feedback
    operation_started = Signal(str)
    operation_finished = Signal(str)

    def __init__(self, db_path: str = "world.kraken"):
        """
        Initializes the worker.

        Args:
            db_path (str): Path to the database file.
        """
        super().__init__()
        self.db_path = db_path
        self.db_service = None

    @Slot()
    def initialize_db(self):
        """Initializes the database connection."""
        try:
            self.operation_started.emit("Connecting to Database...")
            self.db_service = DatabaseService(self.db_path)
            self.db_service.connect()
            logger.info("DatabaseWorker initialized successfully.")
            self.initialized.emit(True)
            self.operation_finished.emit("Database Connected.")
        except Exception:
            logger.critical(f"DatabaseWorker init failed: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to connect to database.")
            self.initialized.emit(False)

    @Slot()
    def load_events(self):
        """Loads all events."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading Events...")
            events = self.db_service.get_all_events()
            self.events_loaded.emit(events)
            self.operation_finished.emit("Events Loaded.")
        except Exception:
            logger.error(f"Failed to load events: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load events.")

    @Slot()
    def load_entities(self):
        """Loads all entities."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading Entities...")
            entities = self.db_service.get_all_entities()
            self.entities_loaded.emit(entities)
            self.operation_finished.emit("Entities Loaded.")
        except Exception:
            logger.error(f"Failed to load entities: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load entities.")

    @Slot(str)
    def load_event_details(self, event_id: str):
        """Loads event details and sends them back."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit(f"Loading Event {event_id}...")
            event = self.db_service.get_event(event_id)
            if event:
                rels = self.db_service.get_relations(event_id)
                incoming = self.db_service.get_incoming_relations(event_id)
                self.event_details_loaded.emit(event, rels, incoming)
            self.operation_finished.emit("Event Details Loaded.")
        except Exception:
            logger.error(f"Failed to load event details: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load event {event_id}")

    @Slot(str)
    def load_entity_details(self, entity_id: str):
        """Loads entity details and sends them back."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit(f"Loading Entity {entity_id}...")
            entity = self.db_service.get_entity(entity_id)
            if entity:
                rels = self.db_service.get_relations(entity_id)
                incoming = self.db_service.get_incoming_relations(entity_id)
                self.entity_details_loaded.emit(entity, rels, incoming)
            self.operation_finished.emit("Entity Details Loaded.")
        except Exception:
            logger.error(f"Failed to load entity details: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load entity {entity_id}")

    @Slot(
        object, object
    )  # Command, Optional[args] - simplified mainly for command objects
    def run_command(self, command: BaseCommand):
        """
        Executes a command object.
        IMPORTANT: The command must NOT already have the db_service injected.
        We inject the worker's thread-local service here.
        """
        if not self.db_service:
            cmd_name = command.__class__.__name__
            logger.error(f"Database not ready when executing {cmd_name}")
            self.error_occurred.emit(f"Database not ready for {cmd_name}.")
            return

        command_name = command.__class__.__name__
        try:
            self.operation_started.emit(f"Executing {command_name}...")

            # Execute with the local service
            result = command.execute(self.db_service)

            # Normalize result to CommandResult
            if isinstance(result, bool):
                success = result
                msg = f"{command_name} {'succeeded' if success else 'failed'}"
                result_obj = CommandResult(
                    success=success, message=msg, command_name=command_name
                )
            elif isinstance(result, CommandResult):
                result_obj = result
                # Ensure command_name is set if missing
                if not result_obj.command_name:
                    result_obj.command_name = command_name
            else:
                # Unexpected return type
                logger.warning(
                    f"Command {command_name} returned unexpected type: {type(result)}"
                )
                result_obj = CommandResult(
                    success=False,
                    message="Internal Error: Invalid command result",
                    command_name=command_name,
                )

            self.command_finished.emit(result_obj)
            self.operation_finished.emit(f"Finished {command_name}.")

        except Exception:
            logger.error(f"Command {command_name} failed: {traceback.format_exc()}")
            self.error_occurred.emit(f"Command {command_name} failed.")
            # Emit failure result
            fail_res = CommandResult(
                success=False,
                message="An unexpected error occurred during execution.",
                command_name=command_name,
            )
            self.command_finished.emit(fail_res)
