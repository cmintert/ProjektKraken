"""Tests for the direct spatial trajectory edit overlay."""

from PySide6.QtCore import QRectF

from src.core.trajectory import Keyframe
from src.core.trajectory_edit import TrajectoryEditSession
from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def _view(qtbot, monkeypatch) -> MapGraphicsView:
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    view = MapGraphicsView()
    qtbot.addWidget(view)
    view.coord_system.set_scene_rect(QRectF(0.0, 0.0, 100.0, 100.0))
    return view


def _snapshot():
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.5, y=0.6),
            Keyframe(t=20.0, x=0.9, y=0.8),
        ],
        playhead=5.0,
    )
    return session.to_snapshot()


def test_overlay_creates_one_handle_per_keyframe_and_segment(qtbot, monkeypatch):
    view = _view(qtbot, monkeypatch)

    view.trajectory_edit_overlay.show(_snapshot())

    assert len(view.trajectory_edit_overlay.keyframe_handles) == 3
    assert len(view.trajectory_edit_overlay.midpoint_handles) == 2


def test_normal_renderer_keyframes_are_passive(qtbot, monkeypatch):
    view = _view(qtbot, monkeypatch)

    view.show_trajectory(
        "marker-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.9, y=0.8),
        ],
    )

    assert len(view.keyframe_items) == 2
    assert all(not item.interactive for item in view.keyframe_items)
    assert all(
        not item.flags() & item.GraphicsItemFlag.ItemIsMovable
        for item in view.keyframe_items
    )


def test_equal_time_segment_disables_midpoint(qtbot, monkeypatch):
    view = _view(qtbot, monkeypatch)
    snapshot = _snapshot()
    start = snapshot["keyframes"][0]["edit_id"]
    end = snapshot["keyframes"][1]["edit_id"]
    snapshot["midpoint_errors"] = {f"{start}:{end}": "Dates must differ."}

    view.trajectory_edit_overlay.show(snapshot)

    assert not view.trajectory_edit_overlay.midpoint_handles[0].isEnabled()
    assert "Dates must differ" in view.trajectory_edit_overlay.midpoint_handles[
        0
    ].toolTip()
