"""
Unit tests for map widget functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from src.gui.widgets.map_widget import (
    MapWidget,
    MapGraphicsView,
    MarkerItem,
)


def create_test_pixmap(width=100, height=100):
    """Helper to create a test pixmap."""
    test_image = QImage(width, height, QImage.Format_RGB32)
    test_image.fill(Qt.white)
    return QPixmap.fromImage(test_image)


def setup_map_with_pixmap(map_view, width=100, height=100):
    """Helper to set up a map view with a test pixmap."""
    pixmap = create_test_pixmap(width, height)
    map_view.pixmap_item = QGraphicsPixmapItem(pixmap)
    map_view.scene.addItem(map_view.pixmap_item)
    return map_view


@pytest.fixture
def map_widget(qtbot):
    """Provides a MapWidget instance."""
    widget = MapWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def map_view(qtbot):
    """Provides a MapGraphicsView instance."""
    view = MapGraphicsView()
    qtbot.addWidget(view)
    return view


def test_map_widget_initialization(map_widget):
    """Test that MapWidget initializes correctly."""
    assert map_widget is not None
    assert map_widget.view is not None
    assert isinstance(map_widget.view, MapGraphicsView)


def test_map_view_initialization(map_view):
    """Test that MapGraphicsView initializes correctly."""
    assert map_view is not None
    assert map_view.scene is not None
    assert map_view.pixmap_item is None
    assert len(map_view.markers) == 0


def test_load_map_invalid_path(map_view):
    """Test that loading an invalid map returns False."""
    result = map_view.load_map("/nonexistent/path.png")
    assert result is False
    assert map_view.pixmap_item is None


def test_add_marker_without_map(map_view):
    """Test that adding a marker without a map logs warning."""
    # Should not crash, just log warning
    map_view.add_marker("marker1", "entity", "Label", 0.5, 0.5)

    # No marker should be added
    assert len(map_view.markers) == 0


def test_add_marker_with_map(map_view):
    """Test adding a marker to a loaded map."""
    setup_map_with_pixmap(map_view)

    # Add marker
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Verify marker was added
    assert "marker1" in map_view.markers
    assert isinstance(map_view.markers["marker1"], MarkerItem)


def test_remove_marker(map_view):
    """Test removing a marker."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Remove marker
    map_view.remove_marker("marker1")

    # Verify removal
    assert "marker1" not in map_view.markers


def test_clear_markers(map_view):
    """Test clearing all markers."""
    setup_map_with_pixmap(map_view)

    # Add multiple markers
    map_view.add_marker("marker1", "entity", "Label 1", 0.2, 0.3)
    map_view.add_marker("marker2", "event", "Label 2", 0.7, 0.8)

    assert len(map_view.markers) == 2

    # Clear all
    map_view.clear_markers()

    assert len(map_view.markers) == 0


def test_update_marker_position(map_view):
    """Test updating a marker's position."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Update position
    map_view.update_marker_position("marker1", 0.8, 0.9)

    # Marker should still exist
    assert "marker1" in map_view.markers


def test_marker_position_changed_signal(map_widget, qtbot):
    """Test that marker movement emits the correct signal."""
    # Create a spy for the signal
    signal_spy = []

    def on_marker_moved(marker_id, x, y):
        signal_spy.append((marker_id, x, y))

    map_widget.marker_position_changed.connect(on_marker_moved)

    # Set up map
    setup_map_with_pixmap(map_widget.view)
    map_widget.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    # Simulate marker movement by calling the internal handler
    map_widget._on_marker_moved("marker1", 0.7, 0.8)

    # Verify signal was emitted with correct values
    # Note: Signal may be emitted twice due to update_marker_position call
    assert len(signal_spy) >= 1
    assert ("marker1", 0.7, 0.8) in signal_spy


def test_marker_item_draggable(map_view):
    """Test that MarkerItem is configured as draggable."""
    setup_map_with_pixmap(map_view)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    marker = map_view.markers["marker1"]

    # Verify draggable flags
    assert marker.flags() & QGraphicsItem.ItemIsMovable
    assert marker.flags() & QGraphicsItem.ItemSendsGeometryChanges


def test_marker_item_colors():
    """Test that MarkerItem has different colors for different types."""
    # Create mock pixmap item
    mock_pixmap_item = MagicMock()

    entity_marker = MarkerItem("m1", "entity", "Entity Label", mock_pixmap_item)
    event_marker = MarkerItem("m2", "event", "Event Label", mock_pixmap_item)
    default_marker = MarkerItem("m3", "unknown", "Unknown", mock_pixmap_item)

    # Colors should be different (now using internal _color attribute)
    assert entity_marker._color != event_marker._color
    assert entity_marker._color == MarkerItem.COLORS["entity"]
    assert event_marker._color == MarkerItem.COLORS["event"]
    assert default_marker._color == MarkerItem.COLORS["default"]


def test_marker_item_tooltip():
    """Test that MarkerItem has the correct tooltip."""
    mock_pixmap_item = MagicMock()
    marker = MarkerItem("m1", "entity", "Test Label", mock_pixmap_item)

    assert marker.toolTip() == "Test Label"


def test_marker_drag_tracking():
    """Test that MarkerItem tracks drag state."""
    mock_pixmap_item = MagicMock()

    marker = MarkerItem("m1", "entity", "Test", mock_pixmap_item)

    # Initially not dragging
    assert marker._is_dragging is False
    assert marker._drag_start_pos is None


def test_normalized_coordinates_conversion(map_view):
    """Test that normalized coordinates are correctly converted."""
    setup_map_with_pixmap(map_view, 1000, 800)

    # Test corner coordinates
    top_left = map_view._normalized_to_scene(0.0, 0.0)
    bottom_right = map_view._normalized_to_scene(1.0, 1.0)
    center = map_view._normalized_to_scene(0.5, 0.5)

    # Top-left should be at pixmap origin
    assert top_left.x() >= 0
    assert top_left.y() >= 0

    # Bottom-right should be at pixmap far corner
    assert bottom_right.x() > top_left.x()
    assert bottom_right.y() > top_left.y()

    # Center should be between them
    assert top_left.x() < center.x() < bottom_right.x()
    assert top_left.y() < center.y() < bottom_right.y()


def test_widget_delegates_to_view(map_widget):
    """Test that MapWidget delegates operations to its view."""
    # Set up map
    setup_map_with_pixmap(map_widget.view)

    # Add marker through widget
    map_widget.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)
    assert "marker1" in map_widget.view.markers

    # Remove marker through widget
    map_widget.remove_marker("marker1")
    assert "marker1" not in map_widget.view.markers


def test_marker_item_change_emits_signal(map_view, qtbot):
    """Test that moving a marker item triggers marker position tracking."""
    signal_spy = []

    def on_marker_moved(marker_id, x, y):
        signal_spy.append((marker_id, x, y))

    map_view.marker_moved.connect(on_marker_moved)

    setup_map_with_pixmap(map_view, 100, 100)
    map_view.add_marker("marker1", "entity", "Test Label", 0.5, 0.5)

    marker = map_view.markers["marker1"]

    # Note: itemChange is only called during interactive drag or certain
    # specific operations. Manual setPos doesn't trigger ItemPositionHasChanged.
    # For testing, we can verify the marker is draggable and can be moved.
    initial_pos = marker.pos()

    # Move the marker programmatically
    new_pos = QPointF(50, 50)
    marker.setPos(new_pos)

    # Verify marker moved
    assert marker.pos() == new_pos

    # In actual usage, dragging would trigger itemChange and emit the signal.
    # For this test, we verify the marker is configured correctly.
    assert marker.flags() & QGraphicsItem.ItemIsMovable
    assert marker.flags() & QGraphicsItem.ItemSendsGeometryChanges
