"""Tag Repository Module.

Handles CRUD operations for Tag entities and tag-based filtering/grouping
in the database.
"""

import hashlib
import json
import logging
import re
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from src.core.entities import Entity
from src.core.events import Event
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TagRepository(BaseRepository):
    """Repository for Tag entities.

    Provides specialized methods for creating, reading, updating, and deleting tags,
    as well as tag-based filtering and grouping of events and entities.
    """

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """Retrieves all tags from the database.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries with id, name, created_at.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(
            "SELECT id, name, created_at FROM tags ORDER BY name"
        )
        rows = cursor.fetchall()
        # Convert sqlite3.Row to dict
        return [dict(zip(["id", "name", "created_at"], row)) for row in rows]

    def get_tags_with_events(self) -> List[Dict[str, Any]]:
        """Retrieves tags that are associated with at least one event.

        Returns:
            List[Dict[str, Any]]: List of distinct tag dictionaries.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Retrieves tags that are associated with at least one event OR entity.

        Returns:
            List[Dict[str, Any]]: List of distinct tag dictionaries.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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

    def get_tag_by_name(self, tag_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a tag by its name.

        Args:
            tag_name: The name of the tag.

        Returns:
            Optional[Dict[str, Any]]: Tag dictionary with id, name, color, created_at
                                      or None if not found.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(
            "SELECT id, name, color, created_at FROM tags WHERE name = ?",
            (tag_name.strip(),),
        )
        result = cursor.fetchone()

        if result:
            return dict(result)
        return None

    def create_tag(self, tag_name: str) -> str:
        """Creates a new tag or returns existing tag ID.

        Args:
            tag_name (str): The name of the tag to create.

        Returns:
            str: The UUID of the tag (new or existing).

        Raises:
            ValueError: If tag_name is empty or whitespace-only.
            sqlite3.Error: If the database operation fails.

        """
        # Validate and normalize tag name
        normalized_name = tag_name.strip()
        if not normalized_name:
            raise ValueError("Tag name cannot be empty or whitespace-only")

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Check if tag already exists
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

    def delete_tag(self, tag_name: str) -> None:
        """Deletes a tag and all its associations.

        Args:
            tag_name (str): The name of the tag to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Get tag ID
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

    def assign_tag_to_event(self, event_id: str, tag_name: str) -> None:
        """Assigns a tag to an event, creating the tag if it doesn't exist.

        Args:
            event_id (str): The ID of the event.
            tag_name (str): The name of the tag to assign.

        Raises:
            ValueError: If tag_name is empty.
            sqlite3.Error: If the database operation fails.

        """
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
        """Assigns a tag to an entity, creating the tag if it doesn't exist.

        Args:
            entity_id (str): The ID of the entity.
            tag_name (str): The name of the tag to assign.

        Raises:
            ValueError: If tag_name is empty.
            sqlite3.Error: If the database operation fails.

        """
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
        """Removes a tag from an event.

        Args:
            event_id (str): The ID of the event.
            tag_name (str): The name of the tag to remove.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Get tag ID
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
        """Removes a tag from an entity.

        Args:
            entity_id (str): The ID of the entity.
            tag_name (str): The name of the tag to remove.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Get tag ID
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
        """Retrieves all tags for a specific event.

        Args:
            event_id (str): The ID of the event.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Retrieves all tags for a specific entity.

        Args:
            entity_id (str): The ID of the entity.

        Returns:
            List[Dict[str, Any]]: List of tag dictionaries.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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

    def get_events_by_tag(self, tag_name: str) -> List[Event]:
        """Retrieves all events that have a specific tag.

        Args:
            tag_name (str): The name of the tag.

        Returns:
            List[Event]: List of Event objects with the specified tag.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Retrieves all entities that have a specific tag.

        Args:
            tag_name (str): The name of the tag.

        Returns:
            List[Entity]: List of Entity objects with the specified tag.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Groups events by tags with support for DUPLICATE and FIRST_MATCH modes.

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
            raise RuntimeError("Database connection not initialized")

        # Build date filter clause
        date_filter = ""
        date_params: List[Any] = []
        if date_range:
            date_filter = "AND e.lore_date >= ? AND e.lore_date <= ?"
            date_params = [date_range[0], date_range[1]]

        # Initialize result structure
        groups = []
        assigned_event_ids: set[str] = set()

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
            params: List[Any] = [tag_name.strip()] + date_params

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
            remaining_params: List[Any] = date_params
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
        """Returns count and metadata for each tag group.

        Args:
            tag_order: List of tag names to get counts for.
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            List of dicts with tag_name, count, earliest_date, latest_date.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Build date filter clause
        date_filter = ""
        date_params: List[Any] = []
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
            params: List[Any] = [tag_name.strip()] + date_params

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

    def get_group_metadata(
        self,
        tag_order: List[str],
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """Returns metadata for each tag group including color, count, and date span.

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
            if not self._connection:
                raise RuntimeError("Database connection not initialized")

            # Count ALL events in database
            cursor = self._connection.execute(
                "SELECT * FROM events ORDER BY lore_date ASC"
            )
            all_events = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get("attributes"):
                    data["attributes"] = json.loads(data["attributes"])
                all_events.append(Event.from_dict(data))

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
        """Returns all events for a specific tag group.

        This is a convenience wrapper around get_events_by_tag with date filtering.

        Args:
            tag_name: The tag name to filter events by.
            date_range: Optional tuple (start_date, end_date) to filter events.

        Returns:
            List[Event]: Events with the specified tag, sorted by lore_date.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # Build date filter clause
        date_filter = ""
        params: List[Any] = [tag_name.strip()]

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
        """Sets the color for a tag.

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
        """Gets the color for a tag, generating one if not set.

        Args:
            tag_name: The name of the tag.

        Returns:
            str: Hex color string (e.g., "#FF0000").

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Generates a deterministic color for a tag based on its name.

        Uses MD5 hashing (non-cryptographic) to produce a stable color from
        the tag name. This is intentional — we need determinism, not security.

        Args:
            tag_name: The name of the tag.

        Returns:
            str: Hex color string (e.g., "#FF0000").

        """
        # Use hash of tag name for deterministic color
        hash_value = int(hashlib.md5(tag_name.encode()).hexdigest()[:6], 16)  # noqa: S324

        # Generate RGB values that are reasonably visible
        r = (hash_value >> 16) & 0xFF
        g = (hash_value >> 8) & 0xFF
        b = hash_value & 0xFF

        # Ensure colors are not too dark (min 50 per channel)
        r = max(r, 80)
        g = max(g, 80)
        b = max(b, 80)

        return f"#{r:02X}{g:02X}{b:02X}"

    def filter_ids_by_tags(
        self,
        object_type: Optional[str] = None,
        include: Optional[List[str]] = None,
        include_mode: str = "any",
        exclude: Optional[List[str]] = None,
        exclude_mode: str = "any",
        case_sensitive: bool = False,
    ) -> List[tuple[str, str]]:
        """Convenience wrapper for tag-based filtering of entities and events.

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
            >>> repo.filter_ids_by_tags(object_type='entity', include=['important'])
            [('entity', 'uuid-1'), ('entity', 'uuid-2')]

            # Get events with ALL of ['battle', 'victory']
            >>> repo.filter_ids_by_tags(
            ...     object_type='event',
            ...     include=['battle', 'victory'],
            ...     include_mode='all'
            ... )
            [('event', 'uuid-3')]

            # Get all objects with 'important' but not 'archived'
            >>> repo.filter_ids_by_tags(
            ...     include=['important'],
            ...     exclude=['archived']
            ... )
            [('entity', 'uuid-1'), ('event', 'uuid-4')]

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

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
        """Retrieves full object instances for a list of (type, id) tuples.

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
            raise RuntimeError("Database connection not initialized")

        event_ids = [oid for otype, oid in object_ids if otype == "event"]
        entity_ids = [oid for otype, oid in object_ids if otype == "entity"]

        events: List[Event] = []
        entities: List[Entity] = []

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
