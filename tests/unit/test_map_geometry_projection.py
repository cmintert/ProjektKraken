"""Display geometry preserves complete topology and dated source ownership."""

import json
import math
import time
from copy import deepcopy

import pytest
from shapely.geometry import LineString

from src.core.feature_geometry_state import FeatureGeometryState
from src.core.marker import Marker
from src.core.projected_geometry import ProjectedGeometry
from src.core.region_geometry import RegionPolygon
from src.services.map_geometry_projection import source_shape
from src.services.map_projection import MapProjector
from tests.unit.test_map_projection import snapshot
from tests.unit.test_map_reparenting import registration

pytestmark = pytest.mark.ci_fast


def u_region():
    return RegionPolygon(
        (
            (0.1, 0.1),
            (0.9, 0.1),
            (0.9, 0.9),
            (0.7, 0.9),
            (0.7, 0.3),
            (0.3, 0.3),
            (0.3, 0.9),
            (0.1, 0.9),
        ),
        (((0.15, 0.5), (0.25, 0.5), (0.25, 0.6), (0.15, 0.6)),),
    )


def geometry_snapshot(kind="region"):
    data = snapshot()
    data.maps[1].attributes["registration"] = registration(
        scale=1, aspect=1, center=(0.5, 0.5)
    )
    data.maps[2].attributes["registration"] = registration(
        scale=1, aspect=2.5, center=(0.5, 0.6)
    )
    geometry = (
        u_region().to_geometry()
        if kind == "region"
        else [
            {"x": x, "y": y}
            for x, y in ((0.1, 0.5), (0.3, 0.9), (0.5, 0.5), (0.7, 0.1), (0.9, 0.5))
        ]
    )
    data.markers = [
        Marker(
            "old",
            "territory",
            "entity",
            0.2,
            0.5,
            id="shape",
            label="Authored territory",
            feature_type=kind,
            geometry=geometry,
        )
    ]
    return data


def test_clipped_region_keeps_all_components_holes_and_source_identity():
    data = geometry_snapshot()
    before = deepcopy(data)
    frame = MapProjector(data).frame("new", 0)
    assert not frame["issues"]
    model = ProjectedGeometry.from_dict(json.loads(json.dumps(frame["geometries"][0])))
    assert len(model.polygons) == 2
    assert sum(len(p.holes) for p in model.polygons) == 1
    assert sum(p.area for p in model.polygons) == pytest.approx(0.375)
    assert (model.source_id, model.source_map, model.target_map) == (
        "shape",
        "old",
        "new",
    )
    assert data == before
    assert ProjectedGeometry.from_dict(model.to_dict()) == model


def test_path_can_exit_and_reenter_without_connecting_disconnected_parts():
    data = geometry_snapshot("path")
    frame = MapProjector(data).frame("new", 0)
    model = ProjectedGeometry.from_dict(frame["geometries"][0])
    assert len(model.lines) == 3
    for line in model.lines:
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in line)
        assert LineString(line).length > 0


@pytest.mark.parametrize("date,dated", [(9, False), (10, True), (19, True)])
def test_dated_replacement_is_selected_before_clipping_and_base_stays_authored(
    date, dated
):
    data = geometry_snapshot()
    marker = data.markers[0]
    replacement = RegionPolygon(
        ((0.4, 0.5), (0.6, 0.5), (0.6, 0.7), (0.4, 0.7))
    ).to_geometry()
    state = FeatureGeometryState(marker.id, 10, replacement, 0.5, 0.6)
    data.states[marker.id] = [state]
    before = deepcopy(marker.geometry)
    frame = MapProjector(data).frame("new", date)
    model = ProjectedGeometry.from_dict(frame["geometries"][0])
    assert len(model.polygons) == (1 if dated else 2)
    assert model.state_id == (state.id if dated else None)
    assert model.effective_date == (10 if dated else None)
    assert marker.geometry == before


def test_equivalent_rings_with_different_start_collapse_but_conflicting_representation_does_not():
    data = geometry_snapshot()
    original = data.markers[0]
    other = deepcopy(original)
    other.id = "second"
    other.geometry["outer"] = other.geometry["outer"][2:] + other.geometry["outer"][:2]
    data.markers.append(other)
    frame = MapProjector(data).frame("new", 0)
    assert len(frame["geometries"]) == 1 and not frame["issues"]
    other.feature_type = "point"
    frame = MapProjector(data).frame("new", 0)
    assert not frame["geometries"] and not frame["points"] and frame["issues"]


def test_invalid_topology_is_reported_without_anchor_fallback_or_repair():
    data = geometry_snapshot()
    data.markers[0].geometry = [
        {"x": x, "y": y} for x, y in ((0, 0), (1, 1), (0, 1), (1, 0))
    ]
    before = deepcopy(data.markers[0].geometry)
    frame = MapProjector(data).frame("new", 0)
    assert not frame["geometries"] and not frame["points"] and frame["issues"]
    assert data.markers[0].geometry == before


def test_simplification_keeps_components_holes_and_original_geometry():
    data = geometry_snapshot()
    projector = MapProjector(data)
    before = deepcopy(data)
    for pixel_size in ((10, 10), (360, 200), (4000, 3000)):
        frame = projector.frame("new", 0, pixel_size=pixel_size)
        model = ProjectedGeometry.from_dict(frame["geometries"][0])
        assert len(model.polygons) == 2
        assert sum(len(p.holes) for p in model.polygons) == 1
    assert data == before


def test_rotated_anisotropic_chains_preserve_display_geometry():
    data = geometry_snapshot()
    data.maps[1].attributes["registration"] = registration(
        scale=0.3, aspect=2, rotation=37
    )
    # Whole-root view contains the complete transformed source, including shear.
    frame = MapProjector(data).frame("root", 0, include_detail=True)
    model = ProjectedGeometry.from_dict(frame["geometries"][0])
    assert len(model.polygons) == 1 and len(model.polygons[0].holes) == 1
    assert model.polygons[0].area == pytest.approx(u_region().area * 0.3 * 0.15)


def test_large_geometry_caches_sources_and_bounds_simplification_error():
    data = geometry_snapshot("path")
    data.maps[2].attributes["registration"] = deepcopy(
        data.maps[1].attributes["registration"]
    )
    marker = data.markers[0]
    marker.geometry = [
        {"x": i / 9999, "y": 0.5 + 0.2 * math.sin(i / 100)} for i in range(10000)
    ]
    projector = MapProjector(data)
    started = time.perf_counter()
    frame = projector.frame("new", 0, pixel_size=(640, 480))
    elapsed = time.perf_counter() - started
    model = ProjectedGeometry.from_dict(frame["geometries"][0])
    assert len(model.lines[0]) < len(marker.geometry)
    original = LineString([(p["x"], p["y"]) for p in marker.geometry])
    assert original.hausdorff_distance(LineString(model.lines[0])) <= 0.5 / 640 + 1e-12
    assert (
        source_shape(projector, marker, 1)[0] is source_shape(projector, marker, 2)[0]
    )
    assert elapsed < 5  # Broad regression ceiling, not a claimed interactive benchmark.


def test_many_split_regions_keep_every_component_and_hole():
    data = geometry_snapshot()
    original = data.markers[0]
    data.markers = []
    for index in range(250):
        marker = deepcopy(original)
        marker.id = f"region-{index}"
        marker.object_id = f"territory-{index}"
        data.markers.append(marker)
    started = time.perf_counter()
    frame = MapProjector(data).frame("new", 0, pixel_size=(360, 640))
    assert len(frame["geometries"]) == 250
    models = [ProjectedGeometry.from_dict(d) for d in frame["geometries"]]
    assert sum(len(m.polygons) for m in models) == 500
    assert sum(len(p.holes) for m in models for p in m.polygons) == 250
    assert time.perf_counter() - started < 5


def test_closed_legacy_ring_and_unordered_dated_snapshots_follow_canonical_resolution():
    data = geometry_snapshot()
    marker = data.markers[0]
    marker.geometry["outer"].append(dict(marker.geometry["outer"][0]))
    assert MapProjector(data).frame("new", 0)["geometries"]
    early = FeatureGeometryState(marker.id, 10, marker.geometry, 0.2, 0.5)
    late = FeatureGeometryState(marker.id, 20, marker.geometry, 0.2, 0.5)
    data.states[marker.id] = [late, early]
    frame = MapProjector(data).frame("new", 15)
    assert frame["geometries"][0]["state_id"] == early.id
