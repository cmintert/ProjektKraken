"""Database Worker Module.

Handles asynchronous database operations to keep the UI responsive.
"""

import json
import logging
import sqlite3
import subprocess
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Set, Tuple, Union, cast

from PySide6.QtCore import QObject, Signal, SignalInstance, Slot

from src.core.command import CommandProtocol, CommandResult
from src.core.entities import Entity
from src.core.events import Event
from src.core.semantic_config import (
    SEMANTIC_COMPLETION_ENABLE_EMBEDDING,
    SEMANTIC_COMPLETION_PROBE_ON_WINDOWS,
    SEMANTIC_COMPLETION_PROBE_TIMEOUT_S,
)
from src.core.summary_data import SummaryData
from src.services import longform_builder
from src.services.asset_store import AssetStore
from src.services.attachment_service import AttachmentService
from src.services.db_service import DatabaseService
from src.services.import_service import ImportResult
from src.services.obsidian_exporter import (
    ObsidianExportCompletion,
    ObsidianExporter,
    ObsidianExportPreparation,
)
from src.services.summary_service import SummaryService

if TYPE_CHECKING:
    from src.core.temporal_manager import TemporalManager
    from src.services.history_service import HistoryService
    from src.services.search_service import SearchService

logger = logging.getLogger(__name__)

_LEGACY_ANALYSIS_ARG_COUNT = 3
_SCOPED_ANALYSIS_ARG_COUNT = 6


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
    trajectories_loaded = Signal(str, list)  # map_id, JSON-safe trajectory snapshots
    feature_geometry_states_loaded = Signal(str, list)
    longform_sequence_loaded = Signal(list)  # List[dict]
    calendar_config_loaded = Signal(
        object
    )  # CalendarConfig | None (use object for union types)
    current_time_loaded = Signal(float)  # Current time in lore_date units
    ai_generation_preferences_loaded = Signal(object)
    grouping_dialog_data_loaded = Signal(
        list, object
    )  # tags_data, GroupingConfig | None (use object for union types)
    graph_data_loaded = Signal(list, list)  # nodes, edges
    graph_metadata_loaded = Signal(list, list)  # tags, rel_types
    graph_lexicon_loaded = Signal(dict, dict)  # raw_lexicon, resolved_lexicon
    timeline_grouping_loaded = Signal(object)
    world_theme_loaded = Signal(str)
    embedding_stats_loaded = Signal(dict)
    completer_data_loaded = Signal(
        list, list, list, list
    )  # tags, rel_types, attr_keys, entity_types

    event_details_loaded = Signal(Event, list, list)  # Event, relations, incoming
    authoring_context_loaded = Signal(str, str, float, str, dict)
    entity_authoring_context_loaded = Signal(str, str, dict)
    entity_details_loaded = Signal(Entity, list, list)  # Entity, relations, incoming
    attachments_loaded = Signal(
        str, str, list
    )  # owner_type, owner_id, List[ImageAttachment]

    filter_results_ready = Signal(list, list)  # List[Event], List[Entity]
    entity_state_resolved = Signal(str, dict)  # entity_id, serialized state

    command_finished = Signal(CommandResult)
    history_loaded = Signal(list)
    history_cleared = Signal(int)
    error_occurred = Signal(str)

    # Status signals for UI feedback
    operation_started = Signal(str)
    operation_finished = Signal(str)

    # Import signals
    import_finished = Signal(ImportResult)
    obsidian_export_prepared = Signal(dict)
    obsidian_export_finished = Signal(dict)
    obsidian_vault_export_finished = Signal(dict)
    summary_generated = Signal(str, SummaryData)
    summary_generation_failed = Signal(str)  # item_id

    # Semantic completion signals
    semantic_suggestions_ready = Signal(str, list)  # (prefix, list[str] names)

    # Index rebuild signals
    index_rebuild_progress = Signal(int, int, int)  # (done, total, pct)
    index_rebuild_finished = Signal(int, int, int)  # (indexed, unchanged, failed)

    # Analysis signals
    validation_complete = Signal(str, str, object)  # job_id, world_id, report
    temporal_analysis_complete = Signal(str, str, object)  # job_id, world_id, report
    analysis_failed = Signal(str, str, str, str)  # job_id, world_id, kind, message
    intelligence_snapshot_ready = Signal(str, dict)  # job_id, serialized snapshot
    intelligence_snapshot_failed = Signal(str, str)  # job_id, message

    def __init__(
        self,
        db_path: str,
        command_types: dict[str, type[Any]] | None = None,
    ) -> None:
        """Initializes the worker.

        Args:
            db_path: Path to the database file.
            command_types: Command classes supplied by the application layer for
                deserializing worker requests without reversing layer dependencies.

        """
        super().__init__()
        self.db_path = db_path
        self._command_types = dict(command_types or {})
        self.db_service: Optional[DatabaseService] = None
        self.asset_store: Optional[AssetStore] = None
        self.attachment_service: Optional[AttachmentService] = None
        self.temporal_manager: Optional["TemporalManager"] = None
        self.history_service: Optional["HistoryService"] = None
        self.summary_service: Optional[SummaryService] = None
        self._search_service: Optional["SearchService"] = None
        # Embedding queue to prevent concurrent embedding operations
        self._embedding_in_progress = False
        self._pending_embeddings: Set[
            Tuple[str, str, Optional[Tuple[str, ...]]]
        ] = set()
        self._semantic_probe_ran = False
        self._semantic_probe_ok = True

    def _ensure_semantic_probe(self) -> bool:
        """Run a one-time crash-safety probe before semantic model usage.

        On Windows, sentence-transformers / torch may crash the host process in
        native code. This probe runs in a child Python process so a failure does
        not terminate the app. If the probe fails, semantic embedding completions
        are disabled for this worker lifetime.
        """
        if self._semantic_probe_ran:
            return self._semantic_probe_ok

        self._semantic_probe_ran = True

        if sys.platform != "win32" or not SEMANTIC_COMPLETION_PROBE_ON_WINDOWS:
            self._semantic_probe_ok = True
            return True

        model_name = "all-MiniLM-L6-v2"
        probe_code = (
            "import os;"
            "os.environ.setdefault('TOKENIZERS_PARALLELISM','false');"
            "os.environ.setdefault('OMP_NUM_THREADS','1');"
            "from sentence_transformers import SentenceTransformer;"
            f"m=SentenceTransformer('{model_name}', device='cpu');"
            "m.encode(['probe'], show_progress_bar=False)"
        )

        try:
            result = subprocess.run(
                [sys.executable, "-c", probe_code],
                check=False,
                capture_output=True,
                text=True,
                timeout=SEMANTIC_COMPLETION_PROBE_TIMEOUT_S,
            )
        except Exception:
            logger.warning("Semantic embedding probe failed", exc_info=True)
            self._semantic_probe_ok = False
            return False

        if result.returncode != 0:
            logger.warning(
                "Semantic embedding probe disabled feature on this run "
                "(code=%s, stderr=%s)",
                result.returncode,
                (result.stderr or "").strip()[:300],
            )
            self._semantic_probe_ok = False
            return False

        self._semantic_probe_ok = True
        logger.info("Semantic embedding probe passed")
        return True

    @Slot()
    def initialize_db(self) -> None:
        """Initializes the database connection and services."""
        try:
            self._search_service = None  # Reset cached service on re-init
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

            self.world_theme_loaded.emit(self.db_service.get_world_theme() or "")

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
            self._search_service = None
            if self.history_service:
                self.history_service.end_session()
                self.history_service = None
            if self.db_service:
                self.db_service.close()
                logger.info("Database connection closed in worker cleanup.")
        except sqlite3.Error as e:
            logger.error(f"Database error during cleanup ({type(e).__name__}): {e}")
        except Exception as e:
            logger.error(
                f"Error during worker cleanup ({type(e).__name__}): {e}\n{traceback.format_exc()}"
            )

    @Slot(str)
    def initialize_history(self, world_id: str) -> None:
        """Create and load persistent command history on the worker thread."""
        if not self.db_service:
            self.error_occurred.emit("Database not ready for command history.")
            return
        try:
            from src.services.history_service import HistoryService

            self.history_service = HistoryService(self.db_service, world_id)
            for name, command_type in self._command_types.items():
                self.history_service.register_command_type(name, command_type)
            commands = self.history_service.load_recent_history(limit=100)
            payloads = [
                {
                    "type": command.__class__.__name__,
                    "data": command.to_dict(),
                    "base": command.base_state_dict(),
                }
                for command in commands
            ]
            self.history_loaded.emit(payloads)
        except Exception:
            logger.exception("Failed to initialize command history")
            self.error_occurred.emit("Failed to initialize command history.")

    @Slot()
    def clear_command_history(self) -> None:
        """Clear persistent history and command artifacts on the worker."""
        if self.history_service is None:
            self.history_cleared.emit(0)
            return
        self.history_cleared.emit(self.history_service.clear_all_history())

    @Slot()
    def load_timeline_grouping_config(self) -> None:
        """Load timeline grouping configuration and tag colors."""
        if self.db_service is None:
            self.timeline_grouping_loaded.emit(None)
            return
        try:
            config = self.db_service.get_timeline_grouping_config()
            tag_order = config.get("tag_order", []) if config else []
            colors = {
                tag_name: self.db_service.get_tag_color(tag_name)
                for tag_name in tag_order
            }
            self.timeline_grouping_loaded.emit(
                {"config": config, "colors": colors}
            )
        except Exception:
            logger.exception("Failed to load timeline grouping configuration")
            self.timeline_grouping_loaded.emit(None)

    @Slot(str)
    def save_world_theme(self, theme_name: str) -> None:
        """Persist the active theme using the worker-owned database service."""
        if self.db_service is None:
            return
        try:
            self.db_service.set_world_theme(theme_name)
        except Exception:
            logger.exception("Failed to save world theme")
            self.error_occurred.emit("Failed to save world theme.")

    @Slot()
    def load_embedding_stats(self) -> None:
        """Emit aggregate semantic-index statistics."""
        if self.db_service is None:
            self.embedding_stats_loaded.emit({"count": 0, "last_updated": None})
            return
        try:
            self.embedding_stats_loaded.emit(self.db_service.get_embedding_stats())
        except Exception:
            logger.exception("Failed to load semantic-index statistics")
            self.embedding_stats_loaded.emit({"count": 0, "last_updated": None})
            self.error_occurred.emit("Failed to load semantic-index statistics.")

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
            trajectories = self.db_service.get_trajectory_snapshots_by_map(map_id)
            self.trajectories_loaded.emit(map_id, trajectories)
            # self.operation_finished.emit("Trajectories Loaded.")
        except Exception:
            logger.error(f"Failed to load trajectories: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load trajectories for map {map_id}.")

    @Slot(str)
    def load_feature_geometry_states(self, map_id: str) -> None:
        """Load every dated vector-geometry state for one map."""
        if not self.db_service:
            return
        try:
            states = self.db_service.feature_geometry_repo.get_states_for_map(map_id)
            self.feature_geometry_states_loaded.emit(map_id, states)
        except Exception:
            logger.error(
                "Failed to load feature geometry states: %s",
                traceback.format_exc(),
            )
            self.error_occurred.emit(
                f"Failed to load dated geometry for map {map_id}."
            )

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
            else:
                # Signal that the requested event was not found so UI can clear editors
                self.event_details_loaded.emit(None, [], [])
            self.operation_finished.emit("Event Details Loaded.")
        except Exception:
            logger.error(f"Failed to load event details: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load event {event_id}")

    @Slot(str, str, float, str)
    def load_event_authoring_context(
        self,
        request_id: str,
        event_id: str,
        context_date: float,
        active_map_id: str,
    ) -> None:
        """Build and emit one serialized Event authoring-context snapshot."""
        if self.db_service is None:
            self.authoring_context_loaded.emit(
                request_id, event_id, context_date, active_map_id, {}
            )
            return
        try:
            from src.services.authoring_context_builder import AuthoringContextBuilder

            self.db_service.ensure_fresh_view()
            with self.db_service.transaction():
                context = AuthoringContextBuilder(
                    self.db_service,
                    world_root=Path(self.db_path).resolve().parent,
                ).build_event_context(
                    event_id,
                    context_date=context_date,
                    active_map_id=active_map_id or None,
                )
            self.authoring_context_loaded.emit(
                request_id,
                event_id,
                context_date,
                active_map_id,
                context.to_dict() if context is not None else {},
            )
        except Exception:
            logger.error(
                "Failed to load Event authoring context: %s", traceback.format_exc()
            )
            self.authoring_context_loaded.emit(
                request_id, event_id, context_date, active_map_id, {}
            )

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
            else:
                # Signal that the requested entity was not found so UI can clear editors
                self.entity_details_loaded.emit(None, [], [])
            self.operation_finished.emit("Entity Details Loaded.")
        except Exception:
            logger.error(f"Failed to load entity details: {traceback.format_exc()}")
            self.error_occurred.emit(f"Failed to load entity {entity_id}")

    @Slot(str, str)
    def load_entity_authoring_context(
        self, request_id: str, entity_id: str
    ) -> None:
        """Build and emit one serialized Entity authoring-context snapshot."""
        if self.db_service is None:
            self.entity_authoring_context_loaded.emit(request_id, entity_id, {})
            return
        try:
            from src.services.authoring_context_builder import AuthoringContextBuilder

            self.db_service.ensure_fresh_view()
            with self.db_service.transaction():
                context = AuthoringContextBuilder(
                    self.db_service,
                    world_root=Path(self.db_path).resolve().parent,
                ).build_entity_context(entity_id)
            self.entity_authoring_context_loaded.emit(
                request_id,
                entity_id,
                context.to_dict() if context is not None else {},
            )
        except Exception:
            logger.error(
                "Failed to load Entity authoring context: %s",
                traceback.format_exc(),
            )
            self.entity_authoring_context_loaded.emit(request_id, entity_id, {})

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

            if allowed_ids is None:
                longform_builder.ensure_all_items_indexed(connection, doc_id)
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

    def _command_from_request(self, request: object) -> CommandProtocol:
        """Reconstruct a command from a serializable main-thread intent."""
        if not isinstance(request, dict):
            required_methods = (
                "execute",
                "undo",
                "to_dict",
                "base_state_dict",
                "restore_base_state",
                "get_description",
            )
            if all(callable(getattr(request, name, None)) for name in required_methods):
                return cast(CommandProtocol, request)
            raise TypeError("Command request must be a serializable dictionary")

        command_type = str(request.get("type", ""))
        command_class = self._command_types.get(command_type)
        if command_class is None:
            raise ValueError(f"Unknown command type: {command_type}")
        data = request.get("data", {})
        base = request.get("base", {})
        if not isinstance(data, dict) or not isinstance(base, dict):
            raise TypeError(f"Invalid command request: {command_type}")
        command = command_class.from_dict(data)
        command.restore_base_state(base)
        return cast(CommandProtocol, command)

    def _new_command(self, command_type: str, **kwargs: object) -> CommandProtocol:
        """Construct a registered command without importing the command layer."""
        command_class = self._command_types.get(command_type)
        if command_class is None:
            raise RuntimeError(f"Command type is not registered: {command_type}")
        return cast(CommandProtocol, command_class(**kwargs))

    @staticmethod
    def _command_state(command: CommandProtocol) -> dict[str, object]:
        """Create the canonical serializable state returned to the UI."""
        return {
            "type": command.__class__.__name__,
            "data": command.to_dict(),
            "base": command.base_state_dict(),
        }

    @Slot(object)
    def run_command(self, request: object) -> None:
        """Execute a serialized command intent with the worker-owned database.

        Args:
            request: Serializable command payload. A command object is accepted
                temporarily for compatibility with direct unit tests.

        Emits:
            command_finished (CommandResult): The result of the command
                                               execution.
            error_occurred (str): If a critical error prevents execution
                                  (though usually captured in result).
            operation_started (str): Status update.
            operation_finished (str): Status update.

        """
        try:
            command = self._command_from_request(request)
        except Exception as exc:
            logger.error("Invalid command request: %s", exc)
            self.command_finished.emit(
                CommandResult(
                    success=False,
                    message=str(exc),
                    command_name="InvalidCommand",
                )
            )
            return

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
                    data={"command_id": command.command_id},
                )
            elif isinstance(result, CommandResult):
                result_obj = result
                # Ensure command_name is set if missing
                if not result_obj.command_name:
                    result_obj.command_name = command_name
                result_obj.data.setdefault("command_id", command.command_id)
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

            if (
                result_obj.success
                and self.history_service is not None
                and command.persist_to_history
            ):
                self.history_service.save_command(command)
            result_obj.data["command_state"] = self._command_state(command)
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
                data={
                    "command_id": command.command_id,
                    "command_state": self._command_state(command),
                },
            )
            self.command_finished.emit(fail_res)

    @Slot(object)
    def run_undo(self, request: object) -> None:
        """Undoes a command.

        Args:
            request: Serialized command state to undo.

        Emits:
            command_finished (CommandResult): Result indicating undo success.

        """
        try:
            command = self._command_from_request(request)
        except Exception as exc:
            self.command_finished.emit(
                CommandResult(
                    success=False,
                    message=str(exc),
                    command_name="Undo_InvalidCommand",
                )
            )
            return

        if not self.db_service:
            logger.error("Database not ready for undo")
            self.error_occurred.emit("Database not ready for undo.")
            return

        command_name = command.__class__.__name__
        try:
            self.operation_started.emit(f"Undoing {command_name}...")
            undo_result = command.undo(self.db_service)
            if isinstance(undo_result, CommandResult):
                result_obj = undo_result
                result_obj.command_name = f"Undo_{command_name}"
            else:
                result_obj = CommandResult(
                    success=True,
                    message=f"Undone: {command.get_description()}",
                    command_name=f"Undo_{command_name}",
                )
            result_obj.data.setdefault("command_id", command.command_id)
            if (
                result_obj.success
                and self.history_service is not None
                and command.persist_to_history
            ):
                self.history_service.set_command_executed(command.command_id, False)
            result_obj.data["command_state"] = self._command_state(command)
            self.command_finished.emit(result_obj)
            self.operation_finished.emit(f"Undone {command_name}.")

        except Exception:
            logger.error(f"Undo {command_name} failed: {traceback.format_exc()}")
            self.error_occurred.emit(f"Undo {command_name} failed.")
            fail_res = CommandResult(
                success=False,
                message="Failed to undo operation.",
                command_name=f"Undo_{command_name}",
                data={
                    "command_id": command.command_id,
                    "command_state": self._command_state(command),
                },
            )
            self.command_finished.emit(fail_res)

    @Slot(object)
    def run_redo(self, request: object) -> None:
        """Redoes a command.

        Args:
            request: Serialized command state to redo.

        Emits:
            command_finished (CommandResult): Result indicating redo success.

        """
        try:
            command = self._command_from_request(request)
        except Exception as exc:
            self.command_finished.emit(
                CommandResult(
                    success=False,
                    message=str(exc),
                    command_name="Redo_InvalidCommand",
                )
            )
            return

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

            result_obj.data.setdefault("command_id", command.command_id)
            if (
                result_obj.success
                and self.history_service is not None
                and command.persist_to_history
            ):
                self.history_service.set_command_executed(command.command_id, True)
            result_obj.data["command_state"] = self._command_state(command)
            self.command_finished.emit(result_obj)
            self.operation_finished.emit(f"Redone {command_name}.")

        except Exception:
            logger.error(f"Redo {command_name} failed: {traceback.format_exc()}")
            self.error_occurred.emit(f"Redo {command_name} failed.")
            fail_res = CommandResult(
                success=False,
                message="Failed to redo operation.",
                command_name=f"Redo_{command_name}",
                data={
                    "command_id": command.command_id,
                    "command_state": self._command_state(command),
                },
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

    @Slot()
    def load_ai_generation_preferences(self) -> None:
        """Load portable AI preferences on the database worker thread."""
        if not self.db_service:
            return
        try:
            preferences = self.db_service.get_ai_generation_preferences()
            self.ai_generation_preferences_loaded.emit(preferences)
        except Exception:
            logger.error(
                "Failed to load AI generation preferences: %s",
                traceback.format_exc(),
            )
            self.ai_generation_preferences_loaded.emit(None)

    @Slot(dict)
    def save_ai_generation_preferences(self, preferences: dict) -> None:
        """Save portable AI preferences on the database worker thread."""
        if not self.db_service:
            return
        try:
            self.db_service.set_ai_generation_preferences(preferences)
        except Exception:
            logger.error(
                "Failed to save AI generation preferences: %s",
                traceback.format_exc(),
            )
            self.error_occurred.emit("Failed to save AI generation preferences.")

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
            logger.error(f"Failed to save graph lexicon: {traceback.format_exc()}")
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

    @Slot(str, str, list)
    def index_object(
        self,
        object_type: str,
        object_id: str,
        excluded_attributes: Optional[List[str]] = None,
    ) -> None:
        """Index a single object (entity or event) for semantic search.

        Queues the embedding request if one is already in progress, otherwise
        starts the embedding immediately. This prevents concurrent embedding
        operations which can fail due to resource conflicts.

        Args:
            object_type: 'entity' or 'event'.
            object_id: UUID of the object to index.
            excluded_attributes: Optional list of attribute keys to exclude.

        """
        if not self.db_service:
            return

        # Queue the request if an embedding is already in progress
        if self._embedding_in_progress:
            self._pending_embeddings.add(
                (object_type, object_id, tuple(excluded_attributes) if excluded_attributes else None)
            )
            logger.debug(
                f"[Worker] Embedding already in progress, queuing {object_type} {object_id}"
            )
            return

        # Start the embedding
        self._do_index_object(object_type, object_id, excluded_attributes)

    def _do_index_object(
        self,
        object_type: str,
        object_id: str,
        excluded_attributes: Optional[List[str]] = None,
    ) -> None:
        """Perform the actual indexing operation.

        Sets the embedding-in-progress flag and processes the embedding,
        then clears the flag and processes any pending embeddings.

        Args:
            object_type: 'entity' or 'event'.
            object_id: UUID of the object to index.
            excluded_attributes: Optional list of attribute keys to exclude.

        """
        self._embedding_in_progress = True

        try:
            self.operation_started.emit(f"Indexing {object_type} {object_id}...")

            # Reuse the cached SearchService so the underlying SentenceTransformer
            # model is loaded only once per worker lifetime.  Creating a fresh
            # provider on every call spawns tqdm monitor threads via
            # huggingface_hub, which causes Windows heap corruption (0xc0000374)
            # under repeated background-thread model instantiation.
            search_service = self._get_search_service()
            if search_service is None:
                raise RuntimeError("Search service unavailable")

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
        finally:
            # Clear the flag and process next pending embedding
            self._embedding_in_progress = False
            self._process_pending_embeddings()

    def _process_pending_embeddings(self) -> None:
        """Process the next pending embedding from the queue."""
        if not self._pending_embeddings:
            return

        # Get the first pending embedding
        next_embedding = self._pending_embeddings.pop()
        object_type, object_id, excluded_attributes_tuple = next_embedding

        # Convert tuple back to list if present
        excluded_attributes = (
            list(excluded_attributes_tuple) if excluded_attributes_tuple else None
        )

        logger.debug(
            f"[Worker] Processing queued embedding for {object_type} {object_id}"
        )
        self._do_index_object(object_type, object_id, excluded_attributes)

    @Slot(str, list)
    def rebuild_search_index(
        self,
        object_type: str,
        excluded_attributes: Optional[List[str]] = None,
    ) -> None:
        """Rebuild the semantic search index on the worker thread.

        Emits index_rebuild_progress periodically and index_rebuild_finished
        when done.

        Args:
            object_type: 'all', 'entity', or 'event'.
            excluded_attributes: Optional list of attribute keys to exclude.

        """
        if not self.db_service:
            self.error_occurred.emit("Database not ready for index rebuild.")
            return

        try:
            # Reuse cached SearchService for the same reason as index_object:
            # avoids repeated SentenceTransformer instantiation on the worker
            # thread which causes Windows heap corruption via tqdm monitor threads.
            try:
                search_service = self._get_search_service()
            except ImportError as e:
                msg = str(e).split("\n")[0]
                self.error_occurred.emit(msg)
                self.index_rebuild_finished.emit(0, 0, 1)
                return

            if search_service is None:
                self.error_occurred.emit("Search service unavailable for rebuild.")
                self.index_rebuild_finished.emit(0, 0, 1)
                return

            types = (
                ["entity", "event"] if object_type == "all" else [object_type]
            )

            self.operation_started.emit("Rebuilding search index...")

            def report_progress(done: int, total: int) -> None:
                percentage = 100 if total == 0 else int(done * 100 / total)
                self.index_rebuild_progress.emit(done, total, percentage)

            result = search_service.rebuild_index(
                object_types=types,
                excluded_attributes=excluded_attributes or [],
                progress_callback=report_progress,
            )

            self.index_rebuild_finished.emit(
                result.indexed,
                result.unchanged,
                result.failed,
            )
            self.operation_finished.emit(
                "Index rebuilt: "
                f"{result.indexed} indexed, "
                f"{result.unchanged} unchanged, "
                f"{result.failed} failed."
            )

        except Exception:
            logger.error(
                f"Index rebuild failed: {traceback.format_exc()}"
            )
            self.error_occurred.emit("Index rebuild failed.")
            self.index_rebuild_finished.emit(0, 0, 1)

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
            self.entity_state_resolved.emit(entity_id, state.to_dict())
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

            from src.services.graph_data_service import GraphDataService
            from src.services.graph_lexicon_resolver import resolve_lexicon_images

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
            resolved = resolve_lexicon_images(raw_lexicon, project_root)
            self.graph_lexicon_loaded.emit(raw_lexicon, resolved)

            self.operation_finished.emit(
                f"Graph Data Loaded ({len(nodes)} nodes, {len(edges)} edges)."
            )
        except Exception:
            logger.error(f"Failed to load graph data: {traceback.format_exc()}")
            self.error_occurred.emit("Failed to load graph data.")

    def _get_search_service(self) -> Optional["SearchService"]:
        """Return a cached SearchService, creating it lazily on first use.

        Returns:
            SearchService instance, or None if unavailable.

        """
        if self._search_service is not None:
            return self._search_service
        if not self.db_service:
            return None
        from src.services.search_service import create_search_service

        conn = self.db_service.get_connection()
        if conn is None:
            return None
        self._search_service = create_search_service(conn)
        return self._search_service

    @Slot(str, int, float)
    def query_semantic_suggestions(
        self, prefix: str, top_k: int = 5, min_score: float = 0.85
    ) -> None:
        """Run a semantic query and emit matching suggestions.

        Called from the main thread via QueuedConnection. Filters results
        by *min_score* before emitting to avoid sending noise to the UI.

        Args:
            prefix: The typed wiki-link prefix text.
            top_k: Maximum results to retrieve from the index.
            min_score: Minimum cosine similarity to include.

        """
        if not SEMANTIC_COMPLETION_ENABLE_EMBEDDING:
            return
        if not self.db_service:
            return
        if not self._ensure_semantic_probe():
            return
        try:
            svc = self._get_search_service()
            if svc is None:
                return
            results = svc.query(text=prefix, top_k=top_k)
            names = [
                r["name"]
                for r in results
                if r["score"] >= min_score and r["name"]
            ]
            self.semantic_suggestions_ready.emit(prefix, names)
        except Exception:
            logger.debug(
                "Semantic suggestion query failed", exc_info=True
            )

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
    def run_markdown_import(self, markdown_text: str, options_json: str) -> None:
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
    def run_markdown_batch_import(self, contents_json: str, options_json: str) -> None:
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
            logger.error(f"Markdown batch import failed: {traceback.format_exc()}")
            result = ImportResult(
                success=False,
                created_entities=[],
                created_events=[],
                created_relations=[],
                errors=[str(e)],
                warnings=[],
            )
            self.import_finished.emit(result)

    def _get_obsidian_export_item(
        self, item_type: str, item_id: str
    ) -> Entity | Event | None:
        """Load one exportable item through the worker-owned database service.

        Args:
            item_type: Supported item type, ``"entity"`` or ``"event"``.
            item_id: Database ID of the requested item.

        Returns:
            The matching entity or event, or ``None`` when unavailable.

        """
        db_service = self.db_service
        if db_service is None:
            return None
        if item_type == "entity":
            return db_service.get_entity(item_id)
        if item_type == "event":
            return db_service.get_event(item_id)
        return None

    @Slot(str, str)
    def prepare_single_obsidian_export(self, item_type: str, item_id: str) -> None:
        """Resolve an export item and emit a serializable identity snapshot.

        Args:
            item_type: Supported item type, ``"entity"`` or ``"event"``.
            item_id: Database ID of the requested item.

        """
        item = self._get_obsidian_export_item(item_type, item_id)

        if self.db_service is None:
            error = "No database connection"
        elif item_type not in {"entity", "event"}:
            error = f"Cannot export unsupported item type '{item_type}'"
        elif item is None:
            error = f"Could not find {item_type} to export"
        else:
            error = ""

        snapshot: ObsidianExportPreparation = {
            "item_type": item_type,
            "item_id": item_id,
            "item_name": item.name if item is not None else "",
            "error": error,
        }
        self.obsidian_export_prepared.emit(snapshot)

    @Slot(str, str, str, dict)
    def run_single_obsidian_export(
        self,
        item_type: str,
        item_id: str,
        file_path: str,
    ) -> None:
        """Export one item using the worker-owned database service.

        Args:
            item_type: Supported item type, ``"entity"`` or ``"event"``.
            item_id: Database ID of the requested item.
            file_path: User-selected output Markdown path.

        """
        item = self._get_obsidian_export_item(item_type, item_id)
        item_name = item.name if item is not None else ""
        target_path = Path(file_path).resolve()
        error = ""

        if self.db_service is None:
            error = "No database connection"
        elif item_type not in {"entity", "event"}:
            error = f"Cannot export unsupported item type '{item_type}'"
        elif item is None:
            error = f"Could not find {item_type} to export"
        else:
            try:
                exporter = ObsidianExporter(self.db_service)
                exported_path = exporter.export_single_item(
                    item,
                    target_path.parent,
                    include_relations=True,
                )
                if exported_path is None:
                    error = "The exporter did not create a file"
                elif exported_path != target_path:
                    exported_path.replace(target_path)
            except Exception as exc:
                logger.exception("Single item export error")
                error = str(exc)

        snapshot: ObsidianExportCompletion = {
            "success": not error,
            "item_type": item_type,
            "item_id": item_id,
            "item_name": item_name,
            "file_path": str(target_path),
            "error": error,
        }
        self.obsidian_export_finished.emit(snapshot)

    @Slot(str)
    def run_obsidian_vault_export(self, output_dir: str) -> None:
        """Export the complete world to an Obsidian-compatible folder.

        Args:
            output_dir: User-selected destination directory.

        """
        db_service = self.db_service
        if db_service is None:
            self.obsidian_vault_export_finished.emit(
                {
                    "success": False,
                    "files_created": 0,
                    "output_dir": output_dir,
                    "errors": ["No database connection"],
                }
            )
            return

        try:
            result = ObsidianExporter(db_service).export_to_folder(
                output_dir=Path(output_dir),
                include_relations=True,
            )
            snapshot = {
                "success": result.success,
                "files_created": result.files_created,
                "output_dir": str(result.output_dir),
                "errors": list(result.errors),
            }
        except Exception as exc:
            logger.exception("Obsidian vault export failed")
            snapshot = {
                "success": False,
                "files_created": 0,
                "output_dir": output_dir,
                "errors": [str(exc)],
            }
        self.obsidian_vault_export_finished.emit(snapshot)

    @Slot(object)  # Union[Entity, Event] - use object for union types
    def generate_summary(self, item: Union[Entity, Event]) -> None:
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
            self.summary_generation_failed.emit(item.id)
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

    def _run_analysis_command(
        self,
        cmd: CommandProtocol,
        result_signal: SignalInstance,
        *args: str,
    ) -> None:
        """Execute an analysis command and emit results on the worker thread.

        Emits :attr:`operation_started` before the command and
        :attr:`operation_finished` after (success or failure).  On success
        emits *result_signal* with the report; on failure emits
        :attr:`error_occurred`.

        Args:
            cmd: A command whose ``execute()`` returns a
                :class:`~src.core.command.CommandResult` with
                ``data["report"]`` on success.
            result_signal: The signal to emit with the report on success.
            start_msg: Status string passed to :attr:`operation_started`.
            done_msg: Status string passed to :attr:`operation_finished`.
            error_prefix: Short label used in error messages, e.g.
                ``"Validation"``.
        """
        if len(args) == _LEGACY_ANALYSIS_ARG_COUNT:
            job_id = world_id = analysis_kind = ""
            start_msg, done_msg, error_prefix = args
        elif len(args) == _SCOPED_ANALYSIS_ARG_COUNT:
            job_id, world_id, analysis_kind, start_msg, done_msg, error_prefix = args
        else:
            raise TypeError("analysis helper expects 3 legacy or 6 job-aware arguments")
        self.operation_started.emit(start_msg)
        try:
            db_service = self.db_service
            if db_service is None:
                logger.error("Database not ready for %s", error_prefix.lower())
                message = f"Database not ready for {error_prefix.lower()}."
                self.error_occurred.emit(message)
                self.analysis_failed.emit(job_id, world_id, analysis_kind, message)
                return

            result = cmd.execute(db_service)
            if result.success:
                report: Any = result.data["report"]
                report.world_id = world_id
                report.snapshot_timestamp = report.timestamp
                result_signal.emit(job_id, world_id, report)
            else:
                message = f"{error_prefix} failed: {result.errors}"
                self.error_occurred.emit(message)
                self.analysis_failed.emit(job_id, world_id, analysis_kind, message)
        except Exception as exc:
            logger.error("%s error: %s\n%s", error_prefix, exc, traceback.format_exc())
            message = f"{error_prefix} error: {exc!s}"
            self.error_occurred.emit(message)
            self.analysis_failed.emit(job_id, world_id, analysis_kind, message)
        finally:
            self.operation_finished.emit(done_msg)

    @Slot(str, str, bool)
    def validate_world(
        self,
        job_id: str = "",
        world_id: str = "",
        editorial_checks: bool = False,
    ) -> None:
        """Run world validation in the worker thread and emit the report.

        On success emits :attr:`validation_complete` with the
        :class:`~src.core.analysis.WorldValidationReport`.
        On failure emits :attr:`error_occurred` with an error string.
        """
        self._run_analysis_command(
            self._new_command(
                "ValidateWorldCommand", editorial_checks=editorial_checks
            ),
            self.validation_complete,
            job_id,
            world_id,
            "validation",
            "Validating world…",
            "Validation finished.",
            "Validation",
        )

    @Slot(str, str)
    def analyze_temporal(self, job_id: str = "", world_id: str = "") -> None:
        """Run temporal analysis in the worker thread and emit the report.

        On success emits :attr:`temporal_analysis_complete` with the
        :class:`~src.core.analysis.TemporalAnalysisReport`.
        On failure emits :attr:`error_occurred` with an error string.
        """
        self._run_analysis_command(
            self._new_command("AnalyzeTemporalCommand"),
            self.temporal_analysis_complete,
            job_id,
            world_id,
            "temporal",
            "Analyzing timeline…",
            "Temporal analysis finished.",
            "Temporal analysis",
        )

    @Slot(str, str, str, dict)
    def prepare_intelligence_analysis(
        self,
        job_id: str,
        world_id: str,
        analysis_type: str = "all",
        options: dict[str, Any] | None = None,
    ) -> None:
        """Capture a serialized click-time snapshot for the AI worker.

        This slot performs only database reads and serialization. It emits the
        snapshot and immediately returns so subsequent database work is not
        blocked by model requests.

        Args:
            job_id: Stable analysis job identifier.
            world_id: ID of the world being captured.
            analysis_type: Requested intelligence analysis scope.
        """
        if self.db_service is None:
            self.intelligence_snapshot_failed.emit(
                job_id, "Database is not ready for AI analysis."
            )
            return

        try:
            from src.services.intelligence_analyzer import (
                build_intelligence_analysis_snapshot,
            )

            self.db_service.ensure_fresh_view()
            snapshot = build_intelligence_analysis_snapshot(
                self.db_service,
                world_id=world_id,
                analysis_type=analysis_type,
                options=options,
            )
            self.intelligence_snapshot_ready.emit(job_id, snapshot)
        except Exception as exc:
            logger.error(
                "Intelligence snapshot error: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            self.intelligence_snapshot_failed.emit(job_id, str(exc))
