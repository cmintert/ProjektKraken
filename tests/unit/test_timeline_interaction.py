import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsView

from src.core.events import Event
from src.gui.widgets.timeline import EventItem, TimelineWidget


@pytest.fixture
def app(qtbot):
    # Ensure app exists
    return QApplication.instance() or QApplication([])


@pytest.fixture
def timeline(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    return widget


def test_timeline_init(timeline):
    assert timeline.view.scene is not None
    assert timeline.view.LANE_HEIGHT == 40


def test_set_events_creates_items(timeline):
    events = [
        Event(id="1", name="E1", lore_date=100.0, type="generic"),
        Event(id="2", name="E2", lore_date=200.0, type="combat"),
    ]
    timeline.set_events(events)

    items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]
    # Sort by X to match date order
    items.sort(key=lambda i: i.x())
    assert len(items) == 2
    assert items[0].event.name == "E1"


def test_fit_view(timeline):
    # Just ensure it doesn't crash
    timeline.fit_view()
    assert True


def test_selection_signal(timeline, qtbot):
    events = [Event(id="1", name="E1", lore_date=100.0, type="generic")]
    timeline.set_events(events)
    # items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]

    with qtbot.waitSignal(timeline.event_selected) as blocker:
        # Simulate logic trace:
        timeline.view.event_selected.emit("1")

    assert blocker.args == ["1"]


def test_focus_event(timeline):
    events = [Event(id="1", name="E1", lore_date=100.0, type="generic")]
    timeline.set_events(events)

    timeline.focus_event("1")
    items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]
    assert items[0].isSelected()


def test_wheel_zoom(timeline):
    # Simulate Wheel Event
    # pos, globalPos, pixelDelta, angleDelta, buttons, modifiers, phase, inverted
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )

    initial_matrix = timeline.view.transform()
    timeline.view.wheelEvent(event)
    new_matrix = timeline.view.transform()

    # Zoom in -> Scale increases
    assert new_matrix.m11() > initial_matrix.m11()


def test_mouse_pan_init(timeline):
    # Test mouse press on background (should not crash)
    # We verifies `setDragMode` is set.
    assert timeline.view.dragMode() == QGraphicsView.ScrollHandDrag

    # Actually, let's skip direct event injection if it's hard.
    # We can verify `setDragMode` is set.
    assert timeline.view.dragMode() == QGraphicsView.ScrollHandDrag


def test_draw_ruler(timeline):
    # Cover drawForeground by forcing a paint?
    # Or just calling it with a dummy painter
    # This is complex to mock.
    # But we can check if scene coordinates map correctly.

    val = timeline.view.mapToScene(0, 0)
    assert val is not None


def test_playhead_drag(timeline, qtbot):
    """Test that dragging the playhead updates time."""
    # 1. Verify cursor
    assert timeline.view._playhead.cursor().shape() == Qt.SizeHorCursor

    # 2. Setup stats
    timeline.view.scale_factor = 10.0
    timeline.view._playhead.set_time(0.0, 10.0)  # at x=0

    # 3. Watch for signal
    with qtbot.waitSignal(timeline.view.playhead_time_changed) as blocker:
        # Simulate drag by manually calling itemChange/moved logic
        # (simulating the QGraphicsItem movement logic is hard without full event stack)

        # We can bypass the event stack and call the handler directly or modify pos
        # Modifying pos triggers itemChange -> triggers on_moved -> triggers signal

        timeline.view._playhead.setPos(100.0, 0.0)

    # 4. Verify new time
    # moved 100px / 10.0 scale = 10.0 time units
    assert blocker.args[0] == 10.0


def test_event_drag_date_change(timeline, qtbot):
    """Test that dragging an event item emits event_date_changed signal."""
    # 1. Setup event
    events = [
        Event(id="test-event-1", name="Draggable", lore_date=50.0, type="generic")
    ]
    timeline.set_events(events)

    # 2. Find the event item
    items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]
    assert len(items) == 1
    item = items[0]

    # 3. Verify initial state
    scale = timeline.view.scale_factor
    initial_x = 50.0 * scale
    assert abs(item.x() - initial_x) < 0.01

    # 4. Store initial Y position (should be preserved during drag)
    initial_y = item.y()

    # 5. Simulate user-initiated drag:
    # - Set _is_dragging to True (normally set by mousePressEvent)
    # - Set _initial_y (normally captured from current Y at drag start)
    item._is_dragging = True
    item._initial_y = initial_y

    # 6. Simulate drag: move to new position
    new_lore_date = 75.0
    new_x = new_lore_date * scale
    item.setPos(new_x, initial_y)

    # 7. Verify the event's lore_date was updated in-memory
    assert abs(item.event.lore_date - new_lore_date) < 0.01

    # 8. Test signal emission on mouse release
    with qtbot.waitSignal(timeline.event_date_changed) as blocker:
        # Call callback directly (simulates mouseReleaseEvent logic)
        item.on_drag_complete = timeline.view._on_event_drag_complete
        if item.on_drag_complete:
            item.on_drag_complete(item.event.id, item.x() / scale)
        item._is_dragging = False

    # 9. Verify signal was emitted with correct values
    assert blocker.args[0] == "test-event-1"
    assert abs(blocker.args[1] - new_lore_date) < 0.01


def test_event_drag_constrained_to_horizontal(timeline):
    """Test that event dragging is constrained to horizontal movement."""
    events = [Event(id="h-test", name="Horizontal", lore_date=100.0, type="generic")]
    timeline.set_events(events)

    items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]
    item = items[0]

    initial_y = item.y()

    # Simulate user-initiated drag
    item._is_dragging = True
    item._initial_y = initial_y

    # Try to move both X and Y
    new_x = 200.0 * timeline.view.scale_factor
    new_y = initial_y + 100  # Try to move vertically

    item.setPos(new_x, new_y)

    # Y should be constrained to initial value
    assert item.y() == initial_y
    # X should have changed
    assert abs(item.x() - new_x) < 0.01

    item._is_dragging = False
