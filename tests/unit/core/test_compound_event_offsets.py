"""Compound calculations preserve ordered calendar meaning and joint evidence."""

from dataclasses import replace

import pytest

from src.core.calendar import CalendarConfig, CalendarConverter, MonthDefinition
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.solver import resolve_world
from src.core.events import Event
from src.core.temporal_expression import TemporalExpression
from src.core.temporal_shift import shift_anchor

pytestmark = pytest.mark.ci_fast


def compound(converter, **values):
    return {
        "unit": "compound",
        "direction": 1,
        "years": 0,
        "months": 0,
        "days": 0,
        "calendar_id": converter._config.id,
        **values,
    }


def child(offset):
    timing = EventTimingDefinition(
        EndpointDefinition("event", anchor_id="event:root", offset=offset)
    )
    return Event("Child", 0, id="child", attributes=timing.apply({}))


@pytest.mark.parametrize("direction", [-1, 1])
def test_ordered_components_and_zero_year(direction):
    converter = CalendarConverter(CalendarConfig.create_default())
    source = converter.start_of_day(1, 1, 15) + 0.25
    offset = compound(converter, direction=direction, years=1, months=2, days=3.5)
    target_year, target_month = (2, 3) if direction == 1 else (-1, 11)
    expected = converter.start_of_day(target_year, target_month, 15) + 0.25
    expected += direction * 3.5
    root = Event("Root", source, id="root")
    result = resolve_world([root, child(offset)], converter)
    assert not result.issues
    assert result.endpoints["event:child"].coordinate == expected
    shifted = shift_anchor(
        result.anchors()["event:root"], {"offset": offset}, converter
    )
    assert shifted.hard_start == expected


@pytest.mark.parametrize(
    "date,values",
    [
        ((2024, 2, 29), {"years": 1, "months": 1}),
        ((2023, 1, 31), {"months": 1, "days": 2}),
    ],
)
def test_invalid_intermediate_dates_are_not_clamped_or_skipped(date, values):
    converter = CalendarConverter(CalendarConfig.create_default())
    root = Event("Root", converter.start_of_day(*date), id="root")
    result = resolve_world([root, child(compound(converter, **values))], converter)
    assert result.endpoints["event:child"].error
    assert result.endpoints["event:root"].coordinate == root.lore_date


def test_custom_calendar_and_compound_days_without_calendar():
    config = CalendarConfig.create_default()
    config.months = [MonthDefinition("A", "A", 10), MonthDefinition("B", "B", 20)]
    config.leap_year_rules = []
    converter = CalendarConverter(config)
    root = Event("Root", converter.start_of_day(0, 2, 4), id="root")
    offset = compound(converter, years=1, months=1, days=2)
    result = resolve_world([root, child(offset)], converter)
    assert not result.issues
    assert result.endpoints["event:child"].coordinate == converter.start_of_day(2, 1, 6)
    result = resolve_world(
        [root, child({"unit": "compound", "direction": -1, "days": 0.125})]
    )
    assert not result.issues
    assert result.endpoints["event:child"].coordinate == root.lore_date - 0.125


def test_uncertain_source_retains_joint_correlation_and_invalid_candidates():
    converter = CalendarConverter(CalendarConfig.create_default())
    start = converter.start_of_day(2023, 1, 27)
    expression = TemporalExpression(
        calendar_id=converter._config.id,
        year=2023,
        month=1,
        day=27,
        explicit_outer_start=start,
        explicit_outer_end=start + 1,
    )
    root = Event(
        "Root",
        start,
        id="root",
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    event = child(compound(converter, years=1, months=1, days=2))
    result = resolve_world([root, event], converter)
    assert not result.issues
    ranges = result.endpoints["event:child"].ranges
    assert float(ranges[0].lower) == converter.start_of_day(2024, 2, 29)
    assert float(ranges[-1].upper) == converter.start_of_day(2024, 3, 1)
    # February 2023 cannot represent January 29-31, even if days are added later.
    event = child(compound(converter, months=1, days=2))
    root.attributes["_temporal_v2"]["expression"] = replace(
        expression, explicit_outer_end=start + 4
    ).to_dict()
    result = resolve_world([root, event], converter)
    assert result.endpoints["event:child"].error


@pytest.mark.parametrize(
    "values",
    [
        {"direction": True},
        {"direction": 0},
        {"years": 0.5},
        {"days": -1},
        {"months": float("inf")},
        {"days": True},
        {"years": 1, "calendar_id": None},
    ],
)
def test_invalid_compound_definitions_are_rejected(values):
    converter = CalendarConverter(CalendarConfig.create_default())
    with pytest.raises(ValueError):
        child(compound(converter, **values))
