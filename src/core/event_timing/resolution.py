"""Detached joint timing results and compatibility boundary projections."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

from src.core.event_timing.constraints import (
    ZERO,
    Constraint,
    ConstraintBranch,
    Interval,
    merge_intervals,
)
from src.core.temporal_expression import ResolvedTemporalBounds


class JointModelHandle:
    """A runtime query capability that deliberately disappears from JSON snapshots."""

    def __init__(self, model: TemporalWorldResolution) -> None:
        """Retain the immutable calculation behind a non-dataclass handle."""
        self.model = model

    def __deepcopy__(self, memo: dict[int, Any]) -> None:
        """Dataclass snapshots contain facts, never a process-local query engine."""
        return None

    @property
    def fingerprint(self) -> str:
        """Identify the exact source generation."""
        return self.model.fingerprint

    def possible(self, query: tuple[Constraint, ...]) -> bool | None:
        """Delegate existential queries to the retained model."""
        return self.model.possible(query)

    def definite(self, query: tuple[Constraint, ...]) -> bool | None:
        """Delegate universal queries to the retained model."""
        return self.model.definite(query)


@dataclass(frozen=True)
class TimingIssue:
    """An actionable defect with stable structural ownership."""

    code: str
    endpoints: tuple[str, ...]
    message: str
    rules: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize an actionable diagnostic."""
        return {
            "code": self.code,
            "endpoints": list(self.endpoints),
            "message": self.message,
            "rules": list(self.rules),
        }


@dataclass(frozen=True)
class EndpointResolution:
    """Evidence remains separate from constraint-derived possibilities."""

    identity: str
    authored: ResolvedTemporalBounds
    ranges: tuple[Interval, ...] = ()
    provenance: tuple[str, ...] = ()
    error: str | None = None
    verified: bool = True
    placement: float | None = None

    def bounds(self) -> ResolvedTemporalBounds:
        """Expose old boundary readers without turning representatives into facts."""
        if self.error:
            return replace(self.authored, anchor_id=self.identity, error=self.error)
        if not self.ranges:
            return replace(self.authored, anchor_id=self.identity)
        first, last = self.ranges[0], self.ranges[-1]
        finite_ranges = tuple(
            (float(item.lower), float(item.upper))
            for item in self.ranges
            if item.lower is not None and item.upper is not None
        )
        return replace(
            self.authored,
            anchor_id=self.identity,
            hard_start=float(first.lower) if first.lower is not None else None,
            hard_end=float(last.upper) if last.upper is not None else None,
            lower_inclusive=first.lower_closed,
            upper_inclusive=last.upper_closed,
            possible_ranges=finite_ranges
            if len(finite_ranges) == len(self.ranges)
            else None,
            possible_inclusivity=tuple(
                (item.lower_closed, item.upper_closed) for item in self.ranges
            )
            if len(finite_ranges) == len(self.ranges)
            else None,
            error=None,
        )

    @property
    def coordinate(self) -> float | None:
        """Choose a deterministic layout coordinate only when timing is usable."""
        if self.error:
            return None
        if self.placement is not None:
            return self.placement
        for item in self.ranges:
            if item.lower is not None and item.upper is not None:
                return float((item.lower + item.upper) / 2)
        if self.authored.hard_start is not None and self.authored.hard_end is not None:
            return (self.authored.hard_start + self.authored.hard_end) / 2
        return self.authored.soft_start


@dataclass
class TemporalWorldResolution:
    """Joint solutions retained for queries, not just independent range envelopes."""

    fingerprint: str
    endpoints: dict[str, EndpointResolution] = field(default_factory=dict)
    components: dict[str, tuple[str, ...]] = field(default_factory=dict)
    branches: dict[tuple[str, ...], tuple[ConstraintBranch, ...]] = field(
        default_factory=dict
    )
    issues: list[TimingIssue] = field(default_factory=list)
    calendar_json: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize exact solved branches without callbacks or runtime handles."""
        from dataclasses import asdict

        endpoints = {}
        for node, item in self.endpoints.items():
            endpoints[node] = {
                "authored": asdict(item.authored),
                "ranges": [
                    (
                        str(part.lower) if part.lower is not None else None,
                        str(part.upper) if part.upper is not None else None,
                        part.lower_closed,
                        part.upper_closed,
                    )
                    for part in item.ranges
                ],
                "error": item.error,
                "verified": item.verified,
                "placement": item.placement,
            }
        components = []
        for component, branches in self.branches.items():
            provenance = self.endpoints[component[0]].provenance if component else ()
            components.append(
                {
                    "nodes": list(component),
                    "provenance": list(provenance),
                    "branches": [
                        [
                            [
                                edge.source,
                                edge.target,
                                str(edge.limit),
                                edge.strict,
                                edge.rule,
                            ]
                            for edge in branch.edges
                        ]
                        for branch in branches
                    ],
                }
            )
        return {
            "fingerprint": self.fingerprint,
            "calendar_json": self.calendar_json,
            "endpoints": endpoints,
            "components": components,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalWorldResolution:
        """Rehydrate a solved generation without repeating disjunctive search."""
        result = cls(data["fingerprint"])
        result.calendar_json = data.get("calendar_json")
        for node, item in data["endpoints"].items():
            ranges = tuple(
                Interval(
                    Fraction(row[0]) if row[0] is not None else None,
                    Fraction(row[1]) if row[1] is not None else None,
                    row[2],
                    row[3],
                )
                for row in item["ranges"]
            )
            result.endpoints[node] = EndpointResolution(
                node,
                ResolvedTemporalBounds(**item["authored"]),
                ranges,
                error=item["error"],
                verified=item["verified"],
                placement=item.get("placement"),
            )
        for group in data["components"]:
            component = tuple(group["nodes"])
            branches = tuple(
                ConstraintBranch(
                    component,
                    [
                        Constraint(row[0], row[1], Fraction(row[2]), row[3], row[4])
                        for row in edges
                    ],
                )
                for edges in group["branches"]
            )
            if any(not branch.feasible for branch in branches):
                raise ValueError("Invalid calculated timing generation")
            result.branches[component] = branches
            for node in component:
                result.components[node] = component
                result.endpoints[node] = replace(
                    result.endpoints[node], provenance=tuple(group["provenance"])
                )
        result.issues = [
            TimingIssue(
                item["code"],
                tuple(item["endpoints"]),
                item["message"],
                tuple(item["rules"]),
            )
            for item in data["issues"]
        ]
        return result

    def anchors(self) -> dict[str, ResolvedTemporalBounds]:
        """Return compatibility views of this resolution generation."""
        handle = JointModelHandle(self)
        return {
            key: replace(
                item.bounds(),
                joint=handle,
                joint_node=key,
                joint_offset=0,
                joint_transform=(),
            )
            for key, item in self.endpoints.items()
        }

    def possible(self, query: tuple[Constraint, ...]) -> bool | None:
        """Existentially conjoin every condition within each affected component."""
        groups: dict[tuple[str, ...], list[Constraint]] = {}
        for edge in query:
            identities = {node for node in (edge.source, edge.target) if node != ZERO}
            components = {
                self.components[node] for node in identities if node in self.components
            }
            if len(components) != 1 or any(
                node not in self.components for node in identities
            ):
                return self._cross_component_query(query)
            component = next(iter(components))
            groups.setdefault(component, []).append(edge)
        for component, conditions in groups.items():
            branches = self.branches.get(component, ())
            if not branches:
                return None
            if not any(branch.with_query(conditions).feasible for branch in branches):
                return False
        return True

    def _cross_component_query(self, query: tuple[Constraint, ...]) -> bool | None:
        """Queries may connect otherwise independent components temporarily."""
        from itertools import product

        nodes = {
            node
            for edge in query
            for node in (edge.source, edge.target)
            if node != ZERO
        }
        if any(node not in self.components for node in nodes):
            return None
        components = sorted({self.components[node] for node in nodes})
        choices = [self.branches.get(component, ()) for component in components]
        if any(not choice for choice in choices):
            return None
        return any(
            ConstraintBranch(
                nodes | {node for branch in selected for node in branch.nodes},
                (*query, *(edge for branch in selected for edge in branch.edges)),
                selected[0].cancel if selected else None,
            ).feasible
            for selected in product(*choices)
        )

    def definite(self, query: tuple[Constraint, ...]) -> bool | None:
        """A conjunction is certain iff none of its negated conditions is possible."""
        possible = self.possible(query)
        if possible is not True:
            return possible
        for edge in query:
            opposite = self.possible((edge.negated(),))
            if opposite is None:
                return None
            if opposite:
                return False
        return True

    def duration(self, event_id: str) -> tuple[Interval, ...]:
        """Project an interval difference in each joint branch."""
        start, end = f"event:{event_id}", f"event:{event_id}:end"
        component = self.components.get(start)
        if component is None or end not in component:
            return ()
        return merge_intervals(
            branch.difference(start, end) for branch in self.branches.get(component, ())
        )

    def exact_duration(self, event_id: str) -> float | None:
        """Return a duration scalar only when it is proven exact."""
        ranges = self.duration(event_id)
        if (
            len(ranges) == 1
            and ranges[0].lower is not None
            and ranges[0].lower == ranges[0].upper
        ):
            return float(ranges[0].lower)
        return None


def domain(bounds: ResolvedTemporalBounds) -> tuple[Interval, ...]:
    """Keep explicit bounds, unboundedness and disjoint calendar images."""
    if bounds.possible_ranges:
        return tuple(
            Interval(Fraction(a), Fraction(b), True, a == b)
            for a, b in bounds.possible_ranges
        )
    return (
        Interval(
            Fraction(bounds.hard_start) if bounds.hard_start is not None else None,
            Fraction(bounds.hard_end) if bounds.hard_end is not None else None,
            bounds.lower_inclusive,
            bounds.upper_inclusive,
        ),
    )
