"""Temporary observing transforms cannot add evidence to the saved Event world."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import TYPE_CHECKING, Literal

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.calendar_domains import calendar_pieces
from src.core.event_timing.constraints import (
    ZERO,
    Constraint,
    ConstraintBranch,
    checkpoint,
)
from src.core.event_timing.definitions import EndpointDefinition

if TYPE_CHECKING:
    from src.core.event_timing.resolution import TemporalWorldResolution


@dataclass(frozen=True)
class Observation:
    """A temporary calculated boundary used only while evaluating a query."""

    source: str
    target: str
    unit: str
    value: float
    calendar_id: str | None


def observe(
    source: str, transforms: tuple[tuple[str, float, str | None], ...]
) -> tuple[str, tuple[Observation, ...]]:
    """Identical transform chains share an identity, independent of captions."""
    steps = []
    for unit, value, calendar in transforms:
        target = (
            "event:@observe:"
            + hashlib.sha256(
                json.dumps((source, unit, value, calendar)).encode()
            ).hexdigest()
        )
        steps.append(Observation(source, target, unit, value, calendar))
        source = target
    return source, tuple(steps)


def _expand(
    branch: ConstraintBranch, step: Observation, converter: CalendarConverter | None
) -> list[ConstraintBranch]:
    nodes = (*branch.nodes, step.target)
    if step.unit == "days":
        amount = Fraction(step.value)
        edges = (
            Constraint(step.source, step.target, amount),
            Constraint(step.target, step.source, -amount),
        )
        return [ConstraintBranch(nodes, (*branch.edges, *edges), branch.cancel)]
    source = step.source.removesuffix(":end")
    endpoint: Literal["start", "end"] = (
        "end" if step.source.endswith(":end") else "start"
    )
    definition = EndpointDefinition(
        "event",
        anchor_id=source,
        endpoint=endpoint,
        offset={
            "unit": step.unit,
            "value": step.value,
            "calendar_id": step.calendar_id,
        },
    )
    pieces = calendar_pieces(
        step.target,
        definition,
        (branch.difference(ZERO, step.source),),
        converter,
        branch.cancel,
    )
    return [
        ConstraintBranch(nodes, (*branch.edges, *piece.edges), branch.cancel)
        for piece in pieces
        if piece.invalid is None
    ]


def possible_observed(
    model: TemporalWorldResolution,
    query: tuple[Constraint, ...],
    observations: tuple[Observation, ...],
) -> bool | None:
    """Retain whole-network consistency through Map/Relation calendar offsets."""
    if not observations:
        return model.possible(query)
    temporary = {step.target for step in observations}
    sources = {step.source for step in observations if step.source not in temporary}
    sources.update(
        node
        for edge in query
        for node in (edge.source, edge.target)
        if node != ZERO and node not in temporary
    )
    if any(node not in model.components for node in sources):
        return None
    components = sorted({model.components[node] for node in sources})
    choices = [model.branches.get(component, ()) for component in components]
    if any(not choice for choice in choices):
        return None
    converter = (
        CalendarConverter(CalendarConfig.from_json(model.calendar_json))
        if model.calendar_json
        else None
    )
    for selected in product(*choices):
        cancel = selected[0].cancel if selected else None
        checkpoint(cancel)
        branch = ConstraintBranch(
            {node for item in selected for node in item.nodes},
            [edge for item in selected for edge in item.edges],
            cancel,
        )
        frontier = [branch]
        for step in dict.fromkeys(observations):
            frontier = [
                candidate
                for item in frontier
                for candidate in _expand(item, step, converter)
                if candidate.feasible
            ]
        if any(item.with_query(query).feasible for item in frontier):
            return True
    return False


def definite_observed(
    model: TemporalWorldResolution,
    query: tuple[Constraint, ...],
    observations: tuple[Observation, ...],
) -> bool | None:
    """Universal validity is absence of every feasible counterexample."""
    for condition in query:
        opposite = possible_observed(model, (condition.negated(),), observations)
        if opposite is None:
            return None
        if opposite:
            return False
    return True
