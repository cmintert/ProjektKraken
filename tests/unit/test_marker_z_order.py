"""Unit tests for Marker Z-Order inheritance."""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from src.app.constants import MAP_LAYER_Z_MARKERS
from src.core.trajectory import Keyframe
from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def _setup_view_with_pixmap(
    qtbot, width: int = 200, height: int = 200
) -> MapGraphicsView:
    """Helper to create a MapGraphicsView with a known pixmap."""
    view = MapGraphicsView()
    qtbot.addWidget(view)

    test_image = QImage(width, height, QImage.Format.Format_RGB32)
    test_image.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(test_image)

    view.pixmap_item = QGraphicsPixmapItem(pixmap)
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, width, height))

    return view


@pytest.fixture
def map_graphics_view(qtbot):
    return _setup_view_with_pixmap(qtbot)


class TestMarkerZOrder:
    def test_trajectory_z_order_inherits_from_marker(self, map_graphics_view):
        """Test that trajectory keyframes sit at a fixed low layer below all markers."""
        view = map_graphics_view

        # 1. Add a marker
        marker_id = "test_marker_1"
        view._marker_manager.add_marker(
            marker_id=marker_id,
            object_type="entity",
            label="Test Entity",
            x=0.5,
            y=0.5,
        )

        # 2. Mock a custom Z-value for the marker (simulating dynamic layer model)
        custom_z = 25.0
        marker = view._marker_manager.find_item(marker_id)
        marker.setZValue(custom_z)

        # 3. Create dummy keyframes
        k1 = Keyframe(t=10.0, x=0.4, y=0.4)
        k2 = Keyframe(t=20.0, x=0.6, y=0.6)

        # 4. Show trajectory
        view._trajectory.show_trajectory(marker_id, [k1, k2])

        # 5. Verify Z-values
        # Trajectories should be at MAP_LAYER_Z_TRAJECTORIES base (0.5)
        # regardless of the marker's Z-value (25.0)
        base_z = 0.5

        # Trajectory path should be at base_z - 0.3
        assert view._trajectory.trajectory_path_item.zValue() == base_z - 0.3

        # Dots should be at base_z - 0.2
        for dot in view._trajectory.keyframe_items:
            assert dot.zValue() == base_z - 0.2

        # Labels should be at base_z - 0.1
        for label in view._trajectory.keyframe_label_items:
            assert label.zValue() == base_z - 0.1

    def test_trajectory_update_z_values(self, map_graphics_view):
        """Test that trajectory Z-values remain fixed even when marker Z changes."""
        view = map_graphics_view
        marker_id = "test_marker_2"

        view._marker_manager.add_marker(
            marker_id=marker_id,
            object_type="entity",
            label="Z Sync Entity",
            x=0.5,
            y=0.5,
        )

        k1 = Keyframe(t=10.0, x=0.4, y=0.4)
        k2 = Keyframe(t=20.0, x=0.6, y=0.6)
        view._trajectory.show_trajectory(marker_id, [k1, k2])

        # Change marker Z-value
        new_z = 42.0
        marker = view._marker_manager.find_item(marker_id)
        marker.setZValue(new_z)

        # Explicit update
        view._trajectory.update_z_values()

        # Verify Z-values remain at the fixed low layer (0.5)
        base_z = 0.5
        assert view._trajectory.trajectory_path_item.zValue() == base_z - 0.3
        assert view._trajectory.keyframe_items[0].zValue() == base_z - 0.2
