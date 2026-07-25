"""Worker-side raster file persistence with path and write safety."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Iterable

from src.core.map_state import RasterLayerState


class RasterAssetService:
    """Own raster paths and atomic file replacement within one world."""

    def __init__(self, world_root: Path) -> None:
        self.world_root = world_root.resolve()
        self.raster_root = (self.world_root / "rasters").resolve()

    def resolve(self, relative_path: str) -> Path:
        """Resolve a portable raster path and reject world-root escapes."""
        path = (self.world_root / relative_path).resolve()
        if not path.is_relative_to(self.world_root):
            raise ValueError(f"Raster path escapes world root: {relative_path}")
        return path

    def atomic_write_bytes(self, relative_path: str, data: bytes) -> None:
        """Write bytes using a same-directory temporary file and replacement."""
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def allocate_snapshot_path(self, node_id: str) -> str:
        """Return a collision-resistant portable path for a dated raster state."""
        filename = f"{uuid.uuid4()}.png"
        return f"rasters/snapshots/{node_id}/{filename}"

    @staticmethod
    def owned_files(layer: RasterLayerState) -> list[str]:
        """Return the base and dated-state files owned by a raster layer."""
        return list(
            dict.fromkeys(
                [
                    layer.file_path,
                    *(snapshot.file_path for snapshot in layer.snapshots),
                ]
            )
        )

    @staticmethod
    def owned_files_from_metadata(
        raster_layers: Iterable[dict[str, object]],
    ) -> list[str]:
        """Collect owned files from version-two or legacy metadata."""
        files: list[str] = []
        for metadata in raster_layers:
            layer = RasterLayerState.from_dict(dict(metadata))
            files.extend(RasterAssetService.owned_files(layer))
        return list(dict.fromkeys(path for path in files if path))

