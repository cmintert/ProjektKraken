"""Request-local reuse of Kraken's canonical timing solver for MCP facts."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.definitions import EVENT_TIMING_SCHEMA, EventTimingDefinition
from src.core.event_timing.projection import project_event
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.mcp_access import McpFailure
from src.services.context_read_inputs import timing_component_ids, timing_graph
from src.services.db_service import DatabaseService

MAX_TIMING_EVENTS = 5000


def calendar_converter(db: DatabaseService) -> CalendarConverter | None:
    """Borrow the saved active calendar without inventing a fallback."""
    config = db.get_active_calendar_config()
    return CalendarConverter(config) if isinstance(config, CalendarConfig) else None


class McpTemporalReader:
    """Resolve at most one bounded world timing snapshot per worker request."""

    def __init__(
        self, db: DatabaseService, expired: Callable[[], bool] | None = None
    ) -> None:
        """Borrow only the active worker-owned database service."""
        self.db = db
        self.resolution: TemporalWorldResolution | None = None
        self._limited = False
        self._expired = expired
        self._components: dict[str, TemporalWorldResolution] = {}
        self._graph: dict[str, set[str]] | None = None

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
                return self._component(event)
            self.resolution = resolve_world(
                self.db.get_all_events(), calendar_converter(self.db), self._expired
            )
        return project_event(event, self.resolution)

    def _component(self, event: Event) -> Event | None:
        """Solve a complete connected component; unrelated world size is immaterial."""
        if event.id not in self._components:
            if self._graph is None:
                self._graph = timing_graph(self.db, self._expired or (lambda: False))
            try:
                ids = timing_component_ids(
                    self.db, {event.id}, self._expired or (lambda: False), self._graph
                )
            except McpFailure as exc:
                if exc.code == "CONTEXT_LIMIT":
                    return None
                raise
            if len(ids) > MAX_TIMING_EVENTS:
                return None
            events = [
                item
                for identifier in sorted(ids)
                if (item := self.db.get_event(identifier)) is not None
            ]
            resolution = resolve_world(
                events, calendar_converter(self.db), self._expired
            )
            self._components.update((identifier, resolution) for identifier in ids)
        return project_event(event, self._components[event.id])


def authored_timing(event: Event) -> dict[str, Any] | None:
    """Expose the typed authored definition, never the private attribute envelope."""
    try:
        return EventTimingDefinition.from_event(event).to_dict()
    except (ValueError, TypeError, KeyError):
        return None
