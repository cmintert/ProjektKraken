"""Database Worker Module.

Handles asynchronous database operations to keep the UI responsive.
"""

import json
import logging
import sqlite3
import traceback
from pathlib import Path
from typing import List, Optional, Set

from PySide6.QtCore import QObject, Signal, Slot

from src.commands.base_command import BaseCommand, CommandResult
from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import SummaryData
from src.services import longform_builder
from src.services.asset_store import AssetStore
from src.services.attachment_service import AttachmentService
from src.services.db_service import DatabaseService
from src.services.import_service import ImportResult
from src.services.summary_service import SummaryService

logger = logging.getLogger(__name__)


class DatabaseWorker(QObject):
    """Worker object that executes database operations in a separate thread.

    Owns the DatabaseService instance to ensure thread affinity.
    """

    # Signals
    initialized = Signal(bool)  # Success/Fail
    events_loaded = Signal(list)  # List[Event]
    entities_loaded = Signal(list)  # List[Entity]
    maps_loaded = Signal(list)  # List[Map]
    markers_loaded = Signal(str, list)  # map_id, List[Marker]
    trajectories_loaded = Signal(list)  # List[Tuple[str, str, List[Keyframe]]]
    longform_sequence_loaded = Signal(list)  # List[dict]
    calendar_config_loaded = Signal(
        object
    )  # CalendarConfig | None (use object for union types)
    current_time_loaded = Signal(float)  # Current time in lore_date units
    grouping_dialog_data_loaded = Signal(
        list, object
    )  # tags_data, GroupingConfig | None (use object for union types)
    graph_data_loaded = Signal(list, list)  # nodes, edges
    graph_metadata_loaded = Signal(list, list)  # tags, rel_types
    graph_lexicon_loaded = Signal(dict, dict)  # raw_lexicon, resolved_lexicon
    completer_data_loaded = Signal(
        list, list, list, list
    )  # tags, rel_types, attr_keys, entity_types

    event_details_loaded = Signal(Event, list, list)  # Event, relations, incoming
    entity_details_loaded = Signal(Entity, list, list)  # Entity, relations, incoming
    attachments_loaded = Signal(
        str, str, list
    )  # owner_type, owner_id, List[ImageAttachment]

    filter_results_ready = Signal(list, list)  # List[Event], List[Entity]
    entity_state_resolved = Signal(str, dict)  # entity_id, resolved_attributes

    command_finished = Signal(CommandResult)
    error_occurred = Signal(str)

    # Status signals for UI feedback
    operation_started = Signal(str)
    operation_finished = Signal(str)

    # Import signals
    import_finished = Signal(ImportResult)
    summary_generated = Signal(str, SummaryData)

    def __init__(self, db_path: str) -> None:
        """Initializes the worker.

        Args:
            db_path: Path to the database file.

        """
        super().__init__()
        self.db_path = db_path
        self.db_service = None
        self.asset_store = None
        self.attachment_service = None
        self.temporal_manager = None

    @Slot()
    def initialize_db(self) -> None:
        """Initializes the database connection and services."""
        try:
            self.operation_started.emit("Connecting to Database...")
            self.db_service = DatabaseService(self.db_path)
            self.db_service.connect()

            # Initialize AssetStore
            # Assume db_path is in project root
            project_root = Path(self.db_path).resolve().parent
            self.asset_store = AssetStore(str(project_root))

            # Initialize AttachmentService
            # Get the repo from db_service (it was initialized in connect())
            attachment_repo = self.db_service.get_attachment_repo()
            self.attachment_service = AttachmentService(
                attachment_repo, self.asset_store
            )

            # Attach to db_service for Command access (Dependency Injection via Context)
            self.db_service.attachment_service = self.attachment_service

            # Initialize SummaryService
            self.summary_service = SummaryService(self.db_service)

            # Initialize TemporalManager
            from src.core.temporal_manager import TemporalManager

            self.temporal_manager = TemporalManager(self.db_service)

            logger.info("DatabaseWorker initialized successfully.")
            self.initialized.emit(True)
            self.operation_finished.emit("Database Connected.")
        except sqlite3.Error as e:
            logger.critical(f"DatabaseWorker database error: {type(e).__name__}: {e}")
            self.error_occurred.emit(f"Database error: {e}")
            self.initialized.emit(False)
        except (OSError, IOError) as e:
            logger.critical(f"DatabaseWorker I/O error: {type(e).__name__}: {e}")
            self.error_occurred.emit(f"Failed to access database file: {e}")
            self.initialized.emit(False)
        except Exception as e:
            logger.critical(
                f"DatabaseWorker init failed ({type(e).__name__}): {e}\n{traceback.format_exc()}"
            )
            self.error_occurred.emit("Failed to connect to database.")
            self.initialized.emit(False)

    @Slot()
    def cleanup(self) -> None:
        """Cleanly closes database connections and other resources.

        Should be called before the thread is terminated.
        """
        try:
            if self.db_service:
                self.db_service.close()
                logger.info("Database connection closed in worker cleanup.")
        except sqlite3.Error as e:
            logger.error(f"Database error during cleanup ({type(e).__name__}): {e}")
        except Exception as e:
            logger.error(
                f"Error during worker cleanup ({type(e).__name__}): {e}\n{traceback.format_exc()}"
            )

    @Slot()
    def load_events(self) -> None:
        """Loads all events."""
        if not self.db_service:
            return

        try:
            self.db_service.ensure_fresh_view()
            self.operation_started.emit("Loading Events...")
            events = self.db_service.get_all_events()
            self.events_loaded.emit(events)
            self.operation_finished.emit("Events Loaded.")
        except Exception:
            logger.error(f"Failed to load events: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load events.")

    @Slot()
    def load_entities(self) -> None:
        """Loads all entities."""
        if not self.db_service:
            return

        try:
            self.db_service.ensure_fresh_view()
            self.operation_started.emit("Loading Entities...")
            entities = self.db_service.get_all_entities()
            self.entities_loaded.emit(entities)
            self.operation_finished.emit("Entities Loaded.")
        except Exception:
            logger.error(f"Failed to load entities: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load entities.")

    @Slot()
    def load_maps(self) -> None:
        """Loads all maps."""
        if not self.db_service:
            return

        try:
            self.db_service.ensure_fresh_view()
            self.operation_started.emit("Loading Maps...")
            maps = self.db_service.get_all_maps()
            self.maps_loaded.emit(maps)
            self.operation_finished.emit("Maps Loaded.")
        except Exception:
            logger.error(f"Failed to load maps: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load maps.")

    @Slot(str)
    def load_markers(self, map_id: str) -> None:
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
    def load_trajectories(self, map_id: str) -> None:
        """Loads trajectories for a specific map."""
        if not self.db_service:
            return

        try:
            # self.operation_started.emit(f"Loading Trajectories for Map {map_id}...")
            # (Quiet operation)
            trajectories = self.db_service.get_trajectories_by_map(map_id)
            self.trajectories_loaded.emit(trajectories)
            # self.operation_finished.emit("Trajectories Loaded.")
        except Exception:
            logger.error(f"Failed to load trajectories: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load trajectories for map {map_id}.")

    @Slot(str, str, float, float, float)
    def add_keyframe(
        self, map_id: str, marker_id: str, t: float, x: float, y: float
    ) -> None:
        """Adds a keyframe to a marker's trajectory and reloads trajectories.

        Args:
            map_id: The map ID (for reloading).
            marker_id: The marker ID.
            t: Time timestamp.
            x: Normalized X.
            y: Normalized Y.

        """
        if not self.db_service:
            return

        try:
            from src.core.trajectory import Keyframe

            kf = Keyframe(t=t, x=x, y=y)
            self.db_service.add_keyframe(map_id, marker_id, kf)
            self.load_trajectories(map_id)
            self.operation_finished.emit("Keyframe added.")
        except Exception:
            logger.error(f"Failed to add keyframe: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to add keyframe.")

    @Slot(str, str, float, float)
    def update_keyframe_time(
        self, map_id: str, marker_id: str, old_t: float, new_t: float
    ) -> None:
        """Updates a keyframe's timestamp (Clock Mode) and reloads trajectories.

        Args:
            map_id: The map ID (for reloading).
            marker_id: The marker ID.
            old_t: Original timestamp.
            new_t: New timestamp.

        """
        if not self.db_service:
            return

        try:
            self.db_service.update_keyframe_time(map_id, marker_id, old_t, new_t)
            self.load_trajectories(map_id)
            self.operation_finished.emit(
                f"Keyframe time updated: {old_t:.1f} → {new_t:.1f}"
            )
        except Exception:
            logger.error(f"Failed to update keyframe time: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to update keyframe timestamp.")

    @Slot(str, str, float)
    def delete_keyframe(self, map_id: str, marker_id: str, t: float) -> None:
        """Deletes a keyframe from a marker's trajectory and reloads trajectories.

        Args:
            map_id: The map ID (for reloading).
            marker_id: The marker ID (object_id).
            t: The timestamp of the keyframe to delete.

        """
        if not self.db_service:
            return

        try:
            self.db_service.delete_keyframe(map_id, marker_id, t)
            self.load_trajectories(map_id)
            self.operation_finished.emit(f"Keyframe at t={t:.1f} deleted.")
        except ValueError as e:
            logger.warning(f"Keyframe delete failed: {e}")
            self.error_occurred.emit(str(e))
        except Exception:
            logger.error(f"Failed to delete keyframe: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to delete keyframe.")

    @Slot(str)
    def load_event_details(self, event_id: str) -> None:
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
    def load_entity_details(self, entity_id: str) -> None:
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
    def load_attachments(self, owner_type: str, owner_id: str) -> None:
        """Loads attachments for a specific owner."""
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

    @Slot(str, str)
    def load_longform_sequence(
        self, doc_id: str, filter_json: Optional[str] = None
    ) -> None:
        """Loads the longform document sequence.

        Args:
            doc_id (str): Document ID to load.
            filter_json (str): Optional JSON serialization of filter configuration.

        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Loading longform document...")

            allowed_ids: Optional[Set[str]] = None
            if filter_json:
                try:
                    filter_config = json.loads(filter_json)
                    if filter_config:
                        # Use DRY compliance: Reuse existing filter logic
                        # filter_ids_by_tags returns List[tuple[str, str]] of (type, id)
                        result_tuples = self.db_service.filter_ids_by_tags(
                            object_type=filter_config.get("object_type"),
                            include=filter_config.get("include"),
                            include_mode=filter_config.get("include_mode", "any"),
                            exclude=filter_config.get("exclude"),
                            exclude_mode=filter_config.get("exclude_mode", "any"),
                            case_sensitive=filter_config.get("case_sensitive", False),
                        )
                        # Extract just the IDs (second element of each tuple)
                        allowed_ids = {item_id for _, item_id in result_tuples}
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode filter JSON: {e}")
                except Exception as e:
                    logger.error(f"Error applying filter in worker: {e}")

            # Ensure connection and get fresh data
            connection = self.db_service.get_connection()
            if not connection:
                raise RuntimeError("Failed to establish database connection")
            self.db_service.ensure_fresh_view()

            sequence = longform_builder.build_longform_sequence(
                connection, doc_id=doc_id, allowed_ids=allowed_ids
            )
            self.longform_sequence_loaded.emit(sequence)
            self.operation_finished.emit(f"Loaded {len(sequence)} longform items")
        except Exception as e:
            logger.error(f"Failed to load longform sequence: {e}")
            self.error_occurred.emit(str(e))

    @Slot()
    def load_calendar_config(self) -> None:
        """Loads the active calendar configuration.

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
    def run_command(self, command: BaseCommand) -> None:
        """Executes a command object.
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
                    success=success,
                    message=msg,
                    command_name=command_name,
                    data={"command": command},  # Include command for undo stack
                )
            elif isinstance(result, CommandResult):
                result_obj = result
                # Ensure command_name is set if missing
                if not result_obj.command_name:
                    result_obj.command_name = command_name
                # Include command in result data for undo stack
                if "command" not in result_obj.data:
                    result_obj.data["command"] = command
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

    @Slot(object)
    def run_undo(self, command: BaseCommand) -> None:
        """Undoes a command.

        Args:
            command (BaseCommand): The command object to undo.

        Emits:
            command_finished (CommandResult): Result indicating undo success.

        """
        if not self.db_service:
            logger.error("Database not ready for undo")
            self.error_occurred.emit("Database not ready for undo.")
            return

        command_name = command.__class__.__name__
        try:
            self.operation_started.emit(f"Undoing {command_name}...")
            command.undo(self.db_service)

            result_obj = CommandResult(
                success=True,
                message=f"Undone: {command.get_description()}",
                command_name=f"Undo_{command_name}",
            )
            self.command_finished.emit(result_obj)
            self.operation_finished.emit(f"Undone {command_name}.")

        except Exception:
            logger.error(f"Undo {command_name} failed: {traceback.format_exc()}")
            self.error_occurred.emit(f"Undo {command_name} failed.")
            fail_res = CommandResult(
                success=False,
                message="Failed to undo operation.",
                command_name=f"Undo_{command_name}",
            )
            self.command_finished.emit(fail_res)

    @Slot(object)
    def run_redo(self, command: BaseCommand) -> None:
        """Redoes a command.

        Args:
            command (BaseCommand): The command object to redo.

        Emits:
            command_finished (CommandResult): Result indicating redo success.

        """
        if not self.db_service:
            logger.error("Database not ready for redo")
            self.error_occurred.emit("Database not ready for redo.")
            return

        command_name = command.__class__.__name__
        try:
            self.operation_started.emit(f"Redoing {command_name}...")
            result = command.execute(self.db_service)

            # Normalize result to CommandResult
            if isinstance(result, bool):
                success = result
                msg = f"Redone: {command.get_description()}"
                result_obj = CommandResult(
                    success=success,
                    message=msg,
                    command_name=f"Redo_{command_name}",
                )
            elif isinstance(result, CommandResult):
                result_obj = result
                result_obj.message = f"Redone: {command.get_description()}"
                result_obj.command_name = f"Redo_{command_name}"
            else:
                result_obj = CommandResult(
                    success=False,
                    message="Internal Error: Invalid command result",
                    command_name=f"Redo_{command_name}",
                )

            self.command_finished.emit(result_obj)
            self.operation_finished.emit(f"Redone {command_name}.")

        except Exception:
            logger.error(f"Redo {command_name} failed: {traceback.format_exc()}")
            self.error_occurred.emit(f"Redo {command_name} failed.")
            fail_res = CommandResult(
                success=False,
                message="Failed to redo operation.",
                command_name=f"Redo_{command_name}",
            )
            self.command_finished.emit(fail_res)

    @Slot()
    def load_current_time(self) -> None:
        """Loads the current time from the database.

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
    def save_current_time(self, time: float) -> None:
        """Saves the current time to the database.

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

    @Slot(dict)
    def save_graph_lexicon(self, config: dict) -> None:
        """Saves the visual lexicon configuration and reloads the graph.

        Args:
            config: Raw lexicon configuration dictionary.

        """
        if not self.db_service:
            return

        try:
            self.db_service.set_graph_lexicon(config)
            logger.info("Saved graph lexicon config")
            # Reload graph data so the new lexicon takes effect
            self.load_graph_data()
        except Exception:
            logger.error(
                f"Failed to save graph lexicon: {traceback.format_exc()}"
            )
            self.error_occurred.emit("Failed to save graph lexicon.")

    @Slot()
    def load_grouping_dialog_data(self) -> None:
        """Loads all necessary data for the grouping configuration dialog.

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

    @Slot(str, str, str, str, list)
    def index_object(
        self,
        object_type: str,
        object_id: str,
        name: str,
        content: str,
        excluded_attributes: Optional[List[str]] = None,
    ) -> None:
        """Index a single object (entity or event) for semantic search.

        Args:
            object_type: 'entity' or 'event'.
            object_id: UUID of the object to index.
            provider: Optional embedding provider name.
            model: Optional model name override.
            excluded_attributes: Optional list of attribute keys to exclude.

        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit(f"Indexing {object_type} {object_id}...")

            # Import search service
            from src.services.search_service import create_search_service

            # Create search service with database connection
            connection = self.db_service.get_connection()
            if not connection:
                raise RuntimeError("Failed to establish database connection")
            search_service = create_search_service(connection)

            # Index the object
            if object_type == "entity":
                search_service.index_entity(object_id, excluded_attributes)
            elif object_type == "event":
                search_service.index_event(object_id, excluded_attributes)
            else:
                raise ValueError(f"Unknown object type: {object_type}")

            self.operation_finished.emit(f"Indexed {object_type} {object_id}.")

        except Exception:
            logger.error(f"Failed to index {object_type}: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to index {object_type} {object_id}.")

    @Slot(dict)
    def apply_filter(self, filter_config: dict) -> None:
        """Applies a tag filter and loads the matching objects.

        Args:
            filter_config: Dictionary containing 'include', 'include_mode',
                           'exclude', 'exclude_mode', etc.

        """
        if not self.db_service:
            return

        try:
            self.operation_started.emit("Filtering items...")

            # Extract params with defaults
            include = filter_config.get("include")
            include_mode = filter_config.get("include_mode", "any")
            exclude = filter_config.get("exclude")
            exclude_mode = filter_config.get("exclude_mode", "any")
            case_sensitive = filter_config.get("case_sensitive", False)
            object_type = filter_config.get("object_type")  # Optional

            # 1. Get filtered IDs
            filtered_ids = self.db_service.filter_ids_by_tags(
                object_type=object_type,
                include=include,
                include_mode=include_mode,
                exclude=exclude,
                exclude_mode=exclude_mode,
                case_sensitive=case_sensitive,
            )

            # 2. Hydrate Objects
            events, entities = self.db_service.get_objects_by_ids(filtered_ids)

            # 3. Emit Results
            self.filter_results_ready.emit(events, entities)

            count = len(events) + len(entities)
            self.operation_finished.emit(f"Filtered {count} items.")

        except Exception:
            logger.error(f"Failed to apply filter: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to apply filter.")

    @Slot(str, float)
    def resolve_entity_state(self, entity_id: str, time: float) -> None:
        """Resolves the state of an entity at a specific time using TemporalManager.

        Emits entity_state_resolved.
        """
        if not self.temporal_manager:
            return

        try:
            # self.operation_started.emit(f"Resolving state for {entity_id} at {time}...")
            # (Quiet operation for smooth scrubbing)
            state = self.temporal_manager.get_entity_state_at(entity_id, time)
            self.entity_state_resolved.emit(entity_id, state)
            # self.operation_finished.emit("State Resolved.")
        except Exception:
            logger.error(
                f"Failed to resolve state for {entity_id}: {traceback.format_exc()}"
            )
            # Emit empty state or handle error?
            # For now, just log.

    @Slot(object, object)
    def load_graph_data(
        self, tags: list[str] | None = None, rel_types: list[str] | None = None
    ) -> None:
        """Loads graph data filtered by tags and relation types.

        Also loads the visual lexicon configuration and resolves icon paths
        to Base64 data URIs for secure rendering.

        Args:
            tags: List of tags to include.
            rel_types: List of relation types to include.

        """
        if not self.db_service:
            return

        try:
            from pathlib import Path

            from src.gui.widgets.graph_view.graph_builder import GraphBuilder
            from src.services.graph_data_service import GraphDataService

            self.operation_started.emit("Loading Graph Data...")
            graph_service = GraphDataService()
            nodes, edges = graph_service.get_graph_data(
                self.db_service, tags, rel_types
            )

            # Fetch metadata
            all_tags = graph_service.get_all_tags(self.db_service)
            all_rel_types = graph_service.get_all_relation_types(self.db_service)

            self.graph_data_loaded.emit(nodes, edges)
            self.graph_metadata_loaded.emit(all_tags, all_rel_types)

            # Load and resolve lexicon
            raw_lexicon = self.db_service.get_graph_lexicon() or {
                "nodes": {},
                "edges": {},
            }
            project_root = Path(self.db_service.db_path).parent
            resolved = GraphBuilder.resolve_lexicon_images(
                raw_lexicon, project_root
            )
            self.graph_lexicon_loaded.emit(raw_lexicon, resolved)

            self.operation_finished.emit(
                f"Graph Data Loaded ({len(nodes)} nodes, {len(edges)} edges)."
            )
        except Exception:
            logger.error(f"Failed to load graph data: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load graph data.")

    @Slot()
    def load_completer_data(self) -> None:
        """Loads data for autocompleters (tags, relation types, attribute keys)."""
        if not self.db_service:
            return

        try:
            from src.services.graph_data_service import GraphDataService

            # self.operation_started.emit("Loading Completer Data...") # Quiet
            graph_service = GraphDataService()

            tags = graph_service.get_all_tags(self.db_service)
            rel_types = graph_service.get_all_relation_types(self.db_service)
            attr_keys = graph_service.get_all_attribute_keys(self.db_service)
            entity_types = graph_service.get_all_entity_types(self.db_service)

            self.completer_data_loaded.emit(tags, rel_types, attr_keys, entity_types)
            # self.operation_finished.emit("Completer Data Loaded.")
        except Exception:
            logger.error(f"Failed to load completer data: {traceback.format_exc()}")
            # self.error_occurred.emit("Failed to load completer data.")

    def _refresh_after_import(self) -> None:
        """Reload events, entities, and calendar after an import.

        Ensures list, timeline, and calendar views receive fresh data.
        Longform reload is handled by DataCoordinator.load_data() on the
        UI thread via LongformManager (which supplies the required doc_id).
        """
        self.load_events()
        self.load_entities()
        self.load_calendar_config()

    @Slot(str, str)
    def run_import(self, parsed_json: str, options_json: str) -> None:
        """Runs import batch using worker's db_service.

        This ensures all DB operations happen on the worker thread with its
        single connection, avoiding WAL isolation issues.

        Args:
            parsed_json: JSON string of pre-parsed data from MainWindow.
            options_json: JSON string of import options (mode, source_name, dry_run).

        """
        if not self.db_service:
            from src.services.import_service import ImportResult

            result = ImportResult(success=False, errors=["Database not ready"])
            self.import_finished.emit(result)
            return

        try:
            self.operation_started.emit("Importing data...")
            from src.services.import_service import ImportService

            # Deserialize JSON strings
            parsed_data = json.loads(parsed_json)
            options = json.loads(options_json) if options_json else {}

            import_service = ImportService(self.db_service)
            result = import_service.import_batch(parsed_data, options)

            self.import_finished.emit(result)

            if result.success:
                # Auto-refresh data so UI updates immediately
                self._refresh_after_import()
                self.operation_finished.emit("Import complete.")
            else:
                self.operation_finished.emit("Import failed.")

        except Exception as e:
            logger.error(f"Import failed: {traceback.format_exc()}")
            from src.services.import_service import ImportResult

            result = ImportResult(success=False, errors=[str(e)])
            self.import_finished.emit(result)

    @Slot(str, str)
    def run_markdown_import(
        self, markdown_text: str, options_json: str
    ) -> None:
        """Import a Markdown file using worker's db_service.

        Parses Markdown content and imports the item into the database
        on the worker thread.

        Args:
            markdown_text: Raw Markdown content string.
            options_json: JSON string of import options.

        """
        if not self.db_service:
            from src.services.import_service import ImportResult

            result = ImportResult(
                success=False,
                created_entities=[],
                created_events=[],
                created_relations=[],
                errors=["Database not ready"],
                warnings=[],
            )
            self.import_finished.emit(result)
            return

        try:
            self.operation_started.emit("Importing Markdown...")
            from src.services.import_service import ImportService

            options = json.loads(options_json) if options_json else {}

            import_service = ImportService(self.db_service)
            result = import_service.import_markdown(markdown_text, options)

            self.import_finished.emit(result)

            if result.success:
                self._refresh_after_import()
                self.operation_finished.emit("Markdown import complete.")
            else:
                self.operation_finished.emit("Markdown import failed.")

        except Exception as e:
            logger.error(f"Markdown import failed: {traceback.format_exc()}")
            from src.services.import_service import ImportResult

            result = ImportResult(
                success=False,
                created_entities=[],
                created_events=[],
                created_relations=[],
                errors=[str(e)],
                warnings=[],
            )
            self.import_finished.emit(result)

    @Slot(str, str)
    def run_markdown_batch_import(
        self, contents_json: str, options_json: str
    ) -> None:
        """Import multiple Markdown files in a single batch operation.

        Parses each Markdown content string and imports all items,
        aggregating results into a single ImportResult.

        Args:
            contents_json: JSON-encoded list of raw Markdown content strings.
            options_json: JSON string of import options.

        """
        from src.services.import_service import ImportResult, ImportService

        if not self.db_service:
            result = ImportResult(
                success=False,
                created_entities=[],
                created_events=[],
                created_relations=[],
                errors=["Database not ready"],
                warnings=[],
            )
            self.import_finished.emit(result)
            return

        try:
            self.operation_started.emit("Importing Markdown batch...")

            contents = json.loads(contents_json)
            options = json.loads(options_json) if options_json else {}

            import_service = ImportService(self.db_service)

            # Aggregate results across all files
            all_entities: List[str] = []
            all_events: List[str] = []
            all_relations: List[str] = []
            all_errors: List[str] = []
            all_warnings: List[str] = []

            for md_text in contents:
                sub = import_service.import_markdown(md_text, options)
                all_entities.extend(sub.created_entities)
                all_events.extend(sub.created_events)
                all_relations.extend(sub.created_relations)
                all_errors.extend(sub.errors)
                all_warnings.extend(sub.warnings)

            result = ImportResult(
                success=len(all_errors) == 0,
                created_entities=all_entities,
                created_events=all_events,
                created_relations=all_relations,
                errors=all_errors,
                warnings=all_warnings,
            )
            self.import_finished.emit(result)

            if result.success:
                self._refresh_after_import()
                self.operation_finished.emit("Markdown batch import complete.")
            else:
                self.operation_finished.emit("Markdown batch import failed.")

        except Exception as e:
            logger.error(
                f"Markdown batch import failed: {traceback.format_exc()}"
            )
            result = ImportResult(
                success=False,
                created_entities=[],
                created_events=[],
                created_relations=[],
                errors=[str(e)],
                warnings=[],
            )
            self.import_finished.emit(result)

    @Slot(object)  # Union[Entity, Event] - use object for union types
    def generate_summary(self, item: object) -> None:
        """Generates a summary for the given item using LLM.

        Args:
            item: Entity or Event object.

        """
        if not self.summary_service:
            return

        try:
            self.operation_started.emit(f"Generating summary for {item.name}...")
            # Note: generate_summary logic might perform DB writes if configured?
            # SummaryService.generate_summary calls llm_provider.generate (blocking io)
            # and then *could* save to DB, but typically just returns updated object/summary data.
            # My implementation returns SummaryData, but DOES NOT save to DB automatically unless
            # I explicitly call update?
            # Actually SummaryService.generate_summary logic:
            # 1. build context
            # 2. call llm
            # 3. create SummaryData
            # 4. updates item.attributes["_summary_data"]
            # 5. insert_summary_embedding (DB call)
            # So yes, it does DB access. Thread safe? Yes, separate thread, own db_service.

            summary = self.summary_service.generate_summary(item)
            self.summary_generated.emit(item.id, summary)
            self.operation_finished.emit("Summary generated.")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}\n{traceback.format_exc()}")
            self.error_occurred.emit(f"Summary generation failed: {str(e)}")

    @Slot()
    def refresh_ai_settings(self) -> None:
        """Refresh AI settings in worker-thread services.

        Clears cached LLM provider so the next generation
        picks up the latest provider/model from QSettings.
        """
        if hasattr(self, "summary_service") and self.summary_service:
            self.summary_service.reset_provider()
        logger.info("DatabaseWorker: AI settings refreshed")
