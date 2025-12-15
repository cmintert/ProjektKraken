from src.gui.widgets.timeline import TimelineWidget, EventItem
from src.core.events import Event


def test_timeline_init(qapp):
    """Test that TimelineWidget initializes correctly."""
    widget = TimelineWidget()
    assert widget.view.scene is not None
    assert widget.view.scale_factor == 20.0


def test_set_events(qapp):
    """Test populating the timeline with events."""
    widget = TimelineWidget()

    events = [
        Event(name="Event A", lore_date=100.0, type="cosmic"),
        Event(name="Event B", lore_date=200.0, type="combat"),
    ]

    widget.set_events(events)

    # Check items in scene. At least axis, events, lines
    items = widget.view.scene.items()
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
    """Test that smart lane packing works correctly."""
    widget = TimelineWidget()
    # Create events with overlapping durations to test smart packing
    events = [
        Event(name="E1", lore_date=10, lore_duration=30),  # 10-40
        Event(name="E2", lore_date=20, lore_duration=30),  # 20-50 (overlaps E1)
        Event(name="E3", lore_date=45, lore_duration=20),  # 45-65 (can reuse lane 0)
    ]

    widget.set_events(events)

    items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
    items.sort(key=lambda i: i.event.lore_date)

    # With smart packing:
    # E1 (10-40) -> Lane 0
    # E2 (20-50) -> Lane 1 (overlaps E1)
    # E3 (45-65) -> Lane 0 (can reuse since 45 > 40)

    y1 = items[0].y()  # E1
    y2 = items[1].y()  # E2
    y3 = items[2].y()  # E3

    # E1 and E2 should be on different lanes (overlapping)
    assert y1 != y2, "Overlapping events should use different lanes"
    
    # E3 should reuse E1's lane (non-overlapping)
    assert y1 == y3, "Non-overlapping events should reuse lanes"


def test_focus_event(qapp):
    """Test that focus_event finds items and selects them."""
    widget = TimelineWidget()
    event = Event(name="Target", lore_date=500.0)
    widget.set_events([event])

    # Pre-condition
    items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
    assert not items[0].isSelected()

    # Action
    widget.focus_event(event.id)

    # Assert
    assert items[0].isSelected()
    # Cannot easily test "centerOn" effect without mocking the view's geometry/viewport,
    # but we can verify it ran without error and selected the item.
