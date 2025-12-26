"""
Database Worker Module.
Handles asynchronous database operations to keep the UI responsive.
"""

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from src.commands.base_command import BaseCommand, CommandResult
from src.services import longform_builder
from src.services.asset_store import AssetStore
from src.services.attachment_service import AttachmentService
from src.services.db_service import DatabaseService

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
    maps_loaded = Signal(list)  # List[Map]
    markers_loaded = Signal(str, list)  # map_id, List[Marker]
    longform_sequence_loaded = Signal(list)  # List[dict]
    calendar_config_loaded = Signal(object)  # CalendarConfig or None
    current_time_loaded = Signal(float)  # Current time in lore_date units
    grouping_dialog_data_loaded = Signal(list, object)  # tags_data, current_config

    event_details_loaded = Signal(object, list, list)  # Event, relations, incoming
    entity_details_loaded = Signal(object, list, list)  # Entity, relations, incoming
    attachments_loaded = Signal(
        str, str, list
    )  # owner_type, owner_id, List[ImageAttachment]

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
        self.asset_store = None
        self.attachment_service = None

    @Slot()
    def initialize_db(self):
        """Initializes the database connection and services."""
        try:
            self.operation_started.emit("Connecting to Database...")
            self.db_service = DatabaseService(self.db_path)
            self.db_service.connect()

            # Initialize AssetStore
            # Assume db_path is in project root
            project_root = Path(self.db_path).resolve().parent
            self.asset_store = AssetStore(project_root)

            # Initialize AttachmentService
            # We access the repo directly from db_service (it was initialized in
            # connect())
            self.attachment_service = AttachmentService(
                self.db_service._attachment_repo, self.asset_store
            )

            # Attach to db_service for Command access (Dependency Injection via Context)
            self.db_service.attachment_service = self.attachment_service

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

    @Slot()
    def load_maps(self):
        """Loads all maps."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading Maps...")
            maps = self.db_service.get_all_maps()
            self.maps_loaded.emit(maps)
            self.operation_finished.emit("Maps Loaded.")
        except Exception:
            logger.error(f"Failed to load maps: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load maps.")

    @Slot(str)
    def load_markers(self, map_id: str):
        """Loads markers for a specific map."""
        if not self.db_service:
            return

        try:
            self.operation_started.emit(f"Loading Markers for Map {map_id}...")
            markers = self.db_service.get_markers_for_map(map_id)
            self.markers_loaded.emit(map_id, markers)
            self.operation_finished.emit("Markers Loaded.")
        except Exception:
            logger.error(f"Failed to load markers: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load markers for map {map_id}.")

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
                # Enrich with names
                for rel in rels:
                    rel["target_name"] = self.db_service.get_name(rel["target_id"])

                incoming = self.db_service.get_incoming_relations(event_id)
                for rel in incoming:
                    rel["source_name"] = self.db_service.get_name(rel["source_id"])

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
                for rel in rels:
                    rel["target_name"] = self.db_service.get_name(rel["target_id"])

                incoming = self.db_service.get_incoming_relations(entity_id)
                for rel in incoming:
                    rel["source_name"] = self.db_service.get_name(rel["source_id"])

                self.entity_details_loaded.emit(entity, rels, incoming)
            self.operation_finished.emit("Entity Details Loaded.")
        except Exception:
            logger.error(f"Failed to load entity details: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load entity {entity_id}")

    @Slot(str, str)
    def load_attachments(self, owner_type: str, owner_id: str):
        """
        Loads attachments for a specific owner.
        """
        if not self.attachment_service:
            return

        try:
            # self.operation_started.emit(f"Loading attachments for {owner_id}...")
            # (Optional: reduce noise if lazy loading)
            attachments = self.attachment_service.get_attachments(owner_type, owner_id)
            self.attachments_loaded.emit(owner_type, owner_id, attachments)
            # self.operation_finished.emit("Attachments Loaded.")
        except Exception:
            logger.error(f"Failed to load attachments: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load attachments for {owner_id}")

    @Slot(str)
    def load_longform_sequence(self, doc_id: str):
        """
        Loads the longform document sequence.

        Args:
            doc_id (str): Document ID to load.
        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading longform document...")
            sequence = longform_builder.build_longform_sequence(
                self.db_service._connection, doc_id=doc_id
            )
            self.longform_sequence_loaded.emit(sequence)
            self.operation_finished.emit(f"Loaded {len(sequence)} longform items")
        except Exception as e:
            logger.error(f"Failed to load longform sequence: {e}")
            self.error_occurred.emit(str(e))

    @Slot()
    def load_calendar_config(self):
        """
        Loads the active calendar configuration.

        Emits calendar_config_loaded with the CalendarConfig or None.
        """
        if not self.db_service:
            self.calendar_config_loaded.emit(None)
            return

        try:
            config = self.db_service.get_active_calendar_config()
            self.calendar_config_loaded.emit(config)
        except Exception as e:
            logger.error(f"Failed to load calendar config: {e}")
            self.calendar_config_loaded.emit(None)

    @Slot(
        object, object
    )  # Command, Optional[args] - simplified mainly for command objects
    def run_command(self, command: BaseCommand):
        """
        Executes a command object.
        IMPORTANT: The command must NOT already have the db_service injected.
        We inject the worker's thread-local service here.

        Args:
            command (BaseCommand): The command object to execute.

        Emits:
            command_finished (CommandResult): The result of the command
                                               execution.
            error_occurred (str): If a critical error prevents execution
                                  (though usually captured in result).
            operation_started (str): Status update.
            operation_finished (str): Status update.
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

    @Slot()
    def load_current_time(self):
        """
        Loads the current time from the database.

        Emits:
            current_time_loaded (float or None): The current time value.
        """
        if not self.db_service:
            return

        try:
            current_time = self.db_service.get_current_time()
            self.current_time_loaded.emit(
                current_time if current_time is not None else 0.0
            )
        except Exception:
            logger.error(f"Failed to load current_time: {traceback.format_exc()}")
            # Emit default value on error
            self.current_time_loaded.emit(0.0)

    @Slot(float)
    def save_current_time(self, time: float):
        """
        Saves the current time to the database.

        Args:
            time (float): The current time in lore_date units.
        """
        if not self.db_service:
            return

        try:
            self.db_service.set_current_time(time)
            logger.debug(f"Saved current_time: {time}")
        except Exception:
            logger.error(f"Failed to save current_time: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to save current time.")

    @Slot()
    def load_grouping_dialog_data(self):
        """
        Loads all necessary data for the grouping configuration dialog.

        Emits:
            grouping_dialog_data_loaded (list, dict): tags_data, current_config
        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading grouping data...")

            # Load all tags
            tags = self.db_service.get_tags_with_events()

            # Prepare tag data with colors and counts
            tags_data = []
            for tag in tags:
                tag_name = tag["name"]
                color = self.db_service.get_tag_color(tag_name)

                # Get event count
                metadata = self.db_service.get_group_metadata([tag_name])
                count = metadata[0]["count"] if metadata and len(metadata) > 0 else 0

                tags_data.append({"name": tag_name, "color": color, "count": count})

            # Get current config
            current_config = self.db_service.get_timeline_grouping_config()

            # Emit data
            self.grouping_dialog_data_loaded.emit(tags_data, current_config)
            self.operation_finished.emit("Grouping data loaded.")

        except Exception:
            logger.error(
                f"Failed to load grouping dialog data: {traceback.format_exc()}"
            )
            self.error_occurred.emit("Failed to load grouping data.")

    @Slot(str, str, str, str)
    def index_object(
        self, object_type: str, object_id: str, provider: str = None, model: str = None
    ):
        """
        Index a single object (entity or event) for semantic search.

        Args:
            object_type: 'entity' or 'event'.
            object_id: UUID of the object to index.
            provider: Optional embedding provider name ('lmstudio' or 'sentence-transformers').
            model: Optional model name override.
        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit(f"Indexing {object_type} {object_id}...")

            # Import search service
            from src.services.search_service import create_search_service

            # Create search service with provider and model
            search_service = create_search_service(
                self.db_service._connection, provider_name=provider, model=model
            )

            # Index the object
            if object_type == "entity":
                search_service.index_entity(object_id)
            elif object_type == "event":
                search_service.index_event(object_id)
            else:
                raise ValueError(f"Unknown object type: {object_type}")

            self.operation_finished.emit(f"Indexed {object_type} {object_id}.")

        except Exception:
            logger.error(f"Failed to index {object_type}: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to index {object_type} {object_id}.")
