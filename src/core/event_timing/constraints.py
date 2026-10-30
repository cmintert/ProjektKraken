"""Exact difference constraints with open bounds and cooperative cancellation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction

from src.core.event_timing.aliases import AffineAliases

ZERO = "@origin"
Weight = tuple[Fraction, int]
Cancel = Callable[[], bool]


class TimingCancelled(Exception):
    """The caller abandoned a calculation; no partial result is saveable."""


def checkpoint(cancel: Cancel | None) -> None:
    """Cooperatively stop obsolete calculations."""
    if cancel is not None and cancel():
        raise TimingCancelled()


def rational(value: float | int | Fraction) -> Fraction:
    """Preserve the exact stored finite value, including fractional days."""
    return Fraction(value)


@dataclass(frozen=True)
class Constraint:
    """`target - source <= limit`, or `< limit` when strict."""

    source: str
    target: str
    limit: Fraction
    strict: bool = False
    rule: str = ""

    @property
    def weight(self) -> Weight:
        """Use a formal infinitesimal, never a floating point epsilon."""
        return self.limit, -int(self.strict)

    def negated(self) -> Constraint:
        """The exact complement, used to prove definite temporal queries."""
        return Constraint(
            self.target, self.source, -self.limit, not self.strict, self.rule
        )


@dataclass(frozen=True)
class Interval:
    """A connected real domain; None denotes a genuinely unbounded side."""

    lower: Fraction | None = None
    upper: Fraction | None = None
    lower_closed: bool = True
    upper_closed: bool = False

    def contains(self, value: Fraction) -> bool:
        """Test membership without rounding away open bounds."""
        return (
            self.lower is None
            or value > self.lower
            or (value == self.lower and self.lower_closed)
        ) and (
            self.upper is None
            or value < self.upper
            or (value == self.upper and self.upper_closed)
        )

    def constraints(self, node: str, rule: str = "") -> tuple[Constraint, ...]:
        """Encode a domain without adding a fictitious date envelope."""
        result = []
        if self.lower is not None:
            result.append(
                Constraint(node, ZERO, -self.lower, not self.lower_closed, rule)
            )
        if self.upper is not None:
            result.append(
                Constraint(ZERO, node, self.upper, not self.upper_closed, rule)
            )
        return tuple(result)


class ConstraintBranch:
    """One convex interpretation of a disjunctive temporal network."""

    def __init__(
        self,
        nodes: Iterable[str],
        edges: Iterable[Constraint],
        cancel: Cancel | None = None,
    ) -> None:
        """Freeze a convex branch and check exact feasibility."""
        self.nodes = tuple(sorted({ZERO, *nodes}))
        self.edges = tuple(edges)
        self.cancel = cancel
        self._distances: dict[str, dict[str, Weight]] = {}
        self.aliases = AffineAliases(self.nodes)
        consistent = self._collapse_equalities()
        self._nodes = tuple(sorted({self.aliases.find(node)[0] for node in self.nodes}))
        self._edges = tuple(
            reduced
            for edge in self.edges
            if (reduced := self._reduced(edge)) is not None
        )
        self.feasible = consistent and self._feasible()

    def _collapse_equalities(self) -> bool:
        lookup = {
            (edge.source, edge.target, edge.limit)
            for edge in self.edges
            if not edge.strict
        }
        for index, edge in enumerate(self.edges):
            if index % 128 == 0:
                checkpoint(self.cancel)
            if not edge.strict and (edge.target, edge.source, -edge.limit) in lookup:
                if not self.aliases.join(edge.source, edge.target, edge.limit):
                    return False
        return True

    def _reduced(self, edge: Constraint) -> Constraint | None:
        source, left = self.aliases.find(edge.source)
        target, right = self.aliases.find(edge.target)
        limit = edge.limit + left - right
        # A nonnegative self-bound is already true after exact alias reduction.
        # Strict zero and negative bounds must remain to prove infeasibility.
        if source == target and (limit, -int(edge.strict)) >= (0, 0):
            return None
        return Constraint(source, target, limit, edge.strict, edge.rule)

    def _relax(self, distances: dict[str, Weight]) -> bool:
        changed = False
        for index, edge in enumerate(self._edges):
            if index % 128 == 0:
                checkpoint(self.cancel)
            old = distances.get(edge.source)
            if old is None:
                continue
            weight = edge.weight
            candidate = old[0] + weight[0], old[1] + weight[1]
            if edge.target not in distances or candidate < distances[edge.target]:
                distances[edge.target] = candidate
                changed = True
        return changed

    def _feasible(self) -> bool:
        distances = dict.fromkeys(self._nodes, (Fraction(0), 0))
        for _ in self._nodes:
            if not self._relax(distances):
                return True
        return False

    def distances(self, source: str) -> dict[str, Weight]:
        """Shortest bounds from one node; cached only within this generation."""
        if source not in self._distances:
            distances = {source: (Fraction(0), 0)}
            for _ in self._nodes:
                if not self._relax(distances):
                    break
            self._distances[source] = distances
        return self._distances[source]

    def difference(self, start: str, end: str) -> Interval:
        """Project end-start while preserving endpoint correlation."""
        first, left = self.aliases.find(start)
        second, right = self.aliases.find(end)
        upper = self.distances(first).get(second)
        lower = self.distances(second).get(first)
        displacement = right - left
        return Interval(
            displacement - lower[0] if lower else None,
            displacement + upper[0] if upper else None,
            lower is None or lower[1] == 0,
            upper is not None and upper[1] == 0,
        )

    def with_query(self, edges: Iterable[Constraint]) -> ConstraintBranch:
        """Conjoin a query with the complete joint interpretation."""
        return ConstraintBranch(self.nodes, (*self.edges, *edges), self.cancel)

    def placement(
        self, preferences: dict[str, float] | None = None
    ) -> dict[str, Fraction]:
        """Choose one jointly feasible rational placement in deterministic order."""
        if not self.feasible:
            raise ValueError("An infeasible branch has no placement")
        branch = self
        selected: dict[str, Fraction] = {ZERO: Fraction(0)}
        preferred: dict[str, Fraction] = {}
        for node, coordinate in sorted((preferences or {}).items()):
            root, offset = self.aliases.find(node)
            preferred.setdefault(root, Fraction(coordinate) - offset)
        for root in self._nodes:
            checkpoint(self.cancel)
            if root == ZERO:
                continue
            interval = branch.difference(ZERO, root)
            if root in preferred and interval.contains(preferred[root]):
                value = preferred[root]
            elif interval.lower is not None and interval.upper is not None:
                value = (interval.lower + interval.upper) / 2
            elif interval.lower is not None:
                value = interval.lower + 1
            elif interval.upper is not None:
                value = interval.upper - 1
            else:
                value = Fraction(0)
            selected[root] = value
            branch = branch.with_query(
                (Constraint(ZERO, root, value), Constraint(root, ZERO, -value))
            )
        return {
            node: selected[root] + offset
            for node in self.nodes
            for root, offset in (self.aliases.find(node),)
        }


def merge_intervals(intervals: Iterable[Interval]) -> tuple[Interval, ...]:
    """Normalize a union while preserving open points and genuine gaps."""
    ordered = sorted(
        set(intervals),
        key=lambda x: (x.lower is not None, x.lower or 0, not x.lower_closed),
    )
    result: list[Interval] = []
    for item in ordered:
        if not result:
            result.append(item)
            continue
        previous = result[-1]
        touching = previous.upper == item.lower and (
            previous.upper_closed or item.lower_closed
        )
        overlaps = (
            previous.upper is None or item.lower is None or item.lower < previous.upper
        )
        if not (touching or overlaps):
            result.append(item)
            continue
        if previous.upper is None or (
            item.upper is not None and previous.upper > item.upper
        ):
            continue
        closed = item.upper_closed or (
            previous.upper == item.upper and previous.upper_closed
        )
        result[-1] = Interval(previous.lower, item.upper, previous.lower_closed, closed)
    return tuple(result)
