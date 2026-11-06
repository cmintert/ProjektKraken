"""Request-local reuse of Kraken's canonical timing solver for MCP facts."""

from dataclasses import replace
from typing import Any

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.definitions import EVENT_TIMING_SCHEMA, EventTimingDefinition
from src.core.event_timing.projection import project_event
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.services.db_service import DatabaseService

MAX_TIMING_EVENTS = 5000


def calendar_converter(db: DatabaseService) -> CalendarConverter | None:
    """Borrow the saved active calendar without inventing a fallback."""
    config = db.get_active_calendar_config()
    return CalendarConverter(config) if isinstance(config, CalendarConfig) else None


class McpTemporalReader:
    """Resolve at most one bounded world timing snapshot per worker request."""

    def __init__(self, db: DatabaseService) -> None:
        """Borrow only the active worker-owned database service."""
        self.db = db
        self.resolution: TemporalWorldResolution | None = None
        self._limited = False

    def projected(self, event: Event) -> Event | None:
        """Resolve schema-2 constraints jointly; refuse oversized timing inputs."""
        schema = event.attributes.get("_temporal_v2", {}).get("schema", 1)
        if schema not in {1, EVENT_TIMING_SCHEMA}:
            return replace(event, lore_date=None)
        if schema != EVENT_TIMING_SCHEMA:
            return event
        if self._limited:
            return None
        if self.resolution is None:
            count = (
                self.db.require_connection()
                .execute(
                    "SELECT count(*) FROM (SELECT id FROM events LIMIT ?)",
                    (MAX_TIMING_EVENTS + 1,),
                )
                .fetchone()[0]
            )
            if count > MAX_TIMING_EVENTS:
                self._limited = True
                return None
            self.resolution = resolve_world(
                self.db.get_all_events(), calendar_converter(self.db)
            )
        return project_event(event, self.resolution)


def authored_timing(event: Event) -> dict[str, Any] | None:
    """Expose the typed authored definition, never the private attribute envelope."""
    try:
        return EventTimingDefinition.from_event(event).to_dict()
    except (ValueError, TypeError, KeyError):
        return None
