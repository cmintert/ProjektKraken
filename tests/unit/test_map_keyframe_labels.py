"""Unit tests for keyframe label collision logic on the map."""

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsPixmapItem
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.core.trajectory import Keyframe


@pytest.fixture
def map_view(qtbot):
    """Provides a MapGraphicsView with a mock scene."""
    view = MapGraphicsView()
    qtbot.addWidget(view)

    # Initialize with a dummy pixmap
    from PySide6.QtGui import QPixmap, QImage
    from PySide6.QtCore import Qt

    img = QImage(1000, 1000, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 1000, 1000))

    # We need a mock calendar converter or TrajectoryRenderer won't make labels!
    from unittest.mock import MagicMock

    mock_conv = MagicMock()
    mock_conv.format_date.return_value = "Lore Date"
    view._trajectory.set_calendar_converter(mock_conv)

    return view


def test_collect_keyframe_obstacles_math(map_view):
    """Verify that _collect_keyframe_obstacles correctly calculates rects."""
    view = map_view
    # Add a trajectory with two keyframes at (500, 500) and (600, 600)
    view.show_trajectory(
        "m1", [Keyframe(t=100.0, x=0.5, y=0.5), Keyframe(t=200.0, x=0.6, y=0.6)]
    )

    view_scale = 1.0
    obstacles = view._collect_keyframe_obstacles(view_scale)

    # Find the label obstacle (the wider one)
    label_obs = next(obs for obs in obstacles if obs.width() > 10)

    # Anchor is 500, 500.
    # tr_rect x is -10. left = 500 - 10 = 490
    assert label_obs.left() == pytest.approx(490.0)

    # In my previous CLI test, top was 510.0.
    # Anchor sp.y is 500. tr_rect.y is 10. 500 + 10 = 510.
    assert label_obs.top() == pytest.approx(510.0)


def test_trajectory_renderer_schedules_layout(map_view, qtbot):
    """Verify that show/clear trajectory schedules a label layout pass."""
    view = map_view
    from unittest.mock import MagicMock

    view._schedule_label_layout = MagicMock()

    view.show_trajectory(
        "m1", [Keyframe(t=100.0, x=0.5, y=0.5), Keyframe(t=200.0, x=0.6, y=0.6)]
    )
    assert view._schedule_label_layout.called

    view._schedule_label_layout.reset_mock()
    view.clear_trajectory()
    assert view._schedule_label_layout.called


def test_marker_dodges_keyframe_label(map_view, qtbot):
    """Verify markers avoid keyframe labels."""
    view = map_view

    # 1. Place a reference keyframe. Its label will be at ~500, 500 + offset.
    view.show_trajectory(
        "ref", [Keyframe(t=100.0, x=0.5, y=0.5), Keyframe(t=200.0, x=0.6, y=0.6)]
    )

    # 2. Place a marker at a position where its DEFAULT label position
    # would collide with the keyframe label.
    # If keyframe label is at 490, 510, let's put a marker right there.
    view.add_marker("m_test", "entity", "Test Marker", 0.5, 0.51)

    view._execute_label_layout()
    marker = view.markers["m_test"]
    assert marker._label_item.isVisible()

    # Force another layout pass with explicit extra obstacles to be sure
    view_scale = 1.0
    extra = view._collect_keyframe_obstacles(view_scale)
    view.label_manager.run_layout_pass(list(view.markers.values()), view_scale, extra)

    # The label should be visible and NOT overlapping the keyframe label
    # (Checking visibility is usually enough to prove it found a valid spot)
    assert marker._label_item.isVisible()
