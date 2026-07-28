"""Regression tests for authoritative worker-owned layer state."""

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


def test_opacity_command_rejects_snapshot_when_db_is_stale(
    mock_db_service_stale,
):
    """A UI snapshot cannot introduce a node absent from worker-owned state."""
    root = MapLayerNode(name="Root", id="root-1")
    new_node = MapLayerNode(name="New Node", id="new-node-1", opacity=1.0)
    root.children.append(new_node)

    snapshot = root.to_dict()

    cmd = SetLayerOpacityCommand(
        map_id="map-1", node_id="new-node-1", opacity=0.5, layer_tree_dict=snapshot
    )

    result = cmd.execute(mock_db_service_stale)

    assert result.success is False
    assert "not found" in result.message
    mock_db_service_stale.map_repo.insert_map.assert_not_called()


def test_visibility_command_rejects_snapshot_when_db_is_stale(
    mock_db_service_stale,
):
    """Visibility changes also require the node to exist in the DB tree."""
    root = MapLayerNode(name="Root", id="root-1")
    new_node = MapLayerNode(name="New Node", id="new-node-1", visible=True)
    root.children.append(new_node)

    snapshot = root.to_dict()

    cmd = SetLayerVisibilityCommand(
        map_id="map-1", node_id="new-node-1", visible=False, layer_tree_dict=snapshot
    )

    result = cmd.execute(mock_db_service_stale)

    assert result.success is False
    assert "not found" in result.message
    mock_db_service_stale.map_repo.insert_map.assert_not_called()


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
