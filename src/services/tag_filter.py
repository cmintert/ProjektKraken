"""
Tag Filter Module.

Provides a composable FilterClause framework for filtering entities and events
by tags. Implements include/exclude logic with 'any' and 'all' semantics,
supporting case-sensitive and case-insensitive matching.

This module works with the normalized tag tables (tags, event_tags, entity_tags)
and returns lightweight (object_type, object_id) tuples for efficiency.
"""

import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class FilterClause(ABC):
    """
    Abstract base class for filter clauses.
    
    Subclasses should implement the matches() method to define
    specific filtering logic.
    """

    @abstractmethod
    def matches(
        self, conn: sqlite3.Connection, object_type: Optional[str] = None
    ) -> Set[Tuple[str, str]]:
        """
        Returns set of (object_type, object_id) tuples that match this clause.

        Args:
            conn: SQLite database connection.
            object_type: Optional filter for 'entity' or 'event'. If None, both.

        Returns:
            Set[Tuple[str, str]]: Set of matching (object_type, object_id) tuples.
        """
        pass


@dataclass
class TagClause(FilterClause):
    """
    Filter clause for tag-based filtering.

    Supports include/exclude lists with 'any' or 'all' semantics,
    and case-sensitive or case-insensitive matching.

    Precedence: apply include filter first (empty include = all objects),
    then apply exclusion to remove matches.

    Attributes:
        include: List of tag names to include.
        include_mode: 'any' or 'all' - whether object must have any or all tags.
        exclude: List of tag names to exclude.
        exclude_mode: 'any' or 'all' - whether to exclude if object has any or all tags.
        case_sensitive: If True, use exact case matching. If False (default), case-insensitive.
    """

    include: Optional[List[str]] = None
    include_mode: str = "any"
    exclude: Optional[List[str]] = None
    exclude_mode: str = "any"
    case_sensitive: bool = False

    def matches(
        self, conn: sqlite3.Connection, object_type: Optional[str] = None
    ) -> Set[Tuple[str, str]]:
        """
        Returns set of (object_type, object_id) tuples matching tag criteria.

        Args:
            conn: SQLite database connection.
            object_type: Optional filter for 'entity' or 'event'. If None, both.

        Returns:
            Set[Tuple[str, str]]: Set of matching (object_type, object_id) tuples.
        """
        # Step 1: Apply include filter
        if self.include and len(self.include) > 0:
            included = self._apply_include(conn, object_type)
        else:
            # Empty include means all objects
            included = self._get_all_objects(conn, object_type)

        # Step 2: Apply exclude filter
        if self.exclude and len(self.exclude) > 0:
            excluded = self._apply_exclude(conn, object_type)
            included = included - excluded

        return included

    def _get_all_objects(
        self, conn: sqlite3.Connection, object_type: Optional[str]
    ) -> Set[Tuple[str, str]]:
        """
        Get all objects (entities and/or events).

        Args:
            conn: SQLite database connection.
            object_type: Optional filter for 'entity' or 'event'. If None, both.

        Returns:
            Set[Tuple[str, str]]: Set of all (object_type, object_id) tuples.
        """
        results = set()

        if object_type is None or object_type == "entity":
            cursor = conn.execute("SELECT id FROM entities")
            for row in cursor.fetchall():
                results.add(("entity", row[0]))

        if object_type is None or object_type == "event":
            cursor = conn.execute("SELECT id FROM events")
            for row in cursor.fetchall():
                results.add(("event", row[0]))

        return results

    def _apply_include(
        self, conn: sqlite3.Connection, object_type: Optional[str]
    ) -> Set[Tuple[str, str]]:
        """
        Apply include filter with 'any' or 'all' semantics.

        Args:
            conn: SQLite database connection.
            object_type: Optional filter for 'entity' or 'event'. If None, both.

        Returns:
            Set[Tuple[str, str]]: Set of included (object_type, object_id) tuples.
        """
        if not self.include:
            return set()

        results = set()

        if object_type is None or object_type == "entity":
            entity_ids = self._filter_entities(
                conn, self.include, self.include_mode, self.case_sensitive
            )
            results.update([("entity", eid) for eid in entity_ids])

        if object_type is None or object_type == "event":
            event_ids = self._filter_events(
                conn, self.include, self.include_mode, self.case_sensitive
            )
            results.update([("event", eid) for eid in event_ids])

        return results

    def _apply_exclude(
        self, conn: sqlite3.Connection, object_type: Optional[str]
    ) -> Set[Tuple[str, str]]:
        """
        Apply exclude filter with 'any' or 'all' semantics.

        Args:
            conn: SQLite database connection.
            object_type: Optional filter for 'entity' or 'event'. If None, both.

        Returns:
            Set[Tuple[str, str]]: Set of excluded (object_type, object_id) tuples.
        """
        if not self.exclude:
            return set()

        results = set()

        if object_type is None or object_type == "entity":
            entity_ids = self._filter_entities(
                conn, self.exclude, self.exclude_mode, self.case_sensitive
            )
            results.update([("entity", eid) for eid in entity_ids])

        if object_type is None or object_type == "event":
            event_ids = self._filter_events(
                conn, self.exclude, self.exclude_mode, self.case_sensitive
            )
            results.update([("event", eid) for eid in event_ids])

        return results

    def _filter_entities(
        self,
        conn: sqlite3.Connection,
        tag_names: List[str],
        mode: str,
        case_sensitive: bool,
    ) -> Set[str]:
        """
        Filter entities by tags with 'any' or 'all' semantics.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names to filter by.
            mode: 'any' or 'all'.
            case_sensitive: If True, exact case matching. If False, case-insensitive.

        Returns:
            Set[str]: Set of entity IDs matching the criteria.
        """
        if not tag_names:
            return set()

        if mode == "any":
            return self._filter_entities_any(conn, tag_names, case_sensitive)
        elif mode == "all":
            return self._filter_entities_all(conn, tag_names, case_sensitive)
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'any' or 'all'.")

    def _filter_entities_any(
        self, conn: sqlite3.Connection, tag_names: List[str], case_sensitive: bool
    ) -> Set[str]:
        """
        Filter entities that have ANY of the specified tags.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names.
            case_sensitive: If True, exact case matching.

        Returns:
            Set[str]: Set of entity IDs.
        """
        if case_sensitive:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT DISTINCT et.entity_id
                FROM entity_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name IN ({placeholders})
            """
            cursor = conn.execute(query, tag_names)
        else:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT DISTINCT et.entity_id
                FROM entity_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE LOWER(t.name) IN ({placeholders})
            """
            cursor = conn.execute(query, [name.lower() for name in tag_names])

        return {row[0] for row in cursor.fetchall()}

    def _filter_entities_all(
        self, conn: sqlite3.Connection, tag_names: List[str], case_sensitive: bool
    ) -> Set[str]:
        """
        Filter entities that have ALL of the specified tags.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names.
            case_sensitive: If True, exact case matching.

        Returns:
            Set[str]: Set of entity IDs.
        """
        if case_sensitive:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT et.entity_id
                FROM entity_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name IN ({placeholders})
                GROUP BY et.entity_id
                HAVING COUNT(DISTINCT t.name) >= ?
            """
            cursor = conn.execute(query, tag_names + [len(tag_names)])
        else:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT et.entity_id
                FROM entity_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE LOWER(t.name) IN ({placeholders})
                GROUP BY et.entity_id
                HAVING COUNT(DISTINCT LOWER(t.name)) >= ?
            """
            cursor = conn.execute(
                query, [name.lower() for name in tag_names] + [len(tag_names)]
            )

        return {row[0] for row in cursor.fetchall()}

    def _filter_events(
        self,
        conn: sqlite3.Connection,
        tag_names: List[str],
        mode: str,
        case_sensitive: bool,
    ) -> Set[str]:
        """
        Filter events by tags with 'any' or 'all' semantics.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names to filter by.
            mode: 'any' or 'all'.
            case_sensitive: If True, exact case matching. If False, case-insensitive.

        Returns:
            Set[str]: Set of event IDs matching the criteria.
        """
        if not tag_names:
            return set()

        if mode == "any":
            return self._filter_events_any(conn, tag_names, case_sensitive)
        elif mode == "all":
            return self._filter_events_all(conn, tag_names, case_sensitive)
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'any' or 'all'.")

    def _filter_events_any(
        self, conn: sqlite3.Connection, tag_names: List[str], case_sensitive: bool
    ) -> Set[str]:
        """
        Filter events that have ANY of the specified tags.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names.
            case_sensitive: If True, exact case matching.

        Returns:
            Set[str]: Set of event IDs.
        """
        if case_sensitive:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT DISTINCT et.event_id
                FROM event_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name IN ({placeholders})
            """
            cursor = conn.execute(query, tag_names)
        else:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT DISTINCT et.event_id
                FROM event_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE LOWER(t.name) IN ({placeholders})
            """
            cursor = conn.execute(query, [name.lower() for name in tag_names])

        return {row[0] for row in cursor.fetchall()}

    def _filter_events_all(
        self, conn: sqlite3.Connection, tag_names: List[str], case_sensitive: bool
    ) -> Set[str]:
        """
        Filter events that have ALL of the specified tags.

        Args:
            conn: SQLite database connection.
            tag_names: List of tag names.
            case_sensitive: If True, exact case matching.

        Returns:
            Set[str]: Set of event IDs.
        """
        if case_sensitive:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT et.event_id
                FROM event_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE t.name IN ({placeholders})
                GROUP BY et.event_id
                HAVING COUNT(DISTINCT t.name) >= ?
            """
            cursor = conn.execute(query, tag_names + [len(tag_names)])
        else:
            placeholders = ",".join(["?"] * len(tag_names))
            query = f"""
                SELECT et.event_id
                FROM event_tags et
                INNER JOIN tags t ON et.tag_id = t.id
                WHERE LOWER(t.name) IN ({placeholders})
                GROUP BY et.event_id
                HAVING COUNT(DISTINCT LOWER(t.name)) >= ?
            """
            cursor = conn.execute(
                query, [name.lower() for name in tag_names] + [len(tag_names)]
            )

        return {row[0] for row in cursor.fetchall()}


def filter_object_ids(
    conn_or_db_service: Union[sqlite3.Connection, "DatabaseService"],
    object_type: Optional[str] = None,
    include: Optional[List[str]] = None,
    include_mode: str = "any",
    exclude: Optional[List[str]] = None,
    exclude_mode: str = "any",
    case_sensitive: bool = False,
) -> List[Tuple[str, str]]:
    """
    Filter objects (entities and/or events) by tags.

    This is the main public API for tag-based filtering. It returns
    lightweight (object_type, object_id) tuples for efficiency.

    Args:
        conn_or_db_service: SQLite connection or DatabaseService instance.
        object_type: Optional filter for 'entity' or 'event'. If None, both.
        include: List of tag names to include. Empty or None means all objects.
        include_mode: 'any' (default) or 'all'. Whether object must have any or all include tags.
        exclude: List of tag names to exclude. Empty or None means no exclusions.
        exclude_mode: 'any' (default) or 'all'. Whether to exclude if object has any or all exclude tags.
        case_sensitive: If True, use exact case matching. If False (default), case-insensitive.

    Returns:
        List[Tuple[str, str]]: List of (object_type, object_id) tuples where
            object_type is 'entity' or 'event'.

    Raises:
        ValueError: If object_type is not None, 'entity', or 'event'.
        ValueError: If include_mode or exclude_mode is not 'any' or 'all'.

    Examples:
        # Get all entities with tag "important"
        >>> filter_object_ids(conn, object_type='entity', include=['important'])
        [('entity', 'uuid-1'), ('entity', 'uuid-2')]

        # Get events with ALL of ['battle', 'victory']
        >>> filter_object_ids(conn, object_type='event', include=['battle', 'victory'], include_mode='all')
        [('event', 'uuid-3')]

        # Get all objects with 'important' but not 'archived'
        >>> filter_object_ids(conn, include=['important'], exclude=['archived'])
        [('entity', 'uuid-1'), ('event', 'uuid-4')]
    """
    # Validate object_type
    if object_type is not None and object_type not in ("entity", "event"):
        raise ValueError(f"Invalid object_type: {object_type}. Must be 'entity', 'event', or None.")

    # Validate modes
    if include_mode not in ("any", "all"):
        raise ValueError(f"Invalid include_mode: {include_mode}. Must be 'any' or 'all'.")
    if exclude_mode not in ("any", "all"):
        raise ValueError(f"Invalid exclude_mode: {exclude_mode}. Must be 'any' or 'all'.")

    # Get connection
    conn = _get_connection(conn_or_db_service)

    # Create TagClause and execute
    clause = TagClause(
        include=include,
        include_mode=include_mode,
        exclude=exclude,
        exclude_mode=exclude_mode,
        case_sensitive=case_sensitive,
    )

    result_set = clause.matches(conn, object_type)

    # Convert to sorted list for deterministic output
    return sorted(list(result_set))


def _get_connection(
    conn_or_db_service: Union[sqlite3.Connection, "DatabaseService"]
) -> sqlite3.Connection:
    """
    Extract SQLite connection from DatabaseService or return connection directly.

    Args:
        conn_or_db_service: SQLite connection or DatabaseService instance.

    Returns:
        sqlite3.Connection: The SQLite connection.

    Raises:
        ValueError: If DatabaseService is not connected.
    """
    if isinstance(conn_or_db_service, sqlite3.Connection):
        return conn_or_db_service

    # Assume it's a DatabaseService
    if not hasattr(conn_or_db_service, "_connection"):
        raise ValueError("Invalid argument: must be sqlite3.Connection or DatabaseService")

    if conn_or_db_service._connection is None:
        raise ValueError("DatabaseService is not connected")

    return conn_or_db_service._connection
