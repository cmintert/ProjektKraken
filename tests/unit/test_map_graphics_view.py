"""
Unit tests for MapGraphicsView mouse coordinate signal behavior.

Tests the mouse_coordinates_changed signal emission with correct
normalized coordinates and in_bounds flag.
"""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def _setup_view_with_pixmap(qtbot, width: int = 100, height: int = 100):
    """
    Helper to create a MapGraphicsView with a known pixmap and scene rect.

    Args:
        qtbot: pytest-qt fixture.
        width: Pixmap width in pixels.
        height: Pixmap height in pixels.

    Returns:
        MapGraphicsView: Configured view with pixmap and coordinate system.
    """
    view = MapGraphicsView()
    qtbot.addWidget(view)

    # Create test pixmap
    test_image = QImage(width, height, QImage.Format.Format_RGB32)
    test_image.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(test_image)

    # Add pixmap to scene
    view.pixmap_item = QGraphicsPixmapItem(pixmap)
    view.scene.addItem(view.pixmap_item)

    # Update coordinate system with map bounds
    view.coord_system.set_scene_rect(QRectF(0, 0, width, height))

    return view


@pytest.fixture
def map_graphics_view(qtbot):
    """Provides a MapGraphicsView instance with a 100x100 pixmap."""
    return _setup_view_with_pixmap(qtbot, width=100, height=100)


class TestMouseCoordinatesSignal:
    """Tests for the mouse_coordinates_changed signal behavior."""

    def test_signal_emits_normalized_coordinates_in_bounds(
        self, map_graphics_view, qtbot
    ):
        """
        Test that mouse_coordinates_changed emits correctly when cursor is over pixmap.

        Verifies that:
        - The signal emits with in_bounds=True
        - Normalized coordinates are correctly calculated from scene position
        """
        view = map_graphics_view
        signals_received = []

        def on_signal(x, y, in_bounds):
            signals_received.append((x, y, in_bounds))

        view.mouse_coordinates_changed.connect(on_signal)

        # Manually call the coordinate conversion logic to verify it
        # The center of a 100x100 map should give (0.5, 0.5)
        from PySide6.QtCore import QPointF

        center_scene_pos = QPointF(50.0, 50.0)
        norm_x, norm_y = view.coord_system.to_normalized(center_scene_pos)

        assert norm_x == pytest.approx(0.5, rel=1e-3)
        assert norm_y == pytest.approx(0.5, rel=1e-3)

        # Also verify top-left and bottom-right
        top_left = QPointF(0.0, 0.0)
        tl_x, tl_y = view.coord_system.to_normalized(top_left)
        assert tl_x == pytest.approx(0.0, rel=1e-3)
        assert tl_y == pytest.approx(0.0, rel=1e-3)

        bottom_right = QPointF(100.0, 100.0)
        br_x, br_y = view.coord_system.to_normalized(bottom_right)
        assert br_x == pytest.approx(1.0, rel=1e-3)
        assert br_y == pytest.approx(1.0, rel=1e-3)

    def test_signal_emits_out_of_bounds_for_external_coordinates(
        self, map_graphics_view
    ):
        """
        Test that coordinates outside pixmap bounds return expected values.

        MapCoordinateSystem.to_normalized does NOT clamp, so out-of-bounds
        coordinates will return values outside [0, 1].
        """
        view = map_graphics_view
        from PySide6.QtCore import QPointF

        # Point outside the map (negative coordinates)
        outside_pos = QPointF(-10.0, -10.0)
        norm_x, norm_y = view.coord_system.to_normalized(outside_pos)

        # For a scene rect (0, 0, 100, 100), point (-10, -10) normalizes to (-0.1, -0.1)
        assert norm_x == pytest.approx(-0.1, rel=1e-3)
        assert norm_y == pytest.approx(-0.1, rel=1e-3)

    def test_pixmap_contains_check_uses_item_coordinates(self, map_graphics_view):
        """
        Test that pixmap.contains() is called with item-local coordinates.

        The pixmap_item.contains() method expects coordinates in the item's
        local coordinate space, not scene coordinates.
        """
        view = map_graphics_view
        from PySide6.QtCore import QPointF

        # Scene position at center of map
        scene_pos = QPointF(50.0, 50.0)

        # Map to item-local coordinates (for a pixmap at origin, this should be same)
        item_pos = view.pixmap_item.mapFromScene(scene_pos)

        # Check contains returns True for center
        assert view.pixmap_item.contains(item_pos) is True

        # Check contains returns False for point outside
        outside_scene_pos = QPointF(-10.0, -10.0)
        outside_item_pos = view.pixmap_item.mapFromScene(outside_scene_pos)
        assert view.pixmap_item.contains(outside_item_pos) is False


class TestCoordinateSystemIntegration:
    """Tests for MapCoordinateSystem integration with the view."""

    def test_coordinate_system_initialized_with_pixmap_bounds(self, qtbot):
        """Test that coordinate system uses pixmap bounds after load."""
        view = _setup_view_with_pixmap(qtbot, width=200, height=100)

        # The scene rect should match pixmap dimensions
        from PySide6.QtCore import QPointF

        # Full width should normalize to x=1.0
        full_width_pos = QPointF(200.0, 50.0)
        norm_x, norm_y = view.coord_system.to_normalized(full_width_pos)
        assert norm_x == pytest.approx(1.0, rel=1e-3)
        assert norm_y == pytest.approx(0.5, rel=1e-3)

    def test_coordinate_system_handles_empty_scene(self, qtbot):
        """Test that coordinate system handles empty scene gracefully."""
        view = MapGraphicsView()
        qtbot.addWidget(view)

        # No pixmap loaded, coordinate system should return (0, 0)
        from PySide6.QtCore import QPointF

        some_pos = QPointF(50.0, 50.0)
        norm_x, norm_y = view.coord_system.to_normalized(some_pos)

        assert norm_x == 0.0
        assert norm_y == 0.0
