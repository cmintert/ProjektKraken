"""Event Repository Module.

Handles CRUD operations for Event entities in the database.
"""

import logging
from typing import List, Optional

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import TemporalExpression, expression_from_attributes
from src.services.repositories.base_repository import BaseRepository
from src.services.repositories.calendar_repository import CalendarRepository

logger = logging.getLogger(__name__)


class EventRepository(BaseRepository):
    """Repository for Event entities.

    Provides specialized methods for creating, reading, updating, and deleting events
    from the database.
    """

    def insert(self, event: Event) -> None:
        """Insert a new event or update an existing one (Upsert).

        Args:
            event: The event domain object to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        self._sync_temporal_projection(event)
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
                    self._serialize_json(event.attributes),
                    event.created_at,
                    event.modified_at,
                ),
            )

    def _sync_temporal_projection(self, event: Event) -> None:
        """Generate compatibility floats from assertions at the persistence boundary."""
        expression = expression_from_attributes(event.attributes)
        if expression is None:
            return
        config = CalendarRepository(self._connection).get(expression.calendar_id)
        if config is None:
            raise ValueError("The event's calendar is unavailable")
        converter = CalendarConverter(config)
        event.lore_date = expression.representative_time(converter)
        end_data = event.attributes["_temporal_v2"].get("end_expression")
        if end_data:
            end = TemporalExpression.from_dict(end_data).representative_time(converter)
            if end < event.lore_date:
                raise ValueError("Event end must not precede its start")
            event.lore_duration = end - event.lore_date

    def get(self, event_id: str) -> Optional[Event]:
        """Retrieve a single event by its UUID.

        Args:
            event_id: The unique identifier of the event.

        Returns:
            The Event object if found, else None.

        """
        sql = "SELECT * FROM events WHERE id = ?"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (event_id,))
        row = cursor.fetchone()

        if row:
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            return Event.from_dict(data)
        return None

    def get_all(self) -> List[Event]:
        """Retrieve all events from the database, sorted chronologically.

        Returns:
            List of all Event objects in the database.

        """
        sql = "SELECT * FROM events ORDER BY lore_date ASC"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql)
        events = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            events.append(Event.from_dict(data))
        return events

    def delete(self, event_id: str) -> None:
        """Delete an event permanently.

        Args:
            event_id: The unique identifier of the event to delete.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM events WHERE id = ?", (event_id,))

    def insert_bulk(self, events: List[Event]) -> None:
        """Insert multiple events in a single transaction.

        Args:
            events: List of event objects to persist.

        Raises:
            sqlite3.Error: If the database operation fails.

        """
        for event in events:
            self._sync_temporal_projection(event)
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
                self._serialize_json(event.attributes),
                event.created_at,
                event.modified_at,
            )
            for event in events
        ]

        with self.transaction() as conn:
            conn.executemany(sql, data)

    def get_by_date_range(self, start_date: float, end_date: float) -> List[Event]:
        """Retrieve events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of Event objects within the date range.

        """
        sql = """
            SELECT * FROM events
            WHERE lore_date >= ? AND lore_date <= ?
            ORDER BY lore_date ASC
        """

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (start_date, end_date))
        events = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            events.append(Event.from_dict(data))
        return events

    def get_by_type(self, event_type: str) -> List[Event]:
        """Retrieve events by type.

        Args:
            event_type: The type of events to retrieve.

        Returns:
            List of Event objects of the specified type.

        """
        sql = "SELECT * FROM events WHERE type = ? ORDER BY lore_date ASC"

        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        cursor = self._connection.execute(sql, (event_type,))
        events = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("attributes"):
                data["attributes"] = self._deserialize_json(data["attributes"])
            events.append(Event.from_dict(data))
        return events
