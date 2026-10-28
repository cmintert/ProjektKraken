"""Shared temporal-window semantics for relations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.core.calendar import CalendarConverter
from src.core.temporal_boundary_resolver import BoundaryResolver as _BoundaryResolver
from src.core.temporal_expression import ResolvedTemporalBounds

STRICT_TEMPORAL_SCHEMA = 2

if TYPE_CHECKING:
    from src.core.temporal_constraints import TemporalConstraint


class TemporalValidity(str, Enum):
    """Truth at a playhead, keeping missing knowledge distinct from falsehood."""

    DEFINITE = "definite"
    POSSIBLE = "possible"
    INACTIVE = "inactive"
    INDETERMINATE = "indeterminate"


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
    start_bounds: ResolvedTemporalBounds | None = None
    end_bounds: ResolvedTemporalBounds | None = None
    semantic: bool = False

    def status_at(self, lore_time: float) -> TemporalValidity:
        """Evaluate shared half-open semantics using evidence bounds only."""
        if not math.isfinite(lore_time):
            return TemporalValidity.INDETERMINATE
        if self.kind == TemporalWindowKind.INTERVAL and self.is_empty:
            return TemporalValidity.INACTIVE
        if self.error:
            return TemporalValidity.INDETERMINATE
        if self.kind == TemporalWindowKind.UNRESOLVED:
            return TemporalValidity.INDETERMINATE
        from src.core.event_timing.window_queries import joint_window_status

        joint_status = joint_window_status([self], lore_time)
        if joint_status is not None:
            return TemporalValidity(joint_status)
        if not self.semantic:
            if self.kind == TemporalWindowKind.UNBOUNDED:
                return TemporalValidity.DEFINITE
            return (
                TemporalValidity.DEFINITE
                if self._legacy_active(lore_time)
                else TemporalValidity.INACTIVE
            )
        if self.kind == TemporalWindowKind.INTERVAL:
            from src.core.temporal_joint import jointly_possible

            if not jointly_possible([self], lore_time):
                return TemporalValidity.INACTIVE
        start, end = self.start_bounds, self.end_bounds
        if self.kind == TemporalWindowKind.INSTANT:
            return _instant_validity(start, lore_time)
        smin = start.hard_start if start else float("-inf")
        smax = start.hard_end if start else float("-inf")
        emin = end.hard_start if end else float("inf")
        emax = end.hard_end if end else float("inf")
        if _outside_possible(start, end, lore_time):
            return TemporalValidity.INACTIVE
        end_certain = emin is not None and (
            lore_time < emin
            or (lore_time == emin and end is not None and not end.lower_inclusive)
        )
        if smax is not None and smax <= lore_time and end_certain:
            return TemporalValidity.DEFINITE
        if None in (smin, smax, emin, emax):
            return TemporalValidity.INDETERMINATE
        return TemporalValidity.POSSIBLE

    @property
    def is_empty(self) -> bool:
        """Prove empty intervals without turning them into occurrences."""
        if self.kind != TemporalWindowKind.INTERVAL:
            return False
        start, end = self.start_bounds, self.end_bounds
        if start and end:
            from src.core.temporal_joint import definitely_reversed

            if definitely_reversed(start, end):
                return True
        return (
            self.start is not None and self.end is not None and self.start >= self.end
        )

    def is_definitely_active(self, lore_time: float) -> bool:
        """Explicit strict policy for consumers requiring certain state."""
        return self.status_at(lore_time) == TemporalValidity.DEFINITE

    def _legacy_active(self, lore_time: float) -> bool:
        """Compatibility calculation only; new callers must select a status policy."""
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
        if self.error or self.kind == TemporalWindowKind.UNRESOLVED or self.is_empty:
            return False
        if self.kind == TemporalWindowKind.INTERVAL:
            return self.end is None or self.start is None or self.start < self.end
        return True


def _instant_validity(
    bounds: ResolvedTemporalBounds | None, time: float
) -> TemporalValidity:
    """Classify occurrences without losing strict constraint endpoint flags."""
    if bounds is None:
        return TemporalValidity.INDETERMINATE
    if bounds.possible_ranges is not None and not any(
        start <= time < end or start == end == time
        for start, end in bounds.possible_ranges
    ):
        return TemporalValidity.INACTIVE
    lower, upper = bounds.hard_start, bounds.hard_end
    if lower is not None and (
        time < lower or (time == lower and not bounds.lower_inclusive)
    ):
        return TemporalValidity.INACTIVE
    if lower == upper == time:
        return TemporalValidity.DEFINITE
    if upper is not None and (
        time > upper or (time == upper and not bounds.upper_inclusive)
    ):
        return TemporalValidity.INACTIVE
    return (
        TemporalValidity.POSSIBLE
        if bounds.has_hard_bounds
        else TemporalValidity.INDETERMINATE
    )


def intersect_window_status(
    windows: list[TemporalWindow],
    lore_time: float,
    constraints: tuple[TemporalConstraint, ...] = (),
) -> TemporalValidity:
    """Intersect inherited windows while retaining shared uncertain transitions."""
    for first in windows:
        for second in windows:
            if (
                first.kind != TemporalWindowKind.INTERVAL
                or second.kind != TemporalWindowKind.INTERVAL
            ):
                continue
            start, end = first.start_bounds, second.end_bounds
            if start is None or end is None or start.error or end.error:
                continue
            if constraints and _ordered_transitions(start, end, constraints):
                return TemporalValidity.INACTIVE
            if start.anchor_id and start.anchor_id == end.anchor_id:
                return TemporalValidity.INACTIVE
            if start.base_anchor and start.base_anchor == end.base_anchor:
                if start.day_offset >= end.day_offset:
                    return TemporalValidity.INACTIVE
            if (
                start.hard_start is not None
                and end.hard_end is not None
                and start.hard_start >= end.hard_end
            ):
                return TemporalValidity.INACTIVE
    from src.core.temporal_joint import jointly_possible

    if not jointly_possible(windows, lore_time):
        return TemporalValidity.INACTIVE
    statuses = [window.status_at(lore_time) for window in windows]
    for status in (
        TemporalValidity.INACTIVE,
        TemporalValidity.INDETERMINATE,
        TemporalValidity.POSSIBLE,
    ):
        if status in statuses:
            return status
    return TemporalValidity.DEFINITE


def _ordered_transitions(
    start: ResolvedTemporalBounds,
    end: ResolvedTemporalBounds,
    constraints: tuple[TemporalConstraint, ...],
) -> bool:
    """Reuse asserted chronology without treating coincident dates as aliases."""
    from src.core.temporal_constraints import anchor_precedes, anchors_share_transition

    if start.anchor_id and end.anchor_id:
        rules = list(constraints)
        return anchors_share_transition(
            end.anchor_id, start.anchor_id, rules
        ) or anchor_precedes(end.anchor_id, start.anchor_id, rules)
    return False


def definite_window_time(windows: list[TemporalWindow], current: float) -> float | None:
    """Choose a navigation coordinate only if every inherited window guarantees it."""
    starts, ends = [], []
    for window in windows:
        if window.semantic:
            for bounds in (window.start_bounds, window.end_bounds):
                if bounds is not None and not bounds.has_hard_bounds:
                    return None
            lower = window.start_bounds.hard_end if window.start_bounds else -math.inf
            upper = window.end_bounds.hard_start if window.end_bounds else math.inf
            if lower is None or upper is None:
                return None
            starts.append(lower)
            ends.append(upper)
        else:
            starts.append(window.start if window.start is not None else -math.inf)
            ends.append(window.end if window.end is not None else math.inf)
    start, end = max(starts, default=-math.inf), min(ends, default=math.inf)
    preferred = start if current < start else max(start, end - 1)
    candidates = (preferred, start, math.nextafter(end, -math.inf), 0.0)
    return next(
        (
            value
            for value in candidates
            if math.isfinite(value)
            and all(window.is_definitely_active(value) for window in windows)
        ),
        None,
    )


def _outside_possible(
    start: ResolvedTemporalBounds | None,
    end: ResolvedTemporalBounds | None,
    time: float,
) -> bool:
    """Honor strict lower bounds and both exact and half-open upper bounds."""
    if start and start.hard_start is not None:
        if time < start.hard_start or (
            time == start.hard_start and not start.lower_inclusive
        ):
            return True
    if end and end.hard_end is not None:
        if time > end.hard_end:
            return True
        if time == end.hard_end:
            return not end.upper_inclusive or end.hard_start == end.hard_end
    return False


def resolve_temporal_window(
    attributes: dict[str, Any],
    source_event_date: float | None = None,
    *,
    source_event_attributes: dict[str, Any] | None = None,
    source_event_id: str | None = None,
    converter: CalendarConverter | None = None,
    anchors: dict[str, ResolvedTemporalBounds] | None = None,
) -> TemporalWindow:
    """Resolve relation attributes into shared interval or instant semantics."""
    if "temporal" in attributes or (
        source_event_attributes
        and "_temporal_v2" in source_event_attributes
        and any(
            attributes.get(key)
            for key in ("valid_from_event", "valid_to_event", "valid_at_event")
        )
    ):
        return _resolve_semantic_window(
            attributes,
            source_event_date,
            source_event_attributes or {},
            source_event_id,
            converter,
            anchors or {},
        )
    from_event = attributes.get("valid_from_event") is True
    to_event = attributes.get("valid_to_event") is True
    is_instant = attributes.get("valid_at_event") is True or (from_event and to_event)

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


def _resolve_semantic_window(
    attributes: dict[str, Any],
    source_date: float | None,
    source_attributes: dict[str, Any],
    source_id: str | None,
    converter: CalendarConverter | None,
    anchors: dict[str, ResolvedTemporalBounds],
) -> TemporalWindow:
    """Normalize semantic and legacy bindings at one domain boundary."""
    resolver = _BoundaryResolver(
        source_date, source_attributes, source_id, converter, anchors
    )

    def legacy_side(name: str) -> dict[str, Any]:
        if attributes.get(f"valid_{name}_event"):
            return {"binding": "source_event"}
        value = attributes.get(f"valid_{name}")
        return {"exact": value} if value is not None else {"status": "open"}

    try:
        spec = attributes.get("temporal")
        if spec is None:
            spec = {"schema": 1, "start": legacy_side("from"), "end": legacy_side("to")}
            if attributes.get("valid_at_event") or (
                attributes.get("valid_from_event") and attributes.get("valid_to_event")
            ):
                spec["at"] = {"binding": "source_event"}
        if not isinstance(spec, dict) or spec.get("schema", 1) not in {1, 2}:
            raise ValueError("Unsupported temporal relation metadata")
        resolver.default_semantics = (
            "strict_v2" if spec.get("schema") == STRICT_TEMPORAL_SCHEMA else "legacy_v1"
        )
        instant = "at" in spec
        start = resolver.boundary(
            spec.get("at", spec.get("start", {"status": "unknown"}))
        )
        end = (
            start
            if instant
            else resolver.boundary(spec.get("end", {"status": "unknown"}))
        )
        error = next((b.error for b in (start, end) if b and b.error), None)
        if (
            not instant
            and start
            and end
            and start.hard_start is not None
            and end.hard_end is not None
        ):
            if start.hard_start >= end.hard_end:
                error = "Temporal start cannot precede the end."
        return TemporalWindow(
            TemporalWindowKind.INSTANT if instant else TemporalWindowKind.INTERVAL,
            start=start.hard_start if start else None,
            end=end.hard_end if end else None,
            error=error,
            start_bounds=start,
            end_bounds=end,
            semantic=True,
        )
    except (ValueError, TypeError, KeyError) as exc:
        return TemporalWindow(
            TemporalWindowKind.UNRESOLVED, error=str(exc), semantic=True
        )
