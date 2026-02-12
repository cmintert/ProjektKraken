"""
TDD tests for the layer rename fix.

Tests:
1. BaseCommand.has_history defaults to True
2. SaveLayerTreeCommand.has_history is False
3. RenameLayerCommand accepts a layer_tree_dict snapshot and
   persists it directly without needing to find the node in DB
4. RenameLayerCommand still works via DB fallback (no snapshot)
5. Undo still works after snapshot-based execute
6. CommandCoordinator skips non-historical commands
"""

from unittest.mock import MagicMock

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.map_commands import (
    RenameLayerCommand,
    SaveLayerTreeCommand,
)
from src.core.map import Map, MapLayerNode


# ------------------------------------------------------------------
#  1. has_history property
# ------------------------------------------------------------------


def test_base_command_has_history_defaults_true():
    """BaseCommand.has_history should default to True."""

    class DummyCommand(BaseCommand):
        def execute(self, db_service):
            return CommandResult(success=True)

        def undo(self, db_service):
            pass

        def to_dict(self):
            return {}

        @classmethod
        def from_dict(cls, data):
            return cls()

    cmd = DummyCommand()
    assert cmd.has_history is True


def test_save_layer_tree_command_has_history_false():
    """SaveLayerTreeCommand should not appear in the undo stack."""
    cmd = SaveLayerTreeCommand("map-1", {"name": "Root"})
    assert cmd.has_history is False


# ------------------------------------------------------------------
#  2. RenameLayerCommand with tree snapshot
# ------------------------------------------------------------------


def _make_map_with_layers(map_id: str = "map-1"):
    """Helper: create a Map object with a simple layer tree."""
    child = MapLayerNode(name="Old Name", layer_type="marker", id="node-1")
    root = MapLayerNode(name="Root", layer_type="group", children=[child])
    map_obj = Map(id=map_id, name="Test Map", image_path="/test.png")
    map_obj.layers = root
    map_obj.attributes = {"layers": root.to_dict()}
    return map_obj, root


def test_rename_with_tree_snapshot_succeeds(db_service):
    """RenameLayerCommand should succeed when given a tree snapshot,
    even if the DB does not contain the node yet (stale)."""
    map_obj, root = _make_map_with_layers()
    db_service.insert_map(map_obj)

    # The snapshot has the node already renamed
    child = root.children[0]
    child.name = "New Name"
    snapshot = root.to_dict()

    cmd = RenameLayerCommand(
        map_id=map_obj.id,
        node_id="node-1",
        new_name="New Name",
        layer_tree_dict=snapshot,
    )
    result = cmd.execute(db_service)

    assert result.success is True
    assert "New Name" in result.message

    # Verify persisted
    saved = db_service.get_map(map_obj.id)
    saved_layers = saved.attributes.get("layers", {})
    assert saved_layers["children"][0]["name"] == "New Name"


def test_rename_without_snapshot_fallback(db_service):
    """RenameLayerCommand should still work when no snapshot is given
    (backward compat / undo path)."""
    map_obj, _ = _make_map_with_layers()
    db_service.insert_map(map_obj)

    cmd = RenameLayerCommand(
        map_id=map_obj.id,
        node_id="node-1",
        new_name="Renamed",
    )
    result = cmd.execute(db_service)

    assert result.success is True

    saved = db_service.get_map(map_obj.id)
    saved_layers = saved.attributes.get("layers", {})
    assert saved_layers["children"][0]["name"] == "Renamed"


def test_rename_undo_after_snapshot(db_service):
    """Undo should restore the previous name via DB read."""
    map_obj, root = _make_map_with_layers()
    db_service.insert_map(map_obj)

    child = root.children[0]
    child.name = "After Rename"
    snapshot = root.to_dict()

    cmd = RenameLayerCommand(
        map_id=map_obj.id,
        node_id="node-1",
        new_name="After Rename",
        layer_tree_dict=snapshot,
    )
    result = cmd.execute(db_service)
    assert result.success is True

    # Undo
    cmd.undo(db_service)

    saved = db_service.get_map(map_obj.id)
    saved_layers = saved.attributes.get("layers", {})
    assert saved_layers["children"][0]["name"] == "Old Name"


def test_rename_snapshot_fails_if_map_missing(db_service):
    """RenameLayerCommand should fail gracefully if the map doesn't exist."""
    cmd = RenameLayerCommand(
        map_id="nonexistent-map",
        node_id="node-1",
        new_name="New Name",
        layer_tree_dict={"name": "Root", "children": []},
    )
    result = cmd.execute(db_service)

    assert result.success is False
    assert "not found" in result.message.lower()


# ------------------------------------------------------------------
#  3. CommandCoordinator respects has_history
# ------------------------------------------------------------------


def test_coordinator_skips_non_historical_commands():
    """CommandCoordinator should not add commands with has_history=False
    to the undo stack."""
    from src.app.command_coordinator import CommandCoordinator

    coordinator = CommandCoordinator(MagicMock())

    save_cmd = SaveLayerTreeCommand("map-1", {"name": "Root"})
    result = CommandResult(
        success=True,
        message="Layer tree saved.",
        command_name="SaveLayerTreeCommand",
        data={"command": save_cmd},
    )

    coordinator.on_command_result(result)

    assert len(coordinator.undo_stack) == 0


def test_coordinator_adds_historical_commands():
    """CommandCoordinator should add commands with has_history=True
    to the undo stack."""
    from src.app.command_coordinator import CommandCoordinator

    coordinator = CommandCoordinator(MagicMock())

    rename_cmd = RenameLayerCommand("map-1", "node-1", "New Name")
    result = CommandResult(
        success=True,
        message="Layer renamed.",
        command_name="RenameLayerCommand",
        data={"command": rename_cmd},
    )

    coordinator.on_command_result(result)

    assert len(coordinator.undo_stack) == 1
    assert coordinator.undo_stack[0] is rename_cmd


def test_rename_serialization_with_snapshot():
    """RenameLayerCommand.to_dict() should NOT include the snapshot
    (it's transient). from_dict() should still work."""
    cmd = RenameLayerCommand(
        map_id="map-1",
        node_id="node-1",
        new_name="New",
        layer_tree_dict={"name": "Root"},
    )
    d = cmd.to_dict()
    assert "layer_tree_dict" not in d

    restored = RenameLayerCommand.from_dict(d)
    assert restored.map_id == "map-1"
    assert restored.node_id == "node-1"
    assert restored.new_name == "New"
