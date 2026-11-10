"""Explicit timeline movement over detached authoritative timing snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.calendar_index import month_span
from src.core.event_timing.definitions import (
    EndpointDefinition,
    EventTimingDefinition,
    finite,
)
from src.core.event_timing.resolution import TemporalWorldResolution
from src.core.events import Event
from src.core.temporal_expression import (
    MAX_LORE_DAY,
    TemporalExpression,
    move_expression,
)
from src.core.temporal_shift import calendar_shift

MOVE_MODES = {"offset": "Adjust offset", "chain": "Move chain"}
MOVEMENT_TOLERANCE = 1e-9


class MovementIndex:
    """Parse authorities and index reference membership once per source snapshot."""

    def __init__(self, events: list[Event]) -> None:
        """Own read-only definitions and directed follower indexes."""
        self.originals = {event.id: event for event in events}
        self.definitions = {
            event.id: EventTimingDefinition.from_event(event) for event in events
        }
        self.followers: dict[str, set[str]] = {event.id: set() for event in events}
        self._chains: dict[str, set[str]] = {}
        for owner, definition in self.definitions.items():
            for endpoint in (definition.start, definition.end):
                if endpoint is not None and endpoint.kind == "event":
                    source = str(endpoint.anchor_id).removeprefix("event:")
                    self.followers.setdefault(source, set()).add(owner)

    def chain(self, identity: str) -> set[str]:
        """Retain reference-only chain semantics independently of chronology."""
        if identity not in self._chains:
            self._chains[identity] = _connected(self.definitions, identity)
        return self._chains[identity]


def _coordinate(resolution: TemporalWorldResolution, node: str) -> float:
    endpoint = resolution.endpoints.get(node)
    if endpoint is None or endpoint.error or not endpoint.verified:
        raise ValueError("Repair unresolved or cyclic timing in the inspector first.")
    value = endpoint.coordinate
    if value is None:
        raise ValueError("This timing has no unambiguous movement anchor.")
    return value


def _exact(resolution: TemporalWorldResolution, node: str) -> float:
    value = _coordinate(resolution, node)
    ranges = resolution.endpoints[node].ranges
    if len(ranges) != 1 or ranges[0].lower != ranges[0].upper:
        raise ValueError(
            "A calendar offset with an uncertain source cannot be moved safely. "
            "Keep its timing in the inspector."
        )
    return value


def _bounded(value: float) -> float:
    value = finite(value)
    if abs(value) > MAX_LORE_DAY:
        raise ValueError("Date is outside the supported lore-day range.")
    return value


def _calendar_offset(
    start: EndpointDefinition,
    target: float,
    resolution: TemporalWorldResolution,
    converter: CalendarConverter | None,
) -> EndpointDefinition:
    offset = deepcopy(start.offset or {})
    if offset.get("unit") == "compound":
        raise ValueError(
            "Edit compound offsets in the inspector to preserve components."
        )
    if converter is None or offset.get("calendar_id") != converter._config.id:
        raise ValueError("The offset's authored calendar is unavailable.")
    source = _exact(resolution, start.source)
    origin, destination = converter.from_float(source), converter.from_float(target)
    unit = str(offset["unit"])
    amount = destination.year - origin.year
    if unit == "months":
        amount = (
            month_span(converter._config, destination.year)
            - month_span(converter._config, origin.year)
            + destination.month
            - origin.month
        )
    candidates = []
    # Adjacent whole units cover the nearest date, including invalid month days.
    for candidate in range(amount - 2, amount + 3):
        try:
            date = _bounded(calendar_shift(source, candidate, unit, converter))
            candidates.append((abs(date - target), candidate))
        except (ValueError, IndexError, OverflowError):
            continue
    if not candidates:
        raise ValueError("No valid nearby whole-calendar offset. Use the inspector.")
    offset["value"] = min(candidates)[1]
    return replace(start, offset=offset)


def _manual_shift(
    endpoint: EndpointDefinition, delta: float, converter: CalendarConverter | None
) -> EndpointDefinition:
    if endpoint.instant is not None:
        return replace(endpoint, instant=_bounded(endpoint.instant + delta))
    if converter is None or endpoint.expression is None:
        raise ValueError("The authored date's calendar is unavailable.")
    original = TemporalExpression.from_dict(endpoint.expression)
    old = original.resolve_bounds(converter)
    if old.error:
        raise ValueError(old.error)
    nominal = replace(original, explicit_outer_start=None, explicit_outer_end=None)
    target = _bounded(nominal.representative_time(converter) + delta)
    moved = move_expression(original, target, converter)
    new = moved.resolve_bounds(converter)
    if new.error:
        raise ValueError(new.error)
    # A coarse date can snap, but its uncertainty must never shrink or expand.
    for lower, upper in (("hard_start", "hard_end"), ("soft_start", "soft_end")):
        before = (getattr(old, lower), getattr(old, upper))
        after = (getattr(new, lower), getattr(new, upper))
        if all(value is not None for value in (*before, *after)):
            assert before[0] is not None and before[1] is not None
            assert after[0] is not None and after[1] is not None
            if (
                abs((before[1] - before[0]) - (after[1] - after[0]))
                > MOVEMENT_TOLERANCE
            ):
                raise ValueError("This move would change the authored date range.")
    return replace(endpoint, expression=moved.to_dict())


def _connected(
    definitions: dict[str, EventTimingDefinition], identity: str
) -> set[str]:
    neighbours: dict[str, set[str]] = {key: set() for key in definitions}
    for owner, timing in definitions.items():
        for endpoint in (timing.start, timing.end):
            if endpoint is not None and endpoint.kind == "event":
                source = str(endpoint.anchor_id).removeprefix("event:")
                if source not in neighbours:
                    raise ValueError("A dependency source is missing. Repair it first.")
                neighbours[owner].add(source)
                neighbours[source].add(owner)
    found, pending = set(), [identity]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(neighbours[current] - found)
    return found


def movement_updates(
    events: list[Event],
    resolution: TemporalWorldResolution,
    converter: CalendarConverter | None,
    intent: dict[str, Any],
    *,
    index: MovementIndex | None = None,
) -> dict[str, dict[str, Any]]:
    """Change only explicitly authorized authorities; never detach or convert units."""
    if intent["generation"] != resolution.fingerprint:
        raise ValueError("Timing changed since dragging began. Try the move again.")
    identity, mode = str(intent["event_id"]), str(intent["mode"])
    if mode not in MOVE_MODES:
        raise ValueError("Choose Adjust offset or Move chain.")
    index = index or MovementIndex(events)
    originals, definitions = index.originals, index.definitions
    if identity not in definitions:
        raise ValueError("The moved Event no longer exists.")
    target = _bounded(intent["target"])
    delta = target - _coordinate(resolution, f"event:{identity}")
    if delta == 0:
        return {}
    if mode == "offset":
        _require_resolved_followers(definitions, identity, resolution, index.followers)
        timing = definitions[identity]
        start = timing.start
        if start.kind == "event":
            _coordinate(resolution, start.source)
            offset = deepcopy(start.offset or {"unit": "days", "value": 0.0})
            start = (
                replace(
                    start, offset={**offset, "value": finite(offset["value"]) + delta}
                )
                if offset["unit"] == "days"
                else _calendar_offset(start, target, resolution, converter)
            )
        else:
            start = _manual_shift(start, delta, converter)
        changes = {identity: replace(timing, start=start)}
    else:
        changes = _shift_chain(
            definitions, identity, delta, resolution, converter, index.chain(identity)
        )
    return {
        key: {"attributes": timing.apply(originals[key].attributes)}
        for key, timing in changes.items()
        if timing != definitions[key]
    }


def _require_resolved_followers(
    definitions: dict[str, EventTimingDefinition],
    identity: str,
    resolution: TemporalWorldResolution,
    followers: dict[str, set[str]],
) -> None:
    """Do not move a known start while its affected interval is unresolved."""
    pending, checked = [identity], set()
    while pending:
        owner = pending.pop()
        if owner in checked:
            continue
        checked.add(owner)
        timing = definitions[owner]
        _coordinate(resolution, f"event:{owner}")
        if timing.end_mode != "none":
            _coordinate(resolution, f"event:{owner}:end")
        pending.extend(followers.get(owner, set()) - checked)


def _shift_chain(
    definitions: dict[str, EventTimingDefinition],
    identity: str,
    delta: float,
    resolution: TemporalWorldResolution,
    converter: CalendarConverter | None,
    members: set[str],
) -> dict[str, EventTimingDefinition]:
    changes = {}
    for key in sorted(members):
        timing = definitions[key]
        _coordinate(resolution, f"event:{key}")
        endpoints: list[EndpointDefinition | None] = []
        for name, endpoint in (("start", timing.start), ("end", timing.end)):
            if endpoint is None:
                endpoints.append(None)
                continue
            node = f"event:{key}" + (":end" if name == "end" else "")
            previous = _coordinate(resolution, node)
            moved = endpoint
            if endpoint.kind == "manual":
                moved = _manual_shift(endpoint, delta, converter)
                if moved.expression is not None:
                    assert converter is not None
                    date = TemporalExpression.from_dict(
                        moved.expression
                    ).representative_time(converter)
                    if abs(date - previous - delta) > MOVEMENT_TOLERANCE:
                        raise ValueError(
                            "The chain cannot move together at its authored precision."
                        )
            elif (endpoint.offset or {}).get("unit", "days") != "days":
                _exact(resolution, endpoint.source)
            endpoints.append(moved)
        assert endpoints[0] is not None
        changes[key] = replace(timing, start=endpoints[0], end=endpoints[1])
    return changes


def movement_errors(
    before: TemporalWorldResolution,
    after: TemporalWorldResolution,
    events: list[Event],
) -> list[str]:
    """A gesture cannot change the shape or inclusivity of uncertain solutions."""
    for node, old in before.endpoints.items():
        new = after.endpoints.get(node)
        if old.error or new is None or new.error:
            continue
        if old.ranges == new.ranges:
            continue
        if old.coordinate is None or new.coordinate is None:
            return ["This movement has an ambiguous timing range. Use the inspector."]
        delta = new.coordinate - old.coordinate
        if len(old.ranges) != len(new.ranges):
            return ["This movement would change the authored uncertainty."]
        for original, moved in zip(old.ranges, new.ranges, strict=True):
            if (original.lower_closed, original.upper_closed) != (
                moved.lower_closed,
                moved.upper_closed,
            ):
                return ["This movement would change the date range boundaries."]
            for left, right in (
                (original.lower, moved.lower),
                (original.upper, moved.upper),
            ):
                if left is None or right is None:
                    if left != right:
                        return ["This movement would change an open date range."]
                elif abs(float(right - left) - delta) > MOVEMENT_TOLERANCE:
                    return [
                        "This movement would change timing uncertainty. Use the inspector."
                    ]
    return _chronology_uncertainty_errors(before, after, events)


def _chronology_uncertainty_errors(
    before: TemporalWorldResolution,
    after: TemporalWorldResolution,
    events: list[Event],
) -> list[str]:
    """Do not infer preserved correlations from unchanged marginal range widths."""
    for event in events:
        metadata = event.attributes.get("_temporal_v2", {})
        for constraint in metadata.get("constraints", []):
            nodes = (constraint["anchor_a"], constraint["anchor_b"])
            old = [before.endpoints.get(node) for node in nodes]
            new = [after.endpoints.get(node) for node in nodes]
            if any(item is None or item.coordinate is None for item in (*old, *new)):
                continue
            uncertain = any(
                item is not None
                and any(part.lower != part.upper for part in item.ranges)
                for item in old
            )
            changes = [
                float(right.coordinate) - float(left.coordinate)
                for left, right in zip(old, new, strict=True)
                if left is not None
                and right is not None
                and left.coordinate is not None
                and right.coordinate is not None
            ]
            if uncertain and abs(changes[0] - changes[1]) > MOVEMENT_TOLERANCE:
                return [
                    "This move could change correlated chronology uncertainty. Use the inspector."
                ]
    return []


def describe_offsets(event: Event, events: list[Event]) -> str:
    """Expose retained source identity and authored units in preview and review."""
    timing = EventTimingDefinition.from_event(event)
    names = {f"event:{item.id}": item.name for item in events}
    lines = []
    for label, endpoint in (("Start", timing.start), ("End", timing.end)):
        if endpoint is not None and endpoint.kind == "event":
            offset = endpoint.offset or {"unit": "days", "value": 0}
            lines.append(
                f"{label} follows {names.get(str(endpoint.anchor_id), 'missing Event')} "
                f"{endpoint.endpoint}; offset: {offset['value']:g} {offset['unit']}."
            )
    return "\n".join(lines)
