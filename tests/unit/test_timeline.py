from src.core.events import Event
from src.gui.widgets.timeline import EventItem, TimelineWidget


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


def test_gravity_packing(qapp):
    """
    Test that 'First Fit' strategy is used (Gravity), not 'Min-Heap'.

    Scenario:
    E1: 0-100 (Lane 0)
    E2: 0-10 (Lane 1)

    E3: 110-120

    Min-Heap (Earliest End Time) would pick Lane 1 (ends at 10) because 10 < 100.
    First Fit (Gravity) should pick Lane 0 because 100 <= 110.
    """
    widget = TimelineWidget()
    events = [
        Event(name="E1", lore_date=0, lore_duration=100),  # Ends 100
        Event(name="E2", lore_date=0, lore_duration=10),  # Ends 10
        Event(name="E3", lore_date=110, lore_duration=10),  # Starts 110
    ]

    # Needs to match widget's scale factor for accurate visual calculation
    # Default is 20.0
    # Visual duration = duration * 20. E1=2000px, E2=200px.
    # E1 visual end = 100 + epsilon.
    # E3 start = 110.
    # Gap is small (15px / 20 = 0.75).
    # So E1 ends (time) around 100.75. E3 starts 110. Fits!

    widget.set_events(events)

    items = [i for i in widget.view.scene.items() if isinstance(i, EventItem)]
    items.sort(key=lambda i: i.event.name)  # E1, E2, E3

    e1_y = items[0].y()
    e2_y = items[1].y()
    e3_y = items[2].y()

    assert e1_y != e2_y, "E1 and E2 overlap, must be different lanes"

    # E1 is first, should be Lane 0 (usually top)
    # E2 is second, Lane 1 (below E1)
    # E3 should reuse E1's lane (Lane 0) because of Gravity

    assert e3_y == e1_y, "E3 should fall to Lane 0 (Gravity), not Lane 1"
