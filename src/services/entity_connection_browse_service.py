"""Independent, bounded human browsing; never assembles an AI snapshot."""

from dataclasses import asdict, dataclass
from typing import Any, cast

from src.core.authoring_context import ContextItem, ContextRelation, ObjectType
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entity_context_mode import EntityContextMode
from src.core.events import Event
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_window import TemporalWindow, resolve_temporal_window
from src.services.db_service import DatabaseService
from src.services.entity_context_projection import (
    EntityContextProjectionService,
    public_value,
)
from src.services.repositories.entity_connection_browse_repository import (
    EntityConnectionBrowseRepository,
)

PAGE_SIZE = 25
CANDIDATE_BATCH_SIZE = 100
POLICY_VERSION = "entity-direct-v1"


@dataclass(frozen=True)
class _BatchContext:
    """Only the temporal dependencies needed by one bounded batch."""

    events: dict[str, Event]
    converter: CalendarConverter | None
    anchors: dict[str, ResolvedTemporalBounds]
    projection: EntityContextProjectionService | None


class StaleConnectionCursor(ValueError):
    """The caller must restart rather than append a different revision."""


class EntityConnectionBrowseService:
    """Evaluate short candidate batches on the database connection's thread."""

    def __init__(self, db: DatabaseService) -> None:
        """Borrow an already-open worker-owned database for this operation."""
        self.db = db
        self.connection = db.require_connection()
        self.repository = EntityConnectionBrowseRepository(self.connection)

    def revision(self) -> list[int]:
        """Detect own writes and external commits on this same connection."""
        return [
            id(self.connection),
            self.connection.total_changes,
            int(self.connection.execute("PRAGMA data_version").fetchone()[0]),
        ]

    def step(self, request: dict[str, Any]) -> dict[str, Any]:
        """Consume at most one batch; qualify before filling the result page."""
        query = request["query"]
        cursor = request.get("cursor") or {}
        revision = self.revision()
        binding = {
            **query,
            "section": "direct",
            "policy": POLICY_VERSION,
            "ordering": "source-predicate-target-casefold-id-v1",
            "filters": {},
        }
        if cursor and (cursor["binding"] != binding or cursor["revision"] != revision):
            raise StaleConnectionCursor
        loaded = int(cursor.get("loaded", 0))
        excluded = int(cursor.get("excluded", 0))
        unreadable = int(cursor.get("unreadable", 0))
        after = cursor.get("after")
        result = []
        consumed = 0
        with self.db.transaction():
            if self.db.get_entity(query["entity_id"]) is None:
                raise LookupError("Selected Entity no longer exists")
            rows = self.repository.candidates(
                query["entity_id"], after, CANDIDATE_BATCH_SIZE
            )
            context = self._context(rows, query)
            for row in rows:
                relation = self._relation(row, context)
                after = [
                    row["sort_source"],
                    row["rel_type"],
                    row["sort_target"],
                    row["id"],
                ]
                consumed += 1
                if relation is None:
                    excluded += 1
                elif isinstance(relation, str):
                    unreadable += 1
                else:
                    result.append(public_value(relation.to_dict()))
                if len(result) >= min(PAGE_SIZE, request.get("remaining", PAGE_SIZE)):
                    break
        if self.revision() != revision:
            raise StaleConnectionCursor
        loaded += len(result)
        done = consumed == len(rows) and len(rows) < CANDIDATE_BATCH_SIZE
        return {
            "rows": result,
            "done": done,
            "eligible_total": loaded if done and not unreadable else None,
            "cursor": {
                "binding": binding,
                "revision": revision,
                "after": after,
                "loaded": loaded,
                "excluded": excluded,
                "unreadable": unreadable,
            },
        }

    @staticmethod
    def _event_ids(row: dict[str, Any]) -> set[str]:
        identifiers = {
            row[f"{side}_id"]
            for side in ("source", "target")
            if row[f"{side}_kind"] == "event"
        }
        attributes = row["attributes"]
        spec = attributes.get("temporal", {})
        if isinstance(spec, dict):
            for side in ("start", "end", "at"):
                boundary = spec.get(side)
                if isinstance(boundary, dict):
                    anchor = boundary.get("anchor", {})
                    identifier = str(anchor.get("anchor_id", ""))
                    if identifier.startswith("event:"):
                        identifiers.add(identifier[6:])
        return identifiers

    def _context(
        self, rows: list[dict[str, Any]], query: dict[str, Any]
    ) -> _BatchContext:
        identifiers = set().union(*(self._event_ids(row) for row in rows))
        events = {}
        for identifier in sorted(identifiers):
            event = self.db.get_event(identifier)
            if event is not None:
                events[event.id] = event
        mode = EntityContextMode(query["mode"])
        if mode != EntityContextMode.ALL_HISTORY:
            projection = EntityContextProjectionService(
                self.db, mode, float(query["date"]), events
            )
            return _BatchContext(events, projection.converter, {}, projection)
        config = self.db.get_active_calendar_config()
        converter = (
            CalendarConverter(config) if isinstance(config, CalendarConfig) else None
        )
        return _BatchContext(
            events,
            converter,
            resolve_event_anchors(list(events.values()), converter),
            None,
        )

    def _relation(
        self, row: dict[str, Any], context: _BatchContext
    ) -> ContextRelation | str | None:
        if not row["source_kind"] or not row["target_kind"]:
            return "unreadable"
        source = ContextItem(
            row["source_id"], cast(ObjectType, row["source_kind"]), row["sort_source"]
        )
        target = ContextItem(
            row["target_id"], cast(ObjectType, row["target_kind"]), row["sort_target"]
        )
        if context.projection is not None:
            return context.projection.relation(row, source, target, 0)
        event = context.events.get(source.id)
        window = resolve_temporal_window(
            row["attributes"],
            event.lore_date if event else None,
            source_event_attributes=event.attributes if event else None,
            source_event_id=source.id,
            converter=context.converter,
            anchors=context.anchors,
        )
        if not window.is_valid:
            return "unreadable"
        kind = window.kind.value
        evidence = asdict(window) | {
            "kind": kind,
            "events": [
                {"id": context.events[key].id, "name": context.events[key].name}
                for key in sorted(self._event_ids(row))
                if key in context.events
            ],
        }
        return ContextRelation(
            row["id"],
            source,
            target,
            row["rel_type"],
            0,
            "persistent"
            if kind == "unbounded"
            else "instant"
            if kind == "instant"
            else "interval",
            window.start,
            window.end,
            temporal_status="overview",
            temporal_summary=self._history_caption(window, context.converter),
            temporal_evidence=evidence,
        )

    @staticmethod
    def _history_caption(
        window: TemporalWindow, converter: CalendarConverter | None
    ) -> str:
        parts = ["Saved connection across dates; not necessarily current"]
        if window.kind.value == "unbounded":
            return parts[0] + "; undated"
        for label, value, bounds in (
            ("starts", window.start, window.start_bounds),
            ("ends", window.end, window.end_bounds),
        ):
            text = "open" if bounds is None else "unknown"
            if bounds is not None and bounds.label:
                text = bounds.label
            elif value is not None:
                text = (
                    converter.format_datetime(value)
                    if converter
                    else f"{value:.12g} lore days"
                )
            parts.append(f"{label}: {text}")
        return "; ".join(parts)
