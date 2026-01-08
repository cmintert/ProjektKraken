"""
Database Service Module.
Provides the low-level SQL interface to the SQLite database.
Follows the Hybrid Schema (Strict Columns + JSON Attributes).

This service now uses specialized repository classes for better
separation of concerns and maintainability.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from src.core.calendar import CalendarConfig
from src.core.entities import Entity
from src.core.events import Event
from src.core.map import Map
from src.core.marker import Marker

# Import repositories for modular CRUD operations
from src.services.repositories import (
    AttachmentRepository,
    CalendarRepository,
    EntityRepository,
    EventRepository,
    MapRepository,
    RelationRepository,
    TrajectoryRepository,
)

if TYPE_CHECKING:
    from src.core.trajectory import Keyframe
    from src.services.attachment_service import AttachmentService

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Handles all raw interactions with the SQLite database.
    Implements the Hybrid Schema (Strict Columns + JSON Attributes).

    This service delegates CRUD operations to specialized repository
    classes while maintaining schema management and connection handling.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """
        Args:
            db_path: Path to the .kraken database file.
                     Defaults to :memory: for testing.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

        # Initialize repositories (will be connected after connection is established)
        self._event_repo = EventRepository()
        self._entity_repo = EntityRepository()
        self._relation_repo = RelationRepository()
        self._map_repo = MapRepository()
        self._calendar_repo = CalendarRepository()
        self._attachment_repo = AttachmentRepository()
        self._trajectory_repo = TrajectoryRepository()
        self.attachment_service: Optional["AttachmentService"] = None

        logger.info(f"DatabaseService initialized with path: {self.db_path}")

    def connect(self) -> None:
        """Establishes connection to the database."""
        try:
            self._connection = sqlite3.connect(self.db_path)
            # Enable Foreign Keys
            self._connection.execute("PRAGMA foreign_keys = ON;")
            # Enable Write-Ahead Logging for better concurrency
            # WAL mode allows concurrent readers with a single writer
            if self.db_path != ":memory:":
                self._connection.execute("PRAGMA journal_mode=WAL;")
                logger.debug("WAL mode enabled for database.")
            # Return rows as Row objects for name access
            self._connection.row_factory = sqlite3.Row
            logger.debug("Database connection established.")

            self._init_schema()
            self._run_migrations()

            # Connect repositories to the database connection
            self._event_repo.set_connection(self._connection)
            self._entity_repo.set_connection(self._connection)
            self._relation_repo.set_connection(self._connection)
            self._map_repo.set_connection(self._connection)
            self._calendar_repo.set_connection(self._connection)
            self._attachment_repo.set_connection(self._connection)
            self._trajectory_repo.set_connection(self._connection)

        except sqlite3.Error as e:
            logger.critical(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed.")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Safe context manager for transactions."""
        if not self._connection:
            self.connect()
        assert self._connection is not None
        try:
            yield self._connection
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise

    def _init_schema(self) -> None:
        """Creates the core tables if they don't exist."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS system_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            lore_date REAL NOT NULL,
            lore_duration REAL DEFAULT 0.0,
            description TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL
        );

        -- Generic Relation Table
        CREATE TABLE IF NOT EXISTS relations (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            rel_type TEXT NOT NULL,
            attributes JSON DEFAULT '{}',
            created_at REAL
        );
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_events_date ON events(lore_date);
        CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);

        -- Calendar Configuration Table
        CREATE TABLE IF NOT EXISTS calendar_config (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            created_at REAL,
            modified_at REAL
        );

        -- Map Table
        CREATE TABLE IF NOT EXISTS maps (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            description TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL
        );

        -- Marker Table
        CREATE TABLE IF NOT EXISTS markers (
            id TEXT PRIMARY KEY,
            map_id TEXT NOT NULL,
            object_id TEXT NOT NULL,
            object_type TEXT NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            label TEXT,
            attributes JSON DEFAULT '{}',
            created_at REAL,
            modified_at REAL,
            UNIQUE(map_id, object_id, object_type),
            FOREIGN KEY(map_id) REFERENCES maps(id) ON DELETE CASCADE
        );

        -- Indexes for markers
        CREATE INDEX IF NOT EXISTS idx_markers_map ON markers(map_id);
        CREATE INDEX IF NOT EXISTS idx_markers_object
            ON markers(object_id, object_type);

        -- Moving Features Table (Temporal Trajectories)
        CREATE TABLE IF NOT EXISTS moving_features (
            id TEXT PRIMARY KEY,
            marker_id TEXT NOT NULL,
            t_start REAL NOT NULL,
            t_end REAL NOT NULL,
            trajectory JSON NOT NULL, -- List of [t, x, y]
            properties JSON DEFAULT '{}', -- Changing properties over time
            created_at REAL,
            FOREIGN KEY(marker_id) REFERENCES markers(id) ON DELETE CASCADE
        );

        -- Indexes for temporal queries
        CREATE INDEX IF NOT EXISTS idx_moving_features_marker
            ON moving_features(marker_id);
        CREATE INDEX IF NOT EXISTS idx_moving_features_time
            ON moving_features(t_start, t_end);

        -- Image Attachments Table
        CREATE TABLE IF NOT EXISTS image_attachments (
            id TEXT PRIMARY KEY,
            owner_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            image_rel_path TEXT NOT NULL,
            thumb_rel_path TEXT,
            caption TEXT,
            order_index INTEGER DEFAULT 0,
            created_at REAL,
            -- Stored as "widthxheight" or JSON [w, h]
            resolution TEXT,
            source TEXT
        );

        -- Indexes for image attachments
        CREATE INDEX IF NOT EXISTS idx_attachments_owner
            ON image_attachments(owner_type, owner_id);

        -- Normalized Tags Tables
        -- Tags table: stores unique tag names
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            color TEXT,
            created_at REAL NOT NULL
        );

        -- Create index on tag name for fast lookups
        CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);

        -- Event-Tag association table
        CREATE TABLE IF NOT EXISTS event_tags (
            event_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (event_id, tag_id),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        -- Create indexes for fast lookups
        CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);
        CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag_id);

        -- Entity-Tag association table
        CREATE TABLE IF NOT EXISTS entity_tags (
            entity_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (entity_id, tag_id),
            FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        -- Create indexes for fast lookups
        CREATE INDEX IF NOT EXISTS idx_entity_tags_entity ON entity_tags(entity_id);
        CREATE INDEX IF NOT EXISTS idx_entity_tags_tag ON entity_tags(tag_id);

        -- Embeddings Table (for semantic search)
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            model TEXT NOT NULL,
            vector BLOB NOT NULL,
            vector_dim INTEGER NOT NULL,
            text_snippet TEXT,
            text_hash TEXT,
            metadata JSON DEFAULT '{}',
            created_at REAL NOT NULL
        );

        -- Upsert-friendly unique constraint to avoid duplicate rows per object/model
        CREATE UNIQUE INDEX IF NOT EXISTS uq_embeddings_obj_model
            ON embeddings(object_type, object_id, model);

        -- Useful indexes for query filtering and status
        CREATE INDEX IF NOT EXISTS idx_embeddings_model_dim
            ON embeddings(model, vector_dim);

        CREATE INDEX IF NOT EXISTS idx_embeddings_object
            ON embeddings(object_type, object_id);

        CREATE INDEX IF NOT EXISTS idx_embeddings_created_at
            ON embeddings(created_at);
        """

        try:
            with self.transaction() as conn:
                conn.executescript(schema_sql)
            logger.debug("Database schema initialized.")
        except sqlite3.Error as e:
            logger.critical(f"Schema initialization failed: {e}")
            raise

    def _run_migrations(self) -> None:
        """Runs necessary schema migrations."""
        try:
            # Check for 'color' column in 'tags' table
            assert self._connection is not None
            cursor = self._connection.execute("PRAGMA table_info(tags)")
            # row_factory is set to sqlite3.Row in connect(), so we can access by name
            columns = [row["name"] for row in cursor.fetchall()]

            if "color" not in columns:
                logger.info("Applying migration: Add color column to tags table")
                # Use a separate transaction for the alteration
                try:
                    self._connection.execute("ALTER TABLE tags ADD COLUMN color TEXT")
                    self._connection.commit()
                    logger.info(
                        "Migration successful: Added color column to tags table"
                    )
                except sqlite3.Error as e:
                    self._connection.rollback()
                    logger.error(f"Failed to add color column to tags table: {e}")
                    raise

        except sqlite3.Error as e:
            logger.critical(f"Migration check failed: {e}")
            raise

    # --------------------------------------------------------------------------
    # Event CRUD - Delegates to EventRepository
    # --------------------------------------------------------------------------

    def insert_event(self, event: Event) -> None:
        """
        Inserts a new event or updates an existing one (Upsert).

        Args:
            event (Event): The event domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        if not self._connection:
            self.connect()
        self._event_repo.insert(event)

    def get_event(self, event_id: str) -> Optional[Event]:
        """
        Retrieves a single event by its UUID.

        Args:
            event_id (str): The unique identifier of the event.

        Returns:
            Optional[Event]: The Event object if found, else None.
        """
        if not self._connection:
            self.connect()
        return self._event_repo.get(event_id)

    def get_all_events(self) -> List[Event]:
        """
        Retrieves all events from the database, sorted chronologically.

        Returns:
            List[Event]: A list of all Event objects in the database.
        """
        return self.get_events()

    def get_events(self, event_type: Optional[str] = None) -> List[Event]:
        """
        Retrieves events, optionally filtered by type.

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
        """
        Deletes an event permanently.

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
        """
        Inserts a new entity or updates an existing one (Upsert).

        Args:
            entity (Entity): The entity domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        if not self._connection:
            self.connect()
        self._entity_repo.insert(entity)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """
        Retrieves a single entity by its UUID.

        Args:
            entity_id (str): The unique identifier of the entity.

        Returns:
            Optional[Entity]: The Entity object if found, else None.
        """
        if not self._connection:
            self.connect()
        return self._entity_repo.get(entity_id)

    def get_all_entities(self) -> List[Entity]:
        """
        Retrieves all entities from the database.

        Returns:
            List[Entity]: A list of all Entity objects.
        """
        return self.get_entities()

    def get_entities(self, entity_type: Optional[str] = None) -> List[Entity]:
        """
        Retrieves entities, optionally filtered by type.

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
        """
        Deletes an entity permanently.

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

    def insert_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Creates a directed relationship between two objects.

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
        import time
        import uuid

        if attributes is None:
            attributes = {}

        rel_id = str(uuid.uuid4())
        created_at = time.time()

        self._relation_repo.insert(
            rel_id, source_id, target_id, rel_type, attributes, created_at
        )

        logger.info(
            f"DB: Inserted relation {rel_id}: {source_id} -> {target_id} ({rel_type})"
        )
        return rel_id

    def get_relations(self, source_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all outgoing relations for a given source object.

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
        """
        Retrieves all incoming relations for a given target object.

        Args:
            target_id (str): The ID of the target object.

        Returns:
            List[Dict[str, Any]]: List of relation dictionaries.
        """
        if not self._connection:
            self.connect()
        return self._relation_repo.get_by_target(target_id)

    def get_relation(self, rel_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single relation by its ID.

        Args:
            rel_id (str): The unique identifier of the relation.

        Returns:
            Optional[Dict[str, Any]]: The relation dict or None.
        """
        relations = self._relation_repo.get_all()
        for rel in relations:
            if rel.get("id") == rel_id:
                return rel
        return None

    def delete_relation(self, rel_id: str) -> None:
        """
        Deletes a relationship by its ID.

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
        """
        Updates an existing relationship.

        Args:
            rel_id (str): The ID of the relation to update.
            target_id (str): New target ID.
            rel_type (str): New relationship type.
            attributes (Dict[str, Any]): New attributes.

        Raises:
            sqlite3.Error: If DB fails.
        """
        if attributes is None:
            attributes = {}

        # Note: RelationRepository.update doesn't update target_id
        # We need to add that functionality or handle it here
        sql = """
            UPDATE relations
            SET target_id = ?, rel_type = ?, attributes = ?
            WHERE id = ?
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    target_id,
                    rel_type,
                    json.dumps(attributes),
                    rel_id,
                ),
            )

    def get_name(self, object_id: str) -> Optional[str]:
        """
        Retrieves the name of an entity or event by its ID.

        Args:
            object_id (str): The ID to resolve.

        Returns:
            Optional[str]: The name if found, else None.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Try Entity
        cursor = self._connection.execute(
            "SELECT name FROM entities WHERE id = ?", (object_id,)
        )
        row = cursor.fetchone()
        if row:
            return row["name"]

        # Try Event
        cursor = self._connection.execute(
            "SELECT name FROM events WHERE id = ?", (object_id,)
        )
        row = cursor.fetchone()
        if row:
            return row["name"]

        return None

    def insert_events_bulk(self, events: List[Event]) -> None:
        """
        Inserts multiple events efficiently using executemany.

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
        """
        Inserts multiple entities efficiently using executemany.

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
        """
        Inserts a new calendar config or updates an existing one (Upsert).

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
        """
        Retrieves a single calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the calendar config.

        Returns:
            Optional[CalendarConfig]: The config if found, else None.
        """
        if not self._connection:
            self.connect()
        return self._calendar_repo.get(config_id)

    def get_all_calendar_configs(self) -> List[CalendarConfig]:
        """
        Retrieves all calendar configurations.

        Returns:
            List[CalendarConfig]: A list of all calendar configs.
        """
        if not self._connection:
            self.connect()
        return self._calendar_repo.get_all()

    def delete_calendar_config(self, config_id: str) -> None:
        """
        Deletes a calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the config to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        if not self._connection:
            self.connect()
        self._calendar_repo.delete(config_id)
        logger.debug(f"Deleted calendar config: {config_id}")

    def get_active_calendar_config(self) -> Optional[CalendarConfig]:
        """
        Retrieves the currently active calendar configuration.

        Returns:
            Optional[CalendarConfig]: The active config if one is set, else None.
        """
        sql = "SELECT config_json FROM calendar_config WHERE is_active = 1"
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(sql)
        row = cursor.fetchone()

        if row:
            data = json.loads(row["config_json"])
            return CalendarConfig.from_dict(data)
        return None

    def set_active_calendar_config(self, config_id: str) -> None:
        """
        Sets a calendar config as the active one.

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
        """
        Retrieves the current time in the world from system_meta.

        Returns:
            Optional[float]: The current time in lore_date units, or None if not set.
        """
        sql = "SELECT value FROM system_meta WHERE key = 'current_time'"
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(sql)
        row = cursor.fetchone()

        if row and row["value"]:
            try:
                return float(row["value"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid current_time value: {row['value']}")
                return None
        return None

    def set_current_time(self, current_time: float) -> None:
        """
        Sets the current time in the world and persists it to system_meta.

        Args:
            current_time (float): The current time in lore_date units.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO system_meta (key, value)
            VALUES ('current_time', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
        with self.transaction() as conn:
            conn.execute(sql, (str(current_time),))
        logger.debug(f"Set current_time to {current_time}")

    # --------------------------------------------------------------------------
    # Map CRUD - Delegates to MapRepository
    # --------------------------------------------------------------------------

    def insert_map(self, map_obj: Map) -> None:
        """
        Inserts a new map or updates an existing one (Upsert).

        Args:
            map_obj (Map): The map domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        if not self._connection:
            self.connect()
        self._map_repo.insert_map(map_obj)

    def get_map(self, map_id: str) -> Optional[Map]:
        """
        Retrieves a single map by its UUID.

        Args:
            map_id (str): The unique identifier of the map.

        Returns:
            Optional[Map]: The Map object if found, else None.
        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_map(map_id)

    def get_all_maps(self) -> List[Map]:
        """
        Retrieves all maps from the database.

        Returns:
            List[Map]: List of all Map objects.
        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_all_maps()

    def delete_map(self, map_id: str) -> None:
        """
        Deletes a map and all its markers from the database.

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
        """
        Inserts a new marker or updates an existing one (Upsert).

        Upserts on UNIQUE(map_id, object_id, object_type). On conflict,
        the existing row's id is retained.

        Args:
            marker (Marker): The marker domain object to persist.

        Returns:
            str: The ID of the inserted/updated marker (may differ from marker.id
                 if a conflict occurred and the existing row was updated).

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        # Note: Repository insert_marker doesn't return ID, so we need special handling
        sql = """
            INSERT INTO markers (id, map_id, object_id, object_type, x, y,
                               label, attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(map_id, object_id, object_type) DO UPDATE SET
                x=excluded.x,
                y=excluded.y,
                label=excluded.label,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at
            RETURNING id;
        """
        with self.transaction() as conn:
            cursor = conn.execute(
                sql,
                (
                    marker.id,
                    marker.map_id,
                    marker.object_id,
                    marker.object_type,
                    marker.x,
                    marker.y,
                    marker.label,
                    json.dumps(marker.attributes),
                    marker.created_at,
                    marker.modified_at,
                ),
            )
            result = cursor.fetchone()
            return result[0] if result else marker.id

    def get_marker(self, marker_id: str) -> Optional[Marker]:
        """
        Retrieves a single marker by its UUID.

        Args:
            marker_id (str): The unique identifier of the marker.

        Returns:
            Optional[Marker]: The Marker object if found, else None.
        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_marker(marker_id)

    def get_markers_for_map(self, map_id: str) -> List[Marker]:
        """
        Retrieves all markers for a specific map.

        Args:
            map_id (str): The unique identifier of the map.

        Returns:
            List[Marker]: List of all Marker objects on the map.
        """
        if not self._connection:
            self.connect()
        return self._map_repo.get_markers_by_map(map_id)

    def get_markers_for_object(self, object_id: str, object_type: str) -> List[Marker]:
        """
        Retrieves all markers for a specific entity or event.

        Args:
            object_id (str): The unique identifier of the entity or event.
            object_type (str): Type of object ('entity' or 'event').

        Returns:
            List[Marker]: List of all Marker objects for the object.
        """
        sql = "SELECT * FROM markers WHERE object_id = ? AND object_type = ?"
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(sql, (object_id, object_type))
        rows = cursor.fetchall()

        markers = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            markers.append(Marker.from_dict(data))
        return markers

    def get_marker_by_composite(
        self, map_id: str, object_id: str, object_type: str
    ) -> Optional[Marker]:
        """
        Retrieves a marker by its composite key (map_id, object_id, object_type).

        This is useful after an upsert to retrieve the canonical marker with its
        actual database ID.

        Args:
            map_id (str): The unique identifier of the map.
            object_id (str): The unique identifier of the entity or event.
            object_type (str): Type of object ('entity' or 'event').

        Returns:
            Optional[Marker]: The Marker object if found, else None.
        """
        sql = """
            SELECT * FROM markers
            WHERE map_id = ? AND object_id = ? AND object_type = ?
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(sql, (map_id, object_id, object_type))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return Marker.from_dict(data)
        return None

    def delete_marker(self, marker_id: str) -> None:
        """
        Deletes a marker from the database.

        Args:
            marker_id (str): The unique identifier of the marker to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = "DELETE FROM markers WHERE id = ?"
        with self.transaction() as conn:
            conn.execute(sql, (marker_id,))

    # --------------------------------------------------------------------------
    # Tag Management - Normalized Tags
    # --------------------------------------------------------------------------

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        Retrieves all tags from the database.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries with id, name, created_at.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            "SELECT id, name, created_at FROM tags ORDER BY name"
        )
        rows = cursor.fetchall()
        # Convert sqlite3.Row to dict
        return [dict(zip(["id", "name", "created_at"], row)) for row in rows]

    def get_tags_with_events(self) -> List[Dict[str, Any]]:
        """
        Retrieves tags that are associated with at least one event.

        Returns:
            List[Dict[str, Any]]: List of distinct tag dictionaries.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            """
            SELECT DISTINCT t.id, t.name, t.created_at
            FROM tags t
            INNER JOIN event_tags et ON t.id = et.tag_id
            ORDER BY t.name
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_active_tags(self) -> List[Dict[str, Any]]:
        """
        Retrieves tags that are associated with at least one event OR entity.

        Returns:
            List[Dict[str, Any]]: List of distinct tag dictionaries.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        query = """
        SELECT DISTINCT t.id, t.name, t.created_at
        FROM tags t
        WHERE t.id IN (SELECT tag_id FROM event_tags)
           OR t.id IN (SELECT tag_id FROM entity_tags)
        ORDER BY t.name
        """
        cursor = self._connection.execute(query)
        rows = cursor.fetchall()
        return [dict(zip(["id", "name", "created_at"], row)) for row in rows]

    def create_tag(self, tag_name: str) -> str:
        """
        Creates a new tag or returns existing tag ID.

        Args:
            tag_name (str): The name of the tag to create.

        Returns:
            str: The UUID of the tag (new or existing).

        Raises:
            ValueError: If tag_name is empty or whitespace-only.
            sqlite3.Error: If the database operation fails.
        """
        import time
        import uuid

        # Validate and normalize tag name
        normalized_name = tag_name.strip()
        if not normalized_name:
            raise ValueError("Tag name cannot be empty or whitespace-only")

        # Check if tag already exists
        assert self._connection is not None
        cursor = self._connection.execute(
            "SELECT id FROM tags WHERE name = ?", (normalized_name,)
        )
        result = cursor.fetchone()
        if result:
            return result["id"]

        # Create new tag
        tag_id = str(uuid.uuid4())
        created_at = time.time()

        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)",
                (tag_id, normalized_name, created_at),
            )

        logger.debug(f"Created tag: {normalized_name} (ID: {tag_id})")
        return tag_id

    def assign_tag_to_event(self, event_id: str, tag_name: str) -> None:
        """
        Assigns a tag to an event, creating the tag if it doesn't exist.

        Args:
            event_id (str): The ID of the event.
            tag_name (str): The name of the tag to assign.

        Raises:
            ValueError: If tag_name is empty.
            sqlite3.Error: If the database operation fails.
        """
        import time

        # Create tag if it doesn't exist
        tag_id = self.create_tag(tag_name)

        # Create association (idempotent due to PRIMARY KEY constraint)
        created_at = time.time()
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO event_tags (event_id, tag_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (event_id, tag_id, created_at),
                )
        except sqlite3.Error as e:
            logger.error(f"Failed to assign tag '{tag_name}' to event {event_id}: {e}")
            raise

    def assign_tag_to_entity(self, entity_id: str, tag_name: str) -> None:
        """
        Assigns a tag to an entity, creating the tag if it doesn't exist.

        Args:
            entity_id (str): The ID of the entity.
            tag_name (str): The name of the tag to assign.

        Raises:
            ValueError: If tag_name is empty.
            sqlite3.Error: If the database operation fails.
        """
        import time

        # Create tag if it doesn't exist
        tag_id = self.create_tag(tag_name)

        # Create association (idempotent due to PRIMARY KEY constraint)
        created_at = time.time()
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO entity_tags (entity_id, tag_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (entity_id, tag_id, created_at),
                )
        except sqlite3.Error as e:
            logger.error(
                f"Failed to assign tag '{tag_name}' to entity {entity_id}: {e}"
            )
            raise

    def remove_tag_from_event(self, event_id: str, tag_name: str) -> None:
        """
        Removes a tag from an event.

        Args:
            event_id (str): The ID of the event.
            tag_name (str): The name of the tag to remove.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        # Get tag ID
        if not self._connection:
            self.connect()
        assert self._connection is not None
        cursor = self._connection.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name.strip(),)
        )
        result = cursor.fetchone()
        if not result:
            # Tag doesn't exist, nothing to remove
            return

        tag_id = result["id"]

        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM event_tags WHERE event_id = ? AND tag_id = ?",
                (event_id, tag_id),
            )

    def remove_tag_from_entity(self, entity_id: str, tag_name: str) -> None:
        """
        Removes a tag from an entity.

        Args:
            entity_id (str): The ID of the entity.
            tag_name (str): The name of the tag to remove.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        # Get tag ID
        if not self._connection:
            self.connect()
        assert self._connection is not None
        cursor = self._connection.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name.strip(),)
        )
        result = cursor.fetchone()
        if not result:
            # Tag doesn't exist, nothing to remove
            return

        tag_id = result["id"]

        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM entity_tags WHERE entity_id = ? AND tag_id = ?",
                (entity_id, tag_id),
            )

    def get_tags_for_event(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all tags for a specific event.

        Args:
            event_id (str): The ID of the event.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            """
            SELECT t.id, t.name, t.created_at
            FROM tags t
            INNER JOIN event_tags et ON t.id = et.tag_id
            WHERE et.event_id = ?
            ORDER BY t.name
            """,
            (event_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_tags_for_entity(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all tags for a specific entity.

        Args:
            entity_id (str): The ID of the entity.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            """
            SELECT t.id, t.name, t.created_at
            FROM tags t
            INNER JOIN entity_tags et ON t.id = et.tag_id
            WHERE et.entity_id = ?
            ORDER BY t.name
            """,
            (entity_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def delete_tag(self, tag_name: str) -> None:
        """
        Deletes a tag and all its associations.

        Args:
            tag_name (str): The name of the tag to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        # Get tag ID
        if not self._connection:
            self.connect()
        assert self._connection is not None
        cursor = self._connection.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name.strip(),)
        )
        result = cursor.fetchone()
        if not result:
            # Tag doesn't exist, nothing to delete
            return

        tag_id = result["id"]

        # Delete tag (CASCADE will handle associations)
        with self.transaction() as conn:
            conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))

        logger.debug(f"Deleted tag: {tag_name}")

    def get_events_by_tag(self, tag_name: str) -> List[Event]:
        """
        Retrieves all events that have a specific tag.

        Args:
            tag_name (str): The name of the tag.

        Returns:
            List[Event]: List of Event objects with the specified tag.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            """
            SELECT e.*
            FROM events e
            INNER JOIN event_tags et ON e.id = et.event_id
            INNER JOIN tags t ON et.tag_id = t.id
            WHERE t.name = ?
            ORDER BY e.lore_date
            """,
            (tag_name.strip(),),
        )
        rows = cursor.fetchall()

        events = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            events.append(Event.from_dict(data))
        return events

    def get_entities_by_tag(self, tag_name: str) -> List[Entity]:
        """
        Retrieves all entities that have a specific tag.

        Args:
            tag_name (str): The name of the tag.

        Returns:
            List[Entity]: List of Entity objects with the specified tag.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            """
            SELECT e.*
            FROM entities e
            INNER JOIN entity_tags et ON e.id = et.entity_id
            INNER JOIN tags t ON et.tag_id = t.id
            WHERE t.name = ?
            ORDER BY e.name
            """,
            (tag_name.strip(),),
        )
        rows = cursor.fetchall()

        entities = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            entities.append(Entity.from_dict(data))
        return entities

    def get_events_grouped_by_tags(
        self,
        tag_order: List[str],
        mode: str = "DUPLICATE",
        date_range: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        Groups events by tags with support for DUPLICATE and FIRST_MATCH modes.

        In DUPLICATE mode (default), events with multiple tags appear in all
        matching groups. In FIRST_MATCH mode, events appear only in their first
        matching group (by tag_order).

        Args:
            tag_order: List of tag names defining groups and their order.
            mode: Grouping mode - "DUPLICATE" (default) or "FIRST_MATCH".
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            Dict containing:
                - groups: List of dicts with tag_name and events list
                - remaining: List of events with no matching group tags

        Raises:
            ValueError: If mode is not DUPLICATE or FIRST_MATCH.
        """
        if mode not in ("DUPLICATE", "FIRST_MATCH"):
            raise ValueError(f"Invalid mode: {mode}. Must be DUPLICATE or FIRST_MATCH")

        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Build date filter clause
        date_filter = ""
        date_params = []
        if date_range:
            date_filter = "AND e.lore_date >= ? AND e.lore_date <= ?"
            date_params = [date_range[0], date_range[1]]

        # Initialize result structure
        groups = []
        assigned_event_ids = set()

        # Process each tag in order
        for tag_name in tag_order:
            # Get events for this tag
            query = f"""
                SELECT e.*
                FROM events e
                INNER JOIN event_tags et ON e.id = et.event_id
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name = ?
                {date_filter}
                ORDER BY e.lore_date
            """
            params = [tag_name.strip()] + date_params

            cursor = self._connection.execute(query, params)
            rows = cursor.fetchall()

            # Convert rows to Event objects
            events = []
            for row in rows:
                data = dict(row)
                if data.get("attributes"):
                    data["attributes"] = json.loads(data["attributes"])
                event = Event.from_dict(data)

                # In FIRST_MATCH mode, skip if already assigned
                if mode == "FIRST_MATCH" and event.id in assigned_event_ids:
                    continue

                events.append(event)
                assigned_event_ids.add(event.id)

            # Add group even if empty (to maintain tag_order)
            groups.append({"tag_name": tag_name, "events": events})

        # Get remaining events (those not in any group)
        remaining_query = f"""
            SELECT e.*
            FROM events e
            WHERE e.id NOT IN (
                SELECT DISTINCT et.event_id
                FROM event_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name IN ({",".join("?" * len(tag_order))})
            )
            {date_filter}
            ORDER BY e.lore_date
        """

        # Handle case where tag_order is empty
        if not tag_order:
            remaining_query = f"""
                SELECT e.*
                FROM events e
                WHERE 1=1
                {date_filter}
                ORDER BY e.lore_date
            """
            remaining_params = date_params
        else:
            remaining_params = [t.strip() for t in tag_order] + date_params

        cursor = self._connection.execute(remaining_query, remaining_params)
        rows = cursor.fetchall()

        remaining = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            remaining.append(Event.from_dict(data))

        return {"groups": groups, "remaining": remaining}

    def get_group_counts(
        self,
        tag_order: List[str],
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns count and metadata for each tag group.

        Args:
            tag_order: List of tag names to get counts for.
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            List of dicts with tag_name, count, earliest_date, latest_date.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Build date filter clause
        date_filter = ""
        date_params = []
        if date_range:
            date_filter = "AND e.lore_date >= ? AND e.lore_date <= ?"
            date_params = [date_range[0], date_range[1]]

        counts = []
        for tag_name in tag_order:
            query = f"""
                SELECT
                    COUNT(DISTINCT e.id) as count,
                    MIN(e.lore_date) as earliest_date,
                    MAX(e.lore_date) as latest_date
                FROM events e
                INNER JOIN event_tags et ON e.id = et.event_id
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name = ?
                {date_filter}
            """
            params = [tag_name.strip()] + date_params

            cursor = self._connection.execute(query, params)
            row = cursor.fetchone()

            counts.append(
                {
                    "tag_name": tag_name,
                    "count": row["count"] if row else 0,
                    "earliest_date": row["earliest_date"] if row else None,
                    "latest_date": row["latest_date"] if row else None,
                }
            )

        return counts

    # --------------------------------------------------------------------------
    # Timeline Grouping Service Methods (Milestone 2)
    # --------------------------------------------------------------------------

    def get_group_metadata(
        self,
        tag_order: List[str],
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns metadata for each tag group including color, count, and date span.

        Args:
            tag_order: List of tag names to get metadata for.
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            List of dicts with tag_name, color, count, earliest_date, latest_date.
        """
        metadata = []

        # Separate "All events" from regular tags
        ALL_EVENTS_TAG = "All events"
        regular_tags = [tag for tag in tag_order if tag != ALL_EVENTS_TAG]
        has_all_events = ALL_EVENTS_TAG in tag_order

        # Get counts for regular tags
        if regular_tags:
            counts = self.get_group_counts(
                tag_order=regular_tags, date_range=date_range
            )

            # Add color to each metadata entry
            for count_info in counts:
                tag_name = count_info["tag_name"]
                color = self.get_tag_color(tag_name)

                metadata.append(
                    {
                        "tag_name": tag_name,
                        "color": color,
                        "count": count_info["count"],
                        "earliest_date": count_info["earliest_date"],
                        "latest_date": count_info["latest_date"],
                    }
                )

        # Add "All events" metadata if requested
        if has_all_events:
            # Count ALL events in database
            all_events = self.get_all_events()
            count = len(all_events)

            # Get min/max dates
            earliest = min((e.lore_date for e in all_events), default=0.0)
            latest = max((e.lore_date for e in all_events), default=0.0)

            metadata.append(
                {
                    "tag_name": ALL_EVENTS_TAG,
                    "color": "#808080",  # Neutral gray
                    "count": count,
                    "earliest_date": earliest,
                    "latest_date": latest,
                }
            )

        return metadata

    def get_events_for_group(
        self,
        tag_name: str,
        date_range: Optional[tuple] = None,
    ) -> List[Event]:
        """
        Returns all events for a specific tag group.

        This is a convenience wrapper around get_events_by_tag with date filtering.

        Args:
            tag_name: The tag name to filter events by.
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            List[Event]: Events with the specified tag, sorted by lore_date.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Build date filter clause
        date_filter = ""
        params = [tag_name.strip()]

        if date_range:
            date_filter = "AND e.lore_date >= ? AND e.lore_date <= ?"
            params.extend([date_range[0], date_range[1]])

        cursor = self._connection.execute(
            f"""
            SELECT e.*
            FROM events e
            INNER JOIN event_tags et ON e.id = et.event_id
            INNER JOIN tags t ON et.tag_id = t.id
            WHERE t.name = ?
            {date_filter}
            ORDER BY e.lore_date
            """,
            tuple(params),
        )
        rows = cursor.fetchall()

        events = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            events.append(Event.from_dict(data))
        return events

    def set_tag_color(self, tag_name: str, color: Optional[str]) -> None:
        """
        Sets the color for a tag.

        Args:
            tag_name: The name of the tag.
            color: Hex color string (e.g., "#FF0000" or "#abc"), or None to clear.

        Raises:
            ValueError: If color format is invalid.
        """
        # Get or create tag
        tag_id = self.create_tag(tag_name)

        if color is None:
            # Clear color
            with self.transaction() as conn:
                conn.execute(
                    "UPDATE tags SET color = NULL WHERE id = ?",
                    (tag_id,),
                )
            logger.debug(f"Cleared color for tag '{tag_name}'")
            return

        import re

        # Validate hex color format
        if not re.match(r"^#[0-9A-Fa-f]{3}$|^#[0-9A-Fa-f]{6}$", color):
            raise ValueError(f"Invalid hex color format: {color}")

        # Normalize short form to long form
        if len(color) == 4:
            color = f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"

        # Update color
        with self.transaction() as conn:
            conn.execute(
                "UPDATE tags SET color = ? WHERE id = ?",
                (color, tag_id),
            )

        logger.debug(f"Set color {color} for tag '{tag_name}'")

    def get_tag_color(self, tag_name: str) -> str:
        """
        Gets the color for a tag, generating one if not set.

        Args:
            tag_name: The name of the tag.

        Returns:
            str: Hex color string (e.g., "#FF0000").
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Get tag
        cursor = self._connection.execute(
            "SELECT id, color FROM tags WHERE name = ?", (tag_name.strip(),)
        )
        result = cursor.fetchone()

        if not result:
            # Tag doesn't exist, create it and generate color
            self.create_tag(tag_name)
            return self._generate_tag_color(tag_name)

        if result["color"]:
            return result["color"]

        # Generate deterministic color
        return self._generate_tag_color(tag_name)

    def _generate_tag_color(self, tag_name: str) -> str:
        """
        Generates a deterministic color for a tag based on its name.

        Args:
            tag_name: The name of the tag.

        Returns:
            str: Hex color string (e.g., "#FF0000").
        """
        import hashlib

        # Use hash of tag name for deterministic color
        hash_value = int(hashlib.md5(tag_name.encode()).hexdigest()[:6], 16)

        # Generate RGB values that are reasonably visible
        r = (hash_value >> 16) & 0xFF
        g = (hash_value >> 8) & 0xFF
        b = hash_value & 0xFF

        # Ensure colors are not too dark (min 50 per channel)
        r = max(r, 80)
        g = max(g, 80)
        b = max(b, 80)

        return f"#{r:02X}{g:02X}{b:02X}"

    def get_tag_by_name(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a tag by its name.

        Args:
            tag_name: The name of the tag.

        Returns:
            Optional[Dict[str, Any]]: Tag dictionary with id, name, color, created_at
                                      or None if not found.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            "SELECT id, name, color, created_at FROM tags WHERE name = ?",
            (tag_name.strip(),),
        )
        result = cursor.fetchone()

        if result:
            return dict(result)
        return None

    def filter_ids_by_tags(
        self,
        object_type: Optional[str] = None,
        include: Optional[List[str]] = None,
        include_mode: str = "any",
        exclude: Optional[List[str]] = None,
        exclude_mode: str = "any",
        case_sensitive: bool = False,
    ) -> List[tuple[str, str]]:
        """
        Convenience wrapper for tag-based filtering of entities and events.

        Filters objects by tags using include/exclude lists with 'any' or 'all'
        semantics. Returns lightweight (object_type, object_id) tuples.

        Args:
            object_type: Optional filter for 'entity' or 'event'. If None, both.
            include: List of tag names to include. Empty or None means all objects.
            include_mode: 'any' (default) or 'all'. Whether object must have
                         any or all include tags.
            exclude: List of tag names to exclude. Empty or None means no exclusions.
            exclude_mode: 'any' (default) or 'all'. Whether to exclude if object
                         has any or all exclude tags.
            case_sensitive: If True, use exact case matching. If False (default),
                           case-insensitive.

        Returns:
            List[tuple[str, str]]: List of (object_type, object_id) tuples where
                object_type is 'entity' or 'event'.

        Raises:
            ValueError: If object_type is invalid or modes are invalid.

        Examples:
            # Get all entities with tag "important"
            >>> db.filter_ids_by_tags(object_type='entity', include=['important'])
            [('entity', 'uuid-1'), ('entity', 'uuid-2')]

            # Get events with ALL of ['battle', 'victory']
            >>> db.filter_ids_by_tags(
            ...     object_type='event',
            ...     include=['battle', 'victory'],
            ...     include_mode='all'
            ... )
            [('event', 'uuid-3')]

            # Get all objects with 'important' but not 'archived'
            >>> db.filter_ids_by_tags(
            ...     include=['important'],
            ...     exclude=['archived']
            ... )
            [('entity', 'uuid-1'), ('event', 'uuid-4')]
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        # Import locally to avoid circular imports
        from src.services import tag_filter

        return tag_filter.filter_object_ids(
            self._connection,
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
        """
        Retrieves full object instances for a list of (type, id) tuples.

        This method is used to hydrate results from `filter_ids_by_tags`.
        Results are returned sorted by their natural order:
        - Events: by lore_date
        - Entities: by name

        Args:
            object_ids: List of (object_type, object_id) tuples.

        Returns:
            Tuple containing (List[Event], List[Entity]).
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        event_ids = [oid for otype, oid in object_ids if otype == "event"]
        entity_ids = [oid for otype, oid in object_ids if otype == "entity"]

        events = []
        entities = []

        # Fetch Events
        if event_ids:
            placeholders = ",".join(["?"] * len(event_ids))
            query = f"""
                SELECT * FROM events
                WHERE id IN ({placeholders})
                ORDER BY lore_date
            """
            cursor = self._connection.execute(query, event_ids)
            rows = cursor.fetchall()
            for row in rows:
                data = dict(row)
                if data.get("attributes"):
                    data["attributes"] = json.loads(data["attributes"])
                events.append(Event.from_dict(data))

        # Fetch Entities
        if entity_ids:
            placeholders = ",".join(["?"] * len(entity_ids))
            query = f"""
                SELECT * FROM entities
                WHERE id IN ({placeholders})
                ORDER BY name
            """
            cursor = self._connection.execute(query, entity_ids)
            rows = cursor.fetchall()
            for row in rows:
                data = dict(row)
                if data.get("attributes"):
                    data["attributes"] = json.loads(data["attributes"])
                entities.append(Entity.from_dict(data))

        return events, entities

    def set_timeline_grouping_config(
        self,
        tag_order: List[str],
        mode: str = "DUPLICATE",
    ) -> None:
        """
        Stores timeline grouping configuration.

        Args:
            tag_order: List of tag names defining groups and their order.
            mode: Grouping mode - "DUPLICATE" or "FIRST_MATCH".

        Raises:
            ValueError: If mode is invalid.
        """
        if mode not in ("DUPLICATE", "FIRST_MATCH"):
            raise ValueError(f"Invalid mode: {mode}. Must be DUPLICATE or FIRST_MATCH")

        config = {"tag_order": tag_order, "mode": mode}
        config_json = json.dumps(config)

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO system_meta (key, value)
                VALUES ('timeline_grouping_config', ?)
                """,
                (config_json,),
            )

        logger.debug(
            f"Saved timeline grouping config: {len(tag_order)} tags, mode={mode}"
        )

    def get_timeline_grouping_config(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves timeline grouping configuration.

        Returns:
            Optional[Dict[str, Any]]: Config dict with tag_order and mode,
                                      or None if not set.
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None

        cursor = self._connection.execute(
            "SELECT value FROM system_meta WHERE key = 'timeline_grouping_config'"
        )
        result = cursor.fetchone()

        if result and result["value"]:
            return json.loads(result["value"])
        return None

    def clear_timeline_grouping_config(self) -> None:
        """
        Clears timeline grouping configuration.
        """
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM system_meta WHERE key = 'timeline_grouping_config'"
            )

        logger.debug("Cleared timeline grouping config")

    # --------------------------------------------------------------------------
    # Temporal Trajectories - Delegates to TrajectoryRepository
    # --------------------------------------------------------------------------

    def insert_trajectory(
        self,
        marker_id: str,
        trajectory: List["Keyframe"],
        properties: Optional[dict] = None,
    ) -> str:
        """
        Inserts a spatial trajectory for a marker.

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
        """
        Retrieves all trajectories for a specific map.

        Args:
            map_id: UUID of the map.

        Returns:
            List of (marker_id, trajectory_id, List[Keyframe]) tuples.
        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_by_map_id(map_id)

    def get_trajectories_by_marker(
        self, marker_id: str
    ) -> List[Tuple[str, List["Keyframe"]]]:
        """
        Retrieves all trajectories for a specific marker.

        Args:
            marker_id: UUID of the marker.

        Returns:
            List of (trajectory_id, List[Keyframe]) tuples.
        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.get_by_marker_db_id(marker_id)

    def add_keyframe(self, map_id: str, object_id: str, keyframe: "Keyframe") -> str:
        """
        Adds a keyframe to the marker's trajectory.

        Args:
            map_id: The ID of the map.
            object_id: The object ID (Entity/Event ID).
            keyframe: The Keyframe object.

        Returns:
            The ID of the updated/created trajectory.
        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.add_keyframe(map_id, object_id, keyframe)

    def update_keyframe_time(
        self, map_id: str, object_id: str, old_t: float, new_t: float
    ) -> str:
        """
        Updates a keyframe's timestamp (Clock Mode editing).

        Args:
            map_id: The ID of the map.
            object_id: The object ID (Entity/Event ID).
            old_t: Original timestamp.
            new_t: New timestamp.

        Returns:
            The ID of the updated trajectory.
        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.update_keyframe_time(
            map_id, object_id, old_t, new_t
        )
