"""Prepare recurrence display text and viewport projections outside widgets."""

import math
from dataclasses import dataclass

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.recurrence import (
    Occurrence,
    RecurrenceRule,
    occurrences_in_window,
    validate_recurrence,
)
from src.core.temporal_expression import TemporalExpression


@dataclass(frozen=True)
class RecurrencePreview:
    """Prepared explanation of a bounded schedule preview."""

    text: str
    error: bool = False


def occurrence_bound(
    value: float,
    expression: TemporalExpression | None,
    converter: CalendarConverter | None,
    *,
    latest: bool,
) -> float:
    """Include an authored precision interval rather than its layout midpoint."""
    if (
        expression is None
        or converter is None
        or expression.calendar_id != converter._config.id
        or expression.qualifier.value != "asserted"
        or expression.day is None
    ):
        return value
    lower, upper = converter.resolve_precision_bounds(expression)
    return math.nextafter(upper, -math.inf) if latest else lower


def preview_recurrence(
    event: Event, converter: CalendarConverter | None
) -> RecurrencePreview:
    """Explain nearby repetitions, skipping invalid dates with bounded work."""
    try:
        rule, anchor, _duration = validate_recurrence(event, converter)
        span = recurrence_period(rule, converter) * 8
        before = occurrences_in_window(
            event, converter, max(-1e12, anchor - span), anchor, limit=8
        )
        after = occurrences_in_window(
            event, converter, anchor, min(1e12, anchor + span), limit=4
        )
        previous = [o.start for o in before.occurrences if o.start < anchor][-3:]
        starts = sorted({*previous, anchor, *(o.start for o in after.occurrences)})
        dates = [format_occurrence(value, converter) for value in starts]
        return RecurrencePreview(
            "Preview: "
            + "; ".join(dates)
            + ". Missing dates are skipped. Bounds apply to start dates."
        )
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return RecurrencePreview(str(exc), True)


def format_occurrence(value: float, converter: CalendarConverter | None) -> str:
    """Format an occurrence without inventing an unavailable calendar."""
    return converter.format_date(value) if converter else f"Day {value:g}"


def recurrence_period(
    rule: RecurrenceRule, converter: CalendarConverter | None
) -> float:
    """Estimate scale eligibility; actual dates always use calendar arithmetic."""
    if rule.frequency == "days":
        return rule.interval
    if converter is None:
        return 0.0
    config = converter._config
    year_length = sum(month.days for month in config.months)
    units = {
        "weeks": len(config.week.day_names),
        "months": year_length / max(1, len(config.months)),
        "years": year_length,
    }
    return units[rule.frequency] * rule.interval


@dataclass(frozen=True)
class RecurrenceProjection:
    """Detached rows, errors and continuations for a viewport."""

    event: Event
    occurrences: tuple[Occurrence, ...] = ()
    error: str = ""
    next_index: int | None = None


def project_recurrence(
    event: Event,
    converter: CalendarConverter | None,
    start: float,
    end: float,
    major_step: float,
    cursor: int | None = None,
) -> RecurrenceProjection:
    """Apply semantic zoom eligibility before bounded expansion."""
    try:
        rule, _anchor, _duration = validate_recurrence(event, converter)
        # An annual rule remains visible at year and closer scales, including
        # calendars whose year differs from the ruler's numeric scale estimate.
        nominal = {
            "days": rule.interval,
            "weeks": 7 * rule.interval,
            "months": 30 * rule.interval,
            "years": 365 * rule.interval,
        }
        if major_step > nominal[rule.frequency] * 1.01:
            return RecurrenceProjection(event)
        page = occurrences_in_window(event, converter, start, end, cursor=cursor)
        return RecurrenceProjection(event, page.occurrences, next_index=page.next_index)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return RecurrenceProjection(event, error=str(exc))
