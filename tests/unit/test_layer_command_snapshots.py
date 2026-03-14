"""Regression tests for layer command snapshots.

H4 fix: SetLayerVisibilityCommand and SetLayerOpacityCommand now ALWAYS
read the layer tree from the DB. The ``layer_tree_dict`` snapshot parameter
is kept for API compatibility but is no longer used to source the tree in
``execute()``, preventing a stale snapshot from overwriting newer DB data.
"""

from unittest.mock import MagicMock

import pytest

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


def test_opacity_command_fails_with_stale_snapshot_when_db_lacks_node(
    mock_db_service_stale,
):
    """H4 fix: even WITH a snapshot, command fails if the DB tree lacks the node.

    Previously (pre-fix), providing a snapshot would succeed even when the DB
    was stale. Now the DB tree is always authoritative.
    """
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

    # H4 fix: the DB tree is always used — command must fail when node is absent
    assert result.success is False
    assert "not found" in result.message


def test_visibility_command_fails_with_stale_snapshot_when_db_lacks_node(
    mock_db_service_stale,
):
    """H4 fix: SetLayerVisibilityCommand uses DB tree, not snapshot."""
    root = MapLayerNode(name="Root", id="root-1")
    new_node = MapLayerNode(name="New Node", id="new-node-1", visible=True)
    root.children.append(new_node)

    snapshot = root.to_dict()

    cmd = SetLayerVisibilityCommand(
        map_id="map-1", node_id="new-node-1", visible=False, layer_tree_dict=snapshot
    )

    result = cmd.execute(mock_db_service_stale)

    # H4 fix: must fail because the DB tree doesn't have new-node-1
    assert result.success is False
    assert "not found" in result.message


def test_opacity_command_succeeds_when_node_exists_in_db():
    """Opacity command works normally when the node exists in the DB."""
    root = MapLayerNode(name="Root", id="root-1")
    child = MapLayerNode(name="Child", id="child-1", opacity=1.0)
    root.children.append(child)
    map_obj = Map(id="map-1", name="Test Map", image_path="path", layers=root)

    service = MagicMock()
    service.map_repo.get_map.return_value = map_obj

    cmd = SetLayerOpacityCommand(map_id="map-1", node_id="child-1", opacity=0.5)
    result = cmd.execute(service)

    assert result.success is True
    saved_map = service.map_repo.insert_map.call_args[0][0]
    assert saved_map.layers.children[0].opacity == 0.5


def test_visibility_command_succeeds_when_node_exists_in_db():
    """Visibility command works normally when the node exists in the DB."""
    root = MapLayerNode(name="Root", id="root-1")
    child = MapLayerNode(name="Child", id="child-1", visible=True)
    root.children.append(child)
    map_obj = Map(id="map-1", name="Test Map", image_path="path", layers=root)

    service = MagicMock()
    service.map_repo.get_map.return_value = map_obj

    cmd = SetLayerVisibilityCommand(map_id="map-1", node_id="child-1", visible=False)
    result = cmd.execute(service)

    assert result.success is True
    saved_map = service.map_repo.insert_map.call_args[0][0]
    assert saved_map.layers.children[0].visible is False
