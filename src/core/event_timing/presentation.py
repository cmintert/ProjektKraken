"""Render persisted projection snapshots without converting them into evidence."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.calendar import CalendarConverter
    from src.core.event_timing.resolution import TemporalWorldResolution
    from src.core.events import Event
    from src.core.temporal_display import TemporalDisplay


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


def projection_display(
    event: Event, converter: CalendarConverter | None, channel: str = "presence"
) -> TemporalDisplay:
    """Present uncertainty, independent ends and authored duration independently."""
    from src.core.temporal_display import TemporalDisplay

    projection = event.attributes["_temporal_v2"]["projection"]
    start, end = projection["start"], projection["end"]
    selected = end if channel == "end" else start
    lower, upper = _limits(selected)
    anchor = selected.get("coordinate")
    if anchor is None:
        anchor = event.lore_date if event.lore_date is not None else 0.0
    error = bool(selected.get("error"))
    caption = endpoint_caption(selected, converter)
    interval = channel == "presence" and projection.get("has_end", False)
    certain_start = certain_end = None
    if interval:
        end_lower, end_upper = _limits(end)
        if end.get("error"):
            caption += " · End unresolved"
            error = True
        else:
            certain_start, certain_end = upper, end_lower
            upper = end_upper
            caption = f"Starts: {endpoint_caption(start, converter)} · Ends: {endpoint_caption(end, converter)}"
        duration = projection.get("duration")
        if duration is not None:
            label = (
                "Duration"
                if projection.get("duration_authored")
                else "Calculated duration"
            )
            caption += f" · {label}: {duration:g} days"
    if certain_start is None or certain_end is None or certain_start >= certain_end:
        certain_start = certain_end = None
    return TemporalDisplay(
        lower,
        upper,
        certain_start,
        certain_end,
        caption,
        kind="duration" if interval else "point",
        anchor=anchor,
        explicit_window=lower != upper,
        error=error,
    )
