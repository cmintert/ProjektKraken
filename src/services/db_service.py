"""Database Service Module. Provides the low-level SQL interface to the SQLite database.
Follows the Hybrid Schema (Strict Columns + JSON Attributes).

This service now uses specialized repository classes for better separation of concerns
and maintainability.
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
    MetaRepository,
    RelationRepository,
    TagRepository,
    TrajectoryRepository,
)

if TYPE_CHECKING:
    from src.core.trajectory import Keyframe
    from src.services.attachment_service import AttachmentService

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
        event_repo: Optional[EventRepository] = None,
        entity_repo: Optional[EntityRepository] = None,
        relation_repo: Optional[RelationRepository] = None,
        map_repo: Optional[MapRepository] = None,
        calendar_repo: Optional[CalendarRepository] = None,
        attachment_repo: Optional[AttachmentRepository] = None,
        trajectory_repo: Optional[TrajectoryRepository] = None,
        tag_repo: Optional[TagRepository] = None,
        meta_repo: Optional[MetaRepository] = None,
    ) -> None:
        """Initializes the database service with optional dependency injection.

        Args:
            db_path: Path to the .kraken database file.
                     Defaults to :memory: for testing.
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
        self._connection: Optional[sqlite3.Connection] = None
        self._backup_service = None

        self._event_repo = event_repo or EventRepository()
        self._entity_repo = entity_repo or EntityRepository()
        self._relation_repo = relation_repo or RelationRepository()
        self._map_repo = map_repo or MapRepository()
        self._calendar_repo = calendar_repo or CalendarRepository()
        self._attachment_repo = attachment_repo or AttachmentRepository()
        self._trajectory_repo = trajectory_repo or TrajectoryRepository()
        self._tag_repo = tag_repo or TagRepository()
        self._meta_repo = meta_repo or MetaRepository()
        self.attachment_service: Optional["AttachmentService"] = None

        logger.info(f"DatabaseService initialized with path: {self.db_path}")

    def connect(self) -> None:
        """Establishes connection to the database."""
        try:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.execute("PRAGMA foreign_keys = ON;")
            if self.db_path != ":memory:":
                # WAL enables concurrent reads during background writes
                self._connection.execute("PRAGMA journal_mode=WAL;")
                logger.debug("WAL mode enabled for database.")
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
            self._tag_repo.set_connection(self._connection)
            self._meta_repo.set_connection(self._connection)

        except sqlite3.Error as e:
            logger.critical(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed.")

    def is_connected(self) -> bool:
        """Checks if the database connection is established.

        Returns:
            bool: True if connected, False otherwise.

        """
        return self._connection is not None

    def get_connection(self) -> Optional[sqlite3.Connection]:
        """Gets the database connection, establishing it if necessary.

        Returns:
            Optional[sqlite3.Connection]: The active connection, or None if
                                          connection failed.

        """
        if not self._connection:
            self.connect()
        return self._connection

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

    def ensure_fresh_view(self) -> None:
        """Ensures the connection sees the most recent data (refreshes snapshot).

        This is critical in WAL mode if another connection has written data.
        We use a two-pronged approach:
        1. Commit any open transaction to release the snapshot.
        2. Execute a WAL checkpoint to force visibility of changes.
        """
        if not self._connection:
            return

        # First, close any open transaction
        if self._connection.in_transaction:
            self._connection.commit()

        # Then force a WAL checkpoint to ensure visibility
        try:
            self._connection.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except Exception:
            pass  # Ignore errors, this is best-effort

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

        -- Marker / MapFeature Table
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
            feature_type TEXT DEFAULT 'point',
            geometry TEXT,
            style TEXT,
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

        -- Command History for Persistent Undo/Redo (Phase 2)
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            world_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            command_type TEXT NOT NULL,
            command_data TEXT NOT NULL,
            description TEXT,
            timestamp REAL NOT NULL,
            is_executed BOOLEAN DEFAULT 1,
            aggregate_id TEXT,
            aggregate_type TEXT,
            is_snapshot BOOLEAN DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_ch_world_time 
            ON command_history(world_id, timestamp DESC);
        
        CREATE INDEX IF NOT EXISTS idx_ch_session 
            ON command_history(session_id);
        
        CREATE INDEX IF NOT EXISTS idx_ch_aggregate 
            ON command_history(aggregate_id, timestamp);

        -- Edit Sessions for Session Tracking
        CREATE TABLE IF NOT EXISTS edit_sessions (
            session_id TEXT PRIMARY KEY,
            world_id TEXT NOT NULL,
            started_at REAL NOT NULL,
            ended_at REAL,
            app_version TEXT
        );
        """

        try:
            with self.transaction() as conn:
                conn.executescript(schema_sql)
            logger.debug("Database schema initialized.")
        except sqlite3.Error as e:
            logger.critical(f"Schema initialization failed: {e}")
            raise

    def _run_migrations(self) -> None:
        """Run all incremental schema migrations against the connected database.

        Applies the following migrations in order, skipping any that have
        already been applied:

        1. Add ``color`` column to the ``tags`` table (tag coloring feature).
        2. Add ``timestamp`` column to the ``command_history`` table (undo/redo
           history timestamps).
        3. Convert legacy trajectory data from ``[[t, x, y], …]`` lists to the
           MF-JSON ``MovingPoint`` format via
           :meth:`_migrate_trajectories_to_mfjson`.
        4. Add ``feature_type``, ``geometry``, and ``style`` columns to the
           ``markers`` table (map-feature geometry/style support).

        Each migration is guarded by a ``PRAGMA table_info`` check so it is
        idempotent and safe to call on an already-migrated database.

        Raises:
            sqlite3.Error: If any migration step fails; the offending
                transaction is rolled back before re-raising.

        """
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

            # Check for 'timestamp' column in 'command_history' table
            cursor = self._connection.execute("PRAGMA table_info(command_history)")
            columns = [row["name"] for row in cursor.fetchall()]

            if "timestamp" not in columns:
                logger.info(
                    "Applying migration: Add timestamp column to command_history table"
                )
                try:
                    # Add column with default 0.0 (old commands will have 0 timestamp)
                    self._connection.execute(
                        "ALTER TABLE command_history ADD COLUMN timestamp REAL NOT NULL DEFAULT 0.0"
                    )
                    self._connection.commit()
                    logger.info(
                        "Migration successful: Added timestamp column to command_history table"
                    )
                except sqlite3.Error as e:
                    self._connection.rollback()
                    logger.error(
                        f"Failed to add timestamp column to command_history table: {e}"
                    )
                    raise

            # Migrate trajectory data from old format to MF-JSON
            self._migrate_trajectories_to_mfjson()

            # --- MapFeature migration: add feature_type, geometry, style ---
            cursor = self._connection.execute("PRAGMA table_info(markers)")
            marker_cols = [row["name"] for row in cursor.fetchall()]

            if "feature_type" not in marker_cols:
                logger.info(
                    "Applying migration: Add feature_type column to markers table"
                )
                try:
                    self._connection.execute(
                        "ALTER TABLE markers ADD COLUMN feature_type TEXT DEFAULT 'point'"
                    )
                    self._connection.commit()
                    logger.info(
                        "Migration successful: Added feature_type column to markers table"
                    )
                except sqlite3.Error as e:
                    self._connection.rollback()
                    logger.error(f"Failed to add feature_type column to markers: {e}")
                    raise

            if "geometry" not in marker_cols:
                logger.info("Applying migration: Add geometry column to markers table")
                try:
                    self._connection.execute(
                        "ALTER TABLE markers ADD COLUMN geometry TEXT"
                    )
                    self._connection.commit()
                    logger.info(
                        "Migration successful: Added geometry column to markers table"
                    )
                except sqlite3.Error as e:
                    self._connection.rollback()
                    logger.error(f"Failed to add geometry column to markers: {e}")
                    raise

            if "style" not in marker_cols:
                logger.info("Applying migration: Add style column to markers table")
                try:
                    self._connection.execute(
                        "ALTER TABLE markers ADD COLUMN style TEXT"
                    )
                    self._connection.commit()
                    logger.info(
                        "Migration successful: Added style column to markers table"
                    )
                except sqlite3.Error as e:
                    self._connection.rollback()
                    logger.error(f"Failed to add style column to markers: {e}")
                    raise

        except sqlite3.Error as e:
            logger.critical(f"Migration check failed: {e}")
            raise

    def _migrate_trajectories_to_mfjson(self) -> None:
        """Migrates old-format trajectories to MF-JSON format.

        Old format: [[t, x, y], ...]
        New format: {"type": "MovingPoint", "coordinates": [[x, y], ...], "datetimes": [...]}
        """
        assert self._connection is not None

        cursor = self._connection.execute("SELECT id, trajectory FROM moving_features")
        rows = cursor.fetchall()
        migrated_count = 0

        for row in rows:
            traj_id = row["id"]
            traj_json = row["trajectory"]
            try:
                data = json.loads(traj_json)
                # Skip if already MF-JSON format
                if isinstance(data, dict) and data.get("type") == "MovingPoint":
                    continue

                # Convert old format (list of [t, x, y])
                if isinstance(data, list) and data:
                    coordinates = [[item[1], item[2]] for item in data]
                    datetimes = [item[0] for item in data]
                    mfjson = {
                        "type": "MovingPoint",
                        "coordinates": coordinates,
                        "datetimes": datetimes,
                    }
                    self._connection.execute(
                        "UPDATE moving_features SET trajectory = ? WHERE id = ?",
                        (json.dumps(mfjson), traj_id),
                    )
                    migrated_count += 1

            except (json.JSONDecodeError, IndexError, TypeError) as e:
                logger.warning(f"Skipping corrupt trajectory {traj_id}: {e}")

        if migrated_count > 0:
            self._connection.commit()
            logger.info(
                f"Migration: Converted {migrated_count} trajectories to MF-JSON format"
            )

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

    def add_keyframe(self, map_id: str, object_id: str, keyframe: "Keyframe") -> str:
        """Adds a keyframe to the marker's trajectory.

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
        """Updates a keyframe's timestamp (Clock Mode editing).

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

    def delete_keyframe(self, map_id: str, object_id: str, t: float) -> Optional[str]:
        """Deletes a keyframe from a marker's trajectory.

        Args:
            map_id: The ID of the map.
            object_id: The object ID (Entity/Event ID).
            t: The timestamp of the keyframe to delete.

        Returns:
            The ID of the updated trajectory, or None if trajectory was deleted.

        """
        if not self._connection:
            self.connect()
        return self._trajectory_repo.delete_keyframe(map_id, object_id, t)

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
