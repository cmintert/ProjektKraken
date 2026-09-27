"""Small chronological constraint checks; no probabilistic world enumeration."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_window import TemporalValidity, TemporalWindow


class TemporalConstraintKind(str, Enum):
    """Chronology asserted independently of calendar precision."""

    BEFORE = "before"
    AFTER = "after"
    SAME_AS = "same_as"


@dataclass(frozen=True)
class TemporalConstraint:
    """An ordering or equality claim between event anchors."""

    anchor_a: str
    relation: TemporalConstraintKind
    anchor_b: str
    min_offset_days: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable chronology claim."""
        return {**asdict(self), "relation": self.relation.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalConstraint:
        """Read a chronology claim."""
        return cls(**{**data, "relation": TemporalConstraintKind(data["relation"])})


def validate_constraints(
    constraints: list[TemporalConstraint],
    anchors: dict[str, ResolvedTemporalBounds] | None = None,
) -> list[str]:
    """Detect strict ordering cycles after contracting equal anchors."""
    parents: dict[str, str] = {}

    def root(anchor: str) -> str:
        parents.setdefault(anchor, anchor)
        while parents[anchor] != anchor:
            anchor = parents[anchor]
        return anchor

    for constraint in constraints:
        if constraint.relation == TemporalConstraintKind.SAME_AS:
            parents[root(constraint.anchor_b)] = root(constraint.anchor_a)
    graph: dict[str, set[str]] = {}
    for constraint in constraints:
        if constraint.relation == TemporalConstraintKind.SAME_AS:
            continue
        a, b = root(constraint.anchor_a), root(constraint.anchor_b)
        if constraint.relation == TemporalConstraintKind.AFTER:
            a, b = b, a
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set())
    indegree = {anchor: 0 for anchor in graph}
    for targets in graph.values():
        for target in targets:
            indegree[target] += 1
    ready = [anchor for anchor, count in indegree.items() if count == 0]
    visited = 0
    while ready:
        anchor = ready.pop()
        visited += 1
        for target in graph[anchor]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    errors = (
        ["Chronological ordering contains a cycle."] if visited < len(graph) else []
    )
    errors.extend(_validate_constraint_bounds(constraints, anchors))
    return errors


def _validate_constraint_bounds(
    constraints: list[TemporalConstraint],
    anchors: dict[str, ResolvedTemporalBounds] | None,
) -> list[str]:
    errors = []
    for constraint in constraints:
        offset = constraint.min_offset_days
        if not math.isfinite(offset) or offset < 0:
            errors.append(
                "A minimum chronological offset must be finite and nonnegative."
            )
            continue
        if anchors is None:
            continue
        a, b = anchors.get(constraint.anchor_a), anchors.get(constraint.anchor_b)
        if a is None or b is None:
            errors.append("A chronological constraint references an unavailable event.")
            continue
        if constraint.relation == TemporalConstraintKind.AFTER:
            a, b = b, a
        if constraint.relation == TemporalConstraintKind.SAME_AS:
            if offset:
                errors.append("The same transition cannot have a nonzero offset.")
            if _disjoint_anchor_bounds(a, b):
                errors.append("Dates disagree with the shared-transition constraint.")
        elif a.hard_start is not None and b.hard_end is not None:
            if a.hard_start + offset > b.hard_end or (
                (offset == 0 or b.hard_start != b.hard_end)
                and a.hard_start + offset >= b.hard_end
            ):
                errors.append("Dates contradict the asserted event order.")
    return errors


def _disjoint_anchor_bounds(
    a: ResolvedTemporalBounds, b: ResolvedTemporalBounds
) -> bool:
    """Compare half-open periods while retaining closed legacy instants."""
    for left, right in ((a, b), (b, a)):
        if left.hard_end is not None and right.hard_start is not None:
            if left.hard_end < right.hard_start:
                return True
            if left.hard_end == right.hard_start and left.hard_start != left.hard_end:
                return True
    return False


def overlap_status(
    first: TemporalWindow,
    second: TemporalWindow,
    constraints: list[TemporalConstraint] | None = None,
) -> TemporalValidity:
    """Classify interval overlap while retaining correlated transition identity."""
    if first.error or second.error:
        return TemporalValidity.INDETERMINATE
    for ending, starting in (
        (first.end_bounds, second.start_bounds),
        (second.end_bounds, first.start_bounds),
    ):
        if (
            ending
            and starting
            and ending.anchor_id
            and (
                anchors_share_transition(
                    ending.anchor_id, starting.anchor_id, constraints or []
                )
                or (
                    starting.anchor_id
                    and anchor_precedes(
                        ending.anchor_id, starting.anchor_id, constraints or []
                    )
                )
            )
        ):
            return TemporalValidity.INACTIVE
    def limits(window: TemporalWindow) -> tuple[float | None, ...]:
        if not window.semantic:
            return (
                window.start if window.start is not None else float("-inf"),
            ) * 2 + (window.end if window.end is not None else float("inf"),) * 2
        start, end = window.start_bounds, window.end_bounds
        return (
            start.hard_start if start else float("-inf"),
            start.hard_end if start else float("-inf"),
            end.hard_start if end else float("inf"),
            end.hard_end if end else float("inf"),
        )

    a, b = limits(first), limits(second)
    if any(value is None for value in (*a, *b)):
        return TemporalValidity.INDETERMINATE
    a0, a1, a2, a3 = (float(value) for value in a if value is not None)
    b0, b1, b2, b3 = (float(value) for value in b if value is not None)
    if max(a0, b0) >= min(a3, b3):
        return TemporalValidity.INACTIVE
    if max(a1, b1) < min(a2, b2):
        return TemporalValidity.DEFINITE
    return TemporalValidity.POSSIBLE


def anchors_share_transition(
    a: str, b: str | None, constraints: list[TemporalConstraint]
) -> bool:
    """Recognize equality aliases without inventing an order."""
    pending = [a]
    seen = set()
    while pending:
        current = pending.pop()
        if current == b:
            return True
        if current in seen:
            continue
        seen.add(current)
        for constraint in constraints:
            if constraint.relation == TemporalConstraintKind.SAME_AS:
                if constraint.anchor_a == current:
                    pending.append(constraint.anchor_b)
                if constraint.anchor_b == current:
                    pending.append(constraint.anchor_a)
    return False


def anchor_precedes(a: str, b: str, constraints: list[TemporalConstraint]) -> bool:
    """Follow asserted order transitively, including equality aliases."""
    edges: dict[str, list[tuple[str, bool]]] = {}
    for constraint in constraints:
        source, target = constraint.anchor_a, constraint.anchor_b
        if constraint.relation == TemporalConstraintKind.AFTER:
            source, target = target, source
        strict = constraint.relation != TemporalConstraintKind.SAME_AS
        edges.setdefault(source, []).append((target, strict))
        if not strict:
            edges.setdefault(target, []).append((source, False))
    pending = [(a, False)]
    seen = set()
    while pending:
        current, strict = pending.pop()
        if (current, strict) in seen:
            continue
        seen.add((current, strict))
        if current == b and strict:
            return True
        pending.extend(
            (target, strict or ordered) for target, ordered in edges.get(current, [])
        )
    return False
