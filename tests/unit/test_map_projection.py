"""Derived location policy uses authored identity, chronology and hierarchy."""

from copy import deepcopy

import pytest

from src.core.map import MapLayerNode
from src.core.marker import Marker
from src.core.trajectory import Keyframe
from src.services.map_coordinates import MapCoordinates
from src.services.map_projection import MapProjector, ProjectionSnapshot
from tests.unit.test_map_reparenting import records

pytestmark = pytest.mark.ci_fast


def snapshot():
    maps = records()
    # Identical sibling registrations make hand-checked coordinates straightforward.
    maps[2].attributes["registration"] = deepcopy(maps[1].attributes["registration"])
    point = Marker("old", "object", "entity", 0.3, 0.6, id="point", label="Location")
    return ProjectionSnapshot(maps, [point])


def test_map_coordinates_roundtrip_all_pairs_and_unrelated_root():
    data = snapshot()
    coordinates = MapCoordinates(data.maps)
    for source in data.maps:
        for target in data.maps:
            uv = coordinates.point(source.id, target.id, 0.2, 0.7)
            assert coordinates.point(target.id, source.id, *uv) == pytest.approx(
                (0.2, 0.7)
            )
    data.maps[2].attributes = {}
    with pytest.raises(ValueError, match="no shared"):
        MapCoordinates(data.maps).point("old", "new", 0.5, 0.5)


def test_unique_source_is_ephemeral_and_target_authored_wins_even_when_hidden():
    data = snapshot()
    before = deepcopy(data)
    frame = MapProjector(data).frame("new", 0)
    assert frame["points"][0]["x"] == pytest.approx(0.3)
    assert frame["points"][0]["sources"] == ["point"]
    assert data == before
    data.markers.append(Marker("new", "object", "entity", 0.9, 0.9, id="local"))
    assert not MapProjector(data).frame("new", 0)["points"]


@pytest.mark.parametrize("x,conflict", [(0.3, False), (0.8, True), (1.8, True)])
def test_equivalent_sources_collapse_but_disagreement_is_reported_before_clipping(
    x, conflict
):
    data = snapshot()
    data.markers.append(Marker("old", "object", "entity", x, 0.6, id="other"))
    frame = MapProjector(data).frame("new", 0)
    assert bool(frame["issues"]) == conflict
    assert len(frame["points"]) == (0 if conflict else 1)


def test_detail_is_conservative_and_explicitly_opted_in():
    projector = MapProjector(snapshot())
    assert not projector.frame("root", 0)["points"]
    assert projector.frame("root", 0, include_detail=True)["points"]


@pytest.mark.parametrize(
    "date,visible", [(9, False), (10, True), (19, True), (20, False)]
)
def test_inherited_half_open_temporal_eligibility(date, visible):
    data = snapshot()
    data.maps[1].layers = MapLayerNode(
        "Root",
        children=[
            MapLayerNode(
                "Group",
                start_date=10,
                end_date=20,
                children=[MapLayerNode("Location", id="point", layer_type="marker")],
            )
        ],
    )
    assert bool(MapProjector(data).frame("new", date)["points"]) == visible


def test_hidden_ancestor_opacity_and_zoom_are_respected():
    data = snapshot()
    node = MapLayerNode("Location", id="point", layer_type="marker", opacity=0.5)
    group = MapLayerNode("Group", opacity=0.4, children=[node])
    data.maps[1].layers = MapLayerNode("Root", children=[group])
    assert MapProjector(data).frame("new", 0)["points"][0]["opacity"] == pytest.approx(
        0.2
    )
    group.visible = False
    assert not MapProjector(data).frame("new", 0)["points"]
    group.visible = True
    node.min_zoom = 2
    assert not MapProjector(data).frame("new", 0)["points"]


@pytest.mark.parametrize(
    "date,expected", [(-1, 0.3), (0, 0.2), (5, 0.5), (10, 0.8), (20, 0.8)]
)
def test_trajectory_is_resolved_at_playhead_before_projection(date, expected):
    data = snapshot()
    data.tracks["point"] = [
        ([Keyframe(0, 0.2, 0.6, "a"), Keyframe(10, 0.8, 0.6, "b")], {})
    ]
    assert MapProjector(data).frame("new", date)["points"][0]["x"] == pytest.approx(
        expected
    )
    data.tracks["point"][0][1][("a", "b")] = "step"
    assert MapProjector(data).frame("new", 5)["points"][0]["x"] == pytest.approx(0.2)


def test_multiple_trajectories_and_broken_alignment_are_not_static_fallbacks():
    data = snapshot()
    data.tracks["point"] = [([], {}), ([], {})]
    frame = MapProjector(data).frame("new", 0)
    assert not frame["points"] and "Multiple" in frame["issues"][0]
    data.maps[1].attributes["registration"]["scale_norm"] = 0
    frame = MapProjector(data).frame("new", 0)
    assert not frame["points"] and frame["issues"]
    data.maps[1].attributes["registration"] = deepcopy(
        data.maps[2].attributes["registration"]
    )
    data.markers.append(Marker("old", "object", "entity", 0.3, 0.6, id="other"))
    assert not MapProjector(data).frame("new", 0)["points"]


def test_large_point_frame_and_fit_ratio_policy():
    data = snapshot()
    data.markers = [
        Marker("old", f"object-{i}", "entity", 0.3, 0.6, id=f"m-{i}")
        for i in range(2000)
    ]
    assert len(MapProjector(data).frame("new", 0)["points"]) == 2000
    node = MapLayerNode(
        "Location",
        id="m-0",
        layer_type="marker",
        min_zoom=2,
        attributes={"zoom_basis": "fit_ratio"},
    )
    data.maps[1].layers = MapLayerNode("Root", children=[node])
    frame = MapProjector(data).frame("new", 0, zoom=0.2, fit_ratio=3)
    assert any(p["source_id"] == "m-0" for p in frame["points"])
