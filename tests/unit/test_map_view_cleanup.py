"""Tests for MapGraphicsView.cleanup() — M1 timer leak prevention.

Verifies that cleanup() stops the _layout_debounce_timer so it can't fire
on a partially-destroyed view, and that repeated calls are safe.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def _make_view(qtbot) -> MapGraphicsView:
    view = MapGraphicsView()
    qtbot.addWidget(view)
    img = QImage(50, 50, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    view.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
    view.graphics_scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 50, 50))
    return view


class TestMapGraphicsViewCleanup:

    def test_cleanup_method_exists(self, qtbot):
        """MapGraphicsView must expose a public cleanup() method."""
        view = _make_view(qtbot)
        assert hasattr(view, "cleanup"), "MapGraphicsView must have a cleanup() method"
        assert callable(view.cleanup)

    def test_cleanup_stops_debounce_timer(self, qtbot):
        """After cleanup(), _layout_debounce_timer must not be active."""
        view = _make_view(qtbot)

        # Arm the timer so it is running
        view._layout_debounce_timer.start(10_000)
        assert view._layout_debounce_timer.isActive()

        view.cleanup()

        assert not view._layout_debounce_timer.isActive(), (
            "cleanup() must stop the debounce timer"
        )

    def test_cleanup_is_idempotent(self, qtbot):
        """Calling cleanup() twice must not raise."""
        view = _make_view(qtbot)
        view.cleanup()
        view.cleanup()  # second call must not raise

    def test_cleanup_does_not_prevent_timer_restart(self, qtbot):
        """After cleanup() the timer can still be restarted (it's not deleted)."""
        view = _make_view(qtbot)
        view.cleanup()
        # Starting the timer again must not raise
        view._layout_debounce_timer.start(10_000)
        assert view._layout_debounce_timer.isActive()
        view._layout_debounce_timer.stop()
