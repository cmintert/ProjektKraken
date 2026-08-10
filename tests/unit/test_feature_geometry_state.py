"""Tests for dated vector-geometry resolution."""

import pytest

from src.core.feature_geometry_state import (
    FeatureGeometryState,
    calculate_feature_anchor,
    resolve_feature_geometry,
    validate_feature_geometry,
)
from src.core.marker import Marker


def _geometry(offset: float) -> list[dict[str, float]]:
    return [
        {"x": offset, "y": 0.1},
        {"x": offset + 0.1, "y": 0.2},
    ]


def _marker() -> Marker:
    return Marker(
        id="marker",
        map_id="map",
        object_id="object",
        object_type="entity",
        x=0.15,
        y=0.15,
        feature_type="path",
        geometry=_geometry(0.1),
    )


def _state(state_id: str, date: float, offset: float) -> FeatureGeometryState:
    geometry = _geometry(offset)
    anchor = calculate_feature_anchor(geometry)
    return FeatureGeometryState(
        id=state_id,
        marker_id="marker",
        effective_date=date,
        geometry=geometry,
        anchor_x=anchor[0],
        anchor_y=anchor[1],
    )


@pytest.mark.parametrize(
    ("date", "source", "state_id"),
    [
        (99.0, "base", None),
        (100.0, "dated", "b"),
        (199.0, "dated", "b"),
        (200.0, "dated", "c"),
        (999.0, "dated", "c"),
    ],
)
def test_resolver_uses_base_exact_and_latest_previous(
    date: float, source: str, state_id: str | None
) -> None:
    resolved = resolve_feature_geometry(
        _marker(), [_state("c", 200.0, 0.5), _state("b", 100.0, 0.3)], date
    )
    assert resolved.source_type == source
    assert resolved.state_id == state_id


def test_acceptance_state_at_150_and_removal() -> None:
    marker = _marker()
    states = [_state("b", 100.0, 0.3), _state("c", 200.0, 0.5)]
    states.append(_state("d", 150.0, 0.4))
    assert resolve_feature_geometry(marker, states, 149.0).state_id == "b"
    assert resolve_feature_geometry(marker, states, 150.0).state_id == "d"
    assert resolve_feature_geometry(marker, states, 199.0).state_id == "d"
    assert resolve_feature_geometry(marker, states, 200.0).state_id == "c"
    states = [state for state in states if state.id != "d"]
    assert resolve_feature_geometry(marker, states, 150.0).state_id == "b"


def test_geometry_validation_rejects_points_and_invalid_coordinates() -> None:
    with pytest.raises(ValueError, match="paths and regions"):
        validate_feature_geometry("point", _geometry(0.1))
    with pytest.raises(ValueError, match="at least 3"):
        validate_feature_geometry("region", _geometry(0.1))
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        validate_feature_geometry("path", [{"x": -1.0, "y": 0.0}, {"x": 0.0, "y": 0.0}])
