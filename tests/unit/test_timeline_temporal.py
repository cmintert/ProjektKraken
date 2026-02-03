"""Tests for Timeline Temporal Visualization.

Verifies that events are visually styled (dulled/desaturated) based on their
temporal relationship to the playhead.
"""

import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from src.app.constants import (
    TEMPORAL_FUTURE_OPACITY,
    TEMPORAL_FUTURE_SATURATION_FACTOR,
)
from src.core.events import Event
from src.gui.widgets.timeline import EventItem, TimelineView


@pytest.fixture(scope="module")
def qapp_module(qapp):
    """Module-level QApplication fixture to avoid recreation."""
    return qapp


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)
    return view


def test_event_item_has_temporal_state_attributes(qapp_module):
    """Test that EventItem has temporal state attributes."""
    event = Event(name="Test Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    assert hasattr(item, "is_future")
    assert hasattr(item, "is_past")
    assert item.is_future is False
    assert item.is_past is False


def test_event_item_set_temporal_state_future(qapp_module):
    """Test setting an event to future state."""
    event = Event(name="Future Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    item.set_temporal_state(is_future=True, is_past=False)

    assert item.is_future is True
    assert item.is_past is False
    assert item.opacity() == TEMPORAL_FUTURE_OPACITY


def test_event_item_set_temporal_state_present(qapp_module):
    """Test setting an event to present/past state (normal)."""
    event = Event(name="Present Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    # Set to future first
    item.set_temporal_state(is_future=True, is_past=False)
    assert item.opacity() == TEMPORAL_FUTURE_OPACITY

    # Now set to present
    item.set_temporal_state(is_future=False, is_past=False)

    assert item.is_future is False
    assert item.opacity() == 1.0


def test_event_item_get_effective_color_future(qapp_module):
    """Test that future events have desaturated color."""
    event = Event(name="Future Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    # Get normal color
    normal_color = item._get_effective_color()
    h_normal, s_normal, l_normal, a_normal = normal_color.getHslF()

    # Set future state
    item.set_temporal_state(is_future=True, is_past=False)

    # Get future color
    future_color = item._get_effective_color()
    h_future, s_future, l_future, a_future = future_color.getHslF()

    # Saturation should be reduced
    expected_saturation = s_normal * TEMPORAL_FUTURE_SATURATION_FACTOR
    assert abs(s_future - expected_saturation) < 0.01

    # Lightness should be slightly increased
    assert l_future > l_normal


def test_event_item_get_effective_color_present(qapp_module):
    """Test that present events have normal color."""
    event = Event(name="Present Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    # Get normal color
    normal_color = item._get_effective_color()
    h_normal, s_normal, l_normal, a_normal = normal_color.getHslF()

    # Set to present state
    item.set_temporal_state(is_future=False, is_past=False)

    # Get present color
    present_color = item._get_effective_color()
    h_present, s_present, l_present, a_present = present_color.getHslF()

    # Colors should be identical
    assert abs(h_present - h_normal) < 0.01
    assert abs(s_present - s_normal) < 0.01
    assert abs(l_present - l_normal) < 0.01


def test_timeline_view_has_update_events_temporal_state_method(timeline_view):
    """Test that TimelineView has the update_events_temporal_state method."""
    assert hasattr(timeline_view, "update_events_temporal_state")
    assert callable(timeline_view.update_events_temporal_state)


def test_timeline_view_updates_future_events(timeline_view):
    """Test that TimelineView correctly marks future events."""
    events = [
        Event(id="e1", name="Past Event", lore_date=50.0, type="generic"),
        Event(id="e2", name="Current Event", lore_date=100.0, type="generic"),
        Event(id="e3", name="Future Event", lore_date=150.0, type="generic"),
    ]

    timeline_view.set_events(events)
    timeline_view.set_playhead_time(100.0)

    # Manually trigger temporal state update
    timeline_view.update_events_temporal_state()

    # Get event items
    event_items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]

    # Find each event
    past_item = next((i for i in event_items if i.event.id == "e1"), None)
    current_item = next((i for i in event_items if i.event.id == "e2"), None)
    future_item = next((i for i in event_items if i.event.id == "e3"), None)

    assert past_item is not None
    assert current_item is not None
    assert future_item is not None

    # Past and current should not be future
    assert past_item.is_future is False
    assert current_item.is_future is False

    # Future should be marked as future
    assert future_item.is_future is True
    assert future_item.opacity() == TEMPORAL_FUTURE_OPACITY


def test_timeline_view_updates_on_playhead_change(timeline_view):
    """Test that temporal state updates when playhead moves."""
    events = [
        Event(id="e1", name="Event 1", lore_date=50.0, type="generic"),
        Event(id="e2", name="Event 2", lore_date=100.0, type="generic"),
        Event(id="e3", name="Event 3", lore_date=150.0, type="generic"),
    ]

    timeline_view.set_events(events)

    # Set playhead to 75 (e1 is past, e2 and e3 are future)
    timeline_view.set_playhead_time(75.0)

    event_items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
    e1_item = next((i for i in event_items if i.event.id == "e1"), None)
    e2_item = next((i for i in event_items if i.event.id == "e2"), None)
    e3_item = next((i for i in event_items if i.event.id == "e3"), None)

    assert e1_item.is_future is False
    assert e2_item.is_future is True
    assert e3_item.is_future is True

    # Move playhead to 125 (e1 and e2 are past, e3 is future)
    timeline_view.set_playhead_time(125.0)

    assert e1_item.is_future is False
    assert e2_item.is_future is False
    assert e3_item.is_future is True


def test_event_item_set_temporal_state_idempotent(qapp_module):
    """Test that setting the same state multiple times doesn't cause issues."""
    event = Event(name="Test Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    # Set to future multiple times
    item.set_temporal_state(is_future=True, is_past=False)
    first_opacity = item.opacity()

    item.set_temporal_state(is_future=True, is_past=False)
    second_opacity = item.opacity()

    item.set_temporal_state(is_future=True, is_past=False)
    third_opacity = item.opacity()

    assert first_opacity == second_opacity == third_opacity == TEMPORAL_FUTURE_OPACITY


def test_event_item_paint_does_not_crash_with_temporal_state(qtbot, qapp_module):
    """Test that painting with temporal state doesn't crash."""
    event = Event(name="Test Event", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    # Set temporal state
    item.set_temporal_state(is_future=True, is_past=False)

    # Paint to image
    image = QImage(400, 100, QImage.Format_ARGB32)
    painter = QPainter(image)
    option = QStyleOptionGraphicsItem()

    # Should not crash
    item.paint(painter, option, None)

    painter.end()
