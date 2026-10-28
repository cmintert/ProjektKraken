"""Compile authored dates, derivations and chronology into separate graphs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.event_timing.constraints import (
    Cancel,
    Constraint,
    Interval,
    checkpoint,
    rational,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.resolution import TimingIssue, domain
from src.core.events import Event
from src.core.temporal_expression import ResolvedTemporalBounds, TemporalExpression
from src.core.temporal_shift import shift_anchor


@dataclass
class CompiledTiming:
    """A pure compilation with no Qt, SQL or mutable source references."""

    fingerprint: str
    definitions: dict[str, EndpointDefinition] = field(default_factory=dict)
    evidence: dict[str, ResolvedTemporalBounds] = field(default_factory=dict)
    domains: dict[str, tuple[Interval, ...]] = field(default_factory=dict)
    edges: list[Constraint] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    neighbors: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    calendars: list[tuple[str, EndpointDefinition]] = field(default_factory=list)
    duration_ends: set[str] = field(default_factory=set)
    invalid: set[str] = field(default_factory=set)
    issues: list[TimingIssue] = field(default_factory=list)

    def connect(self, first: str, second: str) -> None:
        """Join consistency components independently of derivation."""
        self.neighbors[first].add(second)
        self.neighbors[second].add(first)

    def equality(self, source: str, target: str, value: float, rule: str) -> None:
        """Compile a signed equality without rounding its offset."""
        amount = rational(value)
        self.edges.extend(
            (
                Constraint(source, target, amount, rule=rule),
                Constraint(target, source, -amount, rule=rule),
            )
        )
        self.connect(source, target)


def fingerprint(events: list[Event], converter: CalendarConverter | None) -> str:
    """Coordinates are evidence only in legacy records without semantic timing."""
    rows = []
    for event in sorted(events, key=lambda item: item.id):
        metadata = (
            {
                key: value
                for key, value in event.attributes.get("_temporal_v2", {}).items()
                if key != "projection"
            }
            if isinstance(event.attributes.get("_temporal_v2", {}), dict)
            else event.attributes.get("_temporal_v2")
        )
        coordinates = (
            (
                None
                if isinstance(metadata, dict) and metadata.get("expression")
                else event.lore_date,
                None
                if isinstance(metadata, dict) and metadata.get("end_expression")
                else event.lore_duration,
            )
            if not metadata
            or (isinstance(metadata, dict) and metadata.get("schema", 1) == 1)
            else None
        )
        rows.append((event.id, metadata, coordinates))
    payload = {
        "engine": 1,
        "events": rows,
        "calendar": converter._config.to_dict() if converter else None,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _manual(
    endpoint: EndpointDefinition, converter: CalendarConverter | None
) -> ResolvedTemporalBounds:
    if endpoint.expression is None:
        value = endpoint.instant
        from src.core.temporal_expression import MAX_LORE_DAY

        assert value is not None
        if abs(value) > MAX_LORE_DAY:
            return ResolvedTemporalBounds(
                error="Date is outside the supported ±10^12 lore-day range"
            )
        label = converter.format_date(value) if converter else f"{value:g} days"
        return ResolvedTemporalBounds(value, value, upper_inclusive=True, label=label)
    if converter is None:
        return ResolvedTemporalBounds(error="The event's calendar is unavailable.")
    return TemporalExpression.from_dict(endpoint.expression).resolve_bounds(converter)


def _add_event(problem: CompiledTiming, event: Event) -> None:
    start, end = f"event:{event.id}", f"event:{event.id}:end"
    try:
        timing = EventTimingDefinition.from_event(event)
        problem.definitions[start] = timing.start
        if timing.end_mode == "duration":
            assert timing.duration_days is not None
            problem.definitions[end] = EndpointDefinition(
                "event",
                anchor_id=start,
                offset={"unit": "days", "value": timing.duration_days},
            )
            problem.duration_ends.add(end)
        elif timing.end is not None:
            problem.definitions[end] = timing.end
        if end in problem.definitions:
            problem.edges.append(
                Constraint(end, start, Fraction(0), rule=f"interval:{event.id}")
            )
            problem.connect(start, end)
    except (ValueError, TypeError, KeyError) as exc:
        problem.issues.append(TimingIssue("definition", (start,), str(exc)))


def _add_reference(
    problem: CompiledTiming, node: str, endpoint: EndpointDefinition
) -> None:
    source = endpoint.source
    internal_duration = node in problem.duration_ends
    if (
        source.removesuffix(":end") == node.removesuffix(":end")
        and not internal_duration
    ):
        problem.issues.append(
            TimingIssue(
                "self_reference",
                (node,),
                "Use Duration instead of following this Event itself.",
            )
        )
        return
    if source not in problem.definitions:
        problem.issues.append(
            TimingIssue(
                "missing_endpoint",
                (node,),
                f"Referenced endpoint {source} is unavailable.",
            )
        )
        return
    problem.dependencies[node] = source
    problem.connect(source, node)
    offset = endpoint.offset or {"unit": "days", "value": 0}
    if offset.get("unit") == "days" or not offset.get("value"):
        problem.equality(
            source, node, float(offset.get("value", 0)), f"reference:{node}"
        )
    else:
        problem.calendars.append((node, endpoint))


def _chronology(problem: CompiledTiming, events: list[Event]) -> None:
    for event in events:
        metadata = event.attributes.get("_temporal_v2", {})
        if not isinstance(metadata, dict):
            continue
        for index, record in enumerate(metadata.get("constraints", [])):
            _chronology_rule(problem, event.id, index, record)


def _chronology_rule(
    problem: CompiledTiming, owner: str, index: int, record: dict[str, Any]
) -> None:
    try:
        from src.core.temporal_constraints import TemporalConstraint

        rule = TemporalConstraint.from_dict(record)
        first, second = rule.anchor_a, rule.anchor_b
        if first not in problem.definitions or second not in problem.definitions:
            raise ValueError("Chronology references an unavailable endpoint")
        if rule.min_offset_days < 0:
            raise ValueError("Chronology minimum gap must be nonnegative")
        identity = rule.id or f"chronology:{owner}:{index}"
        if rule.relation.value == "same_as":
            if rule.min_offset_days:
                raise ValueError("Shared dates cannot have a minimum gap")
            problem.equality(first, second, 0, identity)
        else:
            if rule.relation.value == "after":
                first, second = second, first
            problem.edges.append(
                Constraint(
                    second,
                    first,
                    -rational(rule.min_offset_days),
                    rule.min_offset_days == 0,
                    identity,
                )
            )
            problem.connect(first, second)
    except (ValueError, TypeError, KeyError) as exc:
        problem.issues.append(TimingIssue("chronology", (f"event:{owner}",), str(exc)))


def _resolve_evidence(
    problem: CompiledTiming, converter: CalendarConverter | None, cancel: Cancel | None
) -> None:
    pending = set(problem.definitions)
    while pending:
        checkpoint(cancel)
        ready = sorted(
            node
            for node in pending
            if node not in problem.dependencies
            or problem.dependencies[node] in problem.evidence
        )
        if not ready:
            problem.issues.append(
                TimingIssue(
                    "dependency_cycle",
                    tuple(sorted(pending)),
                    "Endpoint dependencies contain a cycle.",
                )
            )
            break
        for node in ready:
            endpoint = problem.definitions[node]
            try:
                if endpoint.kind == "manual":
                    bounds = _manual(endpoint, converter)
                    if bounds.error:
                        problem.issues.append(
                            TimingIssue("evidence", (node,), bounds.error)
                        )
                    problem.domains[node] = domain(bounds)
                    bounds = replace(
                        bounds,
                        base_anchor=node,
                        day_offset=0,
                        transition=(node, "days", "0x0.0p+0"),
                    )
                elif node in problem.dependencies:
                    bounds = shift_anchor(
                        problem.evidence[problem.dependencies[node]],
                        {"offset": endpoint.offset or {"unit": "days", "value": 0}},
                        converter,
                        cancel,
                    )
                else:
                    bounds = ResolvedTemporalBounds(
                        error="The referenced endpoint is unavailable."
                    )
            except (ValueError, TypeError, KeyError) as exc:
                bounds = ResolvedTemporalBounds(error=str(exc))
            problem.evidence[node] = replace(bounds, anchor_id=node)
            if bounds.error and any(
                word in bounds.error.lower()
                for word in ("precision", "cannot be represented", "supported")
            ):
                problem.issues.append(TimingIssue("precision", (node,), bounds.error))
            pending.remove(node)


def compile_timing(
    events: list[Event],
    converter: CalendarConverter | None,
    cancel: Cancel | None = None,
) -> CompiledTiming:
    """Compile all authored facts without rejecting pre-existing broken records."""
    problem = CompiledTiming(fingerprint(events, converter))
    for event in sorted(events, key=lambda item: item.id):
        checkpoint(cancel)
        _add_event(problem, event)
    for node, endpoint in problem.definitions.items():
        problem.neighbors[node]
        if endpoint.kind == "event":
            _add_reference(problem, node, endpoint)
    _chronology(problem, events)
    _resolve_evidence(problem, converter, cancel)
    names = {f"event:{event.id}": event.name for event in events}
    for node, bounds in problem.evidence.items():
        name = names.get(node.removesuffix(":end"), node)
        caption = f"{name} — end" if node.endswith(":end") else name
        problem.evidence[node] = replace(
            bounds, label=f"{caption}: {bounds.label}" if bounds.label else caption
        )
    _quarantine(problem)
    return problem


def _quarantine(problem: CompiledTiming) -> None:
    """Broken derivations cannot contribute inferred evidence to healthy sources."""
    structural = {
        "definition",
        "evidence",
        "missing_endpoint",
        "self_reference",
        "dependency_cycle",
        "precision",
    }
    problem.invalid.update(
        node
        for issue in problem.issues
        if issue.code in structural
        for node in issue.endpoints
    )
    changed = True
    while changed:
        added = {
            node
            for node, source in problem.dependencies.items()
            if source in problem.invalid
        } - problem.invalid
        changed = bool(added)
        problem.invalid.update(added)
    problem.edges = [
        edge
        for edge in problem.edges
        if edge.source not in problem.invalid and edge.target not in problem.invalid
    ]
    for node, neighbors in problem.neighbors.items():
        if node in problem.invalid:
            neighbors.clear()
        else:
            neighbors.difference_update(problem.invalid)
