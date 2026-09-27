"""Shared temporal-window semantics for relations."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    TemporalExpression,
    expression_from_attributes,
)


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
        if not math.isfinite(lore_time) or self.error:
            return TemporalValidity.INDETERMINATE
        if self.kind == TemporalWindowKind.UNRESOLVED:
            return TemporalValidity.INDETERMINATE
        if not self.semantic:
            if self.kind == TemporalWindowKind.UNBOUNDED:
                return TemporalValidity.DEFINITE
            return (
                TemporalValidity.DEFINITE
                if self._legacy_active(lore_time)
                else TemporalValidity.INACTIVE
            )
        start, end = self.start_bounds, self.end_bounds
        if self.kind == TemporalWindowKind.INSTANT:
            if start is None:
                return TemporalValidity.INDETERMINATE
            if start.hard_start is not None and lore_time < start.hard_start:
                return TemporalValidity.INACTIVE
            if start.hard_end is not None and lore_time >= start.hard_end:
                if start.hard_start == start.hard_end == lore_time:
                    return TemporalValidity.DEFINITE
                return TemporalValidity.INACTIVE
            return (
                TemporalValidity.POSSIBLE
                if start.has_hard_bounds
                else TemporalValidity.INDETERMINATE
            )
        if start and end and start.anchor_id and start.anchor_id == end.anchor_id:
            return TemporalValidity.INACTIVE
        smin = start.hard_start if start else float("-inf")
        smax = start.hard_end if start else float("-inf")
        emin = end.hard_start if end else float("inf")
        emax = end.hard_end if end else float("inf")
        if smin is not None and lore_time < smin:
            return TemporalValidity.INACTIVE
        if emax is not None and lore_time >= emax:
            return TemporalValidity.INACTIVE
        if smax is not None and emin is not None and smax <= lore_time < emin:
            return TemporalValidity.DEFINITE
        if None in (smin, smax, emin, emax):
            return TemporalValidity.INDETERMINATE
        return TemporalValidity.POSSIBLE

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
        if self.error or self.kind == TemporalWindowKind.UNRESOLVED:
            return False
        if self.kind == TemporalWindowKind.INTERVAL:
            return self.end is None or self.start is None or self.start < self.end
        return True


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
        if not isinstance(spec, dict) or spec.get("schema", 1) != 1:
            raise ValueError("Unsupported temporal relation metadata")
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


@dataclass
class _BoundaryResolver:
    """Resolve one boundary against an immutable query context."""

    source_date: float | None
    source_attributes: dict[str, Any]
    source_id: str | None
    converter: CalendarConverter | None
    anchors: dict[str, ResolvedTemporalBounds]

    def expression_bounds(self, data: dict[str, Any]) -> ResolvedTemporalBounds:
        if self.converter is None:
            return ResolvedTemporalBounds(error="Calendar unavailable for this date.")
        return TemporalExpression.from_dict(data).resolve_bounds(self.converter)

    def source_bounds(self) -> ResolvedTemporalBounds:
        expression = expression_from_attributes(self.source_attributes)
        anchor_id = f"event:{self.source_id}" if self.source_id else None
        if expression is not None:
            return replace(
                self.expression_bounds(expression.to_dict()), anchor_id=anchor_id
            )
        if self.source_date is None:
            return ResolvedTemporalBounds(
                anchor_id=anchor_id, error="Source event unavailable."
            )
        return ResolvedTemporalBounds(
            self.source_date, self.source_date, anchor_id=anchor_id
        )

    def boundary(self, data: dict[str, Any]) -> ResolvedTemporalBounds | None:
        if not isinstance(data, dict):
            raise ValueError("Temporal boundary must be an object")
        status = data.get("status", "known")
        if status in {"open", "not_applicable"}:
            return None
        if status == "unknown":
            return ResolvedTemporalBounds()
        if status != "known":
            raise ValueError("Invalid temporal boundary status")
        if "expression" in data:
            return self.expression_bounds(data["expression"])
        if "exact" in data:
            exact = float(data["exact"])
            if not math.isfinite(exact):
                raise ValueError("Temporal coordinate must be finite")
            return ResolvedTemporalBounds(exact, exact)
        if data.get("binding") == "source_event":
            return self.source_bounds()
        if "anchor" in data:
            ref = data["anchor"]
            anchor_id = ref["anchor_id"]
            result = (
                self.source_bounds()
                if anchor_id == f"event:{self.source_id}"
                else self.anchors.get(
                    anchor_id,
                    ResolvedTemporalBounds(
                        anchor_id=anchor_id, error="Referenced event unavailable."
                    ),
                )
            )
            offset = float(ref.get("offset_days", 0))
            if not math.isfinite(offset):
                raise ValueError("Anchor offset must be finite")
            relation = ref.get("relation", "at")
            if relation not in {"at", "before", "after"}:
                raise ValueError("Unsupported event boundary relation")
            shifted = replace(
                result,
                label=f"{result.label} (offset {offset:+g} days)"
                if offset and result.label
                else result.label,
                soft_start=None
                if result.soft_start is None
                else result.soft_start + offset,
                soft_end=None if result.soft_end is None else result.soft_end + offset,
                hard_start=None
                if result.hard_start is None
                else result.hard_start + offset,
                hard_end=None if result.hard_end is None else result.hard_end + offset,
                anchor_id=anchor_id if offset == 0 else f"{anchor_id}+{offset:g}",
            )
            if relation == "at":
                return shifted
            # Relative bounds constrain one side only. Two independent dates before
            # the same event are not the same transition.
            return replace(
                shifted,
                anchor_id=None,
                soft_start=None,
                soft_end=None,
                hard_start=shifted.hard_start if relation == "after" else None,
                hard_end=shifted.hard_end if relation == "before" else None,
                label=f"{relation.title()} {shifted.label or anchor_id}",
            )
        return ResolvedTemporalBounds()
