"""Relation Repository Module.

Handles CRUD operations for Relation entities in the database.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RelationRepository(BaseRepository):
    """Repository for Relation entities.

    Provides specialized methods for creating, reading, updating, and deleting relations
    from the database.
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
        """Insert a new relation.

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

    @staticmethod
    def _legacy_occurrences(attributes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return normalized occurrence dictionaries from relation attributes."""
        occurrences = attributes.get("occurrences")
        if isinstance(occurrences, list):
            return [
                dict(item)
                for item in occurrences
                if isinstance(item, dict)
                and isinstance(item.get("field"), str)
                and isinstance(item.get("start_offset"), int)
                and isinstance(item.get("end_offset"), int)
            ]

        start_offset = attributes.get("start_offset")
        end_offset = attributes.get("end_offset")
        if isinstance(start_offset, int) and isinstance(end_offset, int):
            return [
                {
                    "field": str(attributes.get("field", "description")),
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "snippet": str(attributes.get("snippet", "")),
                }
            ]
        return []

    def reconcile_mentions(
        self,
        source_id: str,
        field: str,
        occurrences_by_target: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Atomically replace one field's derived wikilink occurrences.

        One ``mentions`` relation is retained per source-target pair. Occurrences
        belonging to fields other than ``field`` are preserved.
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        with self.transaction() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM relations
                WHERE source_id = ? AND rel_type = 'mentions'
                ORDER BY created_at, rowid
                """,
                (source_id,),
            )
            existing: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                relation = dict(row)
                relation["attributes"] = self._deserialize_json(
                    relation.get("attributes") or "{}"
                )
                existing.append(relation)

            existing_by_target: Dict[str, List[Dict[str, Any]]] = {}
            for relation in existing:
                existing_by_target.setdefault(relation["target_id"], []).append(
                    relation
                )

            target_ids = set(existing_by_target) | set(occurrences_by_target)
            created_count = 0
            updated_count = 0
            deleted_count = 0

            for target_id in target_ids:
                target_relations = existing_by_target.get(target_id, [])
                preserved: List[Dict[str, Any]] = []
                for relation in target_relations:
                    attributes = relation.get("attributes", {})
                    if isinstance(attributes, dict):
                        preserved.extend(
                            occurrence
                            for occurrence in self._legacy_occurrences(attributes)
                            if occurrence["field"] != field
                        )

                current = [
                    dict(occurrence)
                    for occurrence in occurrences_by_target.get(target_id, [])
                ]
                combined = preserved + current
                combined.sort(
                    key=lambda item: (
                        str(item.get("field", "")),
                        int(item.get("start_offset", 0)),
                        int(item.get("end_offset", 0)),
                    )
                )

                if not combined:
                    for relation in target_relations:
                        conn.execute(
                            "DELETE FROM relations WHERE id = ?",
                            (relation["id"],),
                        )
                        deleted_count += 1
                    continue

                attributes = {
                    "is_auto_generated": True,
                    "generator": "wikilink",
                    "occurrences": combined,
                }
                if target_relations:
                    survivor = target_relations[0]
                    if survivor.get("attributes") != attributes:
                        conn.execute(
                            "UPDATE relations SET attributes = ? WHERE id = ?",
                            (self._serialize_json(attributes), survivor["id"]),
                        )
                        updated_count += 1
                    for duplicate in target_relations[1:]:
                        conn.execute(
                            "DELETE FROM relations WHERE id = ?",
                            (duplicate["id"],),
                        )
                        deleted_count += 1
                else:
                    relation_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO relations (
                            id, source_id, target_id, rel_type, attributes, created_at
                        )
                        VALUES (?, ?, ?, 'mentions', ?, ?)
                        """,
                        (
                            relation_id,
                            source_id,
                            target_id,
                            self._serialize_json(attributes),
                            time.time(),
                        ),
                    )
                    created_count += 1

            cursor = conn.execute(
                """
                SELECT * FROM relations
                WHERE source_id = ? AND rel_type = 'mentions'
                ORDER BY created_at, rowid
                """,
                (source_id,),
            )
            after: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                relation = dict(row)
                relation["attributes"] = self._deserialize_json(
                    relation.get("attributes") or "{}"
                )
                after.append(relation)

        return {
            "before": existing,
            "after": after,
            "created_count": created_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
        }

    def restore_mentions(
        self, source_id: str, relations: List[Dict[str, Any]]
    ) -> None:
        """Atomically restore an exact snapshot of a source's mentions rows."""
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM relations WHERE source_id = ? AND rel_type = 'mentions'",
                (source_id,),
            )
            for relation in relations:
                conn.execute(
                    """
                    INSERT INTO relations (
                        id, source_id, target_id, rel_type, attributes, created_at
                    )
                    VALUES (?, ?, ?, 'mentions', ?, ?)
                    """,
                    (
                        relation["id"],
                        relation["source_id"],
                        relation["target_id"],
                        self._serialize_json(relation.get("attributes", {})),
                        relation.get("created_at", time.time()),
                    ),
                )

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all relations from the database.

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
        """Retrieve all relations where source_id matches.

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
        """Retrieve all relations where target_id matches.

        Includes 'source_event_date' and 'source_event_description' if the source is an event.

        Args:
            target_id: The target entity/event ID.

        Returns:
            List of relation dictionaries.

        """
        # Join with events table to get source event date, name, and description efficiently
        # We rename e.lore_date to source_event_date to avoid collision/ambiguity
        sql = """
            SELECT r.*, e.lore_date as source_event_date, e.name as source_event_name,
                   e.description as source_event_description
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

    def find_existing(
        self, source_id: str, target_id: str, rel_type: str
    ) -> Dict[str, Any] | None:
        """Find an existing relation by source, target, and type.

        Args:
            source_id: ID of the source entity/event.
            target_id: ID of the target entity/event.
            rel_type: Type of the relation.

        Returns:
            Relation dictionary if found, None otherwise.

        """
        sql = """
            SELECT * FROM relations
            WHERE source_id = ? AND target_id = ? AND rel_type = ?
            LIMIT 1
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (source_id, target_id, rel_type))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            return data
        return None

    def delete(self, relation_id: str) -> None:
        """Delete a relation permanently.

        Args:
            relation_id: The unique identifier of the relation to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM relations WHERE id = ?", (relation_id,))

    def get_for_item(self, item_id: str) -> List[Dict[str, Any]]:
        """Retrieve all relations where the item is either source or target.

        Args:
            item_id: The ID of the item (event or entity).

        Returns:
            List of relation dictionaries.

        """
        sql = "SELECT * FROM relations WHERE source_id = ? OR target_id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (item_id, item_id))
        relations = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            relations.append(data)
        return relations

    def delete_for_item(self, item_id: str) -> None:
        """Delete all relations where the item is either source or target.

        Args:
            item_id: The ID of the item.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM relations WHERE source_id = ? OR target_id = ?",
                (item_id, item_id),
            )

    def get_by_id(self, relation_id: str) -> Dict[str, Any] | None:
        """Retrieve a single relation by its ID.

        Args:
            relation_id: The unique identifier of the relation.

        Returns:
            Relation dictionary if found, None otherwise.

        """
        sql = "SELECT * FROM relations WHERE id = ? LIMIT 1"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (relation_id,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            return data
        return None

    def update(
        self,
        relation_id: str,
        rel_type: str,
        attributes: Dict[str, Any],
        target_id: Optional[str] = None,
    ) -> None:
        """Update a relation's type, attributes, and optionally target_id.

        Args:
            relation_id: The unique identifier of the relation.
            rel_type: New type for the relation.
            attributes: New attributes for the relation.
            target_id: Optional new target ID for the relation.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if target_id is not None:
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
                        self._serialize_json(attributes),
                        relation_id,
                    ),
                )
        else:
            sql = """
                UPDATE relations
                SET rel_type = ?, attributes = ?
                WHERE id = ?
            """
            with self.transaction() as conn:
                conn.execute(
                    sql,
                    (rel_type, self._serialize_json(attributes), relation_id),
                )
