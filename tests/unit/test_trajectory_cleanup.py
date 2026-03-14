"""Tests for TrajectoryRenderer.cleanup() — M13 animation safety.

Verifies that cleanup() stops all running QPropertyAnimations so they
cannot fire callbacks on a destroyed or partially-torn-down renderer.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.trajectory_renderer import TrajectoryRenderer


def _make_view(qtbot) -> MapGraphicsView:
    view = MapGraphicsView()
    qtbot.addWidget(view)
    img = QImage(50, 50, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 50, 50))
    return view


class TestTrajectoryRendererCleanup:

    def test_cleanup_method_exists(self, qtbot):
        """TrajectoryRenderer must expose a public cleanup() method."""
        view = _make_view(qtbot)
        renderer = view._trajectory
        assert hasattr(renderer, "cleanup")
        assert callable(renderer.cleanup)

    def test_cleanup_stops_all_mock_animations(self, qtbot):
        """cleanup() must call stop() on every animation and clear the list."""
        view = _make_view(qtbot)
        renderer = TrajectoryRenderer(view)

        # Inject mock animations directly into the renderer
        mock_anim1 = MagicMock(spec=QPropertyAnimation)
        mock_anim2 = MagicMock(spec=QPropertyAnimation)
        renderer._animations.extend([mock_anim1, mock_anim2])

        renderer.cleanup()

        mock_anim1.stop.assert_called_once()
        mock_anim2.stop.assert_called_once()
        assert len(renderer._animations) == 0

    def test_cleanup_is_idempotent(self, qtbot):
        """Calling cleanup() twice must not raise."""
        view = _make_view(qtbot)
        renderer = view._trajectory
        renderer.cleanup()
        renderer.cleanup()  # must not raise

    def test_cleanup_clears_empty_animations_list(self, qtbot):
        """cleanup() on a renderer with no active animations must not raise."""
        view = _make_view(qtbot)
        renderer = TrajectoryRenderer(view)
        assert len(renderer._animations) == 0
        renderer.cleanup()  # must not raise
        assert len(renderer._animations) == 0

    def test_pulse_item_finished_removes_from_list(self, qtbot):
        """When an animation created by _pulse_item finishes, it gets removed
        from _animations without raising — tests that the signal handler is
        robust and doesn't use a stale lambda that breaks after cleanup().
        """
        view = _make_view(qtbot)
        renderer = TrajectoryRenderer(view)

        # Inject a mock animation into _animations (mimics a running animation)
        mock_anim = MagicMock(spec=QPropertyAnimation)

        # Call the internal removal helper directly
        renderer._animations.append(mock_anim)
        renderer._on_animation_finished(mock_anim)

        assert mock_anim not in renderer._animations

