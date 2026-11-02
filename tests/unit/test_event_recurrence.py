"""Recurrence is calculated independently of persistence and GUI state."""

from dataclasses import replace

import pytest

from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.events import Event
from src.core.recurrence import (
    RECURRENCE_ATTRIBUTE,
    RecurrenceRule,
    occurrences_in_window,
    validate_recurrence,
    weekday_index,
)

pytestmark = pytest.mark.ci_fast


def scheduled(converter, date=0.0, **settings):
    rule = RecurrenceRule(calendar_id=converter._config.id, **settings)
    return Event("Festival", date, attributes={RECURRENCE_ATTRIBUTE: rule.to_dict()})


@pytest.fixture
def calendar():
    return CalendarConverter(CalendarConfig.create_default())


@pytest.mark.parametrize(
    "direction,expected",
    [
        ("forward", [0, 0.5, 1]),
        ("backward", [-1, -0.5, 0]),
        ("both", [-1, -0.5, 0, 0.5, 1]),
    ],
)
def test_fractional_directions(calendar, direction, expected):
    event = scheduled(calendar, frequency="days", interval=0.5, direction=direction)
    page = occurrences_in_window(event, calendar, -1, 1)
    assert [o.start for o in page.occurrences] == expected
    assert len({o.display_id for o in page.occurrences}) == len(expected)


def test_remote_windows_seek_and_paginate(calendar):
    event = scheduled(calendar, frequency="days", interval=0.1, direction="both")
    first = occurrences_in_window(event, calendar, 1e9, 1e9 + 1, limit=3)
    second = occurrences_in_window(
        event, calendar, 1e9, 1e9 + 1, limit=3, cursor=first.next_index
    )
    assert first.examined == second.examined == 3
    assert first.occurrences[-1].start < second.occurrences[0].start
    assert first.occurrences[0].start == 1e9


def test_monthly_does_not_drift_after_short_month(calendar):
    anchor = calendar.to_float(CalendarDate(2024, 1, 31))
    event = scheduled(calendar, anchor, frequency="months")
    page = occurrences_in_window(
        event, calendar, anchor, calendar.to_float(CalendarDate(2024, 5, 1))
    )
    assert [
        (calendar.from_float(o.start).month, calendar.from_float(o.start).day)
        for o in page.occurrences
    ] == [(1, 31), (3, 31)]


def test_leap_day_and_remote_negative_years(calendar):
    anchor = calendar.to_float(CalendarDate(2024, 2, 29))
    event = scheduled(calendar, anchor, direction="both")
    start = calendar.start_of_year(-10000)
    page = occurrences_in_window(event, calendar, start, calendar.start_of_year(-9995))
    assert page.examined <= 6
    assert all(calendar.from_float(o.start).day == 29 for o in page.occurrences)


def test_weekdays_use_floor_before_epoch(calendar):
    assert weekday_index(-0.5, 7) == 6
    event = scheduled(
        calendar, -0.5, frequency="weeks", weekdays=(0, 6), direction="both"
    )
    page = occurrences_in_window(event, calendar, -8, 8)
    assert all(weekday_index(o.start, 7) in (0, 6) for o in page.occurrences)
    assert sum(o.start == -0.5 for o in page.occurrences) == 1


def test_last_weekday_matches_each_month(calendar):
    anchor = calendar.start_of_day(2024, 1, 31)
    day = weekday_index(anchor, 7)
    event = scheduled(calendar, anchor, frequency="months", ordinal=-1, weekdays=(day,))
    page = occurrences_in_window(event, calendar, anchor, calendar.start_of_year(2025))
    assert len(page.occurrences) == 12
    for occurrence in page.occurrences:
        date = calendar.from_float(occurrence.start)
        length = calendar._config.get_months_for_year(date.year)[date.month - 1].days
        assert date.day + 7 > length


def test_inclusive_zero_bound_and_intersecting_duration(calendar):
    event = scheduled(
        calendar, frequency="days", earliest=0, latest=4, direction="both"
    )
    event = replace(event, lore_duration=3)
    page = occurrences_in_window(event, calendar, 2.5, 3.5)
    assert [o.start for o in page.occurrences] == [0, 1, 2, 3]


@pytest.mark.parametrize("interval", [0, -1, float("inf"), float("nan"), True])
def test_invalid_intervals(interval):
    with pytest.raises(ValueError):
        RecurrenceRule(frequency="days", interval=interval)


def test_missing_calendar_and_opaque_version(calendar):
    event = scheduled(calendar)
    with pytest.raises(ValueError, match="calendar"):
        validate_recurrence(event, None)
    event.attributes[RECURRENCE_ATTRIBUTE]["schema"] = 2
    with pytest.raises(ValueError, match="version"):
        validate_recurrence(event, calendar)


def test_nonmatching_anchor_rejected(calendar):
    event = scheduled(calendar, frequency="weeks", weekdays=(1,))
    with pytest.raises(ValueError, match="anchor"):
        validate_recurrence(event, calendar)


def test_missing_fifth_weekday_is_skipped(calendar):
    anchor = calendar.start_of_day(2024, 1, 29)
    day = weekday_index(anchor, 7)
    event = scheduled(calendar, anchor, frequency="months", ordinal=5, weekdays=(day,))
    page = occurrences_in_window(
        event, calendar, anchor, calendar.start_of_day(2024, 7, 1)
    )
    dates = [calendar.from_float(o.start) for o in page.occurrences]
    assert len(dates) < 6
    assert all(date.day >= 29 for date in dates)


def test_duration_ending_at_window_start_does_not_intersect(calendar):
    event = replace(scheduled(calendar, frequency="days", interval=10), lore_duration=3)
    assert not occurrences_in_window(event, calendar, 3, 4).occurrences


@pytest.mark.parametrize("frequency", ["days", "months", "years"])
def test_billion_unit_period_still_returns_only_the_anchor(calendar, frequency):
    event = scheduled(calendar, frequency=frequency, interval=1e9, direction="both")
    page = occurrences_in_window(event, calendar, -1, 1)
    assert [occurrence.start for occurrence in page.occurrences] == [0]
    assert page.examined <= 2
