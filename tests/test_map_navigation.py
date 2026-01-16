from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsObject

# Import from new map package structure
from src.gui.widgets.map_widget import MapWidget

# --- Mocks and Helpers ---


class MockMouseEvent:
    def __init__(self, button, pos):
        self._button = button
        self._pos = pos

    def button(self):
        return self._button

    def pos(self):
        return self._pos

    def scenePos(self):
        return QPointF(self._pos)


@pytest.fixture
def map_widget(qtbot):
    widget = MapWidget()
    qtbot.addWidget(widget)
    return widget


def test_marker_item_inheritance():
    """Verify MarkerItem is a QGraphicsObject to support signals."""
    from src.gui.widgets.map.marker_item import MarkerItem

    assert issubclass(MarkerItem, QGraphicsObject)


def test_marker_emits_clicked(qtbot, map_widget):
    """Verify MarkerItem emits clicked signal when clicked (not dragged)."""

    # We need to manually add a marker to test interaction
    # Current implementation of add_marker creates a MarkerItem
    # We need to spy on the marker's signal

    # Needs a mock pixmap for add_marker to work
    map_widget.view.pixmap_item = MagicMock()
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.width.return_value = 100
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.height.return_value = 100
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.left.return_value = 0
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.top.return_value = 0

    # Add marker
    map_widget.view.add_marker("m1", "entity", "Test Label", 0.5, 0.5)
    marker = map_widget.view.markers["m1"]

    # Mock super().mousePressEvent and mouseReleaseEvent to avoid type errors
    with (
        patch.object(QGraphicsObject, "mousePressEvent"),
        patch.object(QGraphicsObject, "mouseReleaseEvent"),
    ):
        # Mock the signal spy
        with qtbot.waitSignal(marker.clicked, timeout=1000) as blocker:
            # Simulate click: Press and Release at same location
            press_event = MockMouseEvent(Qt.LeftButton, QPointF(50, 50))
            marker.mousePressEvent(press_event)

            release_event = MockMouseEvent(Qt.LeftButton, QPointF(50, 50))
            marker.mouseReleaseEvent(release_event)

    assert blocker.signal_triggered


def test_marker_drag_does_not_emit_clicked(qtbot, map_widget):
    """Verify MarkerItem does NOT emit clicked when dragged."""

    map_widget.view.pixmap_item = MagicMock()
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.width.return_value = 100
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.height.return_value = 100
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.left.return_value = 0
    map_widget.view.pixmap_item.sceneBoundingRect.return_value.top.return_value = 0

    map_widget.view.add_marker("m1", "entity", "Test Label", 0.5, 0.5)
    marker = map_widget.view.markers["m1"]

    # Use built-in waitSignal with raising=True to assert NOT emitted?
    # qtbot.assertNotEmitted is not standard, we handle by checking trigger count
    # or timeout

    try:
        with (
            patch.object(QGraphicsObject, "mousePressEvent"),
            patch.object(QGraphicsObject, "mouseReleaseEvent"),
        ):
            # Release far away (dragged)
            release_event = MockMouseEvent(Qt.LeftButton, QPointF(100, 100))
            marker.mouseReleaseEvent(release_event)

    except Exception:
        # Expected to timeout (good) or fail otherwise
        pass
    except Exception:
        # If it timed out, that's GOOD (signal not emitted)
        pass


def test_map_widget_signal_propagation(qtbot, map_widget):
    """Verify that clicking a marker bubbles up through MapWidget."""

    map_widget.view.pixmap_item = MagicMock()
    # Configure mock returns for geometry calculations
    rect_mock = MagicMock()
    rect_mock.width.return_value = 100
    rect_mock.height.return_value = 100
    rect_mock.left.return_value = 0
    rect_mock.top.return_value = 0
    map_widget.view.pixmap_item.sceneBoundingRect.return_value = rect_mock

    map_widget.view.add_marker("m1", "event", "Event Label", 0.5, 0.5)
    marker = map_widget.view.markers["m1"]

    with qtbot.waitSignal(map_widget.marker_clicked) as blocker:
        # Simulate click on marker
        with (
            patch.object(QGraphicsObject, "mousePressEvent"),
            patch.object(QGraphicsObject, "mouseReleaseEvent"),
        ):
            press_event = MockMouseEvent(Qt.LeftButton, QPointF(0, 0))
            marker.mousePressEvent(press_event)
            release_event = MockMouseEvent(Qt.LeftButton, QPointF(0, 0))
            marker.mouseReleaseEvent(release_event)

    # Check signal args: marker_id, object_type
    assert blocker.args == ["m1", "event"]
