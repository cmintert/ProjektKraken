"""Unit tests for keyframe labels included in LabelManager layout."""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.core.trajectory import Keyframe
from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem


@pytest.fixture
def label_manager():
    """Provides a fresh LabelManager instance."""
    return LabelManager()


@pytest.fixture
def mock_pixmap_item(qapp):
    """Provides a mock pixmap item for markers."""
    return QGraphicsPixmapItem()


def _make_marker(
    pixmap_item, marker_id="m1", label="Test", connection_count=0
):
    """Helper to create a MarkerItem with a given connection_count."""
    marker = MarkerItem(
        marker_id=marker_id,
        object_type="entity",
        label=label,
        pixmap_item=pixmap_item,
    )
    marker.connection_count = connection_count
    return marker


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


class TestExtraObstacles:
    """Tests for extra_obstacles parameter in run_layout_pass."""

    def test_extra_obstacles_registered(self, label_manager):
        """Extra obstacles are registered as occupied rects."""
        obstacles = [QRectF(10, 10, 50, 20)]
        label_manager.run_layout_pass([], 1.0, extra_obstacles=obstacles)
        assert len(label_manager._occupied_rects) == 1
        assert label_manager._occupied_rects[0] == QRectF(10, 10, 50, 20)

    def test_extra_obstacles_none_by_default(self, label_manager):
        """Passing no extra_obstacles behaves the same as before."""
        label_manager.run_layout_pass([], 1.0)
        assert label_manager._occupied_rects == []

    def test_extra_obstacles_block_label_placement(
        self, label_manager, mock_pixmap_item
    ):
        """A marker label should avoid overlapping extra obstacles."""
        marker = _make_marker(mock_pixmap_item)
        marker.setPos(100, 100)

        # First run without obstacles: label is visible at some position.
        label_manager.run_layout_pass([marker], 1.0)
        assert marker._label_item.isVisible() is True

        # Now place large obstacles covering all 8 candidate slots.
        big_obstacle = QRectF(50, 50, 200, 200)
        label_manager.run_layout_pass(
            [marker], 1.0, extra_obstacles=[big_obstacle]
        )
        # The label should be hidden since the obstacle covers the area.
        assert marker._label_item.isVisible() is False

    def test_extra_obstacles_cleared_between_passes(
        self, label_manager, mock_pixmap_item
    ):
        """Extra obstacles from a previous pass do not persist."""
        obstacles = [QRectF(10, 10, 50, 20)]
        label_manager.run_layout_pass([], 1.0, extra_obstacles=obstacles)
        assert len(label_manager._occupied_rects) == 1

        # Second pass without extra obstacles.
        label_manager.run_layout_pass([], 1.0)
        assert label_manager._occupied_rects == []

    def test_multiple_extra_obstacles(self, label_manager):
        """Multiple extra obstacles are all registered."""
        obstacles = [
            QRectF(0, 0, 20, 20),
            QRectF(50, 50, 30, 30),
            QRectF(100, 100, 10, 10),
        ]
        label_manager.run_layout_pass([], 1.0, extra_obstacles=obstacles)
        assert len(label_manager._occupied_rects) == 3


class TestCollectKeyframeObstacles:
    """Tests for _collect_keyframe_obstacles on MapGraphicsView."""

    def test_no_keyframes_returns_empty(self, qtbot):
        """Returns empty list when no trajectory is displayed."""
        view = _setup_view_with_pixmap(qtbot)
        obstacles = view._collect_keyframe_obstacles(1.0)
        assert obstacles == []

    def test_keyframes_produce_obstacles(self, qtbot):
        """Active keyframes produce obstacle rects."""
        view = _setup_view_with_pixmap(qtbot)

        marker_id = "kf_marker"
        view._marker_manager.add_marker(
            marker_id=marker_id,
            object_type="entity",
            label="KF Entity",
            x=0.5,
            y=0.5,
        )

        k1 = Keyframe(t=10.0, x=0.3, y=0.3)
        k2 = Keyframe(t=20.0, x=0.7, y=0.7)
        view._trajectory.show_trajectory(marker_id, [k1, k2])

        obstacles = view._collect_keyframe_obstacles(1.0)

        # 2 keyframe labels = 2 obstacles (dots are excluded per design)
        assert len(obstacles) == 2

    def test_zero_scale_handled(self, qtbot):
        """Zero view_scale does not cause division error."""
        view = _setup_view_with_pixmap(qtbot)

        marker_id = "kf_zero"
        view._marker_manager.add_marker(
            marker_id=marker_id,
            object_type="entity",
            label="Zero Scale",
            x=0.5,
            y=0.5,
        )

        k1 = Keyframe(t=10.0, x=0.3, y=0.3)
        k2 = Keyframe(t=20.0, x=0.7, y=0.7)
        view._trajectory.show_trajectory(marker_id, [k1, k2])

        # Should not raise ZeroDivisionError.
        obstacles = view._collect_keyframe_obstacles(0.0)
        assert len(obstacles) == 2
        # Verify dimensions are finite and non-negative.
        for rect in obstacles:
            assert rect.width() >= 0
            assert rect.height() >= 0

    def test_cleared_trajectory_produces_no_obstacles(self, qtbot):
        """After clearing trajectory, no keyframe obstacles remain."""
        view = _setup_view_with_pixmap(qtbot)

        marker_id = "kf_clear"
        view._marker_manager.add_marker(
            marker_id=marker_id,
            object_type="entity",
            label="Clear Test",
            x=0.5,
            y=0.5,
        )

        k1 = Keyframe(t=10.0, x=0.3, y=0.3)
        k2 = Keyframe(t=20.0, x=0.7, y=0.7)
        view._trajectory.show_trajectory(marker_id, [k1, k2])
        view._trajectory.clear_trajectory()

        obstacles = view._collect_keyframe_obstacles(1.0)
        assert obstacles == []
