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
    id: str | None = None

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
    """Compatibility interface for structured world chronology validation."""
    return [issue.message for issue in chronology_issues(constraints, anchors)]


@dataclass(frozen=True)
class ChronologyIssue:
    """A stable, actionable chronology problem."""

    code: str
    anchor_ids: tuple[str, ...]
    constraint_ids: tuple[str, ...]
    message: str


def chronology_key(constraint: TemporalConstraint) -> tuple[str, str, str]:
    """Return the same key for inverse descriptions of one relationship."""
    a, b = constraint.anchor_a, constraint.anchor_b
    if constraint.relation == TemporalConstraintKind.AFTER:
        a, b = b, a
    if constraint.relation == TemporalConstraintKind.SAME_AS:
        a, b = sorted((a, b))
    return (
        a,
        "same_as"
        if constraint.relation == TemporalConstraintKind.SAME_AS
        else "before",
        b,
    )


def chronology_issues(  # noqa: C901
    constraints: list[TemporalConstraint],
    anchors: dict[str, ResolvedTemporalBounds] | None = None,
) -> list[ChronologyIssue]:
    """Check the whole graph using hard bounds and exact open endpoints."""
    issues: list[ChronologyIssue] = []
    parents: dict[str, str] = {}

    def root(anchor: str) -> str:
        parents.setdefault(anchor, anchor)
        while parents[anchor] != anchor:
            anchor = parents[anchor]
        return anchor

    def issue(code: str, message: str, items: list[TemporalConstraint]) -> None:
        issues.append(
            ChronologyIssue(
                code,
                tuple(
                    sorted(
                        {
                            anchor
                            for item in items
                            for anchor in (item.anchor_a, item.anchor_b)
                        }
                    )
                ),
                tuple(item.id for item in items if item.id),
                message,
            )
        )

    seen: dict[tuple[str, str, str], TemporalConstraint] = {}
    for item in constraints:
        if item.anchor_a == item.anchor_b:
            issue(
                "self_reference",
                "An event cannot be ordered relative to itself.",
                [item],
            )
        if not math.isfinite(item.min_offset_days) or item.min_offset_days < 0:
            issue(
                "invalid_offset",
                "A minimum gap must be finite and nonnegative.",
                [item],
            )
        if item.relation == TemporalConstraintKind.SAME_AS and item.min_offset_days:
            issue(
                "invalid_offset",
                "The same transition cannot have a minimum gap.",
                [item],
            )
        key = chronology_key(item)
        if key in seen:
            issue("duplicate", "This ordering is already recorded.", [seen[key], item])
        else:
            seen[key] = item
        if anchors is not None and (
            item.anchor_a not in anchors or item.anchor_b not in anchors
        ):
            issue(
                "missing_anchor",
                "A chronological ordering references an unavailable event.",
                [item],
            )

    for constraint in constraints:
        if constraint.relation == TemporalConstraintKind.SAME_AS:
            parents[root(constraint.anchor_b)] = root(constraint.anchor_a)
    groups: dict[str, list[str]] = {}
    for anchor in parents:
        groups.setdefault(root(anchor), []).append(anchor)
    if anchors is not None:
        for anchor in anchors:
            group = root(anchor)
            if anchor not in groups.get(group, []):
                groups.setdefault(group, []).append(anchor)

    # A lower bound is (coordinate, strict); an upper bound is
    # (coordinate, exclusive). Year/day periods have exclusive upper limits,
    # while equal legacy bounds represent one included instant.
    lower: dict[str, tuple[float, bool]] = {}
    upper: dict[str, tuple[float, bool]] = {}
    for group, members in groups.items():
        for anchor in set(members):
            bounds = anchors.get(anchor) if anchors is not None else None
            if bounds is None or bounds.error:
                continue
            if bounds.hard_start is not None:
                candidate = (bounds.hard_start, False)
                if group not in lower or candidate > lower[group]:
                    lower[group] = candidate
            if bounds.hard_end is not None:
                exclusive = bounds.hard_start != bounds.hard_end
                candidate_upper = (bounds.hard_end, exclusive)
                if (
                    group not in upper
                    or candidate_upper[0] < upper[group][0]
                    or (candidate_upper[0] == upper[group][0] and exclusive)
                ):
                    upper[group] = candidate_upper

    def impossible(group: str) -> bool:
        if group not in lower or group not in upper:
            return False
        lo, strict = lower[group]
        hi, exclusive = upper[group]
        return lo > hi or (lo == hi and (strict or exclusive))

    for group, members in groups.items():
        if impossible(group):
            related = [
                item
                for item in constraints
                if item.relation == TemporalConstraintKind.SAME_AS
                and item.anchor_a in members
                and item.anchor_b in members
            ]
            issue(
                "shared_transition_conflict",
                "Shared transitions have no common possible date.",
                related,
            )

    graph: dict[str, list[tuple[str, TemporalConstraint]]] = {}
    indegree: dict[str, int] = {group: 0 for group in groups}
    for constraint in constraints:
        if constraint.relation == TemporalConstraintKind.SAME_AS:
            continue
        a, b = root(constraint.anchor_a), root(constraint.anchor_b)
        if constraint.relation == TemporalConstraintKind.AFTER:
            a, b = b, a
        if a == b:
            issue(
                "cycle", "An ordering conflicts with a shared transition.", [constraint]
            )
            continue
        graph.setdefault(a, []).append((b, constraint))
        indegree.setdefault(a, 0)
        indegree[b] = indegree.get(b, 0) + 1
    ready = [anchor for anchor, count in indegree.items() if count == 0]
    path_items: dict[str, list[TemporalConstraint]] = {}
    visited = 0
    while ready:
        anchor = ready.pop()
        visited += 1
        for target, constraint in graph.get(anchor, []):
            if anchor in lower and math.isfinite(constraint.min_offset_days):
                position, strict = lower[anchor]
                gap = constraint.min_offset_days
                candidate = (position + gap, strict or gap == 0)
                if target not in lower or candidate > lower[target]:
                    lower[target] = candidate
                    path_items[target] = [*path_items.get(anchor, []), constraint]
                    if impossible(target):
                        issue(
                            "impossible_chain",
                            "The recorded order cannot fit within the asserted dates.",
                            path_items[target],
                        )
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited < len(indegree):
        cyclic = [
            item
            for item in constraints
            if root(item.anchor_a) in indegree and indegree[root(item.anchor_a)] > 0
        ]
        issue("cycle", "Chronological ordering contains a cycle.", cyclic)
    return issues


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
