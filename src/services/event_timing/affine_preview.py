"""Certified translation preview for exact day-reference trees only."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any

from src.core.event_timing.definitions import EventTimingDefinition
from src.core.events import Event
from src.services.event_timing.movement import MovementIndex, _bounded


def supports_translation(events: list[Event], index: MovementIndex) -> bool:
    """No chronology, uncertainty, calendar rules or independent ends may be skipped."""
    for event in events:
        timing = index.definitions[event.id]
        if timing.end_mode == "independent" or event.attributes.get(
            "_temporal_v2", {}
        ).get("constraints"):
            return False
        start = timing.start
        if start.kind == "manual" and start.instant is None:
            return False
        if start.kind == "event" and (start.offset or {}).get("unit", "days") != "days":
            return False
    return True


def translated_preview(
    index: MovementIndex,
    baseline: dict[str, dict[str, Any]],
    updates: dict[str, dict[str, Any]],
    identity: str,
    mode: str,
) -> tuple[dict[str, dict[str, Any]], float]:
    """Translate exact rational endpoint values after the shared movement guards run."""
    if not updates:
        return {}, float(baseline[identity]["lore_date"])
    authority = identity if mode == "offset" else next(iter(updates))
    original = index.definitions[authority].start
    definition = EventTimingDefinition.from_dict(
        updates[authority]["attributes"]["_temporal_v2"]["timing"]
    )
    if original.kind == "manual":
        assert original.instant is not None and definition.start.instant is not None
        delta = Fraction(definition.start.instant) - Fraction(original.instant)
    else:
        delta = Fraction((definition.start.offset or {})["value"]) - Fraction(
            (original.offset or {})["value"]
        )
    members = index.chain(identity) if mode == "chain" else _followers(index, identity)
    rows = {}
    for key in members:
        previous = baseline[key]
        row = deepcopy(previous["attributes"].get("_temporal_v2", {}))
        if key in updates:
            row = deepcopy(updates[key]["attributes"]["_temporal_v2"])
        projection = deepcopy(
            previous["attributes"].get("_temporal_v2", {}).get("projection")
        )
        if projection is not None:
            for endpoint in (projection.get("start"), projection.get("end")):
                if endpoint is not None:
                    _translate_endpoint(endpoint, delta)
            row["projection"] = projection
        # Semantic authorities newly upgraded from legacy need fresh endpoint projections.
        # Projected coordinates are exact in this certified tree; legacy manual rows
        # need no cached projection to render their numeric date/duration correctly.
        date = (
            projection["start"]["coordinate"]
            if projection is not None
            else _bounded(float(Fraction(previous["lore_date"]) + delta))
        )
        duration = index.definitions[key].duration_days
        if duration is not None:
            _bounded(float(Fraction(date) + Fraction(duration)))
        rows[key] = {
            "lore_date": date,
            "lore_duration": previous["lore_duration"],
            "temporal": row or None,
        }
    return rows, float(rows[identity]["lore_date"])


def _followers(index: MovementIndex, identity: str) -> set[str]:
    found, pending = set(), [identity]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(index.followers.get(current, set()) - found)
    return found


def _translate_endpoint(endpoint: dict[str, Any], delta: Fraction) -> None:
    if endpoint.get("coordinate") is not None:
        endpoint["coordinate"] = _bounded(
            float(Fraction(endpoint["ranges"][0][0]) + delta)
        )
    endpoint["ranges"] = [
        (str(Fraction(lower) + delta), str(Fraction(upper) + delta), left, right)
        for lower, upper, left, right in endpoint["ranges"]
    ]
