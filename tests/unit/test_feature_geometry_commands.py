"""Persistent undo tests for atomic geometry-state commands."""

from src.commands.feature_geometry_commands import (
    ReplaceFeatureGeometryStatesCommand,
)
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map
from src.core.marker import Marker


def test_create_undo_redo_and_serialization(db_service) -> None:
    map_obj = Map(name="Map", image_path="map.png")
    db_service.insert_map(map_obj)
    marker = Marker(
        id="marker",
        map_id=map_obj.id,
        object_id="object",
        object_type="entity",
        x=0.15,
        y=0.15,
        feature_type="path",
        geometry=[{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}],
    )
    db_service.insert_marker(marker)
    state = FeatureGeometryState(
        marker_id=marker.id,
        effective_date=150.0,
        geometry=[{"x": 0.3, "y": 0.3}, {"x": 0.5, "y": 0.5}],
        anchor_x=0.4,
        anchor_y=0.4,
    )
    command = ReplaceFeatureGeometryStatesCommand(
        map_obj.id, marker.id, [], [state], "Create Geometry State"
    )
    assert command.execute(db_service).success
    assert len(db_service.feature_geometry_repo.get_states(marker.id)) == 1
    assert command.undo(db_service).success
    assert db_service.feature_geometry_repo.get_states(marker.id) == []

    restored = ReplaceFeatureGeometryStatesCommand.from_dict(command.to_dict())
    restored.restore_base_state(command.base_state_dict())
    assert restored.execute(db_service).success
    assert len(db_service.feature_geometry_repo.get_states(marker.id)) == 1
