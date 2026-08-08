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


def test_date_edit_reorders_by_stable_identity_and_tracks_feedback() -> None:
    """Retiming may reorder points without detaching their spatial values."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id

    jump_time = session.begin_date_edit(edit_id, current_playhead=4.0)
    session.update_active_date(12.0)
    snapshot = session.to_snapshot()

    assert jump_time == 0.0
    assert session.working_keyframes[1].edit_id == edit_id
    assert session.working_keyframes[1].x == 0.1
    assert snapshot["date_edit_original_t"] == 0.0
    assert snapshot["date_edit_proposed_t"] == 12.0
    assert snapshot["date_edit_delta"] == 12.0
    assert session.finish_date_edit() == 12.0
    assert session.active_date_edit_id is None


def test_repeated_begin_preserves_date_edit_cancel_baseline() -> None:
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.begin_date_edit(edit_id, current_playhead=4.0)
    session.update_active_date(3.0)

    jump_time = session.begin_date_edit(edit_id, current_playhead=8.0)
    restore_playhead = session.cancel_date_edit()

    assert jump_time == 3.0
    assert restore_playhead == 4.0
    assert session.working_keyframes[0].t == 0.0


def test_date_edit_collision_remains_visible_and_blocks_apply() -> None:
    """An invalid proposed date is preserved for correction, not overwritten."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.begin_date_edit(edit_id, current_playhead=4.0)

    session.update_active_date(10.0)

    assert session.can_apply is False
    assert session.validation_errors
    assert next(
        keyframe.t
        for keyframe in session.working_keyframes
        if keyframe.edit_id == edit_id
    ) == 10.0


def test_cancel_date_edit_restores_prior_working_date_and_playhead() -> None:
    """Temporal cancel preserves earlier spatial edits in the same session."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.move_keyframe(edit_id, 0.3, 0.4)
    session.begin_date_edit(edit_id, current_playhead=4.0)
    session.update_active_date(6.0)

    restore_playhead = session.cancel_date_edit()

    restored = next(
        keyframe
        for keyframe in session.working_keyframes
        if keyframe.edit_id == edit_id
    )
    assert restore_playhead == 4.0
    assert restored.t == 0.0
    assert restored.x == 0.3
    assert restored.y == 0.4
    assert session.is_dirty is True
