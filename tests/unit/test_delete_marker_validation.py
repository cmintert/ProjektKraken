"""Tests for DeleteMarkerCommand silent-failure prevention (M10).

Verifies that delete_marker returning 0 affected rows causes the command to
report failure and leaves _is_executed=False, preventing ghost marker on undo.
"""
from unittest.mock import patch

from src.commands.marker_commands import DeleteMarkerCommand
from src.core.map import Map
from src.core.marker import Marker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_marker(db_service) -> tuple[Map, str]:
    """Insert a map + marker, return (map, marker_id)."""
    map_obj = Map(name="Test Map", image_path="/t.png")
    db_service.insert_map(map_obj)
    marker = Marker(
        map_id=map_obj.id,
        object_id="ent-001",
        object_type="entity",
        x=0.3,
        y=0.4,
    )
    marker_id = db_service.insert_marker(marker)
    return map_obj, marker_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_delete_marker_returns_nonzero_rowcount_on_success(db_service):
    """delete_marker() must report ≥ 1 affected row when the marker exists.

    This is a contract test on the repository layer: the returned int must
    be >0 so the command layer can distinguish success from silent no-ops.
    """
    _, marker_id = _make_marker(db_service)
    result = db_service.delete_marker(marker_id)
    assert result == 1


def test_delete_marker_returns_zero_rowcount_when_missing(db_service):
    """delete_marker() must return 0 when the marker does not exist."""
    result = db_service.delete_marker("nonexistent-id-xyz")
    assert result == 0


def test_delete_marker_command_fails_on_zero_rowcount(db_service):
    """DeleteMarkerCommand.execute() returns failure when DB deletes 0 rows.

    The command pre-fetches the marker (so get_marker succeeds), but the
    actual DELETE returns 0 rows — simulated via a patched delete_marker.
    After the call: result.success must be False and _is_executed must be
    False so that undo() is a guaranteed no-op.
    """
    _, marker_id = _make_marker(db_service)

    # Patch db_service.delete_marker to return 0 (silent no-op)
    with patch.object(db_service, "delete_marker", return_value=0):
        cmd = DeleteMarkerCommand(marker_id)
        result = cmd.execute(db_service)

    assert result.success is False
    assert cmd._is_executed is False


def test_undo_is_noop_when_execute_failed(db_service):
    """undo() must not re-insert a marker whose deletion was never confirmed."""
    map_obj, marker_id = _make_marker(db_service)

    original_marker = db_service.get_marker(marker_id)
    assert original_marker is not None

    # Force execute to fail via silent delete no-op
    with patch.object(db_service, "delete_marker", return_value=0):
        cmd = DeleteMarkerCommand(marker_id)
        cmd.execute(db_service)

    # The marker is still in the DB (the mock never deleted it)
    assert db_service.get_marker(marker_id) is not None

    # undo() must not raise and must not double-insert
    cmd.undo(db_service)

    # Still exactly one row
    markers = db_service.get_markers_for_map(map_obj.id)
    assert len(markers) == 1
