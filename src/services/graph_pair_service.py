"""Canonical relation inspection for two graph endpoints."""

from src.core.calendar import CalendarConverter
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_relation_policy import (
    RelationTemporalMode,
    evaluate_temporal_relation,
)
from src.services.db_service import DatabaseService


def graph_pair_relations(
    db: DatabaseService, source: str, target: str, playhead: float
) -> list[dict]:
    """Return both directions, with timing evaluated against the whole world."""
    pair = {source, target}
    rows = [
        row
        for row in db.get_relations_for_item(source)
        if {row["source_id"], row["target_id"]} == pair
    ]
    if not rows:
        return []
    events = {event.id: event for event in db.get_all_events()}
    config = db.get_active_calendar_config()
    converter = CalendarConverter(config) if config else None
    anchors = resolve_event_anchors(list(events.values()), converter)
    for row in rows:
        event = events.get(row["source_id"])
        evaluated = evaluate_temporal_relation(
            row
            if event is None
            else {
                **row,
                "source_event_date": event.lore_date,
                "source_event_attributes": event.attributes,
            },
            playhead,
            converter,
            RelationTemporalMode.ALL_RELATIONS,
            anchors,
        )
        if evaluated is not None:
            row["timing_summary"] = evaluated["temporal_summary"]
    return sorted(rows, key=lambda row: (row["created_at"], row["id"]))
