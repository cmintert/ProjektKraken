"""Render persisted projection snapshots without converting them into evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal

from src.core.event_timing.constraints import rational
from src.core.temporal_expression import (
    MAX_LORE_DAY,
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
)

if TYPE_CHECKING:
    from src.core.calendar import CalendarConverter
    from src.core.event_timing.resolution import TemporalWorldResolution
    from src.core.events import Event


OccurrenceKind = Literal["exact", "window", "soft", "one_sided", "unresolved"]


@dataclass(frozen=True)
class TemporalDisplay:
    """Immutable meaning and bounds of one temporal presentation channel."""

    possible_start: float | None
    possible_end: float | None
    certain_start: float | None = None
    certain_end: float | None = None
    caption: str = "Timing unresolved"
    kind: Literal["point", "duration"] = "point"
    precision: TemporalPrecision | None = None
    qualifier: TemporalQualifier = TemporalQualifier.ASSERTED
    anchor: float = 0.0
    explicit_window: bool = False
    error: bool = False
    occurrence: OccurrenceKind = "unresolved"
    ranges: tuple[tuple[float | None, float | None, bool, bool], ...] = ()


@dataclass(frozen=True)
class TemporalPresentation:
    """Single rendering contract for occurrence, length and possible presence."""

    start: TemporalDisplay
    end: TemporalDisplay | None
    authored_duration: float | None
    presence: TemporalDisplay

    @property
    def layered(self) -> bool:
        """Use a presence span for independent ends or uncertain duration starts."""
        return not self.presence.error and (
            self.end is not None
            or (self.authored_duration is not None and self.start.occurrence != "exact")
        )


def _number(value: str | None) -> float | None:
    return None if value is None or value == "None" else float(Fraction(value))


def _limits(endpoint: dict[str, Any]) -> tuple[float | None, float | None]:
    ranges = endpoint.get("ranges", [])
    if not ranges:
        coordinate = endpoint.get("coordinate")
        return coordinate, coordinate
    return _number(ranges[0][0]), _number(ranges[-1][1])


def endpoint_caption(
    endpoint: dict[str, Any],
    converter: CalendarConverter | None,
    *,
    include_time: bool = False,
) -> str:
    """Describe feasible alternatives, optionally retaining clock time in reviews."""
    if endpoint.get("error"):
        return str(endpoint["error"])
    lower, upper = _limits(endpoint)
    if lower is None and upper is None:
        return "Date unknown"

    def show(value: float | None) -> str:
        if converter is not None and value is not None and include_time:
            return converter.format_datetime(value, include_midnight=False)
        return (
            "unknown"
            if value is None
            else converter.format_date(value)
            if converter
            else f"{value:g} days"
        )

    alternatives = endpoint.get("ranges", [])
    if alternatives:
        parts = []
        for start, end, start_closed, end_closed in alternatives:
            first, last = _number(start), _number(end)
            if first == last and first is not None:
                parts.append(show(first))
                continue
            sides = []
            if first is not None:
                sides.append(("from " if start_closed else "after ") + show(first))
            if last is not None:
                sides.append(("through " if end_closed else "before ") + show(last))
            parts.append("; ".join(sides) or "Date unknown")
        text = " or ".join(parts)
    else:
        text = (
            show(lower)
            if lower == upper
            else f"{show(lower)} to {show(upper)} (possible dates)"
        )
    if not endpoint.get("verified", False):
        text += " — timing constraints need repair"
    return text


def explain_timing(
    event: Event,
    result: TemporalWorldResolution,
    events: list[Event],
    converter: CalendarConverter | None,
) -> str:
    """Separate authored evidence, feasible alternatives and applicable rules."""
    from src.core.event_timing.definitions import EventTimingDefinition

    names = {item.id: item.name for item in events}
    definitions = {}
    chronology = {}
    for item in events:
        node = f"event:{item.id}"
        try:
            timing = EventTimingDefinition.from_event(item)
            definitions[node] = timing.start
            if timing.end is not None:
                definitions[node + ":end"] = timing.end
        except (ValueError, TypeError, KeyError):
            pass
        metadata = item.attributes.get("_temporal_v2", {})
        if isinstance(metadata, dict):
            for index, rule in enumerate(metadata.get("constraints", [])):
                chronology[rule.get("id") or f"chronology:{item.id}:{index}"] = rule

    def endpoint_name(node: str) -> str:
        identity = node.removeprefix("event:").removesuffix(":end")
        return names.get(identity, identity) + (
            " end" if node.endswith(":end") else " start"
        )

    sections = []
    for node in (f"event:{event.id}", f"event:{event.id}:end"):
        endpoint = result.endpoints.get(node)
        if endpoint is None:
            continue
        from src.core.event_timing.projection import endpoint_signature

        signature = endpoint_signature(endpoint)
        sections.append(
            f"{endpoint_name(node)}\nAuthored evidence: {endpoint.authored.label or 'No bounded date evidence'}\nFeasible dates: {endpoint_caption(signature, converter)}"
        )
        rules = []
        for rule in endpoint.provenance:
            if rule.startswith("reference:"):
                target = rule.removeprefix("reference:")
                definition = definitions.get(target)
                if definition is not None and definition.kind == "event":
                    rules.append(
                        endpoint_name(target)
                        + " follows "
                        + endpoint_name(definition.source)
                    )
                else:
                    rules.append("Fixed duration defines " + endpoint_name(target))
            elif rule.startswith("interval:"):
                rules.append(
                    "Start must not follow end: "
                    + names.get(
                        rule.removeprefix("interval:"), rule.removeprefix("interval:")
                    )
                )
            elif rule in chronology:
                assertion = chronology[rule]
                rules.append(
                    endpoint_name(assertion["anchor_a"])
                    + " "
                    + assertion["relation"].replace("_", " ")
                    + " "
                    + endpoint_name(assertion["anchor_b"])
                    + f"; minimum gap {assertion.get('min_offset_days', 0):g} days"
                )
        if rules:
            sections.append(
                "Applicable constraints in this connected group:\n"
                + "\n".join(dict.fromkeys(rules))
            )
    return "\n\n".join(sections)


def _classify(
    lower: float | None,
    upper: float | None,
    expression: TemporalExpression | None,
    endpoint: dict[str, Any],
) -> OccurrenceKind:
    """Choose occurrence meaning once, independently of zoom or storage format."""
    if endpoint.get("error") or not endpoint.get("verified", True):
        return "unresolved"
    if lower is None and upper is None:
        return "soft"
    if lower is None or upper is None:
        return "one_sided"
    if len(endpoint.get("ranges", [])) > 1:
        return "window"
    if expression is not None:
        if (
            expression.explicit_outer_start is not None
            or expression.explicit_outer_end is not None
        ):
            return "window"
        if expression.qualifier not in {
            TemporalQualifier.ASSERTED,
            TemporalQualifier.CALCULATED,
        }:
            return "window"
        return (
            "window"
            if expression.precision in {TemporalPrecision.YEAR, TemporalPrecision.MONTH}
            else "exact"
        )
    return "exact" if lower == upper else "window"


def _endpoint_display(
    endpoint: dict[str, Any],
    converter: CalendarConverter | None,
) -> TemporalDisplay:
    """Combine resolved ranges with their original assertion provenance."""
    lower, upper = _limits(endpoint)
    meaning = endpoint.get("meaning", {})
    data = meaning.get("expression")
    expression = (
        TemporalExpression.from_dict(data)
        if data and not endpoint.get("error")
        else None
    )
    occurrence = _classify(lower, upper, expression, endpoint)
    caption = endpoint_caption(endpoint, converter, include_time=True)
    if (
        expression is None
        and converter is None
        and lower == upper
        and lower is not None
    ):
        caption = f"{lower:.1f}"
    if (
        expression is not None
        and not meaning.get("derived")
        and not endpoint.get("error")
    ):
        bounds = expression.resolve_bounds(converter) if converter else None
        if bounds is not None and (lower, upper) == (
            bounds.hard_start,
            bounds.hard_end,
        ):
            caption = expression.display_text(converter)
            if occurrence != "exact":
                caption += " · exact date unknown"
    return TemporalDisplay(
        lower,
        upper,
        caption=caption,
        precision=expression.precision if expression else None,
        qualifier=expression.qualifier if expression else TemporalQualifier.ASSERTED,
        anchor=endpoint.get("coordinate") or 0.0,
        explicit_window=bool(
            expression
            and (
                expression.explicit_outer_start is not None
                or expression.explicit_outer_end is not None
            )
        ),
        error=occurrence == "unresolved",
        occurrence=occurrence,
        ranges=tuple(
            (_number(first), _number(last), first_closed, last_closed)
            for first, last, first_closed, last_closed in endpoint.get("ranges", [])
        ),
    )


def _presence(
    start: TemporalDisplay,
    end: TemporalDisplay,
    duration: float | None,
    authored: bool,
) -> TemporalDisplay:
    """Retain possible/certain presence without turning precision into duration."""
    certain_start, certain_end = start.possible_end, end.possible_start
    if certain_start is None or certain_end is None or certain_start >= certain_end:
        certain_start = certain_end = None
    caption = f"Starts: {start.caption} · Ends: {end.caption}"
    if duration is not None:
        label = "Duration" if authored else "Calculated duration"
        caption += f" · {label}: {duration:g} days"
    return replace(
        start,
        possible_end=end.possible_end,
        certain_start=certain_start,
        certain_end=certain_end,
        caption=caption,
        kind="duration",
        error=start.error or end.error,
        occurrence="unresolved" if start.error or end.error else start.occurrence,
        ranges=(),
    )


def present_exact_legacy_event(
    event: Event, converter: CalendarConverter | None
) -> TemporalPresentation | None:
    """Present independent numeric timing without building a constraint network."""
    if "_temporal_v2" in event.attributes or event.is_recurring:
        return None
    start = event.lore_date
    duration = event.lore_duration
    if (
        start is None
        or isinstance(start, bool)
        or not -MAX_LORE_DAY <= start <= MAX_LORE_DAY
        or (
            duration is not None
            and (isinstance(duration, bool) or not 0 <= duration <= 2 * MAX_LORE_DAY)
        )
    ):
        return None
    start_day = rational(start)
    end_day = start_day + rational(duration) if duration else None
    if end_day is not None and abs(end_day) > MAX_LORE_DAY:
        return None

    def display(day: Fraction) -> TemporalDisplay:
        exact = str(day)
        return _endpoint_display(
            {
                "coordinate": float(day),
                "ranges": [(exact, exact, True, True)],
                "verified": True,
            },
            converter,
        )

    try:
        start_display = display(start_day)
        presence = (
            _presence(start_display, display(end_day), duration, True)
            if end_day is not None
            else start_display
        )
    except (ValueError, OverflowError):
        return None
    return TemporalPresentation(start_display, None, duration or None, presence)


def present_event(
    event: Event, converter: CalendarConverter | None
) -> TemporalPresentation:
    """Build the sole immutable rendering model from an accepted timing snapshot.

    Detached standalone callers normalize through the same resolver. Prepared
    world snapshots already contain resolution and never invoke the solver.
    """
    return _present_snapshot(
        json.dumps(event.to_dict(), sort_keys=True),
        converter._config.to_json() if converter else None,
    )


def _snapshot(event: Event) -> dict[str, Any] | None:
    """Read only structurally valid derived metadata; malformed sources resolve as errors."""
    metadata = event.attributes.get("_temporal_v2")
    value = metadata.get("projection") if isinstance(metadata, dict) else None
    return value if isinstance(value, dict) else None


@lru_cache(maxsize=2048)
def _present_snapshot(
    event_json: str, calendar_json: str | None
) -> TemporalPresentation:
    """Cache by complete source facts and calendar, never by a mutable object id."""
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.event_timing.definitions import EventTimingDefinition
    from src.core.event_timing.projection import project_event
    from src.core.event_timing.solver import resolve_world
    from src.core.events import Event

    event = Event.from_dict(json.loads(event_json))
    converter = (
        CalendarConverter(CalendarConfig.from_json(calendar_json))
        if calendar_json
        else None
    )
    projection = _snapshot(event)
    try:
        definition = EventTimingDefinition.from_event(event).to_dict()
    except (ValueError, TypeError, KeyError):
        definition = None
    if (
        not projection
        or definition is None
        or "meaning" not in projection.get("start", {})
        or projection.get("definition") != definition
        or projection.get("calendar_json") != calendar_json
    ):
        result = resolve_world([event], converter)
        event = project_event(event, result)
        projection = _snapshot(event)
        if not projection:
            endpoint = result.endpoints[f"event:{event.id}"]
            unknown = TemporalDisplay(
                None,
                None,
                error=True,
                caption="Date unknown"
                if event.lore_date is None and not event.attributes.get("_temporal_v2")
                else endpoint.error or "Timing unresolved",
            )
            return TemporalPresentation(unknown, None, None, unknown)
    start = _endpoint_display(projection["start"], converter)
    authored = projection.get("duration_authored", False)
    duration = projection.get("duration")
    end = (
        _endpoint_display(projection["end"], converter)
        if projection.get("has_end")
        else None
    )
    presence = _presence(start, end, duration, authored) if end is not None else start
    return TemporalPresentation(
        start, end if not authored else None, duration if authored else None, presence
    )


def event_navigation_context(
    event: Event, converter: CalendarConverter | None
) -> dict[str, object]:
    """Describe navigation using exactly the same meaning as the painted marker."""
    start = present_event(event, converter).start
    return {
        "event_id": event.id,
        "name": event.name,
        "caption": start.caption,
        "uncertain": start.occurrence != "exact",
        "unresolved": start.error,
        "time": event.lore_date,
    }
