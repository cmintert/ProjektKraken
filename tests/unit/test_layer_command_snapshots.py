"""Regression tests for layer command snapshots."""

import pytest
from unittest.mock import MagicMock
from src.commands.layer_commands import (
    SetLayerOpacityCommand,
    SetLayerVisibilityCommand,
)
from src.core.map import Map, MapLayerNode


@pytest.fixture
def mock_db_service_stale():
    """Return a DB service with a STALE map version (missing the new node)."""
    service = MagicMock()

    # The DB only knows about the root, but NOT the new child node
    root = MapLayerNode(name="Root", id="root-1")
    # map_obj has NO children in the DB
    map_obj = Map(id="map-1", name="Test Map", image_path="path", layers=root)

    service.map_repo.get_map.return_value = map_obj
    return service


def test_opacity_command_fails_without_snapshot_if_db_stale(mock_db_service_stale):
    """Confirm that without a snapshot, the command fails if DB is stale."""
    # We try to target "new-node-1", which exists in UI but NOT in mock_db_service_stale
    cmd = SetLayerOpacityCommand(map_id="map-1", node_id="new-node-1", opacity=0.5)

    result = cmd.execute(mock_db_service_stale)

    assert result.success is False
    assert "not found" in result.message


def test_opacity_command_succeeds_with_snapshot(mock_db_service_stale):
    """Confirm that WITH a snapshot, the command succeeds even if DB is stale."""
    # Create a snapshot representing the UI state (which HAS the new node)
    root = MapLayerNode(name="Root", id="root-1")
    new_node = MapLayerNode(name="New Node", id="new-node-1", opacity=1.0)
    root.children.append(new_node)

    snapshot = root.to_dict()

    # Init command with the snapshot
    cmd = SetLayerOpacityCommand(
        map_id="map-1", node_id="new-node-1", opacity=0.5, layer_tree_dict=snapshot
    )

    result = cmd.execute(mock_db_service_stale)

    # Should succeed because it uses the snapshot
    assert result.success is True
    assert "set to 50%" in result.message

    # Verify the DB service was called to save the UPDATED map
    saved_map = mock_db_service_stale.map_repo.insert_map.call_args[0][0]

    # The saved map should have the structure from the snapshot
    assert len(saved_map.layers.children) == 1
    assert saved_map.layers.children[0].id == "new-node-1"
    # And the opacity should be applied
    assert saved_map.layers.children[0].opacity == 0.5


def test_visibility_command_succeeds_with_snapshot(mock_db_service_stale):
    """Confirm that SetLayerVisibilityCommand also supports snapshots."""
    # Create a snapshot representing the UI state
    root = MapLayerNode(name="Root", id="root-1")
    new_node = MapLayerNode(name="New Node", id="new-node-1", visible=True)
    root.children.append(new_node)

    snapshot = root.to_dict()

    # Init command with the snapshot
    cmd = SetLayerVisibilityCommand(
        map_id="map-1", node_id="new-node-1", visible=False, layer_tree_dict=snapshot
    )

    result = cmd.execute(mock_db_service_stale)

    assert result.success is True

    # Verify persistence
    saved_map = mock_db_service_stale.map_repo.insert_map.call_args[0][0]
    assert saved_map.layers.children[0].visible is False
