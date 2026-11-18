"""Regression coverage for temporal arithmetic at different precisions."""

from fractions import Fraction

import pytest

from src.core.calendar import CalendarConfig, MonthDefinition, YearVariant
from src.core.date_parser import DateParser
from src.core.event_timing.constraints import Interval
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_calculation import (
    END_PRECEDES_START,
    DateEvidence,
    completed_calendar_years,
    elapsed_time,
    present_elapsed,
)
from src.core.temporal_expression import ResolvedTemporalBounds
from src.core.temporal_shift import shift_anchor


@pytest.fixture
def parser():
    return DateParser(CalendarConfig.create_default())


def _date(parser, text):
    expression = parser.parse_expression(text)
    return DateEvidence(expression.resolve_bounds(parser.converter), expression)


def _instant(day):
    return DateEvidence(ResolvedTemporalBounds(hard_start=day, hard_end=day))


@pytest.mark.parametrize(
    ("birth", "death", "expected"),
    [
        ("8 January 1090", "7 January 1152", (61, 61)),
        ("8 January 1090", "8 January 1152", (62, 62)),
        ("January 1090", "8 January 1152", (61, 62)),
        ("1090", "1152", (61, 62)),
        ("29 February 2000", "28 February 2001", (1, 1)),
        ("8 January 1152", "8 January 1152", (0, 0)),
    ],
)
def test_completed_years_follow_calendar_precision(parser, birth, death, expected):
    result = completed_calendar_years(
        _date(parser, birth), _date(parser, death), parser.converter
    )
    assert result.kind == ("value" if expected[0] == expected[1] else "range")
    assert [(i.lower, i.upper) for i in result.intervals] == [expected]


def test_anniversary_uses_end_of_custom_year_if_birth_month_is_absent():
    calendar = CalendarConfig.create_default()
    calendar.months = [MonthDefinition("First", "Fir", 10)]
    calendar.leap_year_rules = []
    calendar.year_variants = [
        YearVariant(1, [*calendar.months, MonthDefinition("Second", "Sec", 4)])
    ]
    converter = DateParser(calendar).converter
    birth = _instant(converter.start_of_day(1, 2, 1))
    before = _instant(converter.start_of_day(2, 1, 9))
    anniversary = _instant(converter.start_of_day(2, 1, 10))
    assert completed_calendar_years(birth, before, converter).intervals[0].lower == 0
    assert (
        completed_calendar_years(birth, anniversary, converter).intervals[0].lower == 1
    )


def test_circa_requires_opt_in_and_does_not_change_elapsed_evidence(parser):
    birth = _date(parser, "c.1090")
    death = _date(parser, "8 January 1152")
    assert elapsed_time(birth, death).kind == "unavailable"
    assert (
        completed_calendar_years(birth, death, parser.converter).kind == "unavailable"
    )
    result = completed_calendar_years(
        birth, death, parser.converter, allow_circa_estimate=True
    )
    assert result.kind == "estimate"
    assert result.intervals[0].lower == 62
    assert birth.bounds.hard_start is None


def test_elapsed_is_signed_and_display_precision_is_caller_selected():
    result = elapsed_time(_instant(1.875), _instant(2.0625))
    assert result.intervals[0].lower == Fraction(3, 16)
    assert present_elapsed(result, "minutes").intervals[0].lower == 270
    hours = present_elapsed(result, "hours", decimal_places=1)
    assert hours.intervals[0].lower == Fraction(9, 2)
    rounded = present_elapsed(result, "hours")
    assert rounded.rounded
    assert rounded.kind == "value"
    assert result.intervals[0].lower == Fraction(3, 16)
    assert elapsed_time(_instant(2), _instant(1)).intervals[0].lower == -1


def test_open_bounds_and_display_rounding_are_preserved(parser):
    later = DateEvidence(ResolvedTemporalBounds(hard_start=1.0625, hard_end=1.1875))
    result = elapsed_time(_instant(1), later)
    assert result.intervals == (Interval(Fraction(1, 16), Fraction(3, 16)),)
    display = present_elapsed(result, "hours")
    assert display.kind == "range"
    assert display.intervals == (Interval(Fraction(1), Fraction(5), True, True),)
    before = DateEvidence(ResolvedTemporalBounds(hard_start=1, hard_end=2))
    assert (
        completed_calendar_years(_instant(2), before, parser.converter).reason
        == END_PRECEDES_START
    )


@pytest.mark.parametrize("unit", ["days", "years"])
def test_joint_differences_use_dependencies_and_offsets(parser, unit):
    expression = parser.parse_expression("January 1090")
    start = Event(
        name="Start",
        lore_date=None,
        attributes={
            "_temporal_v2": {
                "schema": 2,
                "timing": EventTimingDefinition(
                    EndpointDefinition(expression=expression.to_dict())
                ).to_dict(),
            }
        },
    )
    end = Event(
        name="End",
        lore_date=None,
        attributes={
            "_temporal_v2": {
                "schema": 2,
                "timing": EventTimingDefinition(
                    EndpointDefinition(
                        kind="event",
                        anchor_id=f"event:{start.id}",
                        offset={
                            "value": 5.0,
                            "unit": unit,
                            "calendar_id": expression.calendar_id,
                        },
                    )
                ).to_dict(),
            }
        },
    )
    anchors = resolve_world([start, end], parser.converter).anchors()
    a, b = anchors[f"event:{start.id}"], anchors[f"event:{end.id}"]
    if unit == "years":
        age = completed_calendar_years(
            DateEvidence(a), DateEvidence(b), parser.converter
        )
        assert age.kind == "value"
        assert age.intervals[0].lower == 5
        return
    difference = elapsed_time(DateEvidence(a), DateEvidence(b))
    assert difference.kind == "value"
    assert difference.intervals[0].lower == 5
    shifted = shift_anchor(b, {"offset_days": 2}, parser.converter)
    assert elapsed_time(DateEvidence(a), DateEvidence(shifted)).intervals[0].lower == 7
