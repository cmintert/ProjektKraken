"""Repository and atomic replacement tests for dated vector geometry."""

import copy

import pytest

from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map
from src.core.marker import Marker
from src.services.repositories.feature_geometry_repository import (
    FeatureGeometryConflictError,
)


def _setup_feature(db_service, feature_type: str = "path") -> Marker:
    map_obj = Map(name="Map", image_path="map.png")
    db_service.insert_map(map_obj)
    geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}]
    if feature_type == "region":
        geometry.append({"x": 0.2, "y": 0.1})
    marker = Marker(
        id="marker",
        map_id=map_obj.id,
        object_id="object",
        object_type="entity",
        x=0.15,
        y=0.15,
        feature_type=feature_type,
        geometry=geometry,
    )
    db_service.insert_marker(marker)
    return marker


def _state(date: float, state_id: str = "state") -> FeatureGeometryState:
    return FeatureGeometryState(
        id=state_id,
        marker_id="marker",
        effective_date=date,
        geometry=[{"x": 0.2, "y": 0.2}, {"x": 0.4, "y": 0.4}],
        anchor_x=0.0,
        anchor_y=0.0,
    )


def test_replace_load_sort_and_recalculate_anchor(db_service) -> None:
    marker = _setup_feature(db_service)
    repo = db_service.feature_geometry_repo
    saved = repo.replace_marker_states(
        marker.id, [_state(200.0, "c"), _state(100.0, "b")], expected_snapshot=[]
    )
    assert [state["id"] for state in saved] == ["b", "c"]
    assert saved[0]["anchor_x"] == pytest.approx(0.3)
    assert [state["id"] for state in repo.get_states_for_map(marker.map_id)] == [
        "b",
        "c",
    ]


def test_duplicate_date_and_point_marker_are_rejected(db_service) -> None:
    marker = _setup_feature(db_service)
    with pytest.raises(ValueError, match="same date"):
        db_service.feature_geometry_repo.replace_marker_states(
            marker.id, [_state(100.0, "a"), _state(100.0, "b")]
        )

    point_map = Map(name="Point Map", image_path="point.png")
    db_service.insert_map(point_map)
    point = Marker(
        id="point",
        map_id=point_map.id,
        object_id="point-object",
        object_type="entity",
        x=0.5,
        y=0.5,
    )
    db_service.insert_marker(point)
    invalid = copy.deepcopy(_state(1.0).to_dict())
    invalid["marker_id"] = point.id
    with pytest.raises(ValueError, match="paths and regions"):
        db_service.feature_geometry_repo.replace_marker_states(point.id, [invalid])


def test_expected_snapshot_and_cascade_delete(db_service) -> None:
    marker = _setup_feature(db_service)
    repo = db_service.feature_geometry_repo
    saved = repo.replace_marker_states(marker.id, [_state(100.0)])
    with pytest.raises(FeatureGeometryConflictError):
        repo.replace_marker_states(marker.id, [], expected_snapshot=[])
    assert repo.snapshot_by_marker(marker.id) == saved
    db_service.delete_marker(marker.id)
    assert repo.snapshot_by_marker(marker.id) == []
