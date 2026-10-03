"""Database Service Module. Provides the low-level SQL interface to the SQLite database.
Follows the Hybrid Schema (Strict Columns + JSON Attributes).

This service now uses specialized repository classes for better separation of concerns
and maintainability.
"""

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from src.core.calendar import CalendarConfig
from src.core.entities import Entity
from src.core.events import Event
from src.core.map import Map
from src.core.marker import Marker
from src.services.migrations import prepare_database

# Import repositories for modular CRUD operations
from src.services.repositories import (
    AttachmentRepository,
    CalendarRepository,
    EntityRepository,
    EventRepository,
    FeatureGeometryRepository,
    MapRepository,
    MetaRepository,
    RelationRepository,
    TagRepository,
    TrajectoryRepository,
)
from src.services.repositories.meta_repository import ObjectDisplayMetadata

if TYPE_CHECKING:
    from src.core.trajectory import Keyframe
    from src.services.attachment_service import AttachmentService
    from src.services.repositories.trajectory_repository import TrajectorySnapshot

logger = logging.getLogger(__name__)


class DatabaseService:
    """Handles all raw interactions with the SQLite database. Implements the Hybrid
    Schema (Strict Columns + JSON Attributes).

    This service delegates CRUD operations to specialized repository classes while
    maintaining schema management and connection handling.

    Repositories can be injected via the constructor for testing or custom
    configurations. When omitted, default repository instances are created.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        read_only: bool = False,
        world_root: Path | None = None,
        event_repo: Optional[EventRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        relation_repo: Optional[RelationRepository] = None,
        map_repo: Optional[MapRepository] = None,
        calendar_repo: Optional[CalendarRepository] = None,
        attachment_repo: Optional[AttachmentRepository] = None,
        trajectory_repo: Optional[TrajectoryRepository] = None,
        feature_geometry_repo: Optional[FeatureGeometryRepository] = None,
        tag_repo: Optional[TagRepository] = None,
        meta_repo: Optional[MetaRepository] = None,
    ) -> None:
        """Initializes the database service with optional dependency injection.

        Args:
            db_path: Path to the .kraken database file.
                     Defaults to :memory: for testing.
            read_only: Open an existing database without permitting writes or
                running schema initialization and migrations.
            world_root: Manifest and asset directory when the database is external.
            event_repo: Optional EventRepository instance (injected for testing).
            entity_repo: Optional EntityRepository instance.
            relation_repo: Optional RelationRepository instance.
            map_repo: Optional MapRepository instance.
            calendar_repo: Optional CalendarRepository instance.
            attachment_repo: Optional AttachmentRepository instance.
            trajectory_repo: Optional TrajectoryRepository instance.
            tag_repo: Optional TagRepository instance.
            meta_repo: Optional MetaRepository instance.

        """
        self.db_path = db_path
        self.read_only = read_only
        self.world_root = world_root
        self.migration_status: dict[str, Any] = {}
        self._connection: Optional[sqlite3.Connection] = None
        self._connection_thread_id: int | None = None
        self._backup_service = None

        self._event_repo = event_repo or EventRepository()
        self._entity_repo = entity_repo or EntityRepository()
        self._relation_repo = relation_repo or RelationRepository()
        self._map_repo = map_repo or MapRepository()
        self._calendar_repo = calendar_repo or CalendarRepository()
        self._attachment_repo = attachment_repo or AttachmentRepository()
        self._trajectory_repo = trajectory_repo or TrajectoryRepository()
        self._feature_geometry_repo = (
            feature_geometry_repo or FeatureGeometryRepository()
        )
        self._tag_repo = tag_repo or TagRepository()
        self._meta_repo = meta_repo or MetaRepository()
        self.attachment_service: Optional["AttachmentService"] = None

        logger.info(f"DatabaseService initialized with path: {self.db_path}")

    def connect(self) -> None:
        """Establishes connection to the database."""
        if self.is_connected():
            self.require_connection()
            return
        try:
            if self.read_only:
                if self.db_path == ":memory:":
                    raise ValueError("Read-only databases must use a file path")
                database_uri = f"{Path(self.db_path).resolve().as_uri()}?mode=ro"
                self._connection = sqlite3.connect(database_uri, uri=True)
                self._connection.execute("PRAGMA query_only = ON;")
            else:
                self._connection = sqlite3.connect(self.db_path)
            self._connection_thread_id = threading.get_ident()
            self._connection.execute("PRAGMA foreign_keys = ON;")
            self._connection.row_factory = sqlite3.Row
            logger.debug("Database connection established.")

            self.migration_status = prepare_database(
                self._connection,
                self.db_path,
                read_only=self.read_only,
                world_root=self.world_root,
            )
            if not self.read_only and self.db_path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL;")

            # Connect repositories to the database connection
            self._event_repo.set_connection(self._connection)
            self._entity_repo.set_connection(self._connection)
            self._relation_repo.set_connection(self._connection)
            self._map_repo.set_connection(self._connection)
            self._calendar_repo.set_connection(self._connection)
            self._attachment_repo.set_connection(self._connection)
            self._trajectory_repo.set_connection(self._connection)
            self._feature_geometry_repo.set_connection(self._connection)
            self._tag_repo.set_connection(self._connection)
            self._meta_repo.set_connection(self._connection)

        except Exception:
            self.close()
            logger.exception("Failed to connect to database: %s", self.db_path)
            raise

    def close(self) -> None:
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed.")
        self._connection_thread_id = None

    def is_connected(self) -> bool:
        """Checks if the database connection is established.

        Returns:
            bool: True if connected, False otherwise.

        """
        return self._connection is not None

    def require_connection(self) -> sqlite3.Connection:
        """Return the open connection on its owning thread without opening it.

        Returns:
            The active SQLite connection, whose transaction belongs to its caller.

        Raises:
            RuntimeError: If disconnected or called outside the owning thread.
        """
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        if self._connection_thread_id != threading.get_ident():
            raise RuntimeError("Database connection belongs to another thread")
        return self._connection

    def get_connection(self) -> sqlite3.Connection:
        """Gets the database connection, establishing it if necessary.

        Returns:
            The active connection. Connection failures propagate to the caller.

        """
        if not self._connection:
            self.connect()
        return self.require_connection()

    @property
    def map_repo(self) -> MapRepository:
        """Gets the map repository.

        Returns:
            MapRepository: The map repository instance.

        Raises:
            RuntimeError: If the repository is not initialized.

        """
        if not self._map_repo:
            raise RuntimeError("Map repository not initialized")
        return self._map_repo

    @property
    def trajectory_repo(self) -> TrajectoryRepository:
        """Gets the trajectory repository used by aggregate commands."""
        if not self._trajectory_repo:
            raise RuntimeError("Trajectory repository not initialized")
        return self._trajectory_repo

    @property
    def feature_geometry_repo(self) -> FeatureGeometryRepository:
        """Get the dated feature-geometry repository."""
        return self._feature_geometry_repo

    def get_attachment_repo(self) -> AttachmentRepository:
        """Gets the attachment repository.

        Returns:
            AttachmentRepository: The attachment repository instance.

        Raises:
            RuntimeError: If the repository is not initialized (connection not established).

        """
        if not self._attachment_repo:
            raise RuntimeError("Attachment repository not initialized")
        return self._attachment_repo

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Safe context manager for transactions."""
        connection = self.get_connection()
        owns_transaction = not connection.in_transaction
        try:
            if owns_transaction:
                connection.execute("BEGIN")
            yield connection
            if owns_transaction:
                connection.commit()
        except Exception as e:
            if owns_transaction:
                connection.rollback()
            if not getattr(e, "silent_transaction_rollback", False):
                logger.error(f"Transaction rolled back due to error: {e}")
            raise

    def ensure_fresh_view(self) -> None:
        """Checkpoint when idle without ending a caller-owned transaction.

        Active transactions retain their snapshot until their owner ends them.
        Later reads naturally see committed WAL changes. Disconnected services
        remain disconnected; checkpoint failures are best-effort.
        """
        if not self.is_connected():
            return
        connection = self.require_connection()
        if connection.in_transaction:
            return
        try:
            connection.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except sqlite3.Error:
            logger.debug("Idle WAL checkpoint unavailable", exc_info=True)

    # --------------------------------------------------------------------------
    # Event CRUD - Delegates to EventRepository
    # --------------------------------------------------------------------------

    def insert_event(self, event: Event) -> None:
        """Inserts a new event or updates an existing one (Upsert).

        Args:
            event (Event): The event domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._event_repo.insert(event)

    def get_event(self, event_id: str) -> Optional[Event]:
        """Retrieves a single event by its UUID.

        Args:
            event_id (str): The unique identifier of the event.

        Returns:
            Optional[Event]: The Event object if found, else None.

        """
        if not self._connection:
            self.connect()
        return self._event_repo.get(event_id)

    def get_all_events(self) -> List[Event]:
        """Retrieves all events from the database, sorted chronologically.

        Returns:
            List[Event]: A list of all Event objects in the database.

        """
        return self.get_events()

    def get_events(self, event_type: Optional[str] = None) -> List[Event]:
        """Retrieves events, optionally filtered by type.

        Args:
            event_type: Optional type filter.

        Returns:
            List[Event]: List of matching Event objects.

        """
        if not self._connection:
            self.connect()
        if event_type:
            return self._event_repo.get_by_type(event_type)
        return self._event_repo.get_all()

    def delete_event(self, event_id: str) -> None:
        """Deletes an event permanently.

        Args:
            event_id (str): The unique identifier of the event to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._event_repo.delete(event_id)

    # --------------------------------------------------------------------------
    # Entity CRUD - Delegates to EntityRepository
    # --------------------------------------------------------------------------

    def insert_entity(self, entity: Entity) -> None:
        """Inserts a new entity or updates an existing one (Upsert).

        Args:
            entity (Entity): The entity domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._entity_repo.insert(entity)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Retrieves a single entity by its UUID.

        Args:
            entity_id (str): The unique identifier of the entity.

        Returns:
            Optional[Entity]: The Entity object if found, else None.

        """
        if not self._connection:
            self.connect()
        return self._entity_repo.get(entity_id)

    def get_all_entities(self) -> List[Entity]:
        """Retrieves all entities from the database.

        Returns:
            List[Entity]: A list of all Entity objects.

        """
        return self.get_entities()

    def get_entities(self, entity_type: Optional[str] = None) -> List[Entity]:
        """Retrieves entities, optionally filtered by type.

        Args:
            entity_type: Optional type filter.

        Returns:
            List[Entity]: List of matching Entity objects.

        """
        if not self._connection:
            self.connect()
        if entity_type:
            return self._entity_repo.get_by_type(entity_type)
        return self._entity_repo.get_all()

    def delete_entity(self, entity_id: str) -> None:
        """Deletes an entity permanently.

        Args:
            entity_id (str): The unique identifier of the entity to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._entity_repo.delete(entity_id)

    # --------------------------------------------------------------------------
    # Relation CRUD - Delegates to RelationRepository
    # --------------------------------------------------------------------------

    def _validate_relation_endpoint(self, endpoint_id: str, role: str) -> None:
        """Require a canonical UUID belonging to an entity or event."""
        try:
            canonical = str(uuid.UUID(endpoint_id))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                f"Relation {role} must be a canonical UUID: {endpoint_id!r}"
            ) from exc
        if endpoint_id != canonical:
            raise ValueError(
                f"Relation {role} must be a canonical UUID: {endpoint_id!r}"
            )
        if self.get_entity(endpoint_id) is None and self.get_event(endpoint_id) is None:
            raise ValueError(f"Relation {role} endpoint does not exist: {endpoint_id}")

    def insert_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Creates a directed relationship between two objects.

        Args:
            source_id (str): ID of the source object.
            target_id (str): ID of the target object.
            rel_type (str): Type of relationship (e.g., "caused").
            attributes (Dict[str, Any]): Optional metadata.

        Returns:
            str: The UUID of the newly created relation.

        Raises:
            sqlite3.Error: If DB fails.

        """
        if attributes is None:
            attributes = {}
        if rel_type == "mentions":
            raise ValueError(
                "The 'mentions' relation type is system-managed by wikilinks."
            )
        self._validate_relation_endpoint(source_id, "source")
        self._validate_relation_endpoint(target_id, "target")

        rel_id = str(uuid.uuid4())
        created_at = time.time()

        self._relation_repo.insert(
            rel_id, source_id, target_id, rel_type, attributes, created_at
        )

        logger.info(
            f"DB: Inserted relation {rel_id}: {source_id} -> {target_id} ({rel_type})"
        )
        return rel_id

    def reconcile_mentions(
        self,
        source_id: str,
        field: str,
        occurrences_by_target: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Reconcile one field's generated wikilink mentions atomically."""
        return self._relation_repo.reconcile_mentions(
            source_id,
            field,
            occurrences_by_target,
        )

    def restore_mentions(self, source_id: str, relations: List[Dict[str, Any]]) -> None:
        """Restore an exact snapshot of a source's generated mentions."""
        self._relation_repo.restore_mentions(source_id, relations)

    def get_all_relations(self) -> List[Dict[str, Any]]:
        """Retrieves all relations from the database.

        Returns:
            List of relation dictionaries with keys: id, source_id, target_id,
            rel_type, attributes, created_at.

        """
        if not self._connection:
            self.connect()
        return self._relation_repo.get_all()

    def get_relations_for_item(self, item_id: str) -> List[Dict[str, Any]]:
        """Retrieves all relations where the item is either source or target.

        Args:
            item_id: The ID of the item (event or entity).

        Returns:
            List of relation dictionaries.

        """
        if not self._connection:
            self.connect()
        return self._relation_repo.get_for_item(item_id)

    def delete_relations_for_item(self, item_id: str) -> None:
        """Deletes all relations where the item is either source or target.

        Args:
            item_id: The ID of the item.

        Raises:
            sqlite3.Error: If DB fails.

        """
        if not self._connection:
            self.connect()
        self._relation_repo.delete_for_item(item_id)

    def get_relations(self, source_id: str) -> List[Dict[str, Any]]:
        """Retrieves all outgoing relations for a given source object.

        Args:
            source_id (str): The ID of the source object.

        Returns:
            List[Dict[str, Any]]: List of relation dictionaries.

        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        return self._relation_repo.get_by_source(source_id)

    def get_incoming_relations(self, target_id: str) -> List[Dict[str, Any]]:
        """Retrieves all incoming relations for a given target object.

        Args:
            target_id (str): The ID of the target object.

        Returns:
            List[Dict[str, Any]]: List of relation dictionaries.

        """
        if not self._connection:
            self.connect()
        return self._relation_repo.get_by_target(target_id)

    def get_relation(self, rel_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single relation by its ID.

        Args:
            rel_id: The unique identifier of the relation.

        Returns:
            A dictionary containing the relation data (keys: ``id``,
            ``source_id``, ``target_id``, ``rel_type``, ``attributes``,
            ``created_at``), or ``None`` if no relation with that ID exists.

        """
        return self._relation_repo.get_by_id(rel_id)

    def delete_relation(self, rel_id: str) -> None:
        """Deletes a relationship by its ID.

        Args:
            rel_id (str): The unique identifier of the relation.

        """
        if not self._connection:
            self.connect()
        self._relation_repo.delete(rel_id)

    def update_relation(
        self,
        rel_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates an existing relationship's target, type, and attributes.

        Args:
            rel_id: The unique identifier of the relation to update.
            target_id: New target object ID for the relation.
            rel_type: New relationship type label (e.g. ``"caused"``).
            attributes: Optional metadata dict to replace the existing
                attributes.  Defaults to an empty dict when omitted.

        """
        if attributes is None:
            attributes = {}
        if rel_type == "mentions":
            raise ValueError(
                "The 'mentions' relation type is system-managed by wikilinks."
            )
        self._validate_relation_endpoint(target_id, "target")
        self._relation_repo.update(rel_id, rel_type, attributes, target_id=target_id)

    def get_name(self, object_id: str) -> Optional[str]:
        """Retrieves the display name of an entity or event by its ID.

        Queries the unified meta-repository which covers both the ``events``
        and ``entities`` tables, so the caller does not need to know which
        table the object lives in.

        Args:
            object_id: The UUID of the entity or event.

        Returns:
            The ``name`` column value if the object exists, otherwise ``None``.

        """
        return self._meta_repo.get_name(object_id)

    def get_object_display_metadata(
        self, object_ids: Iterable[str]
    ) -> dict[str, ObjectDisplayMetadata]:
        """Resolve Event and Entity display metadata in bounded batches."""
        return self._meta_repo.get_object_display_metadata(object_ids)

    def insert_events_bulk(self, events: List[Event]) -> None:
        """Inserts multiple events efficiently using executemany.

        This method is optimized for bulk operations, reducing the overhead
        of individual inserts by using SQLite's executemany. Provides
        approximately 50-100x performance improvement over individual inserts
        for large datasets by reducing transaction overhead.

        Args:
            events (List[Event]): List of Event objects to insert.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._event_repo.insert_bulk(events)
        logger.info(f"Bulk inserted {len(events)} events")

    def insert_entities_bulk(self, entities: List[Entity]) -> None:
        """Inserts multiple entities efficiently using executemany.

        This method is optimized for bulk operations, reducing the overhead
        of individual inserts by using SQLite's executemany. Provides
        approximately 50-100x performance improvement over individual inserts
        for large datasets by reducing transaction overhead.

        Args:
            entities (List[Entity]): List of Entity objects to insert.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._entity_repo.insert_bulk(entities)
        logger.info(f"Bulk inserted {len(entities)} entities")

    # --------------------------------------------------------------------------
    # Calendar Config CRUD - Delegates to CalendarRepository
    # --------------------------------------------------------------------------

    def insert_calendar_config(self, config: CalendarConfig) -> None:
        """Inserts a new calendar config or updates an existing one (Upsert).

        Args:
            config (CalendarConfig): The calendar configuration to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._calendar_repo.insert(config)
        logger.debug(f"Inserted/updated calendar config: {config.id}")

    def get_calendar_config(self, config_id: str) -> Optional[CalendarConfig]:
        """Retrieves a single calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the calendar config.

        Returns:
            Optional[CalendarConfig]: The config if found, else None.

        """
        if not self._connection:
            self.connect()
        return self._calendar_repo.get(config_id)

    def get_all_calendar_configs(self) -> List[CalendarConfig]:
        """Retrieves all calendar configurations.

        Returns:
            List[CalendarConfig]: A list of all calendar configs.

        """
        if not self._connection:
            self.connect()
        return self._calendar_repo.get_all()

    def get_active_calendar_config(self) -> Optional[CalendarConfig]:
        """Retrieves the currently active calendar configuration.

        Returns:
            Optional[CalendarConfig]: The active config if found, else None.

        """
        if not self._connection:
            self.connect()
        return self._calendar_repo.get_active()

    def delete_calendar_config(self, config_id: str) -> None:
        """Deletes a calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the config to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._calendar_repo.delete(config_id)
        logger.debug(f"Deleted calendar config: {config_id}")

    def set_active_calendar_config(self, config_id: str) -> None:
        """Sets a calendar config as the active one.

        Deactivates any currently active config and activates the specified one.

        Args:
            config_id (str): The ID of the config to activate.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._calendar_repo.set_active(config_id)
        logger.debug(f"Set active calendar config: {config_id}")

    # --------------------------------------------------------------------------
    # System Meta (for current_time and other world settings)
    # --------------------------------------------------------------------------

    def get_current_time(self) -> Optional[float]:
        """Retrieves the current time in the world from system_meta."""
        return self._meta_repo.get_current_time()

    def set_current_time(self, current_time: float) -> None:
        """Sets the current time in the world and persists it to system_meta."""
        self._meta_repo.set_current_time(current_time)

    def get_world_theme(self) -> Optional[str]:
        """Retrieves the saved theme name for this world from system_meta."""
        return self._meta_repo.get_world_theme()

    def set_world_theme(self, theme_name: str) -> None:
        """Persists the active theme name for this world in system_meta."""
        self._meta_repo.set_world_theme(theme_name)

    def get_ai_generation_preferences(self) -> Optional[Dict[str, Any]]:
        """Retrieve portable AI generation preferences for this world."""
        return self._meta_repo.get_ai_generation_preferences()

    def set_ai_generation_preferences(self, data: Dict[str, Any]) -> None:
        """Persist portable AI generation preferences for this world."""
        self._meta_repo.set_ai_generation_preferences(data)

    # --------------------------------------------------------------------------
    # Map CRUD - Delegates to MapRepository
    # --------------------------------------------------------------------------

    def insert_map(self, map_obj: Map) -> None:
        """Inserts a new map or updates an existing one (Upsert).

        Args:
            map_obj (Map): The map domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._map_repo.insert_map(map_obj)

    def get_map(self, map_id: str) -> Optional[Map]:
        """Retrieves a single map by its UUID.

        Args:
            map_id (str): The unique identifier of the map.

        Returns:
            Optional[Map]: The Map object if found, else None.

        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_map(map_id)

    def get_all_maps(self) -> List[Map]:
        """Retrieves all maps from the database.

        Returns:
            List[Map]: List of all Map objects.

        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_all_maps()

    def delete_map(self, map_id: str) -> None:
        """Deletes a map and all its markers from the database.

        Args:
            map_id (str): The unique identifier of the map to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            self.connect()
        self._map_repo.delete_map(map_id)

    # --------------------------------------------------------------------------
    # Marker CRUD - Delegates to MapRepository
    # --------------------------------------------------------------------------

    def insert_marker(self, marker: Marker) -> str:
        """Inserts a new marker/feature or updates an existing one (Upsert)."""
        return self._map_repo.insert_marker(marker)

    def get_marker(self, marker_id: str) -> Optional[Marker]:
        """Retrieves a single marker by its UUID."""
        return self._map_repo.get_marker(marker_id)

    def get_markers_for_map(self, map_id: str) -> List[Marker]:
        """Retrieves all markers for a specific map."""
        return self._map_repo.get_markers_by_map(map_id)

    def get_markers_for_object(self, object_id: str, object_type: str) -> List[Marker]:
        """Retrieves all markers for a specific entity or event."""
        return self._map_repo.get_markers_for_object(object_id, object_type)

    def get_marker_by_composite(
        self, map_id: str, object_id: str, object_type: str
    ) -> Optional[Marker]:
        """Retrieves a marker by its composite key (map_id, object_id, object_type)."""
        return self._map_repo.get_marker_by_composite(map_id, object_id, object_type)

    def delete_marker(self, marker_id: str) -> int:
        """Deletes a marker from the database.

        Returns:
            int: Number of rows deleted (1 if found, 0 if not found).
        """
        return self._map_repo.delete_marker(marker_id)

    # --------------------------------------------------------------------------
    # Tag Management - Delegates to TagRepository
    # --------------------------------------------------------------------------

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """Retrieves all tags from the database."""
        return self._tag_repo.get_all_tags()

    def get_tags_with_events(self) -> List[Dict[str, Any]]:
        """Retrieves tags that are associated with at least one event."""
        return self._tag_repo.get_tags_with_events()

    def get_active_tags(self) -> List[Dict[str, Any]]:
        """Retrieves tags associated with at least one event or entity."""
        return self._tag_repo.get_active_tags()

    def get_tag_by_name(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a tag by its name."""
        return self._tag_repo.get_tag_by_name(tag_name)

    def create_tag(self, tag_name: str) -> str:
        """Creates a new tag or returns existing tag ID."""
        return self._tag_repo.create_tag(tag_name)

    def delete_tag(self, tag_name: str) -> None:
        """Deletes a tag and all its associations."""
        self._tag_repo.delete_tag(tag_name)

    def assign_tag_to_event(self, event_id: str, tag_name: str) -> None:
        """Assigns a tag to an event, creating the tag if it doesn't exist."""
        self._tag_repo.assign_tag_to_event(event_id, tag_name)

    def assign_tag_to_entity(self, entity_id: str, tag_name: str) -> None:
        """Assigns a tag to an entity, creating the tag if it doesn't exist."""
        self._tag_repo.assign_tag_to_entity(entity_id, tag_name)

    def remove_tag_from_event(self, event_id: str, tag_name: str) -> None:
        """Removes a tag from an event."""
        self._tag_repo.remove_tag_from_event(event_id, tag_name)

    def remove_tag_from_entity(self, entity_id: str, tag_name: str) -> None:
        """Removes a tag from an entity."""
        self._tag_repo.remove_tag_from_entity(entity_id, tag_name)

    def get_tags_for_event(self, event_id: str) -> List[Dict[str, Any]]:
        """Retrieves all tags for a specific event."""
        return self._tag_repo.get_tags_for_event(event_id)

    def get_tags_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """Retrieves all tags for a specific entity."""
        return self._tag_repo.get_tags_for_entity(entity_id)

    def get_entity_tag_memberships(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return all Entity-to-tag memberships for read-side projections."""
        return self._tag_repo.get_entity_tag_memberships()

    def get_events_by_tag(self, tag_name: str) -> List[Event]:
        """Retrieves all events that have a specific tag."""
        return self._tag_repo.get_events_by_tag(tag_name)

    def get_entities_by_tag(self, tag_name: str) -> List[Entity]:
        """Retrieves all entities that have a specific tag."""
        return self._tag_repo.get_entities_by_tag(tag_name)

    def get_events_grouped_by_tags(
        self,
        tag_order: List[str],
        mode: str = "DUPLICATE",
        date_range: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """Groups events by tags with support for DUPLICATE and FIRST_MATCH modes."""
        return self._tag_repo.get_events_grouped_by_tags(tag_order, mode, date_range)

    def get_group_counts(
        self,
        tag_order: List[str],
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Returns count and metadata for each tag group."""
        return self._tag_repo.get_group_counts(tag_order, date_range)

    def get_group_metadata(
        self,
        tag_order: List[str],
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Returns metadata for each tag group including color, count, and date span."""
        return self._tag_repo.get_group_metadata(tag_order, date_range)

    def get_events_for_group(
        self,
        tag_name: str,
        date_range: Optional[tuple] = None,
    ) -> List[Event]:
        """Returns all events for a specific tag group."""
        return self._tag_repo.get_events_for_group(tag_name, date_range)

    def set_tag_color(self, tag_name: str, color: Optional[str]) -> None:
        """Sets the color for a tag."""
        self._tag_repo.set_tag_color(tag_name, color)

    def get_tag_color(self, tag_name: str) -> str:
        """Gets the color for a tag, generating one if not set."""
        return self._tag_repo.get_tag_color(tag_name)

    def filter_ids_by_tags(
        self,
        object_type: Optional[str] = None,
        include: Optional[List[str]] = None,
        include_mode: str = "any",
        exclude: Optional[List[str]] = None,
        exclude_mode: str = "any",
        case_sensitive: bool = False,
    ) -> List[tuple[str, str]]:
        """Convenience wrapper for tag-based filtering of entities and events."""
        return self._tag_repo.filter_ids_by_tags(
            object_type=object_type,
            include=include,
            include_mode=include_mode,
            exclude=exclude,
            exclude_mode=exclude_mode,
            case_sensitive=case_sensitive,
        )

    def get_objects_by_ids(
        self, object_ids: List[tuple[str, str]]
    ) -> tuple[List[Event], List[Entity]]:
        """Retrieves full object instances for a list of (type, id) tuples."""
        return self._tag_repo.get_objects_by_ids(object_ids)

    # --------------------------------------------------------------------------
    # Meta / Config - Delegates to MetaRepository
    # --------------------------------------------------------------------------

    def set_timeline_grouping_config(
        self,
        tag_order: List[str],
        mode: str = "DUPLICATE",
    ) -> None:
        """Stores timeline grouping configuration."""
        self._meta_repo.set_timeline_grouping_config(tag_order, mode)

    def get_timeline_grouping_config(self) -> Optional[Dict[str, Any]]:
        """Retrieves timeline grouping configuration."""
        return self._meta_repo.get_timeline_grouping_config()

    def clear_timeline_grouping_config(self) -> None:
        """Clears timeline grouping configuration."""
        self._meta_repo.clear_timeline_grouping_config()

    def get_graph_lexicon(self) -> Optional[Dict[str, Any]]:
        """Retrieves the graph visual lexicon configuration."""
        return self._meta_repo.get_graph_lexicon()

    def set_graph_lexicon(self, data: Dict[str, Any]) -> None:
        """Stores the graph visual lexicon configuration."""
        self._meta_repo.set_graph_lexicon(data)

    # --------------------------------------------------------------------------
    # Temporal Trajectories - Delegates to TrajectoryRepository
    # --------------------------------------------------------------------------

    def insert_trajectory(
        self,
        marker_id: str,
        trajectory: List["Keyframe"],
        properties: Optional[dict] = None,
    ) -> str:
        """Inserts a spatial trajectory for a marker.

        Args:
            marker_id: UUID of the marker.
            trajectory: List of Keyframe objects.
            properties: Optional JSON metadata.

        Returns:
            UUID of the inserted trajectory record.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.insert(marker_id, trajectory, properties)

    def get_trajectories_by_map(
        self, map_id: str
    ) -> List[Tuple[str, str, List["Keyframe"]]]:
        """Retrieves all trajectories for a specific map.

        Args:
            map_id: UUID of the map.

        Returns:
            List of (marker_id, trajectory_id, List[Keyframe]) tuples.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_by_map_id(map_id)

    def get_trajectory_snapshots_by_map(self, map_id: str) -> list[dict[str, object]]:
        """Return map-scoped serializable trajectory snapshots.

        Args:
            map_id: UUID of the map.

        Returns:
            JSON-safe trajectory records with exact row snapshots.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_snapshots_by_map_id(map_id)

    def get_trajectories_by_marker(
        self, marker_id: str
    ) -> List[Tuple[str, List["Keyframe"]]]:
        """Retrieves all trajectories for a specific marker.

        Args:
            marker_id: UUID of the marker.

        Returns:
            List of (trajectory_id, List[Keyframe]) tuples.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_by_marker_db_id(marker_id)

    def get_marker_trajectory_snapshot(
        self, map_id: str, object_id: str
    ) -> Optional["TrajectorySnapshot"]:
        """Return one marker's exact trajectory row snapshot.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.

        Returns:
            Exact trajectory row state, or ``None`` when no row exists.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_marker_trajectory_snapshot(map_id, object_id)

    def set_marker_trajectory(
        self,
        map_id: str,
        object_id: str,
        keyframes: List["Keyframe"],
        *,
        properties: Optional[dict] = None,
        expected_snapshot: Optional["TrajectorySnapshot"],
    ) -> Optional["TrajectorySnapshot"]:
        """Atomically replace a marker's complete trajectory.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.
            keyframes: Complete desired keyframe state.
            properties: Complete desired trajectory properties, or ``None``
                to preserve the current row properties.
            expected_snapshot: Exact state expected before replacement.

        Returns:
            Exact persisted row state, or ``None`` after deletion.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.set_marker_trajectory(
            map_id,
            object_id,
            keyframes,
            properties=properties,
            expected_snapshot=expected_snapshot,
        )

    def restore_marker_trajectory_snapshot(
        self,
        map_id: str,
        object_id: str,
        snapshot: Optional["TrajectorySnapshot"],
        *,
        expected_snapshot: Optional["TrajectorySnapshot"],
    ) -> Optional["TrajectorySnapshot"]:
        """Restore an exact trajectory row for undo or redo.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.
            snapshot: Exact desired row, or ``None`` for no trajectory.
            expected_snapshot: Exact state expected before restoration.

        Returns:
            Restored row state, or ``None`` after deletion.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.restore_marker_trajectory_snapshot(
            map_id,
            object_id,
            snapshot,
            expected_snapshot=expected_snapshot,
        )

    def register_backup_service(self, backup_service: Any) -> None:
        """Registers a backup service for integration with database operations.

        Args:
            backup_service: The BackupService instance to register.

        """
        self._backup_service = backup_service
        logger.debug("Backup service registered with DatabaseService")

    def get_db_file_path(self) -> str:
        """Returns the current database file path.

        Returns:
            str: Path to the database file.

        """
        return self.db_path

    def vacuum(self) -> bool:
        """Runs VACUUM on the database to reclaim space and optimize storage. This can
        be slow for large databases and should be run infrequently.

        Returns:
            bool: True if successful, False otherwise.

        """
        if not self._connection:
            logger.error("Cannot vacuum: no database connection")
            return False

        if self.db_path == ":memory:":
            logger.warning("Skipping vacuum on in-memory database")
            return True

        try:
            logger.info("Running VACUUM on database...")
            self._connection.execute("VACUUM")
            logger.info("VACUUM completed successfully")
            return True
        except sqlite3.Error as e:
            logger.error(f"VACUUM failed: {e}")
            return False

    # --------------------------------------------------------------------------
    # Embedding Stats
    # --------------------------------------------------------------------------

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Returns aggregate statistics for the embeddings table.

        Returns:
            Dict[str, Any]: A dictionary with ``"count"`` (int) and
                ``"last_updated"`` (float or None) keys.

        """
        if not self._connection:
            return {"count": 0, "last_updated": None}

        try:
            row = self._connection.execute(
                "SELECT COUNT(*) AS cnt, MAX(created_at) AS latest FROM embeddings"
            ).fetchone()
            return {
                "count": row["cnt"] if row else 0,
                "last_updated": row["latest"] if row else None,
            }
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {"count": 0, "last_updated": None}
