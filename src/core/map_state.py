"""Serializable map-aggregate and raster-state value objects."""

from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RasterSnapshotRef:
    """A raster state that becomes effective at a lore date."""

    lore_date: float
    file_path: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the snapshot reference."""
        return {"lore_date": self.lore_date, "file_path": self.file_path}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RasterSnapshotRef":
        """Deserialize a snapshot reference."""
        return cls(
            lore_date=float(data["lore_date"]),
            file_path=str(data["file_path"]),
        )


@dataclass
class RasterLayerState:
    """Canonical raster metadata with legacy-dictionary compatibility."""

    node_id: str
    file_path: str
    resolution: tuple[int, int]
    mode: str
    snapshots: list[RasterSnapshotRef] = field(default_factory=list)
    color_map: dict[str, Any] = field(default_factory=dict)
    value_entity_map: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 2
    extra: dict[str, Any] = field(default_factory=dict)
    _legacy_raw: Optional[dict[str, Any]] = field(
        default=None, repr=False, compare=False
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize using the existing map-attribute storage shape."""
        if self.schema_version < 2 and self._legacy_raw is not None:
            return dict(self._legacy_raw)
        data = dict(self.extra)
        data.update(
            {
                "node_id": self.node_id,
                "file_path": self.file_path,
                "resolution": list(self.resolution),
                "mode": self.mode,
                "snapshots": {
                    format(ref.lore_date, ".17g"): ref.file_path
                    for ref in self.snapshots
                },
                "color_map": dict(self.color_map),
                "value_entity_map": dict(self.value_entity_map),
                "schema_version": self.schema_version,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RasterLayerState":
        """Load version-two or legacy raster metadata."""
        known = {
            "node_id",
            "file_path",
            "resolution",
            "mode",
            "snapshots",
            "color_map",
            "value_entity_map",
            "schema_version",
        }
        raw_snapshots = data.get("snapshots", {})
        snapshots: list[RasterSnapshotRef] = []
        if isinstance(raw_snapshots, dict):
            for raw_date, path in raw_snapshots.items():
                try:
                    snapshots.append(
                        RasterSnapshotRef(float(raw_date), str(path))
                    )
                except (TypeError, ValueError):
                    continue
        snapshots.sort(key=lambda ref: ref.lore_date)
        raw_resolution = data.get("resolution", [0, 0])
        schema_version = int(data.get("schema_version", 1))
        return cls(
            node_id=str(data.get("node_id", "")),
            file_path=str(data.get("file_path", "")),
            resolution=(int(raw_resolution[0]), int(raw_resolution[1])),
            mode=str(data.get("mode", "discrete")),
            snapshots=snapshots,
            color_map=dict(data.get("color_map", {})),
            value_entity_map=dict(data.get("value_entity_map", {})),
            schema_version=schema_version,
            extra={key: value for key, value in data.items() if key not in known},
            _legacy_raw=dict(data) if schema_version < 2 else None,
        )

    def resolve_file(self, lore_date: float) -> str:
        """Return the latest state at or before ``lore_date``."""
        eligible = [
            ref for ref in self.snapshots if ref.lore_date <= lore_date
        ]
        if not eligible:
            return self.file_path
        return max(eligible, key=lambda ref: ref.lore_date).file_path


@dataclass(frozen=True)
class RasterPatch:
    """Immutable compressed before/after raster region."""

    map_id: str
    node_id: str
    target_file: str
    region: tuple[int, int, int, int]
    shape: tuple[int, ...]
    dtype: str
    before_data: bytes
    after_data: bytes

    @staticmethod
    def _encode(raw: bytes) -> str:
        return base64.b64encode(zlib.compress(raw)).decode("ascii")

    @staticmethod
    def _decode(raw: str) -> bytes:
        return zlib.decompress(base64.b64decode(raw.encode("ascii")))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the patch without GUI-owned objects."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "target_file": self.target_file,
            "region": list(self.region),
            "shape": list(self.shape),
            "dtype": self.dtype,
            "before_data": self._encode(self.before_data),
            "after_data": self._encode(self.after_data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RasterPatch":
        """Deserialize a patch."""
        region_values = [int(v) for v in data["region"]]
        shape_values = [int(v) for v in data["shape"]]
        if len(region_values) != 4 or len(shape_values) not in (2, 3):
            raise ValueError("Invalid raster patch dimensions")
        return cls(
            map_id=str(data["map_id"]),
            node_id=str(data["node_id"]),
            target_file=str(data["target_file"]),
            region=(
                region_values[0],
                region_values[1],
                region_values[2],
                region_values[3],
            ),
            shape=tuple(shape_values),
            dtype=str(data["dtype"]),
            before_data=cls._decode(str(data["before_data"])),
            after_data=cls._decode(str(data["after_data"])),
        )


@dataclass(frozen=True)
class MapCalibration:
    """Optional physical scale for a map."""

    width_meters: Optional[float] = None

    def __post_init__(self) -> None:
        if self.width_meters is not None and self.width_meters <= 0:
            raise ValueError("width_meters must be positive or None")

    def to_dict(self) -> dict[str, Optional[float]]:
        """Serialize calibration."""
        return {"width_meters": self.width_meters}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MapCalibration":
        """Deserialize calibration."""
        value = data.get("width_meters")
        return cls(None if value is None else float(value))


@dataclass
class LayerSubtreeSnapshot:
    """Complete reversible state for one deleted layer subtree."""

    parent_id: str
    row: int
    node: dict[str, Any]
    markers: list[dict[str, Any]] = field(default_factory=list)
    trajectories: list[dict[str, Any]] = field(default_factory=list)
    raster_layers: list[dict[str, Any]] = field(default_factory=list)
    raster_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the subtree snapshot."""
        return {
            "parent_id": self.parent_id,
            "row": self.row,
            "node": self.node,
            "markers": self.markers,
            "trajectories": self.trajectories,
            "raster_layers": self.raster_layers,
            "raster_files": self.raster_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerSubtreeSnapshot":
        """Deserialize a subtree snapshot."""
        return cls(
            parent_id=str(data["parent_id"]),
            row=int(data["row"]),
            node=dict(data["node"]),
            markers=list(data.get("markers", [])),
            trajectories=list(data.get("trajectories", [])),
            raster_layers=list(data.get("raster_layers", [])),
            raster_files=[str(path) for path in data.get("raster_files", [])],
        )


@dataclass
class MapAggregateSnapshot:
    """Complete reversible database state for a map."""

    map_data: dict[str, Any]
    markers: list[dict[str, Any]] = field(default_factory=list)
    trajectories: list[dict[str, Any]] = field(default_factory=list)
    raster_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the aggregate snapshot."""
        return {
            "map_data": self.map_data,
            "markers": self.markers,
            "trajectories": self.trajectories,
            "raster_files": self.raster_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MapAggregateSnapshot":
        """Deserialize an aggregate snapshot."""
        return cls(
            map_data=dict(data["map_data"]),
            markers=list(data.get("markers", [])),
            trajectories=list(data.get("trajectories", [])),
            raster_files=[str(path) for path in data.get("raster_files", [])],
        )
