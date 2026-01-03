"""
Relation Repository Module.

Handles CRUD operations for Relation entities in the database.
"""

import logging
from typing import Any, Dict, List

from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RelationRepository(BaseRepository):
    """
    Repository for Relation entities.

    Provides specialized methods for creating, reading, updating,
    and deleting relations from the database.
    """

    def insert(
        self,
        relation_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: Dict[str, Any],
        created_at: float,
    ) -> None:
        """
        Insert a new relation.

        Args:
            relation_id: Unique identifier for the relation.
            source_id: ID of the source entity/event.
            target_id: ID of the target entity/event.
            rel_type: Type of the relation.
            attributes: Additional relation attributes.
            created_at: Creation timestamp.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            INSERT INTO relations (id, source_id, target_id, rel_type,
                                   attributes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    relation_id,
                    source_id,
                    target_id,
                    rel_type,
                    self._serialize_json(attributes),
                    created_at,
                ),
            )

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Retrieve all relations from the database.

        Returns:
            List of relation dictionaries.
        """
        sql = "SELECT * FROM relations"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql)
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            relations.append(data)
        return relations

    def get_by_source(self, source_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all relations where source_id matches.

        Args:
            source_id: The source entity/event ID.

        Returns:
            List of relation dictionaries.
        """
        sql = "SELECT * FROM relations WHERE source_id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (source_id,))
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            relations.append(data)
        return relations

    def get_by_target(self, target_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all relations where target_id matches.

        Includes 'source_event_date' if the source is an event.

        Args:
            target_id: The target entity/event ID.

        Returns:
            List of relation dictionaries.
        """
        # Join with events table to get source event date efficiently
        # We rename e.lore_date to source_event_date to avoid collision/ambiguity
        sql = """
            SELECT r.*, e.lore_date as source_event_date
            FROM relations r
            LEFT JOIN events e ON r.source_id = e.id
            WHERE r.target_id = ?
        """

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (target_id,))
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            relations.append(data)
        return relations

    def delete(self, relation_id: str) -> None:
        """
        Delete a relation permanently.

        Args:
            relation_id: The unique identifier of the relation to delete.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM relations WHERE id = ?", (relation_id,))

    def update(
        self, relation_id: str, rel_type: str, attributes: Dict[str, Any]
    ) -> None:
        """
        Update a relation's type and attributes.

        Args:
            relation_id: The unique identifier of the relation.
            rel_type: New type for the relation.
            attributes: New attributes for the relation.

        Raises:
            sqlite3.Error: If the database operation fails.
        """
        sql = """
            UPDATE relations 
            SET rel_type = ?, attributes = ?
            WHERE id = ?
        """
        with self.transaction() as conn:
            conn.execute(sql, (rel_type, self._serialize_json(attributes), relation_id))
