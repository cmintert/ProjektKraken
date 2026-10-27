"""Versioned boundary resolution; no UI, database or mutable context ownership."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.temporal_expression import (
    MAX_LORE_DAY,
    ResolvedTemporalBounds,
    TemporalExpression,
    expression_from_attributes,
)
from src.core.temporal_shift import shift_anchor


@dataclass
class BoundaryResolver:
    """Resolve boundaries against a detached event/calendar query."""

    source_date: float | None
    source_attributes: dict[str, Any]
    source_id: str | None
    converter: CalendarConverter | None
    anchors: dict[str, ResolvedTemporalBounds]
    default_semantics: str = "legacy_v1"

    def expression_bounds(self, data: dict[str, Any]) -> ResolvedTemporalBounds:
        """Resolve authored precision without substituting a layout coordinate."""
        if self.converter is None:
            return ResolvedTemporalBounds(error="Calendar unavailable for this date.")
        return TemporalExpression.from_dict(data).resolve_bounds(self.converter)

    def source_bounds(self) -> ResolvedTemporalBounds:
        """Keep legacy source-event shortcuts identified with named start anchors."""
        identity = f"event:{self.source_id}" if self.source_id else None
        if identity in self.anchors:
            return self.anchors[identity]
        expression = expression_from_attributes(self.source_attributes)
        if expression is not None:
            bounds = self.expression_bounds(expression.to_dict())
        elif self.source_date is not None:
            bounds = ResolvedTemporalBounds(
                self.source_date, self.source_date, upper_inclusive=True
            )
        else:
            bounds = ResolvedTemporalBounds(error="Source event unavailable.")
        return replace(bounds, anchor_id=identity, base_anchor=identity)

    def boundary(self, data: dict[str, Any]) -> ResolvedTemporalBounds | None:
        """Normalize one boundary without discarding unresolved intent."""
        if not isinstance(data, dict):
            raise ValueError("Temporal boundary must be an object")
        status = data.get("status", "known")
        if status in {"open", "not_applicable"}:
            return None
        if status == "unknown":
            return ResolvedTemporalBounds(label="Date unknown")
        if status != "known":
            raise ValueError("Invalid temporal boundary status")
        if "expression" in data:
            return self.expression_bounds(data["expression"])
        if "exact" in data:
            exact = float(data["exact"])
            if not math.isfinite(exact):
                raise ValueError("Temporal coordinate must be finite")
            return ResolvedTemporalBounds(exact, exact, upper_inclusive=True)
        if data.get("binding") == "source_event":
            return self.source_bounds()
        if "anchor" in data:
            return self.anchor(data["anchor"])
        return ResolvedTemporalBounds()

    def anchor(self, ref: dict[str, Any]) -> ResolvedTemporalBounds:
        """Resolve an explicit endpoint, offset and versioned relative constraint."""
        if not isinstance(ref, dict):
            raise ValueError("Event reference must be an object")
        anchor_id = ref["anchor_id"]
        endpoint = ref.get("endpoint", "start")
        if endpoint not in {"start", "end"}:
            raise ValueError("Unsupported event endpoint")
        key = anchor_id + (":end" if endpoint == "end" else "")
        if key == f"event:{self.source_id}":
            result = self.source_bounds()
        else:
            result = self.anchors.get(
                key,
                ResolvedTemporalBounds(
                    anchor_id=key, error="Referenced event unavailable."
                ),
            )
        shifted = shift_anchor(result, ref, self.converter)
        if any(
            value is not None
            and (not math.isfinite(value) or abs(value) > MAX_LORE_DAY)
            for value in (shifted.hard_start, shifted.hard_end)
        ):
            shifted = replace(
                shifted, error="Event endpoint is outside the supported lore-day range."
            )
        relation = ref.get("relation", "at")
        if relation == "at":
            return shifted
        if relation not in {"before", "after"}:
            raise ValueError("Unsupported event boundary relation")
        strict = ref.get("semantics", self.default_semantics) == "strict_v2"
        return replace(
            shifted,
            anchor_id=None,
            transition=None,
            base_anchor=None,
            possible_ranges=None,
            soft_start=None,
            soft_end=None,
            hard_start=shifted.hard_start if relation == "after" else None,
            hard_end=shifted.hard_end if relation == "before" else None,
            lower_inclusive=not strict,
            upper_inclusive=False,
            label=f"Date {relation} {shifted.label or key}",
            relative_to=shifted,
            relative_relation=relation,
        )
