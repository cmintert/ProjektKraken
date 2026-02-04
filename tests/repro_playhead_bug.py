import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from src.core.events import Event
from src.gui.widgets.timeline import EventItem, TimelineWidget, PlayheadItem


@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])


@pytest.fixture
def timeline(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    return widget


def test_playhead_drag_does_not_move_selected_events(timeline, qtbot):
    """
    Test that dragging the playhead does NOT move selected events.
    This is the reproduction test for the reported bug.
    """
    # 1. Setup an event
    event_id = "test-event"
    initial_date = 100.0
    events = [
        Event(id=event_id, name="Test Event", lore_date=initial_date, type="generic")
    ]
    timeline.set_events(events)

    # 2. Get the event item and initial position
    items = [i for i in timeline.view.scene.items() if isinstance(i, EventItem)]
    assert len(items) == 1
    event_item = items[0]
    initial_x = event_item.x()

    # 3. Select the event
    event_item.setSelected(True)
    assert event_item.isSelected()

    # 4. Get the playhead item
    playhead = timeline.view._playhead
    assert isinstance(playhead, PlayheadItem)
    initial_playhead_x = playhead.x()

    # 5. Simulate dragging the playhead
    # We move the playhead by 50 units
    drag_distance = 50.0

    # We need to simulate the dragging through the scene/view interaction
    # to trigger the bug where selected items move together.
    # In QGraphicsScene, if you drag a movable item, all selected movable items move.

    # We'll simulate this by setting the position and letting the scene's
    # move logic (if any) play out, or by simulating mouse events.

    # Since we're in a unit test without a full event loop, we might need
    # to be careful. However, QGraphicsItem.setPos() on a selected item
    # doesn't automatically move other selected items unless it's done
    # via the scene's mouse interaction.

    # Let's try simulating the mouse interaction:
    playhead_pos = timeline.view.mapFromScene(QPointF(playhead.x(), 0))

    # Press on playhead
    qtbot.mousePress(timeline.view.viewport(), Qt.LeftButton, pos=playhead_pos)

    # Move mouse
    new_playhead_pos = QPointF(
        playhead_pos.x() + drag_distance, playhead_pos.y()
    ).toPoint()
    # qtbot.mouseMove doesn't always trigger the drag if not handled manually
    # but TimelineView handles some of this.

    # Try to use QPoint as qtbot might be picky
    qtbot.mouseMove(timeline.view.viewport(), pos=new_playhead_pos)
    qtbot.mouseRelease(timeline.view.viewport(), Qt.LeftButton, pos=new_playhead_pos)

    # 6. Verify playhead moved
    assert abs(playhead.x() - (initial_playhead_x + drag_distance)) < 1.0

    # 7. Verify event did NOT move
    # If the bug exists, event_item.x() will be initial_x + drag_distance
    assert event_item.x() == initial_x, "Event moved with playhead!"
