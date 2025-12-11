"""
Database Service Module.
Provides the low-level SQL interface to the SQLite database.
Follows the Hybrid Schema (Strict Columns + JSON Attributes).
"""

import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from src.core.events import Event
from src.core.entities import Entity

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Handles all raw interactions with the SQLite database.
    Implements the Hybrid Schema (Strict Columns + JSON Attributes).
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Args:
            db_path: Path to the .kraken database file.
                     Defaults to :memory: for testing.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        logger.info(f"DatabaseService initialized with path: {self.db_path}")

    def connect(self):
        """Establishes connection to the database."""
        try:
            self._connection = sqlite3.connect(self.db_path)
            # Enable Foreign Keys
            self._connection.execute("PRAGMA foreign_keys = ON;")
            # Return rows as Row objects for name access
            self._connection.row_factory = sqlite3.Row
            logger.debug("Database connection established.")

            self._init_schema()
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
        """

        try:
            with self.transaction() as conn:
                conn.executescript(schema_sql)
            logger.debug("Database schema initialized.")
        except sqlite3.Error as e:
            logger.critical(f"Schema initialization failed: {e}")
            raise

    # --------------------------------------------------------------------------
    # Event CRUD
    # --------------------------------------------------------------------------

    def insert_event(self, event: Event) -> None:
        """
        Inserts a new event or updates an existing one (Upsert).

        Args:
            event (Event): The event domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
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
        with self.transaction() as conn:
            conn.execute(
                sql,
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
                ),
            )

    def get_event(self, event_id: str) -> Optional[Event]:
        """
        Retrieves a single event by its UUID.

        Args:
            event_id (str): The unique identifier of the event.

        Returns:
            Optional[Event]: The Event object if found, else None.
        """
        sql = "SELECT * FROM events WHERE id = ?"
        # We don't necessarily need a transaction for reading,
        # but connection must be open
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql, (event_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            # Parse JSON attributes back to dict
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            return Event.from_dict(data)
        return None

    def get_all_events(self) -> List[Event]:
        """
        Retrieves all events from the database, sorted chronologically.

        Returns:
            List[Event]: A list of all Event objects in the database.
        """
        sql = "SELECT * FROM events ORDER BY lore_date ASC"
        if not self._connection:
            self.connect()

        cursor = self._connection.execute(sql)
        events = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = json.loads(data["attributes"])
            events.append(Event.from_dict(data))
        return events

    def delete_event(self, event_id: str) -> None:
        """
        Deletes an event permanently.

        Args:
            event_id (str): The unique identifier of the event to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM events WHERE id = ?", (event_id,))

    # --------------------------------------------------------------------------
    # Entity CRUD
    # --------------------------------------------------------------------------

    def insert_entity(self, entity: Entity) -> None:
        """
        Inserts a new entity or updates an existing one (Upsert).

        Args:
            entity (Entity): The entity domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
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
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    entity.id,
                    entity.type,
                    entity.name,
                    entity.description,
                    json.dumps(entity.attributes),
                    entity.created_at,
                    entity.modified_at,
                ),
            )

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
