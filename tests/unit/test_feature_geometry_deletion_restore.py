"""Deletion commands preserve dated geometry through undo."""

import pytest

from src.commands.layer_commands import DeleteLayerSubtreeCommand
from src.commands.map_crud_commands import DeleteMapCommand
from src.commands.marker_commands import DeleteMarkerCommand
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker


def _setup(db_service, feature_type: str = "region") -> tuple[Map, Marker]:
    root = MapLayerNode(id="root", name="Root")
    child = MapLayerNode(
        id="object", name="Border", layer_type=feature_type
    )
    root.children.append(child)
    map_obj = Map(name="Map", image_path="map.png", layers=root)
    db_service.insert_map(map_obj)
    marker = Marker(
        id="marker",
        map_id=map_obj.id,
        object_id="object",
        object_type="entity",
        x=0.2,
        y=0.2,
        feature_type=feature_type,
        geometry=[
            {"x": 0.1, "y": 0.1},
            {"x": 0.3, "y": 0.1},
            {"x": 0.2, "y": 0.3},
        ],
    )
    db_service.insert_marker(marker)
    state = FeatureGeometryState(
        marker_id=marker.id,
        effective_date=100.0,
        geometry=[
            {"x": 0.2, "y": 0.2},
            {"x": 0.4, "y": 0.2},
            {"x": 0.3, "y": 0.4},
        ],
        anchor_x=0.3,
        anchor_y=0.3,
    )
    db_service.feature_geometry_repo.replace_marker_states(marker.id, [state])
    return map_obj, marker


def test_marker_delete_undo_restores_geometry_states(db_service) -> None:
    _, marker = _setup(db_service)
    command = DeleteMarkerCommand(marker.id)
    assert command.execute(db_service).success
    command.undo(db_service)
    assert len(db_service.feature_geometry_repo.get_states(marker.id)) == 1


@pytest.mark.parametrize("feature_type", ["path", "region"])
def test_layer_subtree_delete_undo_restores_geometry_states(
    db_service, tmp_path, feature_type
) -> None:
    map_obj, marker = _setup(db_service, feature_type)
    command = DeleteLayerSubtreeCommand(
        map_obj.id, marker.object_id, world_root=str(tmp_path)
    )
    assert command.execute(db_service).success
    assert db_service.get_marker(marker.id) is None
    assert db_service.feature_geometry_repo.get_states(marker.id) == []
    command.undo(db_service)
    assert db_service.get_marker(marker.id) is not None
    assert len(db_service.feature_geometry_repo.get_states(marker.id)) == 1


def test_map_delete_undo_restores_geometry_states(db_service) -> None:
    map_obj, marker = _setup(db_service)
    command = DeleteMapCommand(map_obj.id)
    assert command.execute(db_service).success
    command.undo(db_service)
    assert len(db_service.feature_geometry_repo.get_states(marker.id)) == 1
