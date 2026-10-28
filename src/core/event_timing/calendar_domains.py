"""Calendar relations as lazy valid and invalid piecewise translations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from src.core.calendar import CalendarConverter
from src.core.event_timing.constraints import Cancel, Constraint, Interval, checkpoint
from src.core.event_timing.definitions import EndpointDefinition
from src.core.temporal_shift import _calendar_regions, _globally_affine, calendar_shift


@dataclass(frozen=True)
class CalendarPiece:
    """Invalid pieces restrict only the source; they never invent a target."""

    edges: tuple[Constraint, ...]
    invalid: str | None = None


def _piece(
    source: str, target: str, interval: Interval, delta: Fraction | None
) -> CalendarPiece:
    rule = f"calendar:{target}"
    edges = interval.constraints(source, rule)
    if delta is None:
        return CalendarPiece(edges, target)
    return CalendarPiece(
        (
            *edges,
            Constraint(source, target, delta, rule=rule),
            Constraint(target, source, -delta, rule=rule),
        )
    )


def calendar_pieces(
    target: str,
    endpoint: EndpointDefinition,
    ranges: tuple[Interval, ...],
    converter: CalendarConverter | None,
    cancel: Cancel | None,
) -> Iterator[CalendarPiece]:
    """Partition on day validity and calendar months, never enumerate days."""
    offset = endpoint.offset or {}
    amount, unit = int(offset.get("value", 0)), str(offset.get("unit"))
    source = endpoint.source
    if converter is None or offset.get("calendar_id") != converter._config.id:
        yield CalendarPiece((), target)
        return
    if _globally_affine(amount, unit, converter):
        delta = Fraction(calendar_shift(0, amount, unit, converter))
        yield _piece(source, target, Interval(), delta)
        return
    for interval in ranges:
        checkpoint(cancel)
        if interval.lower is None or interval.upper is None:
            # The undefined calendar domain must remain visible, never be trimmed.
            yield CalendarPiece(interval.constraints(source), target)
            continue
        yield from _bounded_pieces(
            source, target, interval, amount, unit, converter, cancel
        )


def _bounded_pieces(
    source: str,
    target: str,
    interval: Interval,
    amount: int,
    unit: str,
    converter: CalendarConverter,
    cancel: Cancel | None,
) -> Iterator[CalendarPiece]:
    """Skip complete periodic regions between sparse year variants."""
    assert interval.lower is not None and interval.upper is not None
    if float(interval.lower) == float(interval.upper):
        yield from _finite_pieces(
            source, target, interval, amount, unit, converter, cancel
        )
        return
    regions = _calendar_regions(
        float(interval.lower), float(interval.upper), amount, unit, converter
    )
    for index, (lower, upper, regular) in enumerate(regions):
        checkpoint(cancel)
        part = Interval(
            interval.lower if index == 0 else Fraction(lower),
            interval.upper if index == len(regions) - 1 else Fraction(upper),
            interval.lower_closed if index == 0 else True,
            False,
        )
        if regular:
            delta = Fraction(calendar_shift(lower, amount, unit, converter)) - Fraction(
                lower
            )
            yield _piece(source, target, part, delta)
        else:
            yield from _finite_pieces(
                source, target, part, amount, unit, converter, cancel
            )
    if interval.upper_closed:
        yield from _finite_pieces(
            source,
            target,
            Interval(interval.upper, interval.upper, True, True),
            amount,
            unit,
            converter,
            cancel,
        )


def _finite_pieces(
    source: str,
    target: str,
    interval: Interval,
    amount: int,
    unit: str,
    converter: CalendarConverter,
    cancel: Cancel | None,
) -> Iterator[CalendarPiece]:
    assert interval.lower is not None and interval.upper is not None
    cursor = interval.lower
    while cursor < interval.upper or (
        cursor == interval.upper and interval.upper_closed
    ):
        checkpoint(cancel)
        date = converter.from_float(float(cursor.numerator // cursor.denominator))
        month_end = Fraction(converter.start_of_next_month(date.year, date.month))
        upper = min(interval.upper, month_end)
        closed = upper == interval.upper and interval.upper_closed and upper < month_end
        part = Interval(
            cursor,
            upper,
            interval.lower_closed if cursor == interval.lower else True,
            closed,
        )
        yield from _month_piece(source, target, part, amount, unit, converter)
        if upper == interval.upper and interval.upper_closed and upper == month_end:
            yield from _month_piece(
                source,
                target,
                Interval(upper, upper, True, True),
                amount,
                unit,
                converter,
            )
        if upper == cursor or upper == interval.upper:
            break
        cursor = upper


def _month_piece(
    source: str,
    target: str,
    part: Interval,
    amount: int,
    unit: str,
    converter: CalendarConverter,
) -> Iterator[CalendarPiece]:
    assert part.lower is not None and part.upper is not None
    date = converter.from_float(float(part.lower.numerator // part.lower.denominator))
    month_start = Fraction(converter.start_of_day(date.year, date.month, 1))
    try:
        destination = calendar_shift(float(month_start), amount, unit, converter)
        target_date = converter.from_float(destination)
        months = converter._config.get_months_for_year(target_date.year)
        valid_end = month_start + months[target_date.month - 1].days
    except (ValueError, OverflowError, IndexError):
        yield _piece(source, target, part, None)
        return
    valid_upper = min(part.upper, valid_end)
    if part.lower < valid_upper or (
        part.lower == valid_upper
        and part.lower < valid_end
        and part.lower_closed
        and part.upper_closed
    ):
        yield _piece(
            source,
            target,
            Interval(
                part.lower,
                valid_upper,
                part.lower_closed,
                part.upper_closed and part.upper < valid_end,
            ),
            Fraction(destination) - month_start,
        )
    if part.upper > valid_end or (part.upper == valid_end and part.upper_closed):
        yield _piece(
            source,
            target,
            Interval(
                max(part.lower, valid_end),
                part.upper,
                part.lower_closed if part.lower > valid_end else True,
                part.upper_closed,
            ),
            None,
        )
