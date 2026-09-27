"""Timeline evidence must not present layout midpoints as known boundaries."""

import pytest

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.temporal_display import event_temporal_display
from src.gui.widgets.temporal_range_widget import TemporalRangeWidget
from src.gui.widgets.timeline.event_item import EventItem

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("duration", [0, 100, 365, 800])
def test_year_extent_is_calendar_bound_not_midpoint(qtbot, duration):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("961")
    event = Event(
        name="Corruption",
        lore_date=expression.representative_time(converter),
        lore_duration=duration,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    display = event_temporal_display(event, converter)
    assert display.possible_start == converter.start_of_year(961)
    assert display.possible_end == converter.start_of_year(962) + duration
    assert (display.certain_start is not None) == (duration > 365)
    EventItem.set_calendar_converter(converter)
    item = EventItem(event, scale_factor=2)
    item.set_zoom(1.5)
    rect = item._display_rect(display)
    assert rect.left() == (converter.start_of_year(961) - event.lore_date) * 3
    assert rect.center().y() == 0
    assert item.shape().contains(rect.center())
    assert item.boundingRect().contains(rect)
    EventItem.set_calendar_converter(None)


def test_soft_dates_never_get_finite_duration_envelopes():
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("c. 961")
    event = Event(
        name="Approximate",
        lore_date=0,
        lore_duration=365,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    display = event_temporal_display(event, converter)
    assert display.possible_start is display.possible_end is None
    assert display.certain_start is None


def test_overlapping_uncertainty_tracks_get_separate_lanes(qtbot):
    from src.gui.widgets.timeline_lane_packer import TimelineLanePacker

    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("961")
    first = Event(
        name="A",
        lore_date=expression.representative_time(converter),
        lore_duration=365,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    second = Event(name="B", lore_date=converter.start_of_year(962) + 250)
    EventItem.set_calendar_converter(converter)
    try:
        lanes, _ = TimelineLanePacker(10).pack_events([first, second])
        assert lanes[first.id] != lanes[second.id]
    finally:
        EventItem.set_calendar_converter(None)


def test_separate_end_assertion_controls_extent():
    converter = CalendarConverter(CalendarConfig.create_default())
    parser = DateParser(converter._config)
    event = Event(
        name="Campaign",
        lore_date=0,
        lore_duration=10,
        attributes={
            "_temporal_v2": {
                "schema": 1,
                "expression": parser.parse_expression("961").to_dict(),
                "end_expression": parser.parse_expression("963").to_dict(),
            }
        },
    )
    display = event_temporal_display(event, converter)
    assert display.possible_end == converter.start_of_year(964)
    assert display.certain_start == converter.start_of_year(962)
    assert display.certain_end == converter.start_of_year(963)
    assert (
        event_temporal_display(
            Event(name="Legacy", lore_date=5, lore_duration=10), converter
        )
        is None
    )


def test_explicit_single_occurrence_clears_duration_without_changing_year(qtbot):
    converter = CalendarConverter(CalendarConfig.create_default())
    widget = TemporalRangeWidget()
    qtbot.addWidget(widget)
    widget.set_calendar_converter(converter)
    expression = DateParser(converter._config).parse_expression("961")
    widget.set_values(expression.representative_time(converter), 365)
    widget.date_start.set_expression(expression)
    widget._update_range_summary()
    assert widget.has_duration.isChecked()
    assert widget.date_end.isHidden()
    assert "351" not in widget.range_summary.text()
    widget.has_duration.setChecked(False)
    assert widget.get_duration() == 0
    assert widget.date_start.get_expression() == expression
    assert widget.date_end.get_expression() is None
