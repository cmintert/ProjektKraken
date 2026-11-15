"""Regression coverage for traced borders and dated excluded areas."""

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.cli.region_package_probe import probe_region_geometry
from src.commands.feature_geometry_commands import ReplaceFeatureGeometryStatesCommand
from src.core.border_trace import RingPosition, border_routes, simple_draft
from src.core.feature_geometry_state import (
    FeatureGeometryState,
    calculate_feature_anchor,
    resolve_feature_geometry,
)
from src.core.map import Map
from src.core.marker import Marker
from src.core.region_geometry import RegionPolygon, cut_region
from src.core.spatial_geometry import SpatialGeometry, relate_geometries
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.services.raster_image_analysis import sample_raster_region_semantics

pytestmark = pytest.mark.ci_fast


def test_package_probe_reopens_a_real_database():
    assert probe_region_geometry()["lake_center_relations"] == (
        "inside",
        "separate",
        "inside",
    )


def _rectangle(x0, y0, x1, y1):
    return RegionPolygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def test_trace_preserves_bends_in_both_directions_and_checks_the_connection():
    ring = ((0.1, 0.1), (0.8, 0.1), (0.8, 0.4), (0.5, 0.4), (0.5, 0.9), (0.1, 0.9))
    direct, other = border_routes(
        ring, RingPosition(0, 0), RingPosition(5, 0.5), 200, 100
    )
    assert direct == ((0.1, 0.1), (0.1, 0.5))
    assert other == (*ring, (0.1, 0.5))
    assert simple_draft(other)
    assert not simple_draft(((0.9, 0.2), (0.3, 0.7), *other))
    assert not simple_draft(
        ((0.1, 0.1), (0.9, 0.7), (0.9, 0.1), (0.1, 0.7)), closed=True
    )
    same_edge = border_routes(
        ring, RingPosition(5, 0.25), RingPosition(5, 0.75), 200, 100
    )
    assert len(same_edge[0]) == 2
    assert len(same_edge[1]) == 8
    assert not border_routes(ring, RingPosition(5, 1), RingPosition(0, 0), 200, 100)


@pytest.mark.parametrize(
    ("cutter", "status", "pieces"),
    [
        (_rectangle(0.3, 0.3, 0.7, 0.7), "ready", 1),
        (_rectangle(0.75, 0.35, 1, 0.65), "ready", 1),
        (_rectangle(0.9, 0.3, 1, 0.7), "unchanged", 1),
        (_rectangle(0.2, 0.1000000001, 0.8, 0.8), "ready", 1),
        (_rectangle(0.45, 0, 0.55, 1), "split", 2),
        (_rectangle(0, 0, 1, 1), "empty", 0),
        (RegionPolygon(((0.1, 0.5), (0.3, 0.3), (0.4, 0.5), (0.3, 0.7))), "invalid", 1),
    ],
)
def test_cut_preserves_all_outcomes(cutter, status, pieces):
    result = cut_region(_rectangle(0.1, 0.1, 0.9, 0.9), cutter)
    assert result.status == status
    assert len(result.polygons) == pieces


def test_cut_uses_filled_area_of_a_cutter_with_holes():
    city = _rectangle(0.2, 0.2, 0.8, 0.8)
    park = _rectangle(0.3, 0.3, 0.7, 0.7)
    target = _rectangle(0.1, 0.1, 0.9, 0.9)
    cutter = RegionPolygon(city.outer, (park.outer,))
    result = cut_region(target, cutter)
    assert result.status == "split"
    assert sorted(part.area for part in result.polygons) == pytest.approx(
        [park.area, target.area - city.area]
    )
    carved = cut_region(target, city).polygons[0]
    assert cut_region(carved, park).status == "unchanged"


def test_dated_lake_roundtrips_and_agrees_across_geometry_consumers(
    db_service, tmp_path, qapp, init_theme_manager
):
    map_obj = Map(name="Map", image_path="map.png")
    db_service.insert_map(map_obj)
    shore = _rectangle(0.2, 0.2, 0.8, 0.8)
    lake = _rectangle(0.4, 0.4, 0.6, 0.6)
    marker = Marker(
        id="region",
        map_id=map_obj.id,
        object_id="region",
        object_type="entity",
        x=0.5,
        y=0.5,
        feature_type="region",
        geometry=shore.to_geometry(),
    )
    db_service.insert_marker(marker)
    carved = cut_region(shore, lake).polygons[0]
    x, y = calculate_feature_anchor(carved.to_geometry())
    revision = FeatureGeometryState(marker.id, 1220, carved.to_geometry(), x, y)
    later = FeatureGeometryState(marker.id, 1250, shore.to_geometry(), 0.5, 0.5)
    repo = db_service.feature_geometry_repo
    before = repo.replace_marker_states(marker.id, [later])
    command = ReplaceFeatureGeometryStatesCommand(
        map_obj.id, marker.id, before, [revision.to_dict(), *before], "Cut area"
    )
    assert command.execute(db_service).success
    assert len(repo.get_states(marker.id)) == 2
    saved = db_service.get_marker(marker.id)
    assert saved is not None
    states = repo.get_states(marker.id)
    assert resolve_feature_geometry(saved, states, 1219).geometry == shore.to_geometry()
    assert resolve_feature_geometry(saved, states, 1250).geometry == shore.to_geometry()
    active = resolve_feature_geometry(saved, states, 1220)
    assert RegionPolygon.from_geometry(active.geometry) == carved
    assert command.undo(db_service).success
    assert len(repo.get_states(marker.id)) == 1
    assert command.execute(db_service).success

    active_marker = Marker.from_dict({**saved.to_dict(), "geometry": active.geometry})
    assert active_marker.compute_area() == pytest.approx(0.32)
    assert active_marker.compute_perimeter() == pytest.approx(3.2)
    region = SpatialGeometry.from_feature("region", x, y, active.geometry)
    assert region is not None
    assert (
        relate_geometries(SpatialGeometry("point", ((0.5, 0.5),)), region).kind
        == "separate"
    )
    assert (
        relate_geometries(SpatialGeometry("point", ((0.4, 0.5),)), region).kind
        == "touches"
    )
    assert (
        relate_geometries(SpatialGeometry("region", lake.outer), region).kind
        == "touches"
    )
    path = SpatialGeometry("path", ((0.3, 0.5), (0.7, 0.5)))
    assert relate_geometries(path, region).kind == "crosses"

    values = np.ones((101, 101), dtype=np.uint8)
    values[43:57, 43:57] = 2
    raster = tmp_path / "terrain.png"
    Image.fromarray(values).save(raster)
    mapping = {
        "mode": "exact",
        "mappings": [
            {"id": "land", "label": "Land", "value": 1},
            {"id": "water", "label": "Water", "value": 2},
        ],
    }
    assert (
        sample_raster_region_semantics(
            str(raster), region.points, mapping, holes=region.holes
        )
        == "Land 100%"
    )

    view = MapGraphicsView()
    view.pixmap_item = QGraphicsPixmapItem(QPixmap(1000, 1000))
    view.graphics_scene.addItem(view.pixmap_item)
    view.add_marker(
        "region",
        "entity",
        "Region",
        x,
        y,
        feature_type="region",
        geometry=active.geometry,
    )
    view.add_marker(
        "city",
        "entity",
        "City",
        0.5,
        0.5,
        feature_type="region",
        geometry=lake.to_geometry(),
    )
    item = view.feature_items["region"]
    assert item not in view.graphics_scene.items(QPointF(500, 500))
    assert view.feature_items["city"] in view.graphics_scene.items(QPointF(500, 500))
    snap = view._snapping_manager.snap_point(
        QPointF(400, 500), QTransform(), {view.feature_items["city"]}
    )
    assert snap.snapped and snap.ring_index == 1
    editor = view._vertex_editor
    editor.start_vertex_editing(item, managed_session=True)
    assert len(editor._midpoint_handles) == len(editor._vertex_handles) == 8
    editor._on_vertex_moved(4, QPointF(410, 410))
    edited = RegionPolygon.from_geometry(item._geometry)
    assert edited.outer == carved.outer
    assert edited.holes[0][0] == (0.41, 0.41)
    editor.cancel_vertex_editing()
    assert RegionPolygon.from_geometry(item._geometry) == carved
