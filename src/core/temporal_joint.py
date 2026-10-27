"""Joint feasibility of shared transitions and independently constrained dates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.core.temporal_expression import ResolvedTemporalBounds

if TYPE_CHECKING:
    from src.core.temporal_window import TemporalWindow


@dataclass
class _Restriction:
    ranges: tuple[tuple[float, float], ...]
    lower: float = -math.inf
    upper: float = math.inf
    lower_closed: bool = True
    upper_closed: bool = True

    def constrain(self, value: float, upper: bool, closed: bool) -> None:
        if upper:
            if value < self.upper:
                self.upper, self.upper_closed = value, closed
            elif value == self.upper:
                self.upper_closed &= closed
        elif value > self.lower:
            self.lower, self.lower_closed = value, closed
        elif value == self.lower:
            self.lower_closed &= closed

    def feasible(self) -> bool:
        for start, end in self.ranges:
            lower, upper = max(start, self.lower), min(end, self.upper)
            if lower < upper:
                return True
            if lower != upper or not math.isfinite(lower):
                continue
            in_domain = start == end == lower or start <= lower < end
            after = lower > self.lower or self.lower_closed
            before = lower < self.upper or self.upper_closed
            if in_domain and after and before:
                return True
        return False


def jointly_possible(windows: list[TemporalWindow], time: float) -> bool:
    """Conjoin playhead constraints on each identifiable underlying transition."""
    restrictions: dict[str, _Restriction] = {}
    for window in windows:
        if not window.semantic:
            continue
        instant = window.kind.value == "instant"
        for side, bound in (("start", window.start_bounds), ("end", window.end_bounds)):
            if bound is None or bound.error:
                continue
            constraint = _constraint(bound, side, instant)
            if constraint is None:
                continue
            root, upper, closed = constraint
            identity = root.base_anchor or root.anchor_id
            if identity is None or root.error:
                continue
            ranges = root.possible_ranges or (
                (
                    root.hard_start if root.hard_start is not None else -math.inf,
                    root.hard_end if root.hard_end is not None else math.inf,
                ),
            )
            offset = root.day_offset
            restriction = restrictions.setdefault(
                identity,
                _Restriction(
                    tuple((start - offset, end - offset) for start, end in ranges)
                ),
            )
            restriction.constrain(time - offset, upper, closed)
    return all(item.feasible() for item in restrictions.values())


def _constraint(
    bound: ResolvedTemporalBounds, side: str, instant: bool
) -> tuple[ResolvedTemporalBounds, bool, bool] | None:
    if bound.relative_to is not None:
        if bound.relative_relation == "after" and (side == "start" or instant):
            return bound.relative_to, True, bound.lower_inclusive
        if bound.relative_relation == "before" and (side == "end" or instant):
            return bound.relative_to, False, False
        return None
    return bound, side == "start", side == "start" or instant


def definitely_reversed(
    start: ResolvedTemporalBounds, end: ResolvedTemporalBounds
) -> bool:
    """Prove an empty interval from ordered views of the same transition."""
    if start.error or end.error:
        return False
    lower = start
    upper = end
    if start.relative_to is not None:
        if start.relative_relation != "after":
            return False
        lower = start.relative_to
    if end.relative_to is not None:
        if end.relative_relation != "before":
            return False
        upper = end.relative_to
    identity = lower.base_anchor or lower.anchor_id
    other = upper.base_anchor or upper.anchor_id
    return (
        identity is not None
        and identity == other
        and (lower.day_offset >= upper.day_offset)
    )
