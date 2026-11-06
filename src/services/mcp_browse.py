"""Bounded saved-object browsing with evidence-based Event overlap."""

import math
from typing import Any

from src.core.mcp_access import PAGE_SIZE, McpFailure
from src.core.temporal_display import TemporalDisplay
from src.core.temporal_presentation import event_temporal_presentation
from src.services.db_service import DatabaseService
from src.services.mcp_facts import event_timing, saved_tags
from src.services.mcp_temporal import McpTemporalReader, calendar_converter
from src.services.repositories.mcp_read_repository import McpReadRepository

CANDIDATE_BATCH_SIZE = 100


def _strings(value: Any, defaults: list[str]) -> list[str]:
    if value is None:
        return defaults
    if (
        not isinstance(value, list)
        or len(value) > PAGE_SIZE
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise McpFailure("INVALID_INPUT")
    return value


def browse_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Validate filters before SQL; dates require Event-only browsing."""
    result = {
        "kinds": _strings(args.get("kinds"), ["entity", "event"]),
        "types": _strings(args.get("types"), []),
        "tags": _strings(args.get("tags"), []),
        "limit": args.get("limit", PAGE_SIZE),
        "date_from": args.get("date_from"),
        "date_to": args.get("date_to"),
    }
    limit = result["limit"]
    if (
        not result["kinds"]
        or any(k not in {"entity", "event"} for k in result["kinds"])
        or type(limit) is not int
        or not 1 <= limit <= PAGE_SIZE
    ):
        raise McpFailure("INVALID_INPUT")
    for key in ("date_from", "date_to"):
        value = result[key]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise McpFailure("INVALID_DATE")
    lower, upper = result["date_from"], result["date_to"]
    if lower is not None or upper is not None:
        if set(result["kinds"]) != {"event"}:
            raise McpFailure("INVALID_INPUT")
        if lower is not None and upper is not None and lower > upper:
            raise McpFailure("INVALID_DATE")
    return result


def overlap(
    display: TemporalDisplay,
    lower: float | None,
    upper: float | None,
    ranges: list[dict[str, Any]] | None = None,
) -> str:
    """Match inclusive possible extents, retaining open bounds and uncertainty."""
    if display.error:
        return "unresolved"
    if ranges is not None and not any(
        _range_overlaps(item, lower, upper) for item in ranges
    ):
        return "excluded"
    start, end = display.possible_start, display.possible_end
    if ranges is None and (
        (
            lower is not None
            and end is not None
            and (end < lower or (end == lower and start != end))
        )
        or (upper is not None and start is not None and start > upper)
    ):
        return "excluded"
    if display.kind == "point":
        definite = (lower is None or (start is not None and start >= lower)) and (
            upper is None or (end is not None and end <= upper)
        )
    else:
        definite = (
            display.certain_start is not None
            and display.certain_end is not None
            and (upper is None or display.certain_start <= upper)
            and (lower is None or display.certain_end >= lower)
        )
    return "definite" if definite else "possible"


def _range_overlaps(
    item: dict[str, Any], lower: float | None, upper: float | None
) -> bool:
    start, end = item["from"], item["until"]
    before = (
        lower is not None
        and end is not None
        and (end < lower or (end == lower and not item["until_inclusive"]))
    )
    after = (
        upper is not None
        and start is not None
        and (start > upper or (start == upper and not item["from_inclusive"]))
    )
    return not (before or after)


def browse_batch(
    db: DatabaseService, filters: dict[str, Any], after: str
) -> tuple[dict[str, Any], str | None]:
    """Evaluate at most one candidate batch, including empty matching pages."""
    candidates = McpReadRepository(db.require_connection()).candidates(
        filters["kinds"], filters["types"], after, CANDIDATE_BATCH_SIZE
    )
    converter = calendar_converter(db)
    reader = McpTemporalReader(db)
    rows: list[dict[str, Any]] = []
    omitted = {"unresolved": 0, "excluded": 0}
    scanned = 0
    for candidate in candidates[:CANDIDATE_BATCH_SIZE]:
        if len(rows) >= filters["limit"]:
            break
        scanned += 1
        after = candidate["ordering"]
        kind, identifier = candidate["kind"], candidate["id"]
        item = (
            db.get_event(identifier) if kind == "event" else db.get_entity(identifier)
        )
        if item is None:
            omitted["unresolved"] += 1
            continue
        names = {tag["name"].casefold() for tag in saved_tags(db, item)}
        if not all(tag.strip().casefold() in names for tag in filters["tags"]):
            omitted["excluded"] += 1
            continue
        row: dict[str, Any] = {
            "kind": kind,
            "id": identifier,
            "name": item.name,
            "type": item.type,
            "snippet": item.description[:400],
        }
        if kind == "event":
            # The kind comes from fixed-table SQL, not an authored attribute.
            event = db.get_event(identifier)
            assert event is not None
            row["lore_date"] = event.lore_date
            row["temporal"] = event_timing(event, converter, reader)
            if filters["date_from"] is not None or filters["date_to"] is not None:
                projected = reader.projected(event)
                status = (
                    "unresolved"
                    if projected is None or row["temporal"]["presence"]["unresolved"]
                    else overlap(
                        event_temporal_presentation(projected, converter).presence,
                        filters["date_from"],
                        filters["date_to"],
                        row["temporal"]["presence"].get("possible_ranges"),
                    )
                )
                if status in omitted:
                    omitted[status] += 1
                    continue
                row["date_match"] = status
        rows.append(row)
    more = scanned < len(candidates)
    return {
        "rows": rows,
        "done": not more,
        "partial": more,
        "omitted_counts": omitted,
        "evaluated_count": scanned,
    }, after if more else None
