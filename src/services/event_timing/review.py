"""Pure, creator-facing explanations over completed timing calculations."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from src.core.calendar import CalendarConverter
from src.core.event_timing.presentation import endpoint_caption, explain_timing
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.events import Event
from src.core.temporal_boundary_resolver import BoundaryResolver
from src.core.temporal_expression import ResolvedTemporalBounds

if TYPE_CHECKING:
    from src.services.event_timing.planning import TimingChangeRequest

_STRICT_SCHEMA = 2
_VALUE_PREVIEW_LIMIT = 120


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _references(
    value: Any,
    source_id: str | None,
    path: tuple[str, ...] = (),
    semantics: str = "legacy_v1",
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Retain the owner boundary of each supported structural reference."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _references(item, source_id, (*path, str(index)), semantics)
    if not isinstance(value, dict):
        return
    if value.get("status", "known") != "known":
        return
    if "schema" in value:
        if value["schema"] not in {1, 2}:
            return
        semantics = "strict_v2" if value["schema"] == _STRICT_SCHEMA else "legacy_v1"
    if "anchor_id" in value or value.get("binding") == "source_event":
        ref = dict(value)
        ref.setdefault("semantics", semantics)
        if ref.get("binding") == "source_event":
            ref = {"anchor_id": f"event:{source_id}"}
        if str(ref.get("anchor_id", "")).startswith("event:"):
            role = next(
                (key for key in reversed(path) if key in {"start", "end", "at"}),
                "timing",
            )
            yield role, ref
        return
    for key, item in value.items():
        if key != "source_reference":
            yield from _references(item, source_id, (*path, key), semantics)


def _consumer_references(consumer: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    attrs = consumer["attributes"]
    source = consumer.get("source_id")
    refs = list(_references(attrs, source))
    if "temporal" not in attrs:
        for flag, role in (
            ("valid_from_event", "start"),
            ("valid_to_event", "end"),
            ("valid_at_event", "at"),
        ):
            if attrs.get(flag):
                refs.append((role, {"anchor_id": f"event:{source}"}))
    return refs


def _node(ref: dict[str, Any]) -> str:
    anchor = str(ref["anchor_id"])
    return anchor + (
        ":end" if ref.get("endpoint") == "end" and not anchor.endswith(":end") else ""
    )


def _name(identity: str | None, objects: dict[str, dict[str, str]]) -> str:
    info = objects.get(identity or "")
    return info["name"] if info else f"Missing object ({identity or 'unknown ID'})"


def _follows(ref: dict[str, Any], objects: dict[str, dict[str, str]]) -> str:
    node = _node(ref)
    identity = node.removeprefix("event:").removesuffix(":end")
    endpoint = "end" if node.endswith(":end") else "start"
    text = f"Follows the {endpoint} of “{_name(identity, objects)}”"
    relation = ref.get("relation", "at")
    if relation != "at":
        text += f"; {relation} that endpoint"
    offset = ref.get("offset") or {"value": ref.get("offset_days", 0), "unit": "days"}
    amount = offset.get("value", 0)
    if amount:
        try:
            amount_text = f"{float(amount):+g}"
        except (ValueError, TypeError):
            amount_text = str(amount)
        text += f"; offset {amount_text} {offset.get('unit', 'days')}"
    return text + "."


def _bounds_caption(
    bounds: ResolvedTemporalBounds, converter: CalendarConverter | None
) -> str:
    ranges = bounds.possible_ranges or ((bounds.hard_start, bounds.hard_end),)
    inclusivity = (
        bounds.possible_inclusivity if bounds.possible_ranges else None
    ) or tuple((bounds.lower_inclusive, bounds.upper_inclusive) for _ in ranges)
    signature = {
        "error": bounds.error,
        "verified": True,
        "ranges": [
            (
                str(lo) if lo is not None else None,
                str(hi) if hi is not None else None,
                left,
                right,
            )
            for (lo, hi), (left, right) in zip(ranges, inclusivity, strict=True)
        ],
    }
    return endpoint_caption(signature, converter, include_time=True)


def _reference_date(
    ref: dict[str, Any],
    resolver: BoundaryResolver,
) -> str:
    # BoundaryResolver owns offsets, strictness and supported reference semantics.
    try:
        return _bounds_caption(resolver.anchor(ref), resolver.converter)
    except (ValueError, TypeError, KeyError) as exc:
        return f"Timing unresolved: {exc}"


def _transition(role: str, predicate: str) -> str:
    if predicate == "changes_state":
        return {
            "start": "Changes take effect",
            "end": "Changes stop applying",
            "at": "Changes occur",
        }.get(role, "Timing changes")
    if predicate == "rules":
        return {
            "start": "Reign begins",
            "end": "Reign ends",
            "at": "Reign recorded at event",
        }.get(role, "Reign timing changes")
    return {
        "start": "Relationship starts",
        "end": "Relationship ends",
        "at": "Relationship occurs",
    }.get(role, "Timing source changes")


def _payload_summary(payload: dict[str, Any]) -> list[str]:
    lines = [
        f"{key} becomes {_brief_value(value)}"
        for key, value in payload.get("attributes", {}).items()
    ]
    lines.extend(f"Remove {key}" for key in payload.get("unset_attributes", []))
    if "description" in payload:
        lines.append("Description changes")
    return lines


def _brief_value(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return (
        text
        if len(text) <= _VALUE_PREVIEW_LIMIT
        else text[: _VALUE_PREVIEW_LIMIT - 1] + "…"
    )


def _consumer_review(
    item: dict[str, Any],
    consumer: dict[str, Any],
    objects: dict[str, dict[str, str]],
    changed: set[str],
    old_resolver: BoundaryResolver,
    resolver: BoundaryResolver,
) -> dict[str, Any]:
    predicate = consumer["name"] if item["kind"] == "relation" else ""
    section = "Relationships" if predicate else "Maps and features"
    heading = consumer["name"]
    summary: list[str] = []
    if predicate:
        source = _name(consumer.get("source_id"), objects)
        target = _name(consumer.get("target_id"), objects)
        heading = f"{source} → {target} — {predicate}"
        if predicate == "changes_state":
            section, heading = "Changes taking effect", target
            summary = _payload_summary(consumer["attributes"].get("payload", {}))
    elif consumer.get("map_name"):
        heading += f" — Map: {consumer['map_name']}"
    refs = [
        (role, ref)
        for role, ref in _consumer_references(consumer)
        if _node(ref) in changed
    ]
    explanations, old_dates, new_dates, identities = [], [], [], []
    for role, ref in refs:
        action = (
            _transition(role, predicate)
            if predicate
            else {
                "start": "Availability starts",
                "end": "Availability ends",
                "at": "Available at event",
            }.get(role, "Timing source changes")
        )
        explanations.append(f"{action}. {_follows(ref, objects)}")
        prefix = action + ": " if len(refs) > 1 else ""
        old_dates.append(prefix + _reference_date(ref, old_resolver))
        new_dates.append(prefix + _reference_date(ref, resolver))
        identities.append(
            (
                _node(ref),
                ref.get("relation", "at"),
                ref.get("offset")
                or {"value": ref.get("offset_days", 0), "unit": "days"},
            )
        )
    return {
        "section": section,
        "heading": heading,
        "explanation": "\n".join([*summary, *explanations])
        or "Uses the revised event timing; see Timing details.",
        "boundaries": [role for role, _ in refs],
        "before_text": "\n".join(old_dates) or item["before_text"],
        "after_text": "\n".join(new_dates) or item["after_text"],
        "timing_group": _json(identities) if identities else item["id"],
        "details": _json(
            {
                "id": item["id"],
                "source_id": consumer.get("source_id"),
                "target_id": consumer.get("target_id"),
                "predicate": predicate,
                "attributes": consumer["attributes"],
            }
        ),
    }


def describe_consequences(
    consequences: list[dict[str, Any]],
    snapshot: dict[str, Any],
    request: TimingChangeRequest,
    before: TemporalWorldResolution,
    after: TemporalWorldResolution,
    old_converter: CalendarConverter | None,
    converter: CalendarConverter | None,
    events: list[Event],
) -> None:
    """Add detached review metadata without changing consequences or solver facts."""
    objects = dict(
        request.review_objects
        if request.review_objects is not None
        else snapshot.get("objects", {})
    )
    objects.update(
        {event.id: {"name": event.name, "kind": "event"} for event in events}
    )
    consumers = {
        (row["kind"], row["id"]): row
        for row in (
            request.consumers
            if request.consumers is not None
            else snapshot.get("consumers", [])
        )
    }
    direct = set(request.updates) | {row["id"] for row in request.creates}
    changed = {
        node
        for node in after.endpoints
        if before.endpoints.get(node) != after.endpoints[node]
    }
    event_index = {event.id: event for event in events}
    old_resolver = BoundaryResolver(None, {}, None, old_converter, before.anchors())
    resolver = BoundaryResolver(None, {}, None, converter, after.anchors())
    for item in consequences:
        if item["kind"] != "event":
            consumer = consumers[(item["kind"], item["id"])]
            # Minimal historical snapshots retain their generic rendering.
            if item["kind"] == "relation" and "source_id" not in consumer:
                continue
            item["review"] = _consumer_review(
                item,
                consumer,
                objects,
                changed,
                old_resolver,
                resolver,
            )
            continue
        event = event_index[item["id"]]
        refs = list(_references(event.attributes.get("_temporal_v2", {}), event.id))
        item["review"] = {
            "section": "Edited events"
            if item["id"] in direct
            else "Other events moving",
            "heading": event.name,
            "explanation": "\n".join(
                f"{role.title()}: {_follows(ref, objects)}" for role, ref in refs
            )
            or (
                "You changed this event's timing."
                if item["id"] in direct
                else "Timing recalculated from the saved dates and chronology rules."
            ),
            "boundaries": [role for role, _ in refs],
            "before_text": item["before_text"],
            "after_text": item["after_text"],
            "timing_group": event.id,
            "details": explain_timing(event, after, events, converter)
            + "\n"
            + _json(
                {"id": event.id, "timing": event.attributes.get("_temporal_v2", {})}
            ),
        }
