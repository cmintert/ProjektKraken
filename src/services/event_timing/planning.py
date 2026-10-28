"""Pure change planning over detached world snapshots."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import uuid4

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.compiler import compile_timing
from src.core.event_timing.constraints import Cancel, Constraint, Interval
from src.core.event_timing.definitions import EventTimingDefinition
from src.core.event_timing.projection import endpoint_signature as _signature
from src.core.event_timing.projection import project_event as _projection
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_references import referenced_endpoints


def digest(value: Any) -> str:
    """Hash JSON-safe relevant facts, independent of dictionary insertion order."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class TimingChangeRequest:
    """An authored patch and the editor's original timing expectation."""

    updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    creates: tuple[dict[str, Any], ...] = ()
    deletes: tuple[str, ...] = ()
    expected: dict[str, dict[str, Any]] = field(default_factory=dict)
    calendar: str | None = None
    calendar_changed: bool = False
    world_id: str = ""
    generation: int = 0
    imported: bool = False
    consumers: tuple[dict[str, Any], ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return worker-safe request data."""
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimingChangeRequest:
        """Detach incoming command and UI data."""
        return cls(**deepcopy(data))


@dataclass
class TimingChangePlan:
    """A complete calculation; only the DB-thread registry can authorize it."""

    identity: str
    world_id: str
    fingerprint: str
    base_fingerprint: str
    request: TimingChangeRequest
    previous: dict[str, dict[str, Any]]
    updated: dict[str, dict[str, Any]]
    consequences: list[dict[str, Any]]
    errors: list[str]
    before: TemporalWorldResolution | None
    after: TemporalWorldResolution | None
    resolved_world: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Cross a thread boundary without sharing solver state or callbacks."""
        return {
            "identity": self.identity,
            "world_id": self.world_id,
            "fingerprint": self.fingerprint,
            "base_fingerprint": self.base_fingerprint,
            "request": self.request.to_dict(),
            "previous": deepcopy(self.previous),
            "updated": deepcopy(self.updated),
            "consequences": deepcopy(self.consequences),
            "errors": list(self.errors),
            "resolved_world": self.after.to_dict()
            if self.after is not None
            else self.resolved_world,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimingChangePlan:
        """Restore a completed internal plan payload on the database thread."""
        values = deepcopy(data)
        values["request"] = TimingChangeRequest.from_dict(values["request"])
        return cls(**values, before=None, after=None)

    @property
    def needs_review(self) -> bool:
        """The directly edited Event is already reviewed in its inspector."""
        direct = set(self.request.updates) | {row["id"] for row in self.request.creates}
        return any(
            item["kind"] != "event" or item["id"] not in direct
            for item in self.consequences
        )

    def review(self) -> dict[str, Any]:
        """Expose explanations without sharing the live solver or plan object."""
        return {
            "plan_id": self.identity,
            "world_id": self.world_id,
            "fingerprint": self.fingerprint,
            "consequences": deepcopy(self.consequences),
            "errors": list(self.errors),
            "needs_review": self.needs_review,
        }


def converter_from_snapshot(snapshot: dict[str, Any]) -> CalendarConverter | None:
    """Reconstruct the captured calendar, never a GUI-owned mutable converter."""
    raw = snapshot.get("calendar")
    return CalendarConverter(CalendarConfig.from_json(raw)) if raw else None


def snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    """Include review labels and every observing temporal dependency."""
    events = []
    for row in snapshot["events"]:
        event = Event.from_dict(row)
        try:
            timing: Any = EventTimingDefinition.from_event(event).to_dict()
        except (ValueError, TypeError, KeyError):
            timing = event.attributes.get("_temporal_v2")
        events.append(
            (
                event.id,
                event.name,
                timing,
                (event.attributes.get("_temporal_v2") or {}).get("constraints")
                if isinstance(event.attributes.get("_temporal_v2", {}), dict)
                else None,
            )
        )
    return digest(
        {
            "events": sorted(events),
            "calendar": snapshot.get("calendar"),
            "calendars": snapshot.get("calendars", []),
            "consumers": snapshot.get("consumers", []),
            "world_id": snapshot["world_id"],
        }
    )


def _candidate(snapshot: dict[str, Any], request: TimingChangeRequest) -> list[Event]:
    events = {row["id"]: Event.from_dict(deepcopy(row)) for row in snapshot["events"]}
    for identity, expected in request.expected.items():
        event = events.get(identity)
        if (
            event is None
            or EventTimingDefinition.from_event(event).to_dict() != expected
        ):
            raise ValueError(
                "Event timing changed since this draft opened. Reload its timing before saving."
            )
    for identity, patch in request.updates.items():
        if identity not in events:
            raise ValueError("The edited Event no longer exists")
        current = events[identity]
        fields = {
            key: deepcopy(value)
            for key, value in patch.items()
            if key in current.to_dict() and key not in {"id", "created_at"}
        }
        events[identity] = replace(current, **fields)
    for row in request.creates:
        if row["id"] in events:
            raise ValueError("The new Event identity already exists")
        events[row["id"]] = Event.from_dict(deepcopy(row))
    for identity in request.deletes:
        events.pop(identity, None)
    return list(events.values())


def _relaxed(previous: list[Constraint], updated: list[Constraint]) -> bool:
    """Certify a conservative partial repair by primitive constraint relaxation."""
    old = {(edge.source, edge.target, edge.rule): edge for edge in previous}
    for edge in updated:
        original = old.get((edge.source, edge.target, edge.rule))
        if original is None or edge.limit < original.limit:
            return False
        if edge.limit == original.limit and edge.strict and not original.strict:
            return False
    return True


def _repair_errors(
    before_events: list[Event],
    after_events: list[Event],
    before: TemporalWorldResolution,
    after: TemporalWorldResolution,
    converter: CalendarConverter | None,
    before_converter: CalendarConverter | None,
) -> list[str]:
    old_problem = compile_timing(before_events, before_converter)
    new_problem = compile_timing(after_events, converter)
    errors = []
    old_issues = {(issue.code, issue.endpoints): issue for issue in before.issues}
    old_definitions = {
        node: endpoint.to_dict() for node, endpoint in old_problem.definitions.items()
    }
    for issue in after.issues:
        old_issue = old_issues.get((issue.code, issue.endpoints)) or next(
            (
                item
                for item in before.issues
                if item.code == issue.code
                and set(issue.endpoints) <= set(item.endpoints)
            ),
            None,
        )
        if old_issue is None:
            errors.append(issue.message)
            continue
        relevant = set(issue.endpoints)
        unchanged = all(
            old_definitions.get(node) == new_problem.definitions[node].to_dict()
            for node in relevant
            if node in new_problem.definitions
        )
        old_edges = [
            edge
            for edge in old_problem.edges
            if edge.source in relevant or edge.target in relevant
        ]
        new_edges = [
            edge
            for edge in new_problem.edges
            if edge.source in relevant or edge.target in relevant
        ]
        unchanged = unchanged and old_edges == new_edges
        relaxed = (
            issue.code == "infeasible"
            and _relaxed(old_edges, new_edges)
            and _domains_relaxed(old_problem.domains, new_problem.domains, relevant)
        )
        if _calendar_restriction_changed(
            relevant,
            old_problem.definitions,
            new_problem.definitions,
            before_converter,
            converter,
        ):
            unchanged = relaxed = False
        if not unchanged and not relaxed:
            errors.append(
                "Cannot prove this timing change repairs or preserves the existing defect: "
                + issue.message
            )
    return errors


def _calendar_restriction_changed(
    nodes: set[str],
    before: dict[str, Any],
    after: dict[str, Any],
    old_converter: CalendarConverter | None,
    converter: CalendarConverter | None,
) -> bool:
    old = old_converter._config.to_json() if old_converter else None
    new = converter._config.to_json() if converter else None
    return old != new and any(
        endpoint.expression is not None
        or (endpoint.offset or {}).get("unit", "days") != "days"
        for definitions in (before, after)
        for node, endpoint in definitions.items()
        if node in nodes
    )


def _contains(outer: Interval, inner: Interval) -> bool:
    lower = outer.lower is None or (
        inner.lower is not None
        and (
            outer.lower < inner.lower
            or (
                outer.lower == inner.lower
                and (outer.lower_closed or not inner.lower_closed)
            )
        )
    )
    upper = outer.upper is None or (
        inner.upper is not None
        and (
            outer.upper > inner.upper
            or (
                outer.upper == inner.upper
                and (outer.upper_closed or not inner.upper_closed)
            )
        )
    )
    return lower and upper


def _domains_relaxed(
    before: dict[str, tuple[Interval, ...]],
    after: dict[str, tuple[Interval, ...]],
    nodes: set[str],
) -> bool:
    for node in nodes:
        if node not in after:
            continue
        if node not in before:
            return False
        if not all(
            any(_contains(new, old) for new in after[node]) for old in before[node]
        ):
            return False
    return True


def _consequences(
    events: list[Event],
    before: TemporalWorldResolution,
    after: TemporalWorldResolution,
    consumers: list[dict[str, Any]],
    converter: CalendarConverter | None,
    previous_events: list[Event],
    previous_converter: CalendarConverter | None,
) -> list[dict[str, Any]]:
    consequences = []
    changed: set[str] = set()
    changed_endpoints: set[str] = set()
    previous = {event.id: event for event in previous_events}
    for event in sorted(events, key=lambda item: (item.name.casefold(), item.id)):
        keys = (f"event:{event.id}", f"event:{event.id}:end")
        old = [_signature(before.endpoints.get(key)) for key in keys]
        new = [_signature(after.endpoints.get(key)) for key in keys]
        if old != new:
            changed.add(event.id)
            changed_endpoints.update(
                key
                for key, old_side, new_side in zip(keys, old, new, strict=True)
                if old_side != new_side
            )
            consequences.append(
                {
                    "kind": "event",
                    "id": event.id,
                    "name": event.name,
                    "before": old,
                    "after": new,
                    "before_text": _describe(
                        previous.get(event.id), before, previous_converter
                    ),
                    "after_text": _describe(event, after, converter),
                }
            )
    for consumer in consumers:
        used = referenced_endpoints(consumer["attributes"]) & changed_endpoints
        if used:
            consequences.append(
                {
                    "kind": consumer["kind"],
                    "id": consumer["id"],
                    "name": consumer["name"],
                    "before": "Previous source timing",
                    "after": "Follows the revised Event timing",
                    "before_text": "\n".join(
                        _describe(
                            previous.get(
                                node.removeprefix("event:").removesuffix(":end")
                            ),
                            before,
                            previous_converter,
                        )
                        for node in sorted(used)
                    ),
                    "after_text": "\n".join(
                        _describe(
                            next(
                                (
                                    event
                                    for event in events
                                    if event.id
                                    == node.removeprefix("event:").removesuffix(":end")
                                ),
                                None,
                            ),
                            after,
                            converter,
                        )
                        for node in sorted(used)
                    ),
                }
            )
    return consequences


def _describe(
    event: Event | None,
    result: TemporalWorldResolution,
    converter: CalendarConverter | None,
) -> str:
    if event is None:
        return "Not present"
    from src.core.event_timing.presentation import endpoint_caption

    def describe(node: str) -> str:
        signature = _signature(result.endpoints.get(node))
        return (
            endpoint_caption(signature, converter, include_time=True)
            if signature
            else "Unresolved"
        )

    start = describe(f"event:{event.id}")
    try:
        definition = EventTimingDefinition.from_event(event)
    except (ValueError, TypeError, KeyError):
        return start
    if definition.end_mode == "none":
        return start
    lines = [f"Start: {start}", f"End: {describe(f'event:{event.id}:end')}"]
    durations = result.duration(event.id)
    if durations:
        lines.append("Duration: " + _duration_description(durations))
    return "\n".join(lines)


def _duration_description(ranges: tuple[Interval, ...]) -> str:
    """Keep gaps and strict bounds when describing a jointly calculated duration."""
    alternatives = []
    for interval in ranges:
        lower, upper = interval.lower, interval.upper
        if lower is not None and lower == upper:
            alternatives.append(f"{float(lower):g} days")
            continue
        bounds = []
        if lower is not None:
            bounds.append(
                ("from " if interval.lower_closed else "more than ")
                + f"{float(lower):g} days"
            )
        if upper is not None:
            bounds.append(
                ("through " if interval.upper_closed else "less than ")
                + f"{float(upper):g} days"
            )
        alternatives.append("; ".join(bounds) or "unknown")
    return " or ".join(alternatives)


def prepare_change(
    snapshot: dict[str, Any], request: TimingChangeRequest, cancel: Cancel | None = None
) -> TimingChangePlan:
    """Calculate an immutable-world proposal without SQL or side effects."""
    if not request.world_id:
        request = replace(request, world_id=snapshot["world_id"])
    before_events = [Event.from_dict(row) for row in snapshot["events"]]
    events = _candidate(snapshot, request)
    converter = converter_from_snapshot(snapshot)
    before_converter = converter
    before = resolve_world(before_events, converter, cancel)
    if request.calendar_changed or request.calendar is not None:
        converter = (
            CalendarConverter(CalendarConfig.from_json(request.calendar))
            if request.calendar is not None
            else None
        )
    after = resolve_world(events, converter, cancel)
    errors = _repair_errors(
        before_events, events, before, after, converter, before_converter
    )
    errors.extend(
        _removed_endpoint_errors(
            before_events,
            events,
            list(request.consumers)
            if request.consumers is not None
            else snapshot.get("consumers", []),
        )
    )
    if request.imported:
        new_ids = {row["id"] for row in request.creates}
        allowed = {
            issue.message
            for issue in after.issues
            if issue.endpoints
            and all(
                node.removeprefix("event:").removesuffix(":end") in new_ids
                for node in issue.endpoints
            )
        }
        errors = [error for error in errors if error not in allowed]
    projected = [_projection(event, after) for event in events]
    previous = {event.id: event.to_dict() for event in before_events}
    updated = {
        event.id: event.to_dict()
        for event in projected
        if previous.get(event.id) != event.to_dict()
    }
    base_fingerprint = snapshot_fingerprint(snapshot)
    consequences = _consequences(
        events,
        before,
        after,
        list(request.consumers)
        if request.consumers is not None
        else snapshot.get("consumers", []),
        converter,
        before_events,
        before_converter,
    )
    confirmation = digest(
        {
            "base": base_fingerprint,
            "request": request.to_dict(),
            "consequences": consequences,
        }
    )
    return TimingChangePlan(
        str(uuid4()),
        snapshot["world_id"],
        confirmation,
        base_fingerprint,
        request,
        {key: previous[key] for key in updated if key in previous},
        updated,
        consequences,
        errors,
        before,
        after,
    )


def _removed_endpoint_errors(
    before: list[Event], after: list[Event], consumers: list[dict[str, Any]]
) -> list[str]:
    available = {event.id: event for event in after}
    removed: set[str] = set()
    for event in before:
        start = f"event:{event.id}"
        if event.id not in available:
            removed.update((start, start + ":end"))
            continue
        try:
            old = EventTimingDefinition.from_event(event)
            new = EventTimingDefinition.from_event(available[event.id])
            if old.end_mode != "none" and new.end_mode == "none":
                removed.add(start + ":end")
        except (ValueError, TypeError, KeyError):
            continue
    references = [(event.name, event.attributes) for event in after]
    references.extend((item["name"], item["attributes"]) for item in consumers)
    return [
        f"Resolve timing references in {name} before removing {', '.join(sorted(used))}."
        for name, attributes in references
        if (used := referenced_endpoints(attributes) & removed)
    ]
