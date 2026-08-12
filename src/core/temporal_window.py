"""Shared temporal-window semantics for relations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TemporalWindowKind(Enum):
    """Supported relation window kinds."""

    INTERVAL = "interval"
    INSTANT = "instant"
    UNBOUNDED = "unbounded"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TemporalWindow:
    """Resolved temporal window for one relation."""

    kind: TemporalWindowKind
    start: float | None = None
    end: float | None = None
    error: str | None = None

    def is_active(self, lore_time: float) -> bool:
        """Return whether the window is active at *lore_time*."""
        if self.kind == TemporalWindowKind.INSTANT:
            return self.start is not None and math.isclose(
                lore_time,
                self.start,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        if self.kind in {
            TemporalWindowKind.UNBOUNDED,
            TemporalWindowKind.UNRESOLVED,
        }:
            return False
        if self.start is not None and lore_time < self.start:
            return False
        return self.end is None or lore_time < self.end

    @property
    def is_valid(self) -> bool:
        """Return whether the window has usable semantics."""
        if self.kind == TemporalWindowKind.UNRESOLVED:
            return False
        if self.kind == TemporalWindowKind.INTERVAL:
            return self.end is None or self.start is None or self.start < self.end
        return True


def resolve_temporal_window(
    attributes: dict[str, Any],
    source_event_date: float | None = None,
) -> TemporalWindow:
    """Resolve relation attributes into shared interval or instant semantics."""
    from_event = attributes.get("valid_from_event") is True
    to_event = attributes.get("valid_to_event") is True
    is_instant = attributes.get("valid_at_event") is True or (
        from_event and to_event
    )

    if (from_event or to_event or is_instant) and source_event_date is None:
        return TemporalWindow(
            TemporalWindowKind.UNRESOLVED,
            error="Dynamic temporal window has no source event date.",
        )

    if is_instant:
        assert source_event_date is not None
        return TemporalWindow(
            TemporalWindowKind.INSTANT,
            start=float(source_event_date),
            end=float(source_event_date),
        )

    start_value = source_event_date if from_event else attributes.get("valid_from")
    end_value = source_event_date if to_event else attributes.get("valid_to")
    if start_value is None and end_value is None:
        return TemporalWindow(TemporalWindowKind.UNBOUNDED)

    try:
        start = float(start_value) if start_value is not None else None
        end = float(end_value) if end_value is not None else None
    except (TypeError, ValueError):
        return TemporalWindow(
            TemporalWindowKind.UNRESOLVED,
            error="Temporal window contains a non-numeric bound.",
        )

    if start is not None and not math.isfinite(start):
        return TemporalWindow(
            TemporalWindowKind.UNRESOLVED,
            error="Temporal window start is not finite.",
        )
    if end is not None and not math.isfinite(end):
        return TemporalWindow(
            TemporalWindowKind.UNRESOLVED,
            error="Temporal window end is not finite.",
        )
    if start is not None and end is not None and start >= end:
        return TemporalWindow(
            TemporalWindowKind.INTERVAL,
            start=start,
            end=end,
            error="Temporal interval start must be before its end.",
        )
    return TemporalWindow(TemporalWindowKind.INTERVAL, start=start, end=end)
