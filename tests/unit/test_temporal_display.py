"""Timeline evidence must not present layout midpoints as known boundaries."""

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.temporal_display import event_temporal_display
from src.core.temporal_expression import TemporalPrecision
from src.gui.widgets.temporal_range_widget import TemporalRangeWidget
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.temporal_geometry import project_temporal_geometry

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize(
    ("authored_date", "exact_day"),
    [
        ("14 June 1209", True),
        ("14 June 1209 14:30", True),
        ("14 June 1209 14:30:15", True),
        ("calculated 14 June 1209", True),
        ("June 1209", False),
        ("1209", False),
        ("c. 14 June 1209", False),
        ("14 June 1209?", False),
        ("estimated 14 June 1209", False),
    ],
)
def test_single_occurrence_caption_respects_known_day(authored_date, exact_day):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression(authored_date)
    event = Event(
        name="Expedition",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )

    display = event_temporal_display(event, converter)

    assert display is not None
    assert display.caption.startswith(authored_date)
    assert ("exact date unknown" not in display.caption) == exact_day


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
    legacy = event_temporal_display(
        Event(name="Legacy", lore_date=5, lore_duration=10), converter
    )
    assert legacy.kind == "duration"
    assert (legacy.possible_start, legacy.possible_end) == (5, 15)
    assert (legacy.certain_start, legacy.certain_end) == (5, 15)


@pytest.mark.parametrize(
    ("authored", "scale", "mode", "compact"),
    [
        (None, 20, "exact", False),
        ("14 June 1209 14:30", 20, "exact", False),
        ("14 June 1209 14:30:15", 20, "exact", False),
        ("14 June 1209", 20, "window", True),
        ("14 June 1209", 24, "window", False),
        ("June 1209", 0.1, "window", True),
        ("1209", 0.1, "window", False),
        ("c. 14 June 1209", 20, "soft", False),
        ("estimated 1209", 20, "soft", False),
        ("between 1207 and 1209", 0.1, "window", False),
        ("before 1209", 20, "one_sided", False),
        ("after 1209", 20, "one_sided", False),
    ],
)
def test_point_visual_grammar(authored, scale, mode, compact):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = (
        DateParser(converter._config).parse_expression(authored)
        if authored is not None
        else None
    )
    event = Event(
        name="Occurrence",
        lore_date=expression.representative_time(converter) if expression else 5,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}}
        if expression
        else {},
    )
    display = event_temporal_display(event, converter)
    geometry = project_temporal_geometry(display, scale)
    assert display.kind == "point"
    assert geometry.mode == mode
    assert geometry.compact is compact
    if mode == "soft":
        assert geometry.right - geometry.left == 32
    if mode == "one_sided":
        assert geometry.cap_left != geometry.cap_right


def test_duration_visual_grammar_and_short_symbol():
    converter = CalendarConverter(CalendarConfig.create_default())
    precise = event_temporal_display(
        Event(name="Legacy", lore_date=100, lore_duration=10), converter
    )
    full = project_temporal_geometry(precise, 1)
    short = project_temporal_geometry(precise, 0.5)
    assert full.mode == short.mode == "duration"
    assert full.compact is False
    assert short.compact is True
    assert short.right - short.left == 6
    assert (full.certain_left, full.certain_right) == (0, 10)
    assert (short.certain_left, short.certain_right) == (
        short.left,
        short.right,
    )

    parser = DateParser(converter._config)
    approximate = parser.parse_expression("c. 1209")
    event = Event(
        name="Unknown start",
        lore_date=approximate.representative_time(converter),
        lore_duration=365,
        attributes={"_temporal_v2": {"schema": 1, "expression": approximate.to_dict()}},
    )
    display = event_temporal_display(event, converter)
    assert display.kind == "duration"
    assert project_temporal_geometry(display, 20).mode == "unresolved"

    year = parser.parse_expression("1209")
    uncertain = Event(
        name="Long duration, uncertain start",
        lore_date=year.representative_time(converter),
        lore_duration=800,
        attributes={"_temporal_v2": {"schema": 1, "expression": year.to_dict()}},
    )
    compact = project_temporal_geometry(
        event_temporal_display(uncertain, converter), 0.001
    )
    assert compact.compact is True
    assert compact.certain_left is not None
    assert compact.certain_right is not None
    assert compact.certain_right - compact.certain_left < 6


def test_hour_precision_and_missing_calendar():
    converter = CalendarConverter(CalendarConfig.create_default())
    minute = DateParser(converter._config).parse_expression("14 June 1209 14:30")
    hour = replace(
        minute, minute=None, precision=TemporalPrecision.HOUR, original_text=None
    )
    event = Event(
        name="Hour",
        lore_date=hour.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": hour.to_dict()}},
    )
    display = event_temporal_display(event, converter)
    assert project_temporal_geometry(display, 20).compact is True
    assert project_temporal_geometry(display, 600).compact is False
    unavailable = event_temporal_display(event, None)
    assert unavailable.error is True
    assert project_temporal_geometry(unavailable, 20).mode == "unresolved"


def test_item_geometry_and_lane_width_follow_zoom(qtbot):
    from src.gui.widgets.timeline_lane_packer import TimelineLanePacker

    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("14 June 1209")
    event = Event(
        name="Day",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    EventItem.set_calendar_converter(converter)
    try:
        item = EventItem(event, scale_factor=20)
        before = event.attributes.copy()
        compact = item._display_rect(event_temporal_display(event, converter))
        assert compact.width() == 16
        assert item.shape().contains(compact.center())
        item.set_zoom(2)
        full = item._display_rect(event_temporal_display(event, converter))
        assert full.width() == 40
        assert item.boundingRect().contains(full)
        packer = TimelineLanePacker(40)
        assert packer._calculate_visual_duration(event) >= full.width() / 40
        item.update_event(event)
        assert event.attributes == before
    finally:
        EventItem.set_calendar_converter(None)


def test_semantic_window_moves_with_drag_without_changing_evidence(qtbot):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("14 June 1209")
    event = Event(
        name="Dragged day",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    EventItem.set_calendar_converter(converter)
    try:
        item = EventItem(event, scale_factor=20)
        original = item._display_rect(event_temporal_display(event, converter))
        original_position = item.x()
        item._is_dragging = True
        item._initial_y = item.y()
        item.setPos(original_position + 100, item.y())
        moved = item._display_rect(event_temporal_display(event, converter))
        assert moved == original
        assert item.x() == original_position + 100
        assert event.attributes["_temporal_v2"]["expression"] == expression.to_dict()
    finally:
        item._is_dragging = False
        EventItem.set_calendar_converter(None)


@pytest.mark.parametrize("selected", [False, True])
def test_exact_fill_is_distinct_from_day_window(qtbot, selected):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = DateParser(converter._config).parse_expression("14 June 1209")
    day = Event(
        name="Day",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    exact = Event(name="Exact", lore_date=day.lore_date)
    EventItem.set_calendar_converter(converter)
    try:
        center_alpha = []
        for event in (exact, day):
            item = EventItem(event, scale_factor=20)
            item.setSelected(selected)
            image = QImage(120, 80, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.translate(40, 20)
            item.paint(painter, QStyleOptionGraphicsItem())
            painter.end()
            center_alpha.append(image.pixelColor(40, 20).alpha())
        assert center_alpha[0] > center_alpha[1]
    finally:
        EventItem.set_calendar_converter(None)


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
