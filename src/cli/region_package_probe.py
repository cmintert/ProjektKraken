"""Offline packaged geometry probe owning an isolated temporary database."""

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from src.commands.neighbor_region_command import CreateNeighborRegionCommand
from src.core.feature_geometry_state import (
    FeatureGeometryState,
    resolve_feature_geometry,
)
from src.core.map import Map
from src.core.marker import Marker
from src.core.region_geometry import RegionPolygon, cut_region, feature_anchor
from src.core.spatial_geometry import SpatialGeometry, relate_geometries
from src.services.db_service import DatabaseService

_CUT_DATE = 1220.0
_LATER_DATE = 1250.0
_REGION_ID = "package-probe-region"


def probe_region_geometry() -> dict[str, object]:
    """Cut, store, reopen and resolve a dated lake in a temporary database."""
    shore = RegionPolygon(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)))
    lake = RegionPolygon(((0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)))
    result = cut_region(shore, lake)
    if result.status != "ready" or len(result.polygons[0].holes) != 1:
        raise RuntimeError(f"Packaged lake cut failed: {result.explanation}")
    with TemporaryDirectory(prefix="kraken-region-probe-") as temp:
        db_path = str(Path(temp) / "lake.kraken")
        _store_fixture(db_path, shore, result.polygons[0])
        relations = _reopen_fixture(db_path)
    if relations != ("inside", "separate", "inside"):
        raise RuntimeError(f"Packaged dated lake failed after reopening: {relations}")
    return {
        "holes": 1,
        "reopened": True,
        "lake_center_relations": relations,
        "neighbor_creation": True,
    }


def _store_fixture(db_path: str, shore: RegionPolygon, carved: RegionPolygon) -> None:
    with closing(DatabaseService(db_path)) as service:
        service.connect()
        map_obj = Map(name="Region geometry probe", image_path="probe.png")
        service.insert_map(map_obj)
        marker = Marker(
            id=_REGION_ID,
            map_id=map_obj.id,
            object_id=_REGION_ID,
            object_type="entity",
            x=0.5,
            y=0.5,
            feature_type="region",
            geometry=shore.to_geometry(),
        )
        service.insert_marker(marker)
        states = []
        for date, polygon in ((_CUT_DATE, carved), (_LATER_DATE, shore)):
            geometry = polygon.to_geometry()
            x, y = feature_anchor(geometry)
            states.append(FeatureGeometryState(marker.id, date, geometry, x, y))
        service.feature_geometry_repo.replace_marker_states(marker.id, states)
        _create_neighbor(service, marker, carved)


def _create_neighbor(
    service: DatabaseService, source: Marker, polygon: RegionPolygon
) -> None:
    """Exercise the packaged guarded command, exact border, undo and redo."""
    outline = RegionPolygon(((0.7, 0.3), (0.9, 0.3), (0.9, 0.7), (0.7, 0.7)))
    result = cut_region(outline, polygon)
    if result.status != "ready":
        raise RuntimeError("Packaged neighboring-region difference failed.")
    geometry = result.polygons[0].to_geometry()
    x, y = feature_anchor(geometry)
    command = CreateNeighborRegionCommand(
        {
            "id": "package-probe-neighbor",
            "map_id": source.map_id,
            "object_id": "package-probe-neighbor",
            "object_type": "entity",
            "feature_type": "region",
            "geometry": geometry,
            "x": x,
            "y": y,
        },
        source.id,
        _CUT_DATE,
        polygon.to_geometry(),
    )
    if not command.execute(service).success:
        raise RuntimeError("Packaged neighboring-region creation failed.")
    command = CreateNeighborRegionCommand.from_dict(command.to_dict())
    command.undo(service)
    if not command.execute(service).success:
        raise RuntimeError("Packaged neighboring-region redo failed.")


def _reopen_fixture(db_path: str) -> tuple[str, ...]:
    with closing(DatabaseService(db_path, read_only=True)) as service:
        service.connect()
        marker = service.get_marker(_REGION_ID)
        if marker is None:
            raise RuntimeError("Packaged region fixture did not reopen.")
        neighbor = service.get_marker("package-probe-neighbor")
        if neighbor is None or neighbor.geometry is None:
            raise RuntimeError("Packaged neighboring region did not reopen.")
        shape = RegionPolygon.from_geometry(neighbor.geometry).validated()
        original = RegionPolygon.from_geometry(marker.geometry or []).validated()
        if (
            shape.intersection(original).area != 0
            or shape.bounds[0] != original.bounds[2]
        ):
            raise RuntimeError("Packaged shared border did not survive reopening.")
        states = service.feature_geometry_repo.get_states(marker.id)
        center = SpatialGeometry("point", ((0.5, 0.5),))
        relations = []
        for date in (_CUT_DATE - 1.0, _CUT_DATE, _LATER_DATE):
            active = resolve_feature_geometry(marker, states, date)
            geometry = SpatialGeometry.from_feature(
                marker.feature_type, active.anchor_x, active.anchor_y, active.geometry
            )
            if geometry is None:
                raise RuntimeError(f"Invalid packaged region fixture at date {date:g}.")
            relations.append(relate_geometries(center, geometry).kind)
        return tuple(relations)
