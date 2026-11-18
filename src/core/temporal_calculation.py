"""Evidence-aware differences between two dates, independent of presentation."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import ceil, floor
from typing import Literal

from src.core.calendar import CalendarConverter
from src.core.event_timing.constraints import Interval, merge_intervals
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    TemporalExpression,
    TemporalQualifier,
)


@dataclass(frozen=True)
class DateEvidence:
    """Resolved occurrence and the authored expression behind it, if available."""

    bounds: ResolvedTemporalBounds
    expression: TemporalExpression | None = None


@dataclass(frozen=True)
class TemporalDifference:
    """A calculation in lore days or completed calendar years."""

    unit: Literal["days", "years", "hours", "minutes", "seconds"]
    kind: Literal["value", "range", "outer_bound", "estimate", "unavailable"]
    intervals: tuple[Interval, ...] = ()
    reason: str = ""
    rounded: bool = False


END_PRECEDES_START = "End precedes start"


def _domain(bounds: ResolvedTemporalBounds) -> tuple[Interval, ...]:
    if (
        bounds.joint is not None
        and bounds.joint_node is not None
        and not bounds.joint_transform
        and not bounds.joint_offset
        and (endpoint := bounds.joint.model.endpoints.get(bounds.joint_node))
        and endpoint.ranges
    ):
        return endpoint.ranges
    if bounds.possible_ranges:
        inclusivity = bounds.possible_inclusivity or tuple(
            (True, lower == upper) for lower, upper in bounds.possible_ranges
        )
        return tuple(
            Interval(Fraction(lower), Fraction(upper), first_closed, last_closed)
            for (lower, upper), (first_closed, last_closed) in zip(
                bounds.possible_ranges, inclusivity, strict=True
            )
        )
    lower, upper = bounds.hard_start, bounds.hard_end
    return (
        Interval(
            Fraction(lower) if lower is not None else None,
            Fraction(upper) if upper is not None else None,
            bounds.lower_inclusive,
            lower == upper or bounds.upper_inclusive,
        ),
    )


def _difference(first: Interval, last: Interval) -> Interval:
    return Interval(
        last.lower - first.upper
        if last.lower is not None and first.upper is not None
        else None,
        last.upper - first.lower
        if last.upper is not None and first.lower is not None
        else None,
        last.lower_closed and first.upper_closed,
        last.upper_closed and first.lower_closed,
    )


def _joint_nodes(
    first: ResolvedTemporalBounds, last: ResolvedTemporalBounds
) -> tuple[str, str] | None:
    a, b = first.joint_node, last.joint_node
    if first.joint is None or last.joint is None or not a or not b:
        return None
    model = first.joint.model
    if model is not last.joint.model:
        return None
    component = model.components.get(a)
    return (a, b) if component is not None and b in component else None


def _timing_usable(bounds: ResolvedTemporalBounds) -> bool:
    if bounds.error:
        return False
    if bounds.joint is None or bounds.joint_node is None:
        return True
    endpoint = bounds.joint.model.endpoints.get(bounds.joint_node)
    return endpoint is not None and endpoint.verified and not endpoint.error


def _result(
    unit: Literal["days", "years"],
    intervals: tuple[Interval, ...],
    *,
    outer: bool = False,
) -> TemporalDifference:
    if len(intervals) == 1 and intervals[0].lower == intervals[0].upper:
        return TemporalDifference(unit, "value", intervals)
    if outer:
        return TemporalDifference(
            unit, "outer_bound", intervals, "Linked dates may narrow these bounds."
        )
    return TemporalDifference(unit, "range", intervals)


def elapsed_time(first: DateEvidence, last: DateEvidence) -> TemporalDifference:
    """Compute signed elapsed days and preserve the solver's endpoint precision."""
    a, b = first.bounds, last.bounds
    if not (_timing_usable(a) and _timing_usable(b)):
        return TemporalDifference("days", "unavailable", reason="Timing unresolved")
    nodes = _joint_nodes(a, b)
    offset = _linear_offset(b)
    first_offset = _linear_offset(a)
    joint_difference = (
        nodes is not None and offset is not None and first_offset is not None
    )
    if joint_difference:
        assert nodes is not None and a.joint is not None
        assert offset is not None and first_offset is not None
        delta = offset - first_offset
        intervals = tuple(
            _difference(Interval(-delta, -delta, True, True), interval)
            for interval in a.joint.model.difference(*nodes)
        )
    else:
        intervals = merge_intervals(
            _difference(left, right) for left, right in product(_domain(a), _domain(b))
        )
    if not intervals or all(i.lower is None and i.upper is None for i in intervals):
        return TemporalDifference("days", "unavailable", reason="Timing is unbounded")
    return _result("days", intervals, outer=nodes is not None and not joint_difference)


def _linear_offset(bounds: ResolvedTemporalBounds) -> Fraction | None:
    offset = Fraction(bounds.joint_offset)
    for unit, amount, _calendar_id in bounds.joint_transform:
        if unit != "days":
            return None
        offset += Fraction(amount)
    return offset


def _completed_years(start: int, end: int, calendar: CalendarConverter) -> int:
    first, last = calendar.from_float(start), calendar.from_float(end)
    months = calendar._config.get_months_for_year(last.year)
    month = min(first.month, len(months))
    day = months[month - 1].days if month != first.month else first.day
    anniversary = (month, min(day, months[month - 1].days))
    return last.year - first.year - int((last.month, last.day) < anniversary)


def _day_limits(interval: Interval) -> tuple[int, int]:
    assert interval.lower is not None and interval.upper is not None
    first = floor(interval.lower)
    last = floor(interval.upper) if interval.upper_closed else ceil(interval.upper) - 1
    return first, last


def _age_range(
    first: Interval, last: Interval, calendar: CalendarConverter
) -> Interval | None:
    difference = _difference(first, last)
    if difference.upper is not None and (
        difference.upper < 0 or (difference.upper == 0 and not difference.upper_closed)
    ):
        return None
    first_day, last_birth_day = _day_limits(first)
    first_end_day, last_day = _day_limits(last)
    return Interval(
        Fraction(max(0, _completed_years(last_birth_day, first_end_day, calendar))),
        Fraction(_completed_years(first_day, last_day, calendar)),
        True,
        True,
    )


def _nominal_year(
    evidence: DateEvidence, calendar: CalendarConverter
) -> tuple[int | None, bool]:
    expression = evidence.expression
    if (
        expression
        and expression.qualifier
        in {
            TemporalQualifier.APPROXIMATE,
            TemporalQualifier.APPROXIMATE_UNCERTAIN,
        }
        and not evidence.bounds.has_hard_bounds
    ):
        if evidence.bounds.soft_start is not None:
            return expression.year, True
    if evidence.bounds.has_hard_bounds:
        domain = _domain(evidence.bounds)
        first = _day_limits(domain[0])[0]
        last = _day_limits(domain[-1])[1]
        start_year = calendar.from_float(first).year
        if start_year == calendar.from_float(last).year:
            return start_year, False
    return None, False


def _authored_year_offset(
    first: ResolvedTemporalBounds,
    last: ResolvedTemporalBounds,
    calendar: CalendarConverter,
) -> int | None:
    """A verified direct calendar-year offset preserves the birth anniversary."""
    nodes = _joint_nodes(first, last)
    if nodes is None or first.joint is None:
        return None
    if (
        first.joint_transform
        or last.joint_transform
        or (first.joint_offset or last.joint_offset)
    ):
        return None
    definition = first.joint.model.definitions.get(nodes[1])
    if (
        definition is None
        or definition.kind != "event"
        or definition.source != nodes[0]
    ):
        return None
    offset = definition.offset or {}
    if (
        offset.get("unit") != "years"
        or offset.get("calendar_id") != calendar._config.id
    ):
        return None
    return int(offset["value"])


def completed_calendar_years(
    first: DateEvidence,
    last: DateEvidence,
    calendar: CalendarConverter,
    *,
    allow_circa_estimate: bool = False,
) -> TemporalDifference:
    """Count anniversaries for chronologically valid pairs of occurrences."""
    a, b = first.bounds, last.bounds
    if not (_timing_usable(a) and _timing_usable(b)):
        return TemporalDifference("years", "unavailable", reason="Timing unresolved")
    elapsed = elapsed_time(first, last)
    if elapsed.intervals:
        end = elapsed.intervals[-1]
        if end.upper is not None and (
            end.upper < 0 or (end.upper == 0 and not end.upper_closed)
        ):
            return TemporalDifference("years", "unavailable", reason=END_PRECEDES_START)
    if a.has_hard_bounds and b.has_hard_bounds:
        offset = _authored_year_offset(a, b, calendar)
        if offset is not None and offset >= 0:
            years = Fraction(offset)
            return _result("years", (Interval(years, years, True, True),))
        intervals = tuple(
            result
            for left, right in product(_domain(a), _domain(b))
            if (result := _age_range(left, right, calendar)) is not None
        )
        if intervals:
            return _result(
                "years",
                merge_intervals(intervals),
                outer=_joint_nodes(a, b) is not None,
            )
    if allow_circa_estimate:
        start_year, circa_start = _nominal_year(first, calendar)
        end_year, circa_end = _nominal_year(last, calendar)
        if (
            (circa_start or circa_end)
            and start_year is not None
            and end_year is not None
            and start_year <= end_year
        ):
            age = Fraction(end_year - start_year)
            return TemporalDifference(
                "years",
                "estimate",
                (Interval(age, age, True, True),),
                "Estimated from the recorded calendar years.",
            )
    return TemporalDifference(
        "years", "unavailable", reason="Date bounds are incomplete"
    )


def present_elapsed(
    result: TemporalDifference,
    unit: Literal["days", "hours", "minutes", "seconds"],
    decimal_places: int = 0,
) -> TemporalDifference:
    """Convert an elapsed result to display units without changing its evidence."""
    if result.unit != "days" or decimal_places < 0:
        raise ValueError("Choose an elapsed result and nonnegative decimal precision")
    scale = {"days": 1, "hours": 24, "minutes": 1440, "seconds": 86400}[unit]
    quantum = 10**decimal_places
    intervals = tuple(
        _display_interval(interval, scale, quantum, result.kind)
        for interval in result.intervals
    )
    rounded = any(
        after != _display_interval(before, scale, quantum=None, kind=result.kind)
        for before, after in zip(result.intervals, intervals, strict=True)
    )
    return TemporalDifference(unit, result.kind, intervals, result.reason, rounded)


def _display_interval(
    interval: Interval, scale: int, quantum: int | None, kind: str
) -> Interval:
    lower = interval.lower * scale if interval.lower is not None else None
    upper = interval.upper * scale if interval.upper is not None else None
    if quantum is None:
        return Interval(lower, upper, interval.lower_closed, interval.upper_closed)
    if lower is not None and lower == upper and kind in {"value", "estimate"}:
        rounded = Fraction(round(lower * quantum), quantum)
        return Interval(rounded, rounded, True, True)
    first = Fraction(floor(lower * quantum), quantum) if lower is not None else None
    last = Fraction(ceil(upper * quantum), quantum) if upper is not None else None
    return Interval(
        first,
        last,
        first != lower or interval.lower_closed,
        last != upper or interval.upper_closed,
    )
