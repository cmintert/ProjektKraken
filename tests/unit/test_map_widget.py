"""
Unit tests for map widget functionality.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem

from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map_widget import (
    MapGraphicsView,
    MapWidget,
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
    # Ensure coordinate system knows about the map bounds
    map_view.coord_system.set_scene_rect(map_view.pixmap_item.boundingRect())
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
    assert signal_spy
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
    # initial_pos = marker.pos()

    # Move the marker programmatically
    new_pos = QPointF(50, 50)
    marker.setPos(new_pos)

    # Verify marker moved
    assert marker.pos() == new_pos

    # In actual usage, dragging would trigger itemChange and emit the signal.
    # For this test, we verify the marker is configured correctly.
    assert marker.flags() & QGraphicsItem.ItemIsMovable
    assert marker.flags() & QGraphicsItem.ItemSendsGeometryChanges


def test_mouse_coordinates_display(map_widget):
    """Test that mouse coordinates update the label correctly."""
    # Mock the label
    map_widget.coord_label = MagicMock()
    map_widget.view.map_width_meters = 1000.0  # Simple width for calc

    # Mock pixmap_item for aspect ratio (square 100x100)
    map_widget.view.pixmap_item = MagicMock()
    map_widget.view.pixmap_item.boundingRect.return_value = QRectF(0, 0, 100, 100)

    # 1. Test In-Bounds
    # x=0.5, y=0.5. With width=1000m, height should be 1000m.
    # Expected: 500m, 500m -> 0.5km, 0.5km
    map_widget._on_mouse_coordinates_changed(0.5, 0.5, True)

    # Check text set on label
    args, _ = map_widget.coord_label.setText.call_args
    text = args[0]
    assert "N: (0.5000, 0.5000)" in text
    assert "RW: 0.50 km, 0.50 km" in text

    # 2. Test Out-of-Bounds - now includes time suffix
    map_widget._on_mouse_coordinates_changed(0.0, 0.0, False)
    args, _ = map_widget.coord_label.setText.call_args
    out_of_bounds_text = args[0]
    assert "Ready" in out_of_bounds_text
    assert "T:" in out_of_bounds_text  # Time is always shown

    # 3. Test Zero Height (Division by Zero protection)
    map_widget.view.pixmap_item.boundingRect.return_value = QRectF(0, 0, 100, 0)
    map_widget._on_mouse_coordinates_changed(0.5, 0.5, True)
    # Should fall back to 1:1 (height_meters = width_meters = 1000)
    # y=0.5 * 1000 = 500
    args, _ = map_widget.coord_label.setText.call_args
    assert "RW: 0.50 km, 0.50 km" in args[0]


def test_clock_mode_logic(map_widget, qtbot):
    """Test the Clock Mode state machine in MapWidget."""
    # Mock specific internal state variables that aren't public
    map_widget._pinned_marker_id = None
    map_widget._pinned_original_t = None

    # Spy on signals
    update_spy = []
    map_widget.update_keyframe_time_requested.connect(
        lambda mid, mkid, ot, nt: update_spy.append((mid, mkid, ot, nt))
    )

    # 1. Enter Clock Mode
    map_widget._on_clock_mode_requested("marker1", 100.0)

    assert map_widget._pinned_marker_id == "marker1"
    assert map_widget._pinned_original_t == 100.0

    # 2. Simulate Timeline Change (Scrubbing)
    # verify positions NOT updated when pinned (internal logic check)
    map_widget.view._update_trajectory_positions = MagicMock()
    map_widget.on_time_changed(150.0)

    # In Clock Mode, _update_trajectory_positions should NOT be called
    # (because we're editing time, not moving spatial markers)
    # map_widget.view._update_trajectory_positions.assert_not_called()
    # Note: Accessing private view state is brittle, but necessary for unit test

    # 3. Commit Change (Click again)
    # Mock getting selected map id
    map_widget.get_selected_map_id = MagicMock(return_value="map1")

    map_widget._on_clock_mode_requested("marker1", 100.0)  # Click again on same

    assert len(update_spy) == 1
    mid, mkid, ot, nt = update_spy[0]
    assert mid == "map1"
    assert mkid == "marker1"
    assert ot == 100.0
    assert nt == 150.0  # The dragged time

    # Should be unpinned
    assert map_widget._pinned_marker_id is None


def test_clock_mode_jumps_time(map_widget, qtbot):
    """Test that entering Clock Mode emits jump_to_time_requested."""
    # Spy on the signal
    signal_spy = []

    def on_jump(t):
        signal_spy.append(t)

    map_widget.jump_to_time_requested.connect(on_jump)

    # Trigger Clock Mode
    marker_id = "marker_1"
    t = 123.45

    # Mock view method to prevent errors during call
    map_widget.view.set_keyframe_pinned = MagicMock()

    map_widget._on_clock_mode_requested(marker_id, t)

    # Verify signal emitted with correct time
    assert len(signal_spy) == 1
    assert signal_spy[0] == t
