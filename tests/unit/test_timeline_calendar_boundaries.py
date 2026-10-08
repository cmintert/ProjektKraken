"""Regression tests for calendar geometry on the timeline ruler."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    CalendarDate,
    MonthDefinition,
    WeekDefinition,
    YearVariant,
)
from src.core.events import Event
from src.gui.widgets.timeline import TimelineView
from src.gui.widgets.timeline_ruler import TickLevel, TimelineRuler

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def gregorian():
    return CalendarConverter(CalendarConfig.create_default())


@pytest.fixture
def fantasy():
    config = CalendarConfig.create_default()
    config.months = [MonthDefinition(f"Month {i}", f"M{i}", 30) for i in range(1, 13)]
    config.leap_year_rules = []
    config.week = WeekDefinition(
        [f"Day {i}" for i in range(5)], [f"D{i}" for i in range(5)]
    )
    return CalendarConverter(config)


def boundary(converter, year, month=1):
    return converter.to_float(CalendarDate(year, month, 1))


def level_ticks(converter, level, start, end):
    ruler = TimelineRuler()
    ruler.set_calendar_converter(converter)
    return ruler._generate_ticks_for_level(
        start, end, ruler.NUMERIC_LEVEL_STEPS[level], level, 1.0, True, 1.0
    )


def test_gregorian_year_961_matches_event_date(gregorian):
    ruler = TimelineRuler()
    ruler.set_calendar_converter(gregorian)
    start, end = boundary(gregorian, 960), boundary(gregorian, 962)
    ticks = ruler.calculate_ticks(start, end, 400, 20)
    years = [tick for tick in ticks if tick.level == TickLevel.YEAR]
    assert [tick.label for tick in years] == ["960", "961", "962"]
    assert [tick.position for tick in years] == [
        boundary(gregorian, year) for year in (960, 961, 962)
    ]
    assert boundary(gregorian, 961) == 350633
    for tick in years:
        assert tick.screen_x == pytest.approx(
            (tick.position - start) * 400 / (end - start)
        )


@pytest.mark.parametrize("year, february_days", [(960, 29), (1900, 28), (2000, 29)])
def test_month_boundaries_follow_leap_rules(gregorian, year, february_days):
    ticks = level_ticks(
        gregorian,
        TickLevel.MONTH,
        boundary(gregorian, year, 2),
        boundary(gregorian, year, 4),
    )
    assert [tick.label for tick in ticks] == ["Feb", "Mar", "Apr"]
    assert [tick.position for tick in ticks] == [
        boundary(gregorian, year, month) for month in (2, 3, 4)
    ]
    assert ticks[1].position - ticks[0].position == february_days


def test_360_day_years_and_year_zero(fantasy):
    ticks = level_ticks(fantasy, TickLevel.YEAR, -720, 720)
    assert [tick.position for tick in ticks] == [-720, -360, 0, 360, 720]
    assert [tick.label for tick in ticks] == ["-1", "0", "1", "2", "3"]


@pytest.mark.parametrize(
    "level,span",
    [
        (TickLevel.DECADE, 10),
        (TickLevel.CENTURY, 100),
        (TickLevel.ERA, 1000),
    ],
)
def test_multi_year_ticks_anchor_to_year_one(gregorian, level, span):
    years = [1 - span, 1, 1 + span]
    ticks = level_ticks(
        gregorian, level, boundary(gregorian, years[0]), boundary(gregorian, years[-1])
    )
    assert [tick.label for tick in ticks] == list(map(str, years))
    assert [tick.position for tick in ticks] == [boundary(gregorian, y) for y in years]


def test_short_variant_changes_year_and_month_boundaries(fantasy):
    config = replace(
        fantasy._config,
        year_variants=[
            YearVariant(
                2, [MonthDefinition("Short", "S", 20), MonthDefinition("Last", "L", 10)]
            )
        ],
    )
    converter = CalendarConverter(config)
    years = level_ticks(converter, TickLevel.YEAR, 0, 750)
    assert [t.position for t in years] == [0, 360, 390, 750]
    months = level_ticks(converter, TickLevel.MONTH, 360, 420)
    assert [(t.position, t.label) for t in months] == [
        (360, "S"),
        (380, "L"),
        (390, "M1"),
        (420, "M2"),
    ]


def test_five_day_weeks_are_epoch_aligned(fantasy):
    ticks = level_ticks(fantasy, TickLevel.WEEK, -12, 12)
    assert [tick.position for tick in ticks] == [-15, -10, -5, 0, 5, 10]
    assert all(t.label.endswith("D0") for t in ticks)


def test_quarters_start_on_month_boundaries(gregorian):
    ticks = level_ticks(gregorian, TickLevel.QUARTER, 0, 364)
    assert [t.position for t in ticks] == [0, 90, 181, 273]
    assert [t.label for t in ticks] == ["Q1", "Q2", "Q3", "Q4"]


def test_quarter_zoom_crossing_variant_uses_year_and_month(fantasy):
    config = replace(
        fantasy._config, year_variants=[YearVariant(2, fantasy._config.months[:6])]
    )
    ruler = TimelineRuler()
    ruler.set_calendar_converter(CalendarConverter(config))
    # 400 days / 600 pixels selects quarters with the ordinary LOD thresholds.
    ticks = ruler.calculate_ticks(200, 600, 600, 20)
    assert {t.level for t in ticks if t.is_major} == {TickLevel.YEAR}
    assert {t.level for t in ticks if not t.is_major} == {TickLevel.MONTH}
    assert all(t.level != TickLevel.QUARTER for t in ticks)
    assert all(0 < t.opacity < 1 for t in ticks if not t.is_major)


def test_major_and_minor_boundaries_are_unique(gregorian):
    ruler = TimelineRuler()
    ruler.set_calendar_converter(gregorian)
    ticks = ruler.calculate_ticks(0, 400, 600, 20)
    assert len({t.position for t in ticks}) == len(ticks)
    assert next(t for t in ticks if t.position == 0).is_major


@pytest.mark.parametrize("start", [-1.0, 0.0, 350633.0])
@pytest.mark.parametrize(
    "level,units", [(TickLevel.HOUR, 24), (TickLevel.MINUTE, 1440)]
)
def test_subday_ticks_have_exact_clock_labels(gregorian, start, level, units):
    ticks = level_ticks(gregorian, level, start, start + 20 / units)
    assert len(ticks) == 21
    for index, tick in enumerate(ticks):
        assert tick.position == (round(start * units) + index) / units
        minutes = index * (60 if level == TickLevel.HOUR else 1)
        assert tick.label == f"{minutes // 60:02}:{minutes % 60:02}"


def test_calendar_ticks_are_bounded_for_wide_ranges(fantasy):
    ticks = level_ticks(fantasy, TickLevel.MONTH, 0, 360 * 1000)
    assert len(ticks) == 500
    assert all(a.position < b.position for a, b in zip(ticks, ticks[1:]))


def test_narrow_range_keeps_only_preceding_year_boundary(gregorian):
    start = boundary(gregorian, 961) + 0.5
    ticks = level_ticks(gregorian, TickLevel.YEAR, start, start + 0.001)
    assert [(t.position, t.label) for t in ticks] == [(350633, "961")]


@pytest.mark.parametrize("year", [-1, 0, 1])
def test_months_cross_epoch_without_skipping_a_year(gregorian, year):
    ticks = level_ticks(
        gregorian,
        TickLevel.MONTH,
        boundary(gregorian, year, 12),
        boundary(gregorian, year + 1, 2),
    )
    assert [t.position for t in ticks] == [
        boundary(gregorian, year, 12),
        boundary(gregorian, year + 1),
        boundary(gregorian, year + 1, 2),
    ]
    assert [t.label for t in ticks] == ["Dec", "Jan", "Feb"]


@pytest.mark.parametrize("month_count", [1, 10, 13])
def test_nonstandard_years_never_generate_quarters(fantasy, month_count):
    months = [MonthDefinition(f"Month{i}", f"M{i}", 30) for i in range(month_count)]
    converter = CalendarConverter(replace(fantasy._config, months=months))
    assert level_ticks(converter, TickLevel.QUARTER, 0, 400) == []
    ruler = TimelineRuler()
    ruler.set_calendar_converter(converter)
    ticks = ruler.calculate_ticks(0, 400, 600, 20)
    assert ticks
    assert {t.level for t in ticks} <= {TickLevel.YEAR, TickLevel.MONTH}


def test_empty_week_skips_week_level(fantasy):
    converter = CalendarConverter(
        replace(
            fantasy._config,
            week=WeekDefinition([], []),
        )
    )
    ruler = TimelineRuler()
    ruler.set_calendar_converter(converter)
    ticks = ruler.calculate_ticks(0, 100, 800, 20)
    assert ticks
    assert {t.level for t in ticks if t.is_major} == {TickLevel.MONTH}
    assert all(t.level != TickLevel.WEEK for t in ticks)


def test_weekday_labels_use_day_names_length(fantasy):
    converter = CalendarConverter(
        replace(
            fantasy._config,
            week=WeekDefinition(fantasy._config.week.day_names, ["D0", "D1"]),
        )
    )
    ticks = level_ticks(converter, TickLevel.DAY, 0, 5)
    assert [t.label for t in ticks] == ["1 D0", "2 D1", "3", "4", "5", "6 D0"]


@pytest.mark.parametrize("calendar", [False, True])
def test_clock_labels_cross_midnight(gregorian, calendar):
    ruler = TimelineRuler()
    ruler.set_calendar_converter(gregorian if calendar else None)
    ticks = ruler._generate_ticks_for_level(
        -2 / 1440,
        2 / 1440,
        1 / 1440,
        TickLevel.MINUTE,
        1,
        True,
        1,
    )
    assert [t.label for t in ticks] == ["23:58", "23:59", "00:00", "00:01", "00:02"]


def test_calendar_switch_and_numeric_reset(gregorian, fantasy):
    ruler = TimelineRuler()
    for converter, expected in [(gregorian, 365), (fantasy, 360), (None, 365)]:
        ruler.set_calendar_converter(converter)
        ticks = ruler._generate_ticks_for_level(0, 400, 365, TickLevel.YEAR, 1, True, 1)
        assert ticks[1].position == expected


@pytest.mark.parametrize(
    "start,end,width",
    [
        (0, 0, 800),
        (1, 0, 800),
        (0, 1, 0),
        (0, 1, -1),
        (float("nan"), 1, 800),
        (0, float("inf"), 800),
    ],
)
def test_invalid_viewports_have_no_ticks(gregorian, start, end, width):
    ruler = TimelineRuler()
    ruler.set_calendar_converter(gregorian)
    assert ruler.calculate_ticks(start, end, width, 20) == []


@pytest.mark.parametrize("zoom,pan", [(0.015, 0), (0.025, 80)])
def test_january_event_aligns_with_painted_year_tick(
    qtbot,
    gregorian,
    monkeypatch,
    zoom,
    pan,
):
    view = TimelineView()
    qtbot.addWidget(view)
    view.resize(1000, 360)
    view.set_ruler_calendar(gregorian)
    view.set_events(
        [
            Event(
                id=str(year),
                name=f"1 January {year}",
                lore_date=boundary(gregorian, year),
            )
            for year in (960, 961, 962)
        ]
    )
    view.show()
    view._apply_zoom(zoom)
    view.focus_event("961")
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().value() + pan)

    painted_ticks = []
    calculate = view._ruler.calculate_ticks

    def capture_ticks(*args, **kwargs):
        ticks = calculate(*args, **kwargs)
        painted_ticks.extend(ticks)
        return ticks

    monkeypatch.setattr(view._ruler, "calculate_ticks", capture_ticks)
    image = QImage(view.viewport().size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        view.drawForeground(painter, QRectF(view.viewport().rect()))
    finally:
        painter.end()

    year_tick = next(
        t for t in painted_ticks if t.level == TickLevel.YEAR and t.label == "961"
    )
    event = view._event_items["961"]
    event_x = view.mapFromScene(event.scenePos()).x()
    tick_x = view.mapFromScene(QPointF(year_tick.position * view.scale_factor, 0)).x()
    assert 0 < event_x < image.width() - 1
    assert tick_x == event_x
    # Inspect actual paint output in the tick stem, away from labels and grid lines.
    stem_y = view.CALENDAR_RULER_HEIGHT - view.MAJOR_TICK_HEIGHT // 2
    assert image.pixelColor(event_x, stem_y) != image.pixelColor(event_x + 2, stem_y)
