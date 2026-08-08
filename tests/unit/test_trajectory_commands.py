"""Tests for atomic, persistent trajectory command history."""

import json

from src.commands.trajectory_commands import UpdateTrajectoryCommand
from src.core.map import Map
from src.core.marker import Marker
from src.core.trajectory import Keyframe, mfjson_to_keyframes


def _create_marker(db_service) -> tuple[str, Marker]:
    """Create one map marker and return its public map identity."""
    map_obj = Map(name="Trajectory Test", image_path="/test.png")
    db_service.insert_map(map_obj)
    marker = Marker(
        map_id=map_obj.id,
        object_id="entity-trajectory",
        object_type="entity",
        x=0.5,
        y=0.5,
    )
    db_service.insert_marker(marker)
    return map_obj.id, marker


def test_update_command_execute_undo_redo_restore_exact_rows(db_service) -> None:
    """Execute, undo, and redo preserve exact row metadata and identity."""
    map_id, marker = _create_marker(db_service)
    trajectory_id = db_service.insert_trajectory(
        marker.id,
        [Keyframe(t=0.0, x=0.1, y=0.1), Keyframe(t=10.0, x=0.9, y=0.9)],
        properties={"stroke": "dashed"},
    )
    legacy_json = json.dumps([[0.0, 0.1, 0.1], [10.0, 0.9, 0.9]])
    with db_service.transaction() as connection:
        connection.execute(
            """
            UPDATE moving_features
            SET trajectory = ?, created_at = ?
            WHERE id = ?
            """,
            (legacy_json, 1234.5, trajectory_id),
        )
    before = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    assert before is not None

    supplied = [
        Keyframe(t=30.0, x=0.8, y=0.7),
        Keyframe(t=20.0, x=0.2, y=0.3),
    ]
    command = UpdateTrajectoryCommand(map_id, marker.object_id, before, supplied)
    supplied[0].x = 0.0
    result = command.execute(db_service)

    assert result.success is True
    after = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    assert after is not None
    assert after["id"] == before["id"]
    assert after["properties"] == before["properties"]
    assert after["created_at"] == before["created_at"]
    persisted_keyframes = mfjson_to_keyframes(json.loads(after["trajectory"]))
    assert persisted_keyframes == [
        Keyframe(t=20.0, x=0.2, y=0.3),
        Keyframe(t=30.0, x=0.8, y=0.7),
    ]

    undo_result = command.undo(db_service)
    assert undo_result.success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) == before

    redo_result = command.execute(db_service)
    assert redo_result.success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) == after


def test_update_command_serialization_preserves_undo_state(db_service) -> None:
    """A history round-trip can undo to the exact legacy row snapshot."""
    map_id, marker = _create_marker(db_service)
    db_service.insert_trajectory(
        marker.id, [Keyframe(t=1.0, x=0.1, y=0.1)]
    )
    before = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    command = UpdateTrajectoryCommand(
        map_id,
        marker.object_id,
        before,
        [Keyframe(t=2.0, x=0.2, y=0.2)],
    )
    assert command.execute(db_service).success is True

    payload = json.loads(json.dumps(command.to_dict()))
    restored = UpdateTrajectoryCommand.from_dict(payload)
    restored.restore_base_state(command.base_state_dict())
    payload["after_keyframes"][0]["x"] = 0.9

    assert restored.after_keyframes[0].x == 0.2
    assert restored.undo(db_service).success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) == before


def test_update_command_creation_uses_same_row_id_after_redo(db_service) -> None:
    """Undo and redo of a new trajectory restore the same generated row."""
    map_id, marker = _create_marker(db_service)
    command = UpdateTrajectoryCommand(
        map_id,
        marker.object_id,
        None,
        [Keyframe(t=5.0, x=0.4, y=0.6)],
    )

    assert command.execute(db_service).success is True
    created = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    assert created is not None
    assert command.undo(db_service).success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) is None
    assert command.execute(db_service).success is True
    redone = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    assert redone == created


def test_update_command_deletion_restores_complete_row(db_service) -> None:
    """Deleting all points and undoing restores the exact prior row."""
    map_id, marker = _create_marker(db_service)
    db_service.insert_trajectory(
        marker.id, [Keyframe(t=5.0, x=0.4, y=0.6)], {"color": "blue"}
    )
    before = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    command = UpdateTrajectoryCommand(map_id, marker.object_id, before, [])

    assert command.execute(db_service).success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) is None
    assert command.undo(db_service).success is True
    assert db_service.get_marker_trajectory_snapshot(map_id, marker.object_id) == before


def test_update_command_rejects_stale_before_snapshot(db_service) -> None:
    """A command failure leaves external trajectory changes untouched."""
    map_id, marker = _create_marker(db_service)
    trajectory_id = db_service.insert_trajectory(
        marker.id, [Keyframe(t=1.0, x=0.1, y=0.1)]
    )
    before = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    with db_service.transaction() as connection:
        connection.execute(
            "UPDATE moving_features SET properties = ? WHERE id = ?",
            ('{"external": true}', trajectory_id),
        )

    command = UpdateTrajectoryCommand(
        map_id,
        marker.object_id,
        before,
        [Keyframe(t=2.0, x=0.2, y=0.2)],
    )
    result = command.execute(db_service)

    assert result.success is False
    assert "changed" in result.message
    assert command.is_executed is False
    current = db_service.get_marker_trajectory_snapshot(map_id, marker.object_id)
    assert current is not None
    assert current["properties"] == '{"external": true}'
