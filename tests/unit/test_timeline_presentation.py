"""Independent temporal channels and accepted viewing-context regressions."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.temporal_display import event_temporal_display
from src.core.temporal_presentation import (
    event_navigation_context,
    event_temporal_presentation,
)
from src.core.theme_manager import ThemeManager
from src.core.visual_roles import contrast
from src.gui.widgets.timeline import EventItem, TimelineWidget
from src.gui.widgets.timeline.group_band_item import GroupBandItem
from src.gui.widgets.timeline.item_layout import timeline_item_layout
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def calendar():
    converter = CalendarConverter(CalendarConfig.create_default())
    EventItem.set_calendar_converter(converter)
    yield converter
    EventItem.set_calendar_converter(None)


def authored(converter, text, duration=0, end=None):
    parser = DateParser(converter._config)
    expression = parser.parse_expression(text)
    metadata = {"schema": 1, "expression": expression.to_dict()}
    if end:
        metadata["end_expression"] = parser.parse_expression(end).to_dict()
    return Event(
        name="Council",
        lore_date=expression.representative_time(converter),
        lore_duration=duration,
        attributes={"_temporal_v2": metadata},
    )


@pytest.mark.parametrize(
    "text",
    [
        "1218",
        "c. 1218",
        "before 1218",
        "after 1218",
        "June 1218",
        "between June 1218 and October 1218",
    ],
)
def test_duration_length_never_includes_occurrence_uncertainty(calendar, qapp, text):
    owner = authored(calendar, text, 3)
    before = deepcopy(owner.to_dict())
    presentation = event_temporal_presentation(owner, calendar)
    assert presentation.presence == event_temporal_display(owner, calendar)
    assert owner.to_dict() == before
    layout = timeline_item_layout(presentation, owner.name, 2.4)
    assert [row.label for row in layout.rows] == ["Starts", "Duration", "Possible span"]
    assert layout.rows[1].geometry.right - layout.rows[
        1
    ].geometry.left == pytest.approx(7.2)
    assert layout.rows[0].geometry.mode != "unresolved"
    assert layout.rows[2].geometry.mode != "unresolved"


def test_measure_threshold_is_independent_from_year_and_presence_thresholds(
    calendar, qapp
):
    presentation = event_temporal_presentation(authored(calendar, "1218", 3), calendar)
    broad = timeline_item_layout(presentation, "Council", 0.02)
    close = timeline_item_layout(presentation, "Council", 2.4)
    assert broad.rows[1].geometry.compact
    assert broad.rows[1].geometry.right - broad.rows[1].geometry.left == 6
    assert not broad.rows[2].geometry.compact
    assert not close.rows[1].geometry.compact
    assert close.rows[0].geometry.right - close.rows[0].geometry.left == 876
    assert close.rows[2].geometry.right - close.rows[2].geometry.left == pytest.approx(
        883.2
    )


def test_independent_endpoints_do_not_invent_an_authored_length(calendar, qapp):
    presentation = event_temporal_presentation(
        authored(calendar, "June 1218", 120, "October 1218"), calendar
    )
    assert presentation.authored_duration is None
    layout = timeline_item_layout(presentation, "Council", 1.2)
    assert [r.label for r in layout.rows] == ["Starts", "Ends", "Possible span"]
    assert all(not row.measure for row in layout.rows)
    assert layout.rows[-1].geometry.certain_left is not None
    assert layout.rows[-1].geometry.certain_right is not None


def test_invalid_calendar_still_uses_actual_error_symbol(calendar, qapp):
    owner = authored(calendar, "1218", 3)
    owner.attributes["_temporal_v2"]["expression"]["calendar_id"] = "missing"
    layout = timeline_item_layout(
        event_temporal_presentation(owner, calendar), "Council", 1
    )
    assert len(layout.rows) == 1
    assert layout.rows[0].geometry.mode == "unresolved"


def test_shared_hit_and_packing_extents_cover_all_three_channels(calendar, qapp):
    owner = authored(calendar, "1218", 800)
    item = EventItem(owner, 1.2)
    before = item.boundingRect()
    for row in item._layout().rows:
        assert item.shape().contains(row.rect.center())
        assert before.contains(row.rect)
    item.setSelected(True)
    item.set_temporal_state(True)
    assert item.boundingRect() == before
    assert item.opacity() == 1
    assert "Not yet" in item.display_name
    packer = TimelineLanePacker(1.2)
    assert packer._calculate_visual_duration(owner) == pytest.approx(
        before.width() / 1.2
    )
    neighbor = Event(name="Neighbor", lore_date=owner.lore_date + 100)
    assignments, heights = packer.pack_events([owner, neighbor])
    assert assignments[owner.id] != assignments[neighbor.id]
    assert max(heights) >= before.height()


@pytest.mark.parametrize(
    "theme_name",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_date_caption_and_time_roles_remain_readable_in_future_state(qapp, theme_name):
    manager = ThemeManager()
    previous = manager.current_theme_name
    try:
        manager.current_theme_name = theme_name
        theme = manager.get_theme()
        item = EventItem(Event(name="Council", lore_date=100))
        item.set_temporal_state(True)
        assert item.opacity() == 1
        assert item._secondary_text_color.name() == theme["supporting_caption"].lower()
        assert contrast(theme["supporting_caption"], theme["app_bg"]) >= 4.5
        assert contrast(theme["timeline_viewed_time"], theme["app_bg"]) >= 3
        assert contrast(theme["timeline_world_time"], theme["app_bg"]) >= 3
    finally:
        manager.current_theme_name = previous


def test_collapsed_band_receives_uncertainty_and_legacy_dates_stay_exact(
    calendar, qapp
):
    band = GroupBandItem(
        "Council", ThemeManager().get_theme()["event_main"], 2, 0, 1, True
    )
    starts = [
        event_temporal_presentation(authored(calendar, text), calendar).start
        for text in ("1218", "c. 1218")
    ]
    band.set_event_presentations(starts)
    assert band.presentations == tuple(starts)
    assert band.get_height() == 24
    band.set_event_dates([1, 2])
    assert [(p.possible_start, p.possible_end) for p in band.presentations] == [
        (1, 1),
        (2, 2),
    ]


@pytest.fixture
def timeline(qtbot, calendar):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.set_calendar_converter(calendar)
    widget.resize(800, 600)
    widget.show()
    return widget


def test_accepted_context_survives_pan_zoom_selection_then_clears(
    timeline, calendar, qtbot
):
    owner = authored(calendar, "1218", 3)
    timeline.set_events([owner])
    timeline.set_current_time(owner.lore_date + 50)
    timeline.set_playhead_time(
        owner.lore_date, event_navigation_context(owner, calendar)
    )
    qtbot.waitUntil(lambda: timeline.time_status.notice.isVisible())
    assert "occurrence date is not exact" in timeline.time_status.notice.text()
    timeline.center_on_date(owner.lore_date + 10)
    timeline.view._apply_zoom(0.03)
    timeline.view._event_items[owner.id].setSelected(True)
    timeline.view.time_indicators.settle()
    assert timeline.time_status.notice.isVisible()
    assert timeline.get_current_time() == owner.lore_date + 50
    timeline.set_playhead_time(owner.lore_date + 1)
    timeline.view.time_indicators.settle()
    assert not timeline.time_status.notice.isVisible()


def test_rejected_and_deferred_navigation_do_not_replace_accepted_context(
    timeline, calendar
):
    first = authored(calendar, "1218")
    second = authored(calendar, "1219")
    timeline.set_events([first, second])
    timeline.set_playhead_time(
        first.lore_date, event_navigation_context(first, calendar)
    )
    timeline.accept_navigation_context()
    accepted = dict(timeline.view.time_indicators.context)
    timeline.set_navigation_acceptor(lambda time: time == first.lore_date)
    timeline.set_playhead_time(
        second.lore_date, event_navigation_context(second, calendar)
    )
    timeline.accept_navigation_context()
    assert timeline.view.time_indicators.context == accepted
    timeline.set_playhead_time(first.lore_date)
    timeline.accept_navigation_context()
    assert timeline.view.time_indicators.context == accepted
    timeline.set_playhead_time(
        second.lore_date, event_navigation_context(second, calendar)
    )
    timeline.set_navigation_acceptor(lambda time: True)
    timeline.accept_navigation_context()
    assert timeline.view.time_indicators.context["event_id"] == second.id


def test_target_refresh_and_deletion_clear_stale_context(timeline, calendar):
    owner = authored(calendar, "1218")
    timeline.set_events([owner])
    timeline.set_playhead_time(
        owner.lore_date, event_navigation_context(owner, calendar)
    )
    timeline.accept_navigation_context()
    owner.name = "Renamed council"
    timeline.set_events([owner])
    timeline.accept_navigation_context()
    assert "Renamed council" in timeline.time_status.notice.text()
    timeline.set_events([])
    timeline.accept_navigation_context()
    assert timeline.view.time_indicators.context == {}


def test_manual_snap_publishes_target_without_modifying_assertions(timeline, calendar):
    owner = authored(calendar, "1218")
    before = deepcopy(owner.to_dict())
    timeline.set_events([owner])
    timeline.view._apply_zoom(0.06)
    timeline.set_playhead_event_snapping(True)
    time = timeline.view._manual_playhead_time((owner.lore_date + 5) * 20)
    timeline.view._playhead.setPos(time * 20, 0)
    timeline.accept_navigation_context()
    assert time == owner.lore_date
    assert timeline.view.time_indicators.context["uncertain"]
    assert owner.to_dict() == before


def test_time_lines_remain_dashed_and_coincident_identity_is_named(timeline):
    timeline.set_events([Event(name="Council", lore_date=0)])
    timeline.set_playhead_time(0)
    timeline.set_current_time(20)
    timeline.view._apply_zoom(0.06)
    timeline.center_on_date(0)
    image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    timeline.view.time_indicators.paint(painter)
    painter.end()
    x = timeline.view.mapFromScene(QPointF(400, 0)).x()
    alphas = [image.pixelColor(x, y).alpha() for y in range(100, 200)]
    assert max(alphas) > 0
    assert min(alphas) == 0
    timeline.set_current_time(0)
    assert timeline.get_playhead_time() == timeline.get_current_time()
    timeline.view.time_indicators.refresh()
    assert "Viewing:" in timeline.time_status.dates.text()
    assert "World current time:" in timeline.time_status.dates.text()


def test_production_group_duplicates_share_zoom_and_refresh_captions(
    timeline, calendar
):
    owner = authored(calendar, "1218", 3)
    owner.attributes["_tags"] = ["Council"]
    provider = Mock()
    provider.get_events_for_group.return_value = [owner]
    provider.get_group_metadata.side_effect = lambda tag_order, date_range=None: [
        {
            "tag_name": tag,
            "color": ThemeManager().get_theme()["event_main"],
            "count": 1,
            "earliest_date": owner.lore_date,
            "latest_date": owner.lore_date,
        }
        for tag in tag_order
    ]
    timeline.set_data_provider(provider)
    timeline.set_events([owner])
    timeline.set_grouping_config(["Council"])
    timeline.view._apply_zoom(0.06)
    items = [
        item
        for item in timeline.view.graphics_scene.items()
        if isinstance(item, EventItem)
    ]
    assert len(items) == 2
    for item in items:
        first = item._layout().rows[0].geometry
        assert first.right - first.left == pytest.approx(438)
        assert item._zoom_level == 0.06
    manager = timeline.view._band_manager
    manager._on_collapse_requested("Council")
    band = manager.get_band("Council")
    assert "Duration: 3 days" in band.toolTip()
    owner.lore_duration = 7
    timeline.view.repack_events()
    assert "Duration: 7 days" in band.toolTip()
    assert (
        band.presentations[0].possible_end - band.presentations[0].possible_start == 365
    )


def test_first_items_do_not_hide_behind_time_identity_rows(timeline, calendar):
    timeline.set_events([authored(calendar, "1218", 3)])
    timeline.view.verticalScrollBar().setValue(
        timeline.view.verticalScrollBar().minimum()
    )
    item = next(
        item
        for item in timeline.view.graphics_scene.items()
        if isinstance(item, EventItem)
    )
    top = timeline.view.mapFromScene(item.sceneBoundingRect().topLeft()).y()
    assert top >= timeline.view.RULER_HEIGHT


@pytest.mark.parametrize("persisted_time", [0.0, 42.25, -12.5, 444682.5])
def test_saved_playhead_restores_after_complete_widget_initialization(
    qtbot, monkeypatch, persisted_time
):
    settings = Mock()
    settings.value.side_effect = lambda key, default, **kwargs: (
        persisted_time if key == "timeline/playhead_time" else default
    )
    monkeypatch.setattr(
        "src.gui.widgets.timeline.timeline_view.QSettings", lambda: settings
    )
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(
        lambda: f"{persisted_time:g} days" in widget.time_status.dates.text()
    )
    qtbot.waitUntil(lambda: widget.view.time_indicators.pending is None)
    assert widget.get_playhead_time() == persisted_time
    assert widget.get_current_time() == 0.0
    assert widget.view.time_indicators.context == {}
    assert widget.view.time_indicators.pending is None
    settings.setValue.assert_not_called()
