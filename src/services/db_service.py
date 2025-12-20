"""
Database Service Module.
Provides the low-level SQL interface to the SQLite database.
Follows the Hybrid Schema (Strict Columns + JSON Attributes).

This service now uses specialized repository classes for better
separation of concerns and maintainability.
"""

import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from src.core.events import Event
from src.core.entities import Entity
from src.core.calendar import CalendarConfig
from src.core.map import Map
from src.core.marker import Marker

# Import repositories for modular CRUD operations
from src.services.repositories import (
    EventRepository,
    EntityRepository,
    RelationRepository,
    MapRepository,
    CalendarRepository,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Handles all raw interactions with the SQLite database.
    Implements the Hybrid Schema (Strict Columns + JSON Attributes).
    
    This service delegates CRUD operations to specialized repository
    classes while maintaining schema management and connection handling.
    """

    def __init__(self, db_path: str = ":memory:"):
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
        
        logger.info(f"DatabaseService initialized with path: {self.db_path}")

    def connect(self):
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
            
            # Connect repositories to the database connection
            self._event_repo.set_connection(self._connection)
            self._entity_repo.set_connection(self._connection)
            self._relation_repo.set_connection(self._connection)
            self._map_repo.set_connection(self._connection)
            self._calendar_repo.set_connection(self._connection)
            
        except sqlite3.Error as e:
            logger.critical(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed.")

    @contextmanager
    def transaction(self):
        """Safe context manager for transactions."""
        if not self._connection:
            self.connect()
        try:
            yield self._connection
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise

    def _init_schema(self):
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
        CREATE INDEX IF NOT EXISTS idx_markers_object ON markers(object_id, object_type);
        """

        try:
            with self.transaction() as conn:
                conn.executescript(schema_sql)
            logger.debug("Database schema initialized.")
        except sqlite3.Error as e:
            logger.critical(f"Schema initialization failed: {e}")
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
        self._event_repo.insert(event)

    def get_event(self, event_id: str) -> Optional[Event]:
        """
        Retrieves a single event by its UUID.

        Args:
            event_id (str): The unique identifier of the event.

        Returns:
            Optional[Event]: The Event object if found, else None.
        """
        return self._event_repo.get(event_id)

    def get_all_events(self) -> List[Event]:
        """
        Retrieves all events from the database, sorted chronologically.

        Returns:
            List[Event]: A list of all Event objects in the database.
        """
        return self._event_repo.get_all()

    def delete_event(self, event_id: str) -> None:
        """
        Deletes an event permanently.

        Args:
            event_id (str): The unique identifier of the event to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
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
        self._entity_repo.insert(entity)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """
        Retrieves a single entity by its UUID.

        Args:
            entity_id (str): The unique identifier of the entity.

        Returns:
            Optional[Entity]: The Entity object if found, else None.
        """
        sql = "SELECT * FROM entities WHERE id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (entity_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return Entity.from_dict(data)
        return None

    def get_all_entities(self) -> List[Entity]:
        """
        Retrieves all entities from the database.

        Returns:
            List[Entity]: A list of all Entity objects.
        """
        sql = "SELECT * FROM entities"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql)
        entities = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            entities.append(Entity.from_dict(data))
        return entities

    def delete_entity(self, entity_id: str) -> None:
        """
        Deletes an entity permanently.

        Args:
            entity_id (str): The unique identifier of the entity to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))

    # --------------------------------------------------------------------------
    # Relation CRUD
    # --------------------------------------------------------------------------

    def insert_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Dict[str, Any] = None,
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
        import uuid
        import time

        if attributes is None:
            attributes = {}

        rel_id = str(uuid.uuid4())
        created_at = time.time()

        sql = """
            INSERT INTO relations (id, source_id, target_id, rel_type,
                                   attributes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    rel_id,
                    source_id,
                    target_id,
                    rel_type,
                    json.dumps(attributes),
                    created_at,
                ),
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
        sql = "SELECT * FROM relations WHERE source_id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (source_id,))
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            relations.append(data)
        return relations

    def get_incoming_relations(self, target_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all incoming relations for a given target object.

        Args:
            target_id (str): The ID of the target object.

        Returns:
            List[Dict[str, Any]]: List of relation dictionaries.
        """
        sql = "SELECT * FROM relations WHERE target_id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (target_id,))
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            relations.append(data)
        return relations

    def get_relation(self, rel_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single relation by its ID.

        Args:
            rel_id (str): The unique identifier of the relation.

        Returns:
            Optional[Dict[str, Any]]: The relation dict or None.
        """
        sql = "SELECT * FROM relations WHERE id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (rel_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return data
        return None

    def delete_relation(self, rel_id: str) -> None:
        """
        Deletes a relationship by its ID.

        Args:
            rel_id (str): The unique identifier of the relation.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM relations WHERE id = ?", (rel_id,))

    def update_relation(
        self,
        rel_id: str,
        target_id: str,
        rel_type: str,
        attributes: Dict[str, Any] = None,
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
        if not events:
            return

        sql = """
            INSERT INTO events (id, type, name, lore_date, lore_duration,
                                description, attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                name=excluded.name,
                lore_date=excluded.lore_date,
                lore_duration=excluded.lore_duration,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """

        data = [
            (
                event.id,
                event.type,
                event.name,
                event.lore_date,
                event.lore_duration,
                event.description,
                json.dumps(event.attributes),
                event.created_at,
                event.modified_at,
            )
            for event in events
        ]

        with self.transaction() as conn:
            conn.executemany(sql, data)
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
        if not entities:
            return

        sql = """
            INSERT INTO entities (id, type, name, description,
                                  attributes, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                name=excluded.name,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """

        data = [
            (
                entity.id,
                entity.type,
                entity.name,
                entity.description,
                json.dumps(entity.attributes),
                entity.created_at,
                entity.modified_at,
            )
            for entity in entities
        ]

        with self.transaction() as conn:
            conn.executemany(sql, data)
        logger.info(f"Bulk inserted {len(entities)} entities")

    # --------------------------------------------------------------------------
    # Calendar Config CRUD
    # --------------------------------------------------------------------------

    def insert_calendar_config(self, config: CalendarConfig) -> None:
        """
        Inserts a new calendar config or updates an existing one (Upsert).

        Args:
            config (CalendarConfig): The calendar configuration to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO calendar_config (id, name, config_json, is_active,
                                         created_at, modified_at)
            VALUES (?, ?, ?, 0, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                config_json=excluded.config_json,
                modified_at=excluded.modified_at;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    config.id,
                    config.name,
                    json.dumps(config.to_dict()),
                    config.created_at,
                    config.modified_at,
                ),
            )
        logger.debug(f"Inserted/updated calendar config: {config.id}")

    def get_calendar_config(self, config_id: str) -> Optional[CalendarConfig]:
        """
        Retrieves a single calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the calendar config.

        Returns:
            Optional[CalendarConfig]: The config if found, else None.
        """
        sql = "SELECT config_json FROM calendar_config WHERE id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (config_id,))
        row = cursor.fetchone()

        if row:
            data = json.loads(row["config_json"])
            return CalendarConfig.from_dict(data)
        return None

    def get_all_calendar_configs(self) -> List[CalendarConfig]:
        """
        Retrieves all calendar configurations.

        Returns:
            List[CalendarConfig]: A list of all calendar configs.
        """
        sql = "SELECT config_json FROM calendar_config ORDER BY name"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql)
        configs = []
        for row in cursor.fetchall():
            data = json.loads(row["config_json"])
            configs.append(CalendarConfig.from_dict(data))
        return configs

    def delete_calendar_config(self, config_id: str) -> None:
        """
        Deletes a calendar config by its ID.

        Args:
            config_id (str): The unique identifier of the config to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM calendar_config WHERE id = ?", (config_id,))
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
        with self.transaction() as conn:
            # Deactivate all
            conn.execute("UPDATE calendar_config SET is_active = 0")
            # Activate the specified one
            conn.execute(
                "UPDATE calendar_config SET is_active = 1 WHERE id = ?",
                (config_id,),
            )
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
    # Map CRUD
    # --------------------------------------------------------------------------

    def insert_map(self, map_obj: Map) -> None:
        """
        Inserts a new map or updates an existing one (Upsert).

        Args:
            map_obj (Map): The map domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO maps (id, name, image_path, description, attributes,
                            created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                image_path=excluded.image_path,
                description=excluded.description,
                attributes=excluded.attributes,
                modified_at=excluded.modified_at;
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    map_obj.id,
                    map_obj.name,
                    map_obj.image_path,
                    map_obj.description,
                    json.dumps(map_obj.attributes),
                    map_obj.created_at,
                    map_obj.modified_at,
                ),
            )

    def get_map(self, map_id: str) -> Optional[Map]:
        """
        Retrieves a single map by its UUID.

        Args:
            map_id (str): The unique identifier of the map.

        Returns:
            Optional[Map]: The Map object if found, else None.
        """
        sql = "SELECT * FROM maps WHERE id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (map_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return Map.from_dict(data)
        return None

    def get_all_maps(self) -> List[Map]:
        """
        Retrieves all maps from the database.

        Returns:
            List[Map]: List of all Map objects.
        """
        sql = "SELECT * FROM maps ORDER BY name"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql)
        rows = cursor.fetchall()

        maps = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            maps.append(Map.from_dict(data))
        return maps

    def delete_map(self, map_id: str) -> None:
        """
        Deletes a map and all its markers from the database.

        Args:
            map_id (str): The unique identifier of the map to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = "DELETE FROM maps WHERE id = ?"
        with self.transaction() as conn:
            conn.execute(sql, (map_id,))

    # --------------------------------------------------------------------------
    # Marker CRUD
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
        sql = "SELECT * FROM markers WHERE id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (marker_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return Marker.from_dict(data)
        return None

    def get_markers_for_map(self, map_id: str) -> List[Marker]:
        """
        Retrieves all markers for a specific map.

        Args:
            map_id (str): The unique identifier of the map.

        Returns:
            List[Marker]: List of all Marker objects on the map.
        """
        sql = "SELECT * FROM markers WHERE map_id = ?"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (map_id,))
        rows = cursor.fetchall()

        markers = []
        for row in rows:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            markers.append(Marker.from_dict(data))
        return markers

    def get_markers_for_object(
        self, object_id: str, object_type: str
    ) -> List[Marker]:
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
