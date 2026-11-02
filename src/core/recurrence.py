"""Optional Event schedules and bounded, persistence-free occurrence queries."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.calendar_index import locate_year, month_span
from src.core.event_timing.definitions import EventTimingDefinition
from src.core.events import Event
from src.core.temporal_expression import MAX_LORE_DAY, TemporalExpression

RECURRENCE_ATTRIBUTE = "_recurrence"
MAX_CANDIDATES = 4096


@dataclass(frozen=True)
class RecurrenceRule:
    """A schedule phased from an Event's authored date, never a new Event type."""

    frequency: str = "years"
    interval: float = 1
    direction: str = "forward"
    calendar_id: str | None = None
    weekdays: tuple[int, ...] = ()
    ordinal: int | None = None
    earliest: float | None = None
    latest: float | None = None
    schema: int = 1

    def __post_init__(self) -> None:
        """Reject unsupported schedules instead of guessing their meaning."""
        if self.schema != 1 or isinstance(self.schema, bool):
            raise ValueError("Unsupported recurrence version; stored data is preserved")
        if self.frequency not in {"days", "weeks", "months", "years"}:
            raise ValueError("Choose days, weeks, months or years")
        if (
            isinstance(self.interval, bool)
            or not math.isfinite(self.interval)
            or self.interval <= 0
        ):
            raise ValueError("Repeat interval must be finite and positive")
        if self.frequency != "days" and not float(self.interval).is_integer():
            raise ValueError("Calendar repeat intervals must be whole numbers")
        if self.direction not in {"forward", "backward", "both"}:
            raise ValueError("Choose forward, backward or both directions")
        self._validate_calendar_fields()
        self._validate_bounds()

    def _validate_calendar_fields(self) -> None:
        if self.frequency != "days" and not self.calendar_id:
            raise ValueError("Calendar recurrence requires a saved calendar")
        if any(type(day) is not int or day < 0 for day in self.weekdays):
            raise ValueError("Choose valid calendar weekdays")
        if tuple(sorted(set(self.weekdays))) != self.weekdays:
            raise ValueError("Weekdays must be unique and ordered")
        if self.frequency == "weeks" and not self.weekdays:
            raise ValueError("Choose at least one weekday")
        if self.ordinal is not None:
            if (
                type(self.ordinal) is not int
                or self.ordinal not in {-1, 1, 2, 3, 4, 5}
                or self.frequency not in {"months", "years"}
                or len(self.weekdays) != 1
            ):
                raise ValueError("Choose first through fifth, or last, and one weekday")
        elif self.frequency != "weeks" and self.weekdays:
            raise ValueError("Monthly weekday rules require an ordinal")

    def _validate_bounds(self) -> None:
        for value in (self.earliest, self.latest):
            if value is not None and (
                isinstance(value, bool)
                or not math.isfinite(value)
                or abs(value) > MAX_LORE_DAY
            ):
                raise ValueError("Recurrence bounds must be supported finite dates")
        if (
            self.earliest is not None
            and self.latest is not None
            and self.earliest > self.latest
        ):
            raise ValueError("Earliest occurrence must not follow latest occurrence")

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible definition."""
        return {**asdict(self), "weekdays": list(self.weekdays)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecurrenceRule:
        """Read exactly the supported schema, retaining opaque data at the caller."""
        values = dict(data)
        values["weekdays"] = tuple(values.get("weekdays", ()))
        return cls(**values)


@dataclass(frozen=True)
class Occurrence:
    """Detached display projection; never passed to Event persistence consumers."""

    event_id: str
    index: int
    start: float
    duration: float

    @property
    def display_id(self) -> str:
        """Return a deterministic identity scoped to this schedule."""
        return f"{self.event_id}/occurrence/{self.index}"


@dataclass(frozen=True)
class OccurrencePage:
    """Bounded results and a continuation cursor, including sparse invalid dates."""

    occurrences: tuple[Occurrence, ...]
    next_index: int | None = None
    examined: int = 0


def weekday_index(value: float, week_length: int) -> int:
    """Use calendar days, including the fractional day before the epoch."""
    if week_length <= 0:
        raise ValueError("This calendar has no weekdays")
    return math.floor(value) % week_length


def anchor_date(event: Event, converter: CalendarConverter | None) -> float:
    """Resolve an exact authored date without mistaking a layout point for evidence."""
    definition = EventTimingDefinition.from_event(event)
    if definition.end_mode == "independent":
        raise ValueError("Repeats require no end or a fixed duration")
    start = definition.start
    if start.kind != "manual":
        raise ValueError("Repeats require an independently authored exact date")
    if start.expression is None:
        assert start.instant is not None
        return start.instant
    expression = TemporalExpression.from_dict(start.expression)
    if expression.qualifier.value != "asserted" or expression.day is None:
        raise ValueError("Repeats require an exact calendar date with a day")
    if converter is None or expression.calendar_id != converter._config.id:
        raise ValueError("The anchor's calendar is unavailable")
    return converter.resolve_precision_bounds(expression)[0]


def validate_recurrence(
    event: Event, converter: CalendarConverter | None
) -> tuple[RecurrenceRule, float, float]:
    """Validate the complete schedule against its authored Event and calendar."""
    rule = RecurrenceRule.from_dict(event.attributes[RECURRENCE_ATTRIBUTE])
    anchor = anchor_date(event, converter)
    if not math.isfinite(anchor) or abs(anchor) > MAX_LORE_DAY:
        raise ValueError("The anchor is outside the supported date range")
    duration = EventTimingDefinition.from_event(event).duration_days or 0.0
    if rule.earliest is not None and anchor < rule.earliest:
        raise ValueError("The anchor precedes the earliest occurrence")
    if rule.latest is not None and anchor > rule.latest:
        raise ValueError("The anchor follows the latest occurrence")
    if rule.frequency != "days":
        if converter is None or converter._config.id != rule.calendar_id:
            raise ValueError("The recurrence calendar is unavailable")
        week_length = len(converter._config.week.day_names)
        if rule.weekdays and (not week_length or max(rule.weekdays) >= week_length):
            raise ValueError("A selected weekday is unavailable in this calendar")
        if rule.frequency == "weeks":
            if weekday_index(anchor, week_length) not in rule.weekdays:
                raise ValueError("The anchor must fall on a selected weekday")
        elif rule.ordinal is not None:
            date = converter.from_float(anchor)
            candidate = _month_day(rule, converter, date.year, date.month, date.day)
            if candidate != math.floor(anchor):
                raise ValueError("The anchor does not match the selected weekday rule")
    return rule, anchor, duration


def _month_day(
    rule: RecurrenceRule, converter: CalendarConverter, year: int, month: int, day: int
) -> float:
    if rule.ordinal is None:
        return converter.start_of_day(year, month, day)
    start = converter.start_of_month(year, month)
    length = converter._config.get_months_for_year(year)[month - 1].days
    week_length = len(converter._config.week.day_names)
    offset = (rule.weekdays[0] - weekday_index(start, week_length)) % week_length
    offset += (
        ((length - 1 - offset) // week_length) * week_length
        if rule.ordinal == -1
        else (rule.ordinal - 1) * week_length
    )
    if offset >= length or offset < 0:
        raise ValueError("This month has no matching weekday occurrence")
    return start + offset


def _calendar_candidates(
    rule: RecurrenceRule,
    anchor: float,
    converter: CalendarConverter,
    lower: float,
    upper: float,
    cursor: int | None,
) -> Iterator[tuple[int, float | None]]:
    date, first, last = (converter.from_float(v) for v in (anchor, lower, upper))
    step = int(rule.interval)
    origin = month_span(converter._config, date.year) + date.month - 1
    if rule.frequency == "years":
        begin = (first.year - date.year) // step
        end = (last.year - date.year) // step
    else:
        begin = (
            month_span(converter._config, first.year) + first.month - 1 - origin
        ) // step
        end = (
            month_span(converter._config, last.year) + last.month - 1 - origin
        ) // step
    begin = max(begin, cursor) if cursor is not None else begin
    fraction = anchor - math.floor(anchor)
    for index in range(begin, min(end + 1, begin + MAX_CANDIDATES)):
        year, month = date.year + index * step, date.month
        if rule.frequency == "months":
            ordinal = origin + index * step
            year = locate_year(ordinal, lambda y: month_span(converter._config, y))
            month = ordinal - month_span(converter._config, year) + 1
        try:
            yield index, _month_day(rule, converter, year, month, date.day) + fraction
        except ValueError:
            yield index, None


def _candidates(
    rule: RecurrenceRule,
    anchor: float,
    converter: CalendarConverter | None,
    lower: float,
    upper: float,
    cursor: int | None,
) -> Iterator[tuple[int, float | None]]:
    if rule.frequency in {"months", "years"}:
        assert converter is not None
        yield from _calendar_candidates(rule, anchor, converter, lower, upper, cursor)
        return
    if rule.frequency == "days":
        base, step = Fraction(str(anchor)), Fraction(str(rule.interval))
        begin = math.ceil((Fraction(str(lower)) - base) / step)
        end = math.floor((Fraction(str(upper)) - base) / step)
        begin = max(begin, cursor) if cursor is not None else begin
        for index in range(begin, min(end + 1, begin + MAX_CANDIDATES)):
            value = float(base + index * step)
            if float(base + (index + 1) * step) <= value:
                raise ValueError(
                    "Repeat interval is too small at this date's precision"
                )
            yield index, value
        return
    assert converter is not None
    week_length = len(converter._config.week.day_names)
    origin = math.floor(anchor) // week_length * week_length
    fraction = anchor - math.floor(anchor)
    span = week_length * int(rule.interval)
    count = len(rule.weekdays)
    begin = math.floor((lower - origin) / span) * count
    end = math.floor((upper - origin) / span) * count + count - 1
    begin = max(begin, cursor) if cursor is not None else begin
    for index in range(begin, min(end + 1, begin + MAX_CANDIDATES)):
        cycle, rank = divmod(index, count)
        yield index, origin + cycle * span + rule.weekdays[rank] + fraction


def occurrences_in_window(
    event: Event,
    converter: CalendarConverter | None,
    start: float,
    end: float,
    *,
    limit: int = 512,
    cursor: int | None = None,
) -> OccurrencePage:
    """Seek directly to a window; bound both returned items and examined candidates.

    A continuation cursor resumes sparse/large queries without restarting from the
    anchor. Bounds include starts; the viewport includes intersecting durations.
    """
    if not all(math.isfinite(v) and abs(v) <= MAX_LORE_DAY for v in (start, end)):
        raise ValueError("Choose a finite supported occurrence window")
    if end < start or not 1 <= limit <= MAX_CANDIDATES:
        raise ValueError("Choose an ordered window and a bounded page size")
    rule, anchor, duration = validate_recurrence(event, converter)
    lower = max(
        -MAX_LORE_DAY,
        start - duration,
        rule.earliest if rule.earliest is not None else -MAX_LORE_DAY,
    )
    upper = min(end, rule.latest if rule.latest is not None else MAX_LORE_DAY)
    if rule.direction == "forward":
        lower = max(lower, anchor)
    elif rule.direction == "backward":
        upper = min(upper, anchor)
    if lower > upper:
        return OccurrencePage(())
    result = []
    examined = 0
    last_index = None
    for index, value in _candidates(rule, anchor, converter, lower, upper, cursor):
        examined += 1
        last_index = index
        if (
            value is not None
            and lower <= value <= upper
            and (value >= start or value + duration > start)
        ):
            result.append(Occurrence(event.id, index, value, duration))
        if len(result) == limit:
            return OccurrencePage(tuple(result), index + 1, examined)
    continuation = (
        last_index + 1
        if examined == MAX_CANDIDATES and last_index is not None
        else None
    )
    return OccurrencePage(tuple(result), continuation, examined)
