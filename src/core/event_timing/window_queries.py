"""Conjoin observing visibility windows with the Event constraint network."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from src.core.event_timing.constraints import ZERO, Constraint
from src.core.event_timing.observations import (
    Observation,
    definite_observed,
    observe,
    possible_observed,
)

if TYPE_CHECKING:
    from src.core.event_timing.resolution import JointModelHandle
    from src.core.temporal_expression import ResolvedTemporalBounds
    from src.core.temporal_window import TemporalWindow


def _conditions(
    bound: ResolvedTemporalBounds, time: float, side: str, instant: bool
) -> tuple[tuple[Constraint, ...], tuple[Observation, ...]] | None:
    if bound.relative_to is not None or bound.joint is None or bound.joint_node is None:
        return None
    coordinate = Fraction(time) - Fraction(bound.joint_offset)
    node, observations = observe(bound.joint_node, bound.joint_transform)
    before = Constraint(ZERO, node, coordinate)
    after = Constraint(node, ZERO, -coordinate, not instant)
    if instant:
        return (before, after), observations
    return ((before,) if side == "start" else (after,)), observations


def joint_window_status(windows: list[TemporalWindow], time: float) -> str | None:
    """Return an exact joint status when every finite side has a model identity."""
    model: JointModelHandle | None = None
    query: list[Constraint] = []
    observations: list[Observation] = []
    incomplete = False
    unknown_limits = False
    for window in windows:
        if not window.semantic or window.error:
            return None
        instant = window.kind.value == "instant"
        sides = (
            (("start", window.start_bounds),)
            if instant
            else (("start", window.start_bounds), ("end", window.end_bounds))
        )
        for side, bound in sides:
            if bound is None:
                continue
            if bound.error:
                return "indeterminate"
            conditions = _conditions(bound, time, side, instant)
            if conditions is None:
                incomplete = True
                continue
            if bound.joint is None:
                return None
            if model is not None and model.fingerprint != bound.joint.fingerprint:
                return "indeterminate"
            model = bound.joint
            query.extend(conditions[0])
            observations.extend(conditions[1])
            unknown_limits |= bound.hard_start is None or bound.hard_end is None
    if model is None:
        return None
    possible = possible_observed(model.model, tuple(query), tuple(observations))
    if possible is None:
        return "indeterminate"
    if not possible:
        return "inactive"
    if incomplete:
        return None
    definite = definite_observed(model.model, tuple(query), tuple(observations))
    if definite:
        return "definite"
    return "indeterminate" if unknown_limits or definite is None else "possible"
