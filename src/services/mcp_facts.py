"""Public saved facts and temporal presentation for worker-local MCP reads."""

from dataclasses import asdict
from fractions import Fraction
from typing import Any

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.core.mcp_access import McpFailure
from src.core.temporal_display import TemporalDisplay
from src.core.temporal_presentation import event_temporal_presentation
from src.services.db_service import DatabaseService
from src.services.mcp_temporal import (
    McpTemporalReader,
    authored_timing,
    calendar_converter,
)


def display_fields(display: TemporalDisplay) -> dict[str, Any]:
    """Publish evidence and captions without a layout anchor posing as a date."""
    return {
        "caption": display.caption,
        "kind": display.kind,
        "possible_start": display.possible_start,
        "possible_end": display.possible_end,
        "certain_start": display.certain_start,
        "certain_end": display.certain_end,
        "precision": display.precision.value if display.precision else None,
        "qualifier": display.qualifier.value,
        "explicit_window": display.explicit_window,
        "unresolved": display.error,
    }


def event_timing(
    event: Event, converter: CalendarConverter | None, reader: McpTemporalReader
) -> dict[str, Any]:
    """Keep occurrence, independent end, authored duration and presence separate."""
    projected = reader.projected(event)
    if projected is None:
        unavailable = display_fields(
            TemporalDisplay(None, None, error=True, caption="TIMING_LIMIT")
        )
        return {
            "calendar_available": converter is not None,
            "start": unavailable,
            "end": None,
            "presence": dict(unavailable),
            "authored_duration": None,
        }
    presentation = event_temporal_presentation(projected, converter)
    result: dict[str, Any] = {
        "calendar_available": converter is not None,
        "start": display_fields(presentation.start),
        "end": display_fields(presentation.end) if presentation.end else None,
        "authored_duration": presentation.authored_duration,
        "presence": display_fields(presentation.presence),
    }
    projection = projected.attributes.get("_temporal_v2", {}).get("projection", {})
    definition = authored_timing(event)
    for channel in ("start", "end"):
        fields = result[channel]
        if fields is not None:
            _endpoint_evidence(
                fields, projection.get(channel), (definition or {}).get(channel)
            )
    if presentation.presence.kind == "point":
        result["presence"] = dict(result["start"])
    elif result["start"]["unresolved"] or (
        result["end"] and result["end"]["unresolved"]
    ):
        result["presence"]["unresolved"] = True
    return result


def _endpoint_evidence(
    fields: dict[str, Any],
    projection: dict[str, Any] | None,
    definition: dict[str, Any] | None,
) -> None:
    if projection is not None:
        fields["possible_ranges"] = [
            {
                "from": float(Fraction(start)) if start not in {None, "None"} else None,
                "until": float(Fraction(end)) if end not in {None, "None"} else None,
                "from_inclusive": first,
                "until_inclusive": last,
            }
            for start, end, first, last in projection.get("ranges", [])
        ]
        fields["verified"] = projection.get("verified", False)
        if not fields["verified"]:
            fields["unresolved"] = True
    if definition:
        expression = definition.get("expression")
        if expression:
            fields["qualifier"] = expression.get("qualifier", "asserted")
            fields["precision"] = expression.get("precision", "day")
        elif definition.get("kind") == "event":
            fields["qualifier"] = "calculated"


def saved_tags(db: DatabaseService, item: Entity | Event) -> list[dict[str, str]]:
    """Reconcile normalized tags and legacy names like authoring context does."""
    stored = (
        db.get_tags_for_event(item.id)
        if isinstance(item, Event)
        else db.get_tags_for_entity(item.id)
    )
    by_name = {
        str(row["name"]).strip().casefold(): {
            "id": str(row["id"]),
            "name": str(row["name"]).strip(),
        }
        for row in stored
        if str(row.get("name", "")).strip()
    }
    for name in item.tags:
        if isinstance(name, str) and name.strip():
            by_name.setdefault(
                name.strip().casefold(), {"id": "", "name": name.strip()}
            )
    return sorted(by_name.values(), key=lambda tag: (tag["name"].casefold(), tag["id"]))


def object_key(args: dict[str, Any]) -> tuple[str, str]:
    """Validate an explicit Entity/Event identity before reading any batch rows."""
    kind, identifier = args.get("kind"), args.get("id")
    if (
        not isinstance(kind, str)
        or kind not in {"entity", "event"}
        or not isinstance(identifier, str)
        or not identifier
    ):
        raise McpFailure("INVALID_INPUT")
    return kind, identifier


def saved_object(
    db: DatabaseService, kind: str, identifier: str, reader: McpTemporalReader
) -> dict[str, Any]:
    """Project saved fields; historical resolution remains a context operation."""
    item = db.get_entity(identifier) if kind == "entity" else db.get_event(identifier)
    if item is None:
        raise McpFailure("NOT_FOUND")
    saved = item.to_dict()
    data = {
        key: saved[key]
        for key in ("id", "name", "type", "description", "created_at", "modified_at")
    }
    data.update(
        {
            "kind": kind,
            "attributes": item.attributes,
            "tags": saved_tags(db, item),
            "provenance": {"kind": "saved", "object_kind": kind, "id": identifier},
        }
    )
    if isinstance(item, Event):
        data.update({key: saved[key] for key in ("lore_date", "lore_duration")})
        expression = item.temporal_expression
        data["timing"] = expression.to_dict() if expression else None
        data["authored_timing"] = authored_timing(item)
        data["temporal"] = event_timing(item, calendar_converter(db), reader)
    return data


def world_overview(db: DatabaseService, world: dict[str, Any]) -> dict[str, Any]:
    """Return saved-object counts and explicitly standard calendar structure."""
    from src.services.repositories.mcp_read_repository import McpReadRepository

    config = db.get_active_calendar_config()
    calendar = None
    if isinstance(config, CalendarConfig):
        calendar = {
            "id": config.id,
            "name": config.name,
            "epoch_name": config.epoch_name,
            "months": [month.to_dict() for month in config.months],
            "week": asdict(config.week),
            "has_year_variants": bool(config.year_variants),
            "has_leap_year_rules": bool(config.leap_year_rules),
        }
    return {
        "id": world["world_id"],
        "name": world["world_name"],
        "read_only": True,
        "counts": McpReadRepository(db.require_connection()).counts(),
        "calendar": calendar,
    }


def enrich_context(
    db: DatabaseService,
    data: dict[str, Any],
    kind: str,
    identifier: str,
    reader: McpTemporalReader,
) -> None:
    """Add presentation at known context paths without walking authored values."""
    converter = calendar_converter(db)
    data["provenance"] = {
        "kind": "context",
        "object_kind": kind,
        "id": identifier,
        "mode": data.get("mode"),
        "lore_day": data.get("context_date"),
    }
    for section in ("attributes", "possible_changes"):
        for attribute in data.get(section, []):
            if attribute.get("source") is None:
                attribute["source"] = {"kind": "unavailable"}
    description = data.get("effective_description")
    if description is not None and description.get("source") is None:
        description["source"] = {"kind": "unavailable"}
    if kind == "event":
        event = db.get_event(identifier)
        if event is not None:
            data["temporal"] = event_timing(event, converter, reader)
    events = []
    for section in ("previous_events", "concurrent_events", "next_events"):
        events.extend(data.get(section, []))
    if kind == "entity":
        events.extend(data.get("mentions", []))
        events.extend(row["event"] for row in data.get("event_appearances", []))
        for row in data.get("co_appearances", []):
            events.extend(row["events"])
    for reference in events:
        event = db.get_event(reference["id"])
        if event is not None:
            reference["temporal"] = event_timing(event, converter, reader)
