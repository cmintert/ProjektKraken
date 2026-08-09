"""Tests for the direct spatial trajectory edit overlay."""

from PySide6.QtCore import QRectF

from src.core.trajectory import (
    SEGMENT_MODE_STEP,
    Keyframe,
    TrajectoryDistanceContext,
)
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


def test_relocation_uses_broken_connector_and_disables_midpoint(qtbot, monkeypatch):
    view = _view(qtbot, monkeypatch)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.8, y=0.7),
        ],
    )
    destination_id = session.working_keyframes[1].edit_id
    session.select_keyframe(destination_id)
    session.set_arrival_mode(destination_id, SEGMENT_MODE_STEP)

    view.trajectory_edit_overlay.show(session.to_snapshot())

    assert len(view.trajectory_edit_overlay._relocation_path_items) == 1
    assert not view.trajectory_edit_overlay.midpoint_handles[0].isEnabled()
    assert (
        "relocation"
        in view.trajectory_edit_overlay.midpoint_handles[0].toolTip().lower()
    )


def test_date_edit_highlights_adjacent_affected_segments(qtbot, monkeypatch):
    view = _view(qtbot, monkeypatch)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.5, y=0.6),
            Keyframe(t=20.0, x=0.9, y=0.8),
        ],
    )
    middle_id = session.working_keyframes[1].edit_id
    session.begin_date_edit(middle_id)

    view.trajectory_edit_overlay.show(session.to_snapshot())

    temporal_path = view.trajectory_edit_overlay.temporal_path_item
    assert temporal_path is not None
    assert not temporal_path.path().isEmpty()


def test_temporal_highlight_is_removed_after_date_edit_finishes(
    qtbot, monkeypatch
):
    view = _view(qtbot, monkeypatch)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.5, y=0.6),
        ],
    )
    edit_id = session.working_keyframes[0].edit_id
    session.begin_date_edit(edit_id)
    view.trajectory_edit_overlay.show(session.to_snapshot())
    session.finish_date_edit()

    view.trajectory_edit_overlay.show(session.to_snapshot())

    assert view.trajectory_edit_overlay.temporal_path_item is None


def test_speed_anchor_remains_visibly_marked_when_selection_moves(
    qtbot, monkeypatch
):
    view = _view(qtbot, monkeypatch)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=12.0, x=0.25, y=0.0),
            Keyframe(t=20.0, x=1.0, y=0.0),
        ],
    )
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    session.set_speed_anchor(start_id)
    session.select_keyframe(end_id)

    view.trajectory_edit_overlay.show(session.to_snapshot())

    start_handle = view.trajectory_edit_overlay.keyframe_handles[0]
    assert start_handle.pen().widthF() == 3.0
    assert "Speed start anchor" in start_handle.toolTip()


def test_equalization_preview_highlights_range_and_locks_handles(
    qtbot, monkeypatch
):
    view = _view(qtbot, monkeypatch)
    session = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=12.0, x=0.25, y=0.0),
            Keyframe(t=20.0, x=1.0, y=0.0),
        ],
    )
    session.set_speed_anchor(session.working_keyframes[0].edit_id)
    session.preview_speed_equalization(
        session.working_keyframes[-1].edit_id,
        TrajectoryDistanceContext(1.0, 1.0),
    )

    view.trajectory_edit_overlay.show(session.to_snapshot())

    temporal_path = view.trajectory_edit_overlay.temporal_path_item
    assert temporal_path is not None
    assert not temporal_path.path().isEmpty()
    assert all(
        not handle.isEnabled()
        for handle in view.trajectory_edit_overlay.keyframe_handles
    )
    assert all(
        not handle.isEnabled()
        for handle in view.trajectory_edit_overlay.midpoint_handles
    )
