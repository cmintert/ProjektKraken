"""Tests for the GUI-independent trajectory edit session."""

import pytest

from src.core.trajectory import (
    KEYFRAME_TIME_EPSILON,
    Keyframe,
    TrajectoryDistanceContext,
)
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
    )


def _speed_session() -> TrajectoryEditSession:
    return TrajectoryEditSession.create(
        map_id="map-1",
        marker_id="marker-1",
        trajectory_id="trajectory-1",
        keyframes=[
            Keyframe(t=0.0, x=0.0, y=0.0),
            Keyframe(t=12.0, x=0.25, y=0.0),
            Keyframe(t=20.0, x=1.0, y=0.0),
        ],
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

    session.begin_date_edit(edit_id)
    session.update_active_date(12.0)
    snapshot = session.to_snapshot()

    assert session.working_keyframes[1].edit_id == edit_id
    assert session.working_keyframes[1].x == 0.1
    assert snapshot["date_edit_original_t"] == 0.0
    assert snapshot["date_edit_proposed_t"] == 12.0
    assert snapshot["date_edit_delta"] == 12.0
    assert session.finish_date_edit()
    assert session.active_date_edit_id is None


def test_explicit_time_assignment_reorders_without_detaching_position() -> None:
    """One-step playhead copying uses the same stable date mutation."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id

    session.set_keyframe_time(edit_id, 12.0)

    moved = session.working_keyframes[-1]
    assert moved.edit_id == edit_id
    assert (moved.t, moved.x, moved.y) == (12.0, 0.1, 0.2)
    assert session.selected_keyframe_id == edit_id
    assert session.can_apply


def test_repeated_begin_preserves_date_edit_cancel_baseline() -> None:
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.begin_date_edit(edit_id)
    session.update_active_date(3.0)

    session.begin_date_edit(edit_id)
    cancelled = session.cancel_date_edit()

    assert cancelled
    assert session.working_keyframes[0].t == 0.0


def test_date_edit_collision_remains_visible_and_blocks_apply() -> None:
    """An invalid proposed date is preserved for correction, not overwritten."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.begin_date_edit(edit_id)

    session.update_active_date(10.0)

    assert session.can_apply is False
    assert session.validation_errors
    assert next(
        keyframe.t
        for keyframe in session.working_keyframes
        if keyframe.edit_id == edit_id
    ) == 10.0


def test_cancel_date_edit_restores_prior_working_date() -> None:
    """Temporal cancel preserves earlier spatial edits in the same session."""
    session = _session()
    edit_id = session.working_keyframes[0].edit_id
    session.move_keyframe(edit_id, 0.3, 0.4)
    session.begin_date_edit(edit_id)
    session.update_active_date(6.0)

    cancelled = session.cancel_date_edit()

    restored = next(
        keyframe
        for keyframe in session.working_keyframes
        if keyframe.edit_id == edit_id
    )
    assert cancelled
    assert restored.t == 0.0
    assert restored.x == 0.3
    assert restored.y == 0.4
    assert session.is_dirty is True


def test_speed_anchor_exposes_only_valid_later_range() -> None:
    """An end anchor needs at least one intermediate keyframe."""
    session = _speed_session()
    start_id, middle_id, end_id = (
        keyframe.edit_id for keyframe in session.working_keyframes
    )

    session.set_speed_anchor(start_id)
    session.select_keyframe(middle_id)
    adjacent = session.to_snapshot()
    session.select_keyframe(end_id)
    valid = session.to_snapshot()

    assert adjacent["speed_anchor_index"] == 0
    assert adjacent["can_equalize_to_selected"] is False
    assert valid["can_equalize_to_selected"] is True


def test_speed_equalization_preview_reports_changed_dates_and_speed() -> None:
    """Preview changes only working dates and blocks final trajectory Apply."""
    session = _speed_session()
    start_id, _, end_id = (
        keyframe.edit_id for keyframe in session.working_keyframes
    )
    session.set_speed_anchor(start_id)

    session.preview_speed_equalization(
        end_id,
        TrajectoryDistanceContext(1000.0, 500.0, "m"),
    )
    snapshot = session.to_snapshot()

    assert [item.t for item in session.working_keyframes] == [0.0, 5.0, 20.0]
    assert snapshot["is_equalization_previewing"] is True
    assert snapshot["equalization_changes"] == [
        {
            "edit_id": session.working_keyframes[1].edit_id,
            "keyframe_number": 2,
            "original_t": 12.0,
            "proposed_t": 5.0,
        }
    ]
    assert snapshot["equalization_total_distance"] == 1000.0
    assert snapshot["equalization_average_speed"] == 50.0
    assert snapshot["equalization_distance_unit"] == "m"
    assert session.can_apply is False


def test_cancel_equalization_restores_prior_working_copy() -> None:
    """Cancel restores pre-preview dates without discarding spatial edits."""
    session = _speed_session()
    middle_id = session.working_keyframes[1].edit_id
    session.move_keyframe(middle_id, 0.25, 0.2)
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    session.set_speed_anchor(start_id)
    session.preview_speed_equalization(
        end_id,
        TrajectoryDistanceContext(1.0, 1.0),
    )

    assert session.cancel_speed_equalization() is True

    restored = session.working_keyframes[1]
    assert restored.t == 12.0
    assert (restored.x, restored.y) == (0.25, 0.2)
    assert session.speed_anchor_id is None
    assert session.is_dirty is True
    assert session.can_apply is True


def test_confirm_equalization_keeps_preview_in_working_copy() -> None:
    """Confirm ends the preview but still waits for trajectory Apply."""
    session = _speed_session()
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    session.set_speed_anchor(start_id)
    session.preview_speed_equalization(
        end_id,
        TrajectoryDistanceContext(1.0, 1.0),
    )

    assert session.confirm_speed_equalization() is True

    assert [item.t for item in session.working_keyframes] == [0.0, 5.0, 20.0]
    assert session.is_equalization_previewing is False
    assert session.speed_anchor_id is None
    assert session.can_apply is True


def test_whole_trajectory_equalization_uses_endpoints() -> None:
    """Whole equalization chooses the first and last keyframes as anchors."""
    session = _speed_session()

    session.preview_whole_speed_equalization(
        TrajectoryDistanceContext(1.0, 1.0)
    )
    snapshot = session.to_snapshot()

    assert snapshot["equalization_start_id"] == session.working_keyframes[0].edit_id
    assert snapshot["equalization_end_id"] == session.working_keyframes[-1].edit_id
    assert snapshot["speed_anchor_id"] == session.working_keyframes[0].edit_id


def test_equalization_rejects_adjacent_already_equal_and_zero_distance() -> None:
    """Unusable anchor ranges remain unchanged with clear diagnostics."""
    session = _speed_session()
    start_id, middle_id, end_id = (
        keyframe.edit_id for keyframe in session.working_keyframes
    )
    session.set_speed_anchor(start_id)
    with pytest.raises(ValueError, match="intermediate"):
        session.preview_speed_equalization(
            middle_id, TrajectoryDistanceContext(1.0, 1.0)
        )

    session.begin_date_edit(middle_id)
    session.update_active_date(5.0)
    session.finish_date_edit()
    with pytest.raises(ValueError, match="already"):
        session.preview_speed_equalization(
            end_id, TrajectoryDistanceContext(1.0, 1.0)
        )

    zero = TrajectoryEditSession.create(
        "map-1",
        "marker-1",
        "trajectory-1",
        [
            Keyframe(0.0, 0.5, 0.5),
            Keyframe(10.0, 0.5, 0.5),
            Keyframe(20.0, 0.5, 0.5),
        ],
    )
    zero.set_speed_anchor(zero.working_keyframes[0].edit_id)
    with pytest.raises(ValueError, match="zero-distance"):
        zero.preview_speed_equalization(
            zero.working_keyframes[-1].edit_id,
            TrajectoryDistanceContext(1.0, 1.0),
        )


def test_equalization_preview_blocks_other_working_mutations() -> None:
    """Preview remains stable until explicitly applied or cancelled."""
    session = _speed_session()
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    session.set_speed_anchor(start_id)
    session.preview_speed_equalization(
        end_id,
        TrajectoryDistanceContext(1.0, 1.0),
    )

    with pytest.raises(ValueError, match="preview"):
        session.move_keyframe(start_id, 0.1, 0.1)
    with pytest.raises(ValueError, match="preview"):
        session.begin_date_edit(start_id)
