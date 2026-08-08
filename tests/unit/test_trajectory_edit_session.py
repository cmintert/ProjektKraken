"""Tests for the GUI-independent trajectory edit session."""

import pytest

from src.core.trajectory import KEYFRAME_TIME_EPSILON, Keyframe
from src.core.trajectory_edit import TrajectoryEditSession


def _session() -> TrajectoryEditSession:
    return TrajectoryEditSession.create(
        map_id="map-1",
        marker_id="marker-1",
        trajectory_id="trajectory-1",
        keyframes=[
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=10.0, x=0.9, y=0.8),
        ],
        playhead=4.0,
    )


def test_session_snapshots_do_not_share_keyframe_instances() -> None:
    """Original and working values are independently reconstructed."""
    session = _session()

    assert session.original_keyframes[0] is not session.working_keyframes[0]
    assert session.original_keyframes[0].edit_id == session.working_keyframes[0].edit_id


def test_move_changes_only_position_and_marks_dirty() -> None:
    """Spatial dragging preserves time and stable selection identity."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id

    session.move_keyframe(edit_id, 0.3, 0.4)

    assert session.working_keyframes[0].t == 0.0
    assert session.working_keyframes[0].x == 0.3
    assert session.working_keyframes[0].y == 0.4
    assert session.selected_keyframe_id == edit_id
    assert session.is_dirty is True
    assert session.can_apply is True
    assert session.original_keyframes[0].x == 0.1


def test_midpoint_insertion_assigns_fixed_temporal_midpoint() -> None:
    """Inserted time does not depend on the spatial drop position."""
    session = _session()
    start, end = session.working_keyframes

    inserted_id = session.insert_between(start.edit_id, end.edit_id, 0.7, 0.1)
    inserted = next(
        keyframe
        for keyframe in session.working_keyframes
        if keyframe.edit_id == inserted_id
    )
    session.move_keyframe(inserted_id, 0.2, 0.9)

    assert inserted.t == 5.0
    assert next(
        keyframe.t
        for keyframe in session.working_keyframes
        if keyframe.edit_id == inserted_id
    ) == 5.0
    assert session.selected_keyframe_id == inserted_id


def test_midpoint_insertion_rejects_timestamp_collision() -> None:
    """A segment too narrow for a unique midpoint remains unchanged."""
    session = TrajectoryEditSession.create(
        map_id="map-1",
        marker_id="marker-1",
        trajectory_id="trajectory-1",
        keyframes=[
            Keyframe(t=0.0, x=0.1, y=0.2),
            Keyframe(t=KEYFRAME_TIME_EPSILON, x=0.9, y=0.8),
        ],
        playhead=0.0,
    )
    start, end = session.working_keyframes

    with pytest.raises(ValueError, match="times within"):
        session.insert_between(start.edit_id, end.edit_id, 0.5, 0.5)

    assert len(session.working_keyframes) == 2


def test_delete_allows_one_and_zero_keyframe_states() -> None:
    """Deletion removes exactly one selected point at a time."""
    session = _session()
    session.select_keyframe(session.working_keyframes[1].edit_id)

    assert session.delete_selected_keyframe() is True
    assert len(session.working_keyframes) == 1
    assert session.can_apply is True
    assert session.delete_selected_keyframe() is True
    assert session.working_keyframes == []
    assert session.can_apply is True


def test_conflict_blocks_apply_without_losing_working_state() -> None:
    """External conflict keeps local edits inspectable."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.move_keyframe(edit_id, 0.3, 0.4)

    session.mark_conflicted()

    assert session.is_conflicted is True
    assert session.can_apply is False
    assert session.working_keyframes[0].x == 0.3


def test_restore_original_discards_changes_and_conflict() -> None:
    """Full cancel recreates the authoritative session-start state."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.move_keyframe(edit_id, 0.3, 0.4)
    session.mark_conflicted()

    session.restore_original()

    assert session.is_dirty is False
    assert session.is_conflicted is False
    assert session.working_keyframes == list(session.original_keyframes)
    assert session.working_keyframes[0] is not session.original_keyframes[0]
