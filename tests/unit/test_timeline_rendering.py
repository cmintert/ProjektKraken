"""
Additional tests for Timeline rendering and EventItem paint methods.
"""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QImage
from PySide6.QtWidgets import QStyleOptionGraphicsItem
from src.gui.widgets.timeline import (
    TimelineWidget,
    TimelineView,
    EventItem,
    TimelineScene,
)
from src.core.events import Event


@pytest.fixture
def timeline_view(qtbot):
    """Create TimelineView for testing."""
    view = TimelineView()
    qtbot.addWidget(view)
    return view


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        Event(id="e1", name="Event 1", lore_date=1000.0, type="cosmic"),
        Event(id="e2", name="Event 2", lore_date=2000.0, type="combat"),
        Event(id="e3", name="Event 3", lore_date=3000.0, type="session"),
    ]


def test_event_item_bounding_rect():
    """Test EventItem bounding rectangle."""
    event = Event(name="Test", lore_date=100.0, type="generic")
    item = EventItem(event, scale_factor=10.0)

    rect = item.boundingRect()
    assert isinstance(rect, QRectF)
    assert rect.width() == EventItem.MAX_WIDTH
    assert rect.height() == EventItem.ICON_SIZE * 2 + 8


def test_event_item_paint(qtbot):
    """Test EventItem paint method doesn't crash."""
    event = Event(name="Test Event", lore_date=1000.0, type="combat")
    item = EventItem(event, scale_factor=20.0)

    # Create a QPainter with a QImage
    image = QImage(400, 100, QImage.Format_ARGB32)
    image.fill(Qt.black)
    painter = QPainter(image)

    option = QStyleOptionGraphicsItem()

    # This should not crash
    item.paint(painter, option, None)

    painter.end()


def test_event_item_paint_selected(qtbot):
    """Test EventItem paint when selected."""
    event = Event(name="Selected Event", lore_date=1000.0, type="cosmic")
    item = EventItem(event, scale_factor=20.0)
    item.setSelected(True)

    # Create a QPainter
    image = QImage(400, 100, QImage.Format_ARGB32)
    image.fill(Qt.black)
    painter = QPainter(image)

    option = QStyleOptionGraphicsItem()

    # Paint selected item
    item.paint(painter, option, None)

    painter.end()
    assert item.isSelected()


def test_event_item_color_by_type():
    """Test that different event types get different colors."""
    cosmic = EventItem(Event(name="C", lore_date=1.0, type="cosmic"), 10.0)
    combat = EventItem(Event(name="C", lore_date=1.0, type="combat"), 10.0)
    generic = EventItem(Event(name="G", lore_date=1.0, type="generic"), 10.0)

    assert cosmic.base_color != combat.base_color
    assert cosmic.base_color != generic.base_color


def test_event_item_position():
    """Test EventItem is positioned based on lore_date."""
    event = Event(name="Test", lore_date=500.0, type="generic")
    scale = 25.0
    item = EventItem(event, scale_factor=scale)

    assert item.x() == 500.0 * scale
    assert item.y() == 0  # Default Y is 0


def test_timeline_scene_init():
    """Test TimelineScene initialization."""
    scene = TimelineScene()
    assert scene.backgroundBrush() is not None


def test_timeline_view_set_events_empty(timeline_view):
    """Test setting empty events list."""
    timeline_view.set_events([])

    # Should have at least the axis line
    items = timeline_view.scene.items()
    assert len(items) >= 1


def test_timeline_view_set_events_with_data(timeline_view, sample_events):
    """Test setting events creates all items."""
    timeline_view.set_events(sample_events)

    event_items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
    assert len(event_items) == 3

    # Check all events are in scene
    for event in sample_events:
        found = any(item.event.id == event.id for item in event_items)
        assert found, f"Event {event.id} not found in scene"


def test_timeline_view_drag_mode(timeline_view):
    """Test drag mode is set correctly."""
    from PySide6.QtWidgets import QGraphicsView

    assert timeline_view.dragMode() == QGraphicsView.ScrollHandDrag


def test_timeline_view_fit_all(timeline_view, sample_events):
    """Test fit_all method."""
    timeline_view.set_events(sample_events)

    # Should not crash
    timeline_view.fit_all()

    # Scene rect should be set
    assert timeline_view.scene.sceneRect().isValid()


def test_timeline_view_focus_event_found(timeline_view):
    """Test focusing on an event that exists."""
    event = Event(id="target", name="Target", lore_date=1000.0, type="generic")
    timeline_view.set_events([event])

    timeline_view.focus_event("target")

    # Find the EventItem
    items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
    assert len(items) == 1
    assert items[0].isSelected()


def test_timeline_view_focus_event_not_found(timeline_view, sample_events):
    """Test focusing on non-existent event doesn't crash."""
    timeline_view.set_events(sample_events)

    # Should not crash
    timeline_view.focus_event("nonexistent-id")

    # No item should be selected
    items = [i for i in timeline_view.scene.items() if isinstance(i, EventItem)]
    assert not any(item.isSelected() for item in items)


def test_timeline_view_scale_factor(timeline_view):
    """Test scale factor is set."""
    assert timeline_view.scale_factor == 20.0


def test_timeline_widget_btn_fit(qtbot):
    """Test Fit View button exists and is connected."""
    widget = TimelineWidget()
    qtbot.addWidget(widget)

    assert widget.btn_fit is not None
    assert widget.btn_fit.text() == "Fit View"

    # Click should not crash
    widget.set_events([Event(name="E", lore_date=100.0, type="generic")])
    widget.btn_fit.click()


def test_timeline_widget_header_frame(qtbot):
    """Test header frame exists."""
    widget = TimelineWidget()
    qtbot.addWidget(widget)

    assert widget.header_frame is not None
    assert widget.header_frame.objectName() == "TimelineHeader"


def test_timeline_view_scene_rect_updates(timeline_view, sample_events):
    """Test scene rect updates when events are set."""
    timeline_view.set_events(sample_events)

    scene_rect = timeline_view.scene.sceneRect()
    assert scene_rect.width() > 0
    assert scene_rect.height() > 0


def test_event_item_flags():
    """Test EventItem has correct flags."""
    from PySide6.QtWidgets import QGraphicsItem

    event = Event(name="Test", lore_date=100.0, type="generic")
    item = EventItem(event, 10.0)

    flags = item.flags()
    assert flags & QGraphicsItem.ItemIsSelectable
    assert flags & QGraphicsItem.ItemIsFocusable
    assert flags & QGraphicsItem.ItemIgnoresTransformations


def test_timeline_view_lane_height_constant(timeline_view):
    """Test LANE_HEIGHT constant."""
    assert timeline_view.LANE_HEIGHT == 40


def test_timeline_view_ruler_height_constant(timeline_view):
    """Test RULER_HEIGHT constant."""
    assert timeline_view.RULER_HEIGHT == 40
