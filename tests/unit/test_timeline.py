import pytest
from src.gui.widgets.timeline import TimelineWidget, EventItem
from src.core.events import Event


def test_timeline_init(qapp):
    """Test that TimelineWidget initializes correctly."""
    widget = TimelineWidget()
    assert widget.scene is not None
    assert widget.scale_factor == 20.0


def test_set_events(qapp):
    """Test populating the timeline with events."""
    widget = TimelineWidget()

    events = [
        Event(name="Event A", lore_date=100.0, type="cosmic"),
        Event(name="Event B", lore_date=200.0, type="combat"),
    ]

    widget.set_events(events)

    # Check items in scene. At least axis, events, lines
    items = widget.scene.items()
    assert len(items) >= 5

    # Verify EventItems
    event_items = [i for i in items if isinstance(i, EventItem)]
    assert len(event_items) == 2

    # Check positions
    event_items.sort(key=lambda i: i.event.lore_date)

    assert event_items[0].event.name == "Event A"
    assert event_items[0].x() == 100.0 * 20.0

    assert event_items[1].event.name == "Event B"
    assert event_items[1].x() == 200.0 * 20.0


def test_lane_layout_logic(qapp):
    """Test that events are assigned to different Y levels (Lanes)."""
    widget = TimelineWidget()
    # Generate 9 events to ensure wrapping (Module 8)
    events = [Event(name=f"E{i}", lore_date=i * 10) for i in range(1, 10)]

    widget.set_events(events)

    items = [i for i in widget.scene.items() if isinstance(i, EventItem)]
    items.sort(key=lambda i: i.event.lore_date)

    # Check Y coordinates
    # E1 -> Lane 0 (Index 0 in items, i=0 loop index in set_events)
    # Wait, loop index in set_events matches `events` order (sorted by date).
    # items[0] corresponds to E1.

    # Lane logic: i % 8
    # Item 0 (E1): 0%8 = 0
    # Item 1 (E2): 1%8 = 1
    # Item 8 (E9): 8%8 = 0 -> Same as E1

    y1 = items[0].y()
    y2 = items[1].y()
    y9 = items[8].y()

    assert y1 != y2  # Different lanes
    assert y1 == y9  # Wrapped around to same lane
