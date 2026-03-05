"""Commands for raster (heatmap) layer operations.

Handles creation, deletion, and painting on raster layers.
Raster metadata is persisted inside ``maps.attributes["raster_layers"]``
and the pixel data lives in 16-bit PNG files on disk.
"""

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.app.constants import MAP_LAYER_TYPE_RASTER
from src.commands.base_command import BaseCommand, CommandResult
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


def _get_raster_layers(map_obj: Any) -> List[Dict[str, Any]]:
    """Extract the raster_layers list from a Map's attributes."""
    attrs = map_obj.attributes or {}
    return list(attrs.get("raster_layers", []))


def _set_raster_layers(map_obj: Any, raster_layers: List[Dict[str, Any]]) -> None:
    """Write the raster_layers list back into a Map's attributes."""
    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
    attrs["raster_layers"] = raster_layers
    map_obj.attributes = attrs


class CreateRasterLayerCommand(BaseCommand):
    """Create a new raster layer: blank PNG, layer node, and metadata.

    On execute, the command:
    1. Creates a blank 16-bit PNG in ``<world>/rasters/``.
    2. Adds a :class:`MapLayerNode` (type ``"raster"``) to the layer tree.
    3. Appends raster metadata to ``maps.attributes["raster_layers"]``.

    Args:
        map_id: ID of the parent map.
        name: Human-readable layer name.
        width: Buffer width in pixels.
        height: Buffer height in pixels.
        mode: ``"discrete"`` or ``"continuous"``.
        default_value: Initial fill value (0–65535).
        world_root: Absolute path to the world directory (for file storage).

    """

    def __init__(
        self,
        map_id: str,
        name: str,
        width: int,
        height: int,
        mode: str = "discrete",
        default_value: int = 0,
        world_root: str = "",
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.name = name
        self.width = width
        self.height = height
        self.mode = mode
        self.default_value = default_value
        self.world_root = world_root

        # Generated on execute
        self._node_id: str = str(uuid.uuid4())
        self._file_path: str = ""

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Create the raster file, layer node, and persist metadata.

        Args:
            db_service: The database service.

        Returns:
            CommandResult with ``data["node_id"]`` and ``data["file_path"]``.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="CreateRasterLayerCommand",
                )

            # 1. Create blank buffer and save to disk
            buf = MapDataBuffer(self.width, self.height, self.default_value)
            raster_dir = Path(self.world_root) / "rasters"
            raster_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{self.name.replace(' ', '_')}_{self._node_id[:8]}.png"
            abs_path = raster_dir / filename
            buf.save(str(abs_path))

            # Store relative path from world root
            self._file_path = f"rasters/{filename}"

            # 2. Add layer node to tree
            node = MapLayerNode(
                name=self.name,
                layer_type=MAP_LAYER_TYPE_RASTER,
                id=self._node_id,
            )
            if map_obj.layers is None:
                from src.app.constants import MAP_LAYER_TYPE_GROUP

                map_obj.layers = MapLayerNode(
                    name="Root", layer_type=MAP_LAYER_TYPE_GROUP
                )
            map_obj.layers.children.append(node)

            # 3. Update raster metadata
            raster_layers = _get_raster_layers(map_obj)
            now = time.time()
            raster_meta: Dict[str, Any] = {
                "node_id": self._node_id,
                "file_path": self._file_path,
                "resolution": [self.width, self.height],
                "mode": self.mode,
                "default_value": self.default_value,
                "value_entity_map": {},
                "color_map": ColorMap().to_dict(),
                "created_at": now,
                "modified_at": now,
            }
            raster_layers.append(raster_meta)
            _set_raster_layers(map_obj, raster_layers)

            # 4. Persist layer tree
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            logger.info(
                "Created raster layer '%s' (%s) at %s",
                self.name,
                self._node_id,
                self._file_path,
            )
            return CommandResult(
                success=True,
                message=f"Raster layer '{self.name}' created.",
                command_name="CreateRasterLayerCommand",
                data={
                    "node_id": self._node_id,
                    "file_path": self._file_path,
                },
            )
        except Exception as e:
            logger.error("CreateRasterLayerCommand failed: %s", e)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="CreateRasterLayerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Remove the raster layer, its node, and delete the file.

        Args:
            db_service: The database service.

        """
        if not self._is_executed:
            return
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj:
                # Remove layer node
                if map_obj.layers:
                    map_obj.layers.children = [
                        c for c in map_obj.layers.children if c.id != self._node_id
                    ]
                # Remove raster metadata
                raster_layers = _get_raster_layers(map_obj)
                raster_layers = [
                    r for r in raster_layers if r.get("node_id") != self._node_id
                ]
                _set_raster_layers(map_obj, raster_layers)

                attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                attrs["layers"] = map_obj.layers.to_dict() if map_obj.layers else {}
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)

            # Delete file
            if self._file_path and self.world_root:
                abs_path = Path(self.world_root) / self._file_path
                if abs_path.exists():
                    abs_path.unlink()

            self._is_executed = False
            logger.info("Undid raster layer creation: %s", self._node_id)
        except Exception as e:
            logger.error("Undo CreateRasterLayerCommand failed: %s", e)

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "default_value": self.default_value,
            "world_root": self.world_root,
            "node_id": self._node_id,
            "file_path": self._file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CreateRasterLayerCommand":
        """Deserialize command from dictionary."""
        cmd = cls(
            map_id=data["map_id"],
            name=data["name"],
            width=data["width"],
            height=data["height"],
            mode=data.get("mode", "discrete"),
            default_value=data.get("default_value", 0),
            world_root=data.get("world_root", ""),
        )
        cmd._node_id = data.get("node_id", cmd._node_id)
        cmd._file_path = data.get("file_path", "")
        return cmd


class DeleteRasterLayerCommand(BaseCommand):
    """Delete a raster layer: remove node, metadata, and file.

    Args:
        map_id: ID of the parent map.
        node_id: Layer node ID of the raster to delete.
        world_root: Absolute path to the world directory.

    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        world_root: str = "",
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.world_root = world_root

        # Stored for undo
        self._deleted_meta: Optional[Dict[str, Any]] = None
        self._deleted_node_dict: Optional[Dict[str, Any]] = None
        self._file_backup: Optional[bytes] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Delete the raster layer.

        Args:
            db_service: The database service.

        Returns:
            CommandResult.

        """
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="DeleteRasterLayerCommand",
                )

            # Find and remove the raster metadata
            raster_layers = _get_raster_layers(map_obj)
            self._deleted_meta = None
            new_raster_layers = []
            for r in raster_layers:
                if r.get("node_id") == self.node_id:
                    self._deleted_meta = r
                else:
                    new_raster_layers.append(r)
            _set_raster_layers(map_obj, new_raster_layers)

            # Find and remove the layer node
            if map_obj.layers:
                for i, c in enumerate(map_obj.layers.children):
                    if c.id == self.node_id:
                        self._deleted_node_dict = c.to_dict()
                        map_obj.layers.children.pop(i)
                        break

            # Backup and delete file
            if self._deleted_meta and self.world_root:
                file_path = self._deleted_meta.get("file_path", "")
                abs_path = Path(self.world_root) / file_path
                if abs_path.exists():
                    self._file_backup = abs_path.read_bytes()
                    abs_path.unlink()

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            if map_obj.layers:
                attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Raster layer deleted.",
                command_name="DeleteRasterLayerCommand",
            )
        except Exception as e:
            logger.error("DeleteRasterLayerCommand failed: %s", e)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="DeleteRasterLayerCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the deleted raster layer.

        Args:
            db_service: The database service.

        """
        if not self._is_executed:
            return
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                return

            # Restore layer node
            if self._deleted_node_dict and map_obj.layers:
                node = MapLayerNode.from_dict(self._deleted_node_dict)
                map_obj.layers.children.append(node)

            # Restore metadata
            if self._deleted_meta:
                raster_layers = _get_raster_layers(map_obj)
                raster_layers.append(self._deleted_meta)
                _set_raster_layers(map_obj, raster_layers)

            # Restore file
            if self._file_backup and self._deleted_meta and self.world_root:
                file_path = self._deleted_meta.get("file_path", "")
                abs_path = Path(self.world_root) / file_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(self._file_backup)

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            if map_obj.layers:
                attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)

            self._is_executed = False
        except Exception as e:
            logger.error("Undo DeleteRasterLayerCommand failed: %s", e)

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "world_root": self.world_root,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DeleteRasterLayerCommand":
        """Deserialize command from dictionary."""
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            world_root=data.get("world_root", ""),
        )


class PaintRasterCommand(BaseCommand):
    """Undoable brush paint operation on a raster buffer.

    Stores a snapshot of the affected region before painting so that
    :meth:`undo` can restore it.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        center_x: Normalised X of brush centre [0, 1].
        center_y: Normalised Y of brush centre [0, 1].
        radius_px: Brush radius in buffer pixels.
        value: Paint value (0–65535).
        falloff: 0.0 = hard, 1.0 = full linear falloff.

    Note:
        The ``buffer`` is injected at execution time by the caller
        (MapHandler / MapGraphicsView) — it is **not** serialised.
        This command is intended for in-session undo/redo only.

    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        center_x: float,
        center_y: float,
        radius_px: int,
        value: int,
        falloff: float = 0.0,
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.center_x = center_x
        self.center_y = center_y
        self.radius_px = radius_px
        self.value = value
        self.falloff = falloff

        # Set by caller before execute
        self.buffer: Optional[MapDataBuffer] = None

        # Snapshot for undo
        self._before: Optional[np.ndarray] = None
        self._dirty_region: Optional[tuple] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Paint the brush stroke and snapshot the dirty region.

        Args:
            db_service: The database service (unused for paint, but required
                by the command interface).

        Returns:
            CommandResult.

        """
        if self.buffer is None:
            return CommandResult(
                success=False,
                message="No buffer attached.",
                command_name="PaintRasterCommand",
            )
        try:
            # Pre-compute dirty region for snapshot
            cx, cy = self.buffer._norm_to_pixel(self.center_x, self.center_y)
            r = max(1, self.radius_px)
            min_col = max(0, cx - r)
            max_col = min(self.buffer.width - 1, cx + r)
            min_row = max(0, cy - r)
            max_row = min(self.buffer.height - 1, cy + r)

            self._dirty_region = (min_col, min_row, max_col, max_row)
            self._before = self.buffer.get_region(min_col, min_row, max_col, max_row)

            self.buffer.paint_brush(
                self.center_x,
                self.center_y,
                self.radius_px,
                self.value,
                self.falloff,
            )

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Paint applied.",
                command_name="PaintRasterCommand",
            )
        except Exception as e:
            logger.error("PaintRasterCommand failed: %s", e)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="PaintRasterCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the pre-paint region.

        Args:
            db_service: The database service.

        """
        if (
            self._is_executed
            and self.buffer is not None
            and self._before is not None
            and self._dirty_region is not None
        ):
            min_col, min_row, _max_col, _max_row = self._dirty_region
            self.buffer.set_region(min_col, min_row, self._before)
            self._is_executed = False

    @property
    def has_history(self) -> bool:
        """Paint commands are not persisted to command history files."""
        return False

    def to_dict(self) -> Dict:
        """Serialize (minimal — paint ops are session-only)."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius_px": self.radius_px,
            "value": self.value,
            "falloff": self.falloff,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PaintRasterCommand":
        """Deserialize command from dictionary."""
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            center_x=data["center_x"],
            center_y=data["center_y"],
            radius_px=data["radius_px"],
            value=data["value"],
            falloff=data.get("falloff", 0.0),
        )
