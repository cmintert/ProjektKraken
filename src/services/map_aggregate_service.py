"""Worker-owned loading and validation of complete map state."""

from __future__ import annotations

from pathlib import Path

from src.core.map_state import MapAggregateSnapshot, RasterLayerState
from src.services.db_service import DatabaseService
from src.services.raster_asset_service import RasterAssetService


class MapAggregateService:
    """Load map state required for safe destructive commands."""

    def __init__(self, db_service: DatabaseService) -> None:
        self.db_service = db_service

    def snapshot(self, map_id: str) -> MapAggregateSnapshot:
        """Capture a map, markers, trajectories, and raster file manifest."""
        map_obj = self.db_service.map_repo.get_map(map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {map_id}")

        markers = self.db_service.get_markers_for_map(map_id)
        marker_data = [marker.to_dict() for marker in markers]
        trajectories: list[dict[str, object]] = []
        for marker in markers:
            trajectories.extend(
                self.db_service.trajectory_repo.snapshot_by_marker(marker.id)
            )

        raster_metadata = (map_obj.attributes or {}).get("raster_layers", [])
        raster_files = RasterAssetService.owned_files_from_metadata(raster_metadata)
        world_root = Path(self.db_service.get_db_file_path()).resolve().parent
        image_path = (world_root / map_obj.image_path).resolve()
        if (
            map_obj.image_path
            and image_path.is_relative_to(world_root)
            and image_path.exists()
        ):
            raster_files.insert(
                0,
                image_path.relative_to(world_root).as_posix(),
            )
        return MapAggregateSnapshot(
            map_data=map_obj.to_dict(),
            markers=marker_data,
            trajectories=trajectories,
            raster_files=raster_files,
        )

    def validate(self, map_id: str) -> list[str]:
        """Return aggregate consistency errors without changing the world."""
        map_obj = self.db_service.map_repo.get_map(map_id)
        if map_obj is None:
            return [f"Map not found: {map_id}"]

        errors: list[str] = []
        raster_metadata = (map_obj.attributes or {}).get("raster_layers", [])
        states = [RasterLayerState.from_dict(dict(item)) for item in raster_metadata]
        metadata_ids = {state.node_id for state in states}

        raster_node_ids: set[str] = set()

        def collect(node: object) -> None:
            if getattr(node, "layer_type", "") == "raster":
                raster_node_ids.add(str(getattr(node, "id")))
            for child in getattr(node, "children", []):
                collect(child)

        if map_obj.layers is not None:
            collect(map_obj.layers)
        for node_id in sorted(raster_node_ids - metadata_ids):
            errors.append(f"Raster node has no metadata: {node_id}")
        for node_id in sorted(metadata_ids - raster_node_ids):
            errors.append(f"Raster metadata has no layer node: {node_id}")
        return errors
