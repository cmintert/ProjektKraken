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
from src.gui.widgets.map.raster_mapping import make_empty_vem, validate_no_overlaps
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
        logger.debug(
            "CreateRasterLayerCommand.execute: map_id=%s name=%r size=%dx%d "
            "mode=%s default_value=%d world_root=%r",
            self.map_id,
            self.name,
            self.width,
            self.height,
            self.mode,
            self.default_value,
            self.world_root,
        )
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                logger.error("CreateRasterLayerCommand: map not found: %s", self.map_id)
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="CreateRasterLayerCommand",
                )
            logger.debug(
                "CreateRasterLayerCommand: got map %r (attrs keys=%s)",
                map_obj.name,
                list((map_obj.attributes or {}).keys()),
            )

            # 1. Create blank buffer and save to disk
            buf = MapDataBuffer(self.width, self.height, self.default_value)
            raster_dir = Path(self.world_root) / "rasters"
            raster_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{self.name.replace(' ', '_')}_{self._node_id[:8]}.png"
            abs_path = raster_dir / filename
            logger.debug("CreateRasterLayerCommand: saving PNG → %s", abs_path)
            buf.save(str(abs_path))
            logger.debug(
                "CreateRasterLayerCommand: PNG saved OK (%d bytes)",
                abs_path.stat().st_size if abs_path.exists() else -1,
            )

            # Store relative path from world root
            self._file_path = f"rasters/{filename}"

            # 2. Add layer node to tree
            node = MapLayerNode(
                name=self.name,
                layer_type=MAP_LAYER_TYPE_RASTER,
                id=self._node_id,
            )
            logger.debug(
                "CreateRasterLayerCommand: new layer node id=%s", self._node_id
            )
            if map_obj.layers is None:
                from src.app.constants import MAP_LAYER_TYPE_GROUP

                map_obj.layers = MapLayerNode(
                    name="Root", layer_type=MAP_LAYER_TYPE_GROUP
                )
                logger.debug("CreateRasterLayerCommand: created new root layer node")
            map_obj.layers.children.append(node)
            logger.debug(
                "CreateRasterLayerCommand: layer tree now has %d children",
                len(map_obj.layers.children),
            )

            # 3. Update raster metadata
            raster_layers = _get_raster_layers(map_obj)
            logger.debug(
                "CreateRasterLayerCommand: existing raster_layers count=%d",
                len(raster_layers),
            )
            now = time.time()
            raster_meta: Dict[str, Any] = {
                "node_id": self._node_id,
                "file_path": self._file_path,
                "resolution": [self.width, self.height],
                "mode": self.mode,
                "default_value": self.default_value,
                "value_entity_map": make_empty_vem(self.mode),
                "color_map": ColorMap(
                    type="gradient",
                    gradient_start="#00000000",
                    gradient_end="#FF000080",
                ).to_dict(),
                "created_at": now,
                "modified_at": now,
            }
            raster_layers.append(raster_meta)
            _set_raster_layers(map_obj, raster_layers)
            logger.debug(
                "CreateRasterLayerCommand: raster_layers now has %d entries",
                len(raster_layers),
            )

            # 4. Persist layer tree
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            logger.debug("CreateRasterLayerCommand: persisting map to DB")
            db_service.map_repo.insert_map(map_obj)
            logger.debug("CreateRasterLayerCommand: DB persist OK")

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
            logger.error("CreateRasterLayerCommand failed: %s", e, exc_info=True)
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
        logger.debug(
            "DeleteRasterLayerCommand.execute: map_id=%s node_id=%s world_root=%r",
            self.map_id,
            self.node_id,
            self.world_root,
        )
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                logger.error("DeleteRasterLayerCommand: map not found: %s", self.map_id)
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="DeleteRasterLayerCommand",
                )

            # Find and remove the raster metadata
            raster_layers = _get_raster_layers(map_obj)
            logger.debug(
                "DeleteRasterLayerCommand: raster_layers before=%d", len(raster_layers)
            )
            self._deleted_meta = None
            new_raster_layers = []
            for r in raster_layers:
                if r.get("node_id") == self.node_id:
                    self._deleted_meta = r
                    logger.debug(
                        "DeleteRasterLayerCommand: found meta for node_id=%s",
                        self.node_id,
                    )
                else:
                    new_raster_layers.append(r)
            _set_raster_layers(map_obj, new_raster_layers)

            # Find and remove the layer node
            if map_obj.layers:
                for i, c in enumerate(map_obj.layers.children):
                    if c.id == self.node_id:
                        self._deleted_node_dict = c.to_dict()
                        map_obj.layers.children.pop(i)
                        logger.debug(
                            "DeleteRasterLayerCommand: removed layer node at index %d",
                            i,
                        )
                        break

            # Backup and delete file
            if self._deleted_meta and self.world_root:
                file_path = self._deleted_meta.get("file_path", "")
                abs_path = Path(self.world_root) / file_path
                if abs_path.exists():
                    self._file_backup = abs_path.read_bytes()
                    abs_path.unlink()
                    logger.debug(
                        "DeleteRasterLayerCommand: deleted file %s (%d bytes backed up)",
                        abs_path,
                        len(self._file_backup),
                    )
                else:
                    logger.warning(
                        "DeleteRasterLayerCommand: file not found: %s", abs_path
                    )

            # Persist
            attrs = dict(map_obj.attributes) if map_obj.attributes else {}
            if map_obj.layers:
                attrs["layers"] = map_obj.layers.to_dict()
            map_obj.attributes = attrs
            db_service.map_repo.insert_map(map_obj)
            logger.debug("DeleteRasterLayerCommand: DB persist OK")

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Raster layer deleted.",
                command_name="DeleteRasterLayerCommand",
            )
        except Exception as e:
            logger.error("DeleteRasterLayerCommand failed: %s", e, exc_info=True)
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


class StrokeRasterCommand(BaseCommand):
    """Undoable region-snapshot command for completed raster strokes.

    Stores compressed before/after snapshots of the dirty region so
    that an entire brush drag, flood fill, or gradient operation can
    be undone in a single step.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        dirty_region: ``(min_col, min_row, max_col, max_row)``.
        before_bytes: Raw ``uint16`` bytes of the region before the edit.
        after_bytes: Raw ``uint16`` bytes of the region after the edit.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        dirty_region: tuple[int, int, int, int],
        before_bytes: bytes,
        after_bytes: bytes,
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.dirty_region = dirty_region
        self._before_bytes = before_bytes
        self._after_bytes = after_bytes

        # Injected at execution time by the caller
        self.buffer: Optional[MapDataBuffer] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply the after-snapshot to the buffer.

        The buffer is typically already in the "after" state (the tool
        already painted live).  This command exists for the undo stack.
        If the buffer has been reverted we re-apply ``after_bytes``.
        """
        logger.debug(
            "StrokeRasterCommand.execute: node_id=%s dirty=%s before=%d bytes after=%d bytes",
            self.node_id,
            self.dirty_region,
            len(self._before_bytes),
            len(self._after_bytes),
        )
        if self.buffer is None:
            logger.error(
                "StrokeRasterCommand.execute: no buffer attached for node_id=%s",
                self.node_id,
            )
            return CommandResult(
                success=False,
                message="No buffer attached.",
                command_name="StrokeRasterCommand",
            )
        try:
            self._apply_snapshot(self._after_bytes)
            self._is_executed = True
            logger.debug("StrokeRasterCommand.execute: applied after-snapshot OK")
            return CommandResult(
                success=True,
                message="Stroke applied.",
                command_name="StrokeRasterCommand",
            )
        except Exception as e:
            logger.error("StrokeRasterCommand.execute failed: %s", e, exc_info=True)
            return CommandResult(
                success=False, message=str(e), command_name="StrokeRasterCommand"
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the before-snapshot."""
        logger.debug(
            "StrokeRasterCommand.undo: node_id=%s dirty=%s",
            self.node_id,
            self.dirty_region,
        )
        if self._is_executed and self.buffer is not None:
            self._apply_snapshot(self._before_bytes)
            self._is_executed = False
            logger.debug("StrokeRasterCommand.undo: before-snapshot applied OK")
        else:
            logger.warning(
                "StrokeRasterCommand.undo: skipped (is_executed=%s, buffer=%s)",
                self._is_executed,
                self.buffer is not None,
            )

    def _apply_snapshot(self, raw: bytes) -> None:
        """Write raw uint16 bytes back into the buffer's dirty region."""
        if self.buffer is None:
            return
        d = self.dirty_region
        w = d[2] - d[0] + 1
        h = d[3] - d[1] + 1
        arr = np.frombuffer(raw, dtype=np.uint16).reshape((h, w))
        self.buffer.set_region(d[0], d[1], arr)

    @property
    def has_history(self) -> bool:
        """Stroke commands are session-only (not persisted to file)."""
        return False

    def to_dict(self) -> Dict:
        """Minimal serialization."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "dirty_region": list(self.dirty_region),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StrokeRasterCommand":
        """Deserialize (lossy — byte data not persisted)."""
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            dirty_region=tuple(data["dirty_region"]),
            before_bytes=b"",
            after_bytes=b"",
        )


class SetRasterMappingCommand(BaseCommand):
    """Undoable command to update a raster layer's value→entity mapping and colour map.

    Persists both the semantic ``value_entity_map`` and the display
    ``color_map`` to ``maps.attributes`` in the database.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        new_mapping: New ``value_entity_map`` dict.
        old_mapping: Previous ``value_entity_map`` dict (for undo).
        new_color_map: New colour-map dict (``ColorMap.to_dict()``); pass
            ``None`` to leave the colour map unchanged.
        old_color_map: Previous colour-map dict (for undo); ignored when
            ``new_color_map`` is ``None``.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        new_mapping: Dict[str, Any],
        old_mapping: Dict[str, Any],
        new_color_map: Optional[Dict[str, Any]] = None,
        old_color_map: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_mapping = new_mapping
        self.old_mapping = old_mapping
        self.new_color_map = new_color_map
        self.old_color_map = old_color_map

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply the new mapping to the map's attributes.

        Validates that mappings are mutually exclusive (no overlaps)
        before persisting.  Returns a failed result without writing if
        the mapping is invalid.
        """
        logger.debug(
            "SetRasterMappingCommand.execute: map_id=%s node_id=%s new_mapping_mode=%s",
            self.map_id,
            self.node_id,
            self.new_mapping.get("mode")
            if isinstance(self.new_mapping, dict)
            else type(self.new_mapping),
        )
        try:
            overlap_errors = validate_no_overlaps(self.new_mapping)
            if overlap_errors:
                msg = "Mapping rejected — overlapping entries: " + "; ".join(
                    overlap_errors
                )
                logger.warning("SetRasterMappingCommand.execute: %s", msg)
                return CommandResult(
                    success=False,
                    message=msg,
                    command_name="SetRasterMappingCommand",
                )
            self._set_mapping(db_service, self.new_mapping, self.new_color_map)
            self._is_executed = True
            logger.debug("SetRasterMappingCommand.execute: mapping persisted OK")
            return CommandResult(
                success=True,
                message="Mapping updated.",
                command_name="SetRasterMappingCommand",
            )
        except Exception as e:
            logger.error("SetRasterMappingCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False, message=str(e), command_name="SetRasterMappingCommand"
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the old mapping."""
        logger.debug(
            "SetRasterMappingCommand.undo: map_id=%s node_id=%s",
            self.map_id,
            self.node_id,
        )
        if self._is_executed:
            self._set_mapping(db_service, self.old_mapping, self.old_color_map)
            self._is_executed = False
            logger.debug("SetRasterMappingCommand.undo: old mapping restored")
        else:
            logger.warning("SetRasterMappingCommand.undo: skipped (not executed)")

    def _set_mapping(
        self,
        db_service: DatabaseService,
        mapping: Dict[str, Any],
        color_map: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write mapping dict (and optionally colour map) into the raster layer metadata."""
        repo = db_service.map_repo
        map_obj = repo.get_map(self.map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {self.map_id}")
        raster_layers = _get_raster_layers(map_obj)
        logger.debug(
            "SetRasterMappingCommand._set_mapping: found %d raster layers, looking for node_id=%s",
            len(raster_layers),
            self.node_id,
        )
        found = False
        for rl in raster_layers:
            if rl.get("node_id") == self.node_id:
                rl["value_entity_map"] = mapping
                if color_map is not None:
                    rl["color_map"] = color_map
                found = True
                logger.debug(
                    "SetRasterMappingCommand._set_mapping: mapping set on node_id=%s "
                    "(color_map=%s)",
                    self.node_id,
                    "updated" if color_map is not None else "unchanged",
                )
                break
        if not found:
            logger.warning(
                "SetRasterMappingCommand._set_mapping: node_id=%s not found in raster_layers",
                self.node_id,
            )
        _set_raster_layers(map_obj, raster_layers)
        repo.insert_map(map_obj)

    def to_dict(self) -> Dict:
        """Serialize command."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "new_mapping": self.new_mapping,
            "old_mapping": self.old_mapping,
            "new_color_map": self.new_color_map,
            "old_color_map": self.old_color_map,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SetRasterMappingCommand":
        """Deserialize command."""
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            new_mapping=data.get("new_mapping", {}),
            old_mapping=data.get("old_mapping", {}),
            new_color_map=data.get("new_color_map"),
            old_color_map=data.get("old_color_map"),
        )


class SetRasterBlendModeCommand(BaseCommand):
    """Set the blend mode for a raster layer.

    Blend mode is a visual preference and is not added to the undo
    history (``has_history`` returns ``False``).  Undo is still
    implemented to satisfy the :class:`BaseCommand` interface.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        new_mode: New blend mode name (must be a key of
            :data:`~src.gui.widgets.map.raster_layer_item._BLEND_MODE_MAP`).
        old_mode: Previous blend mode name (for undo).
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        new_mode: str,
        old_mode: str,
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_mode = new_mode
        self.old_mode = old_mode

    @property
    def has_history(self) -> bool:
        """Blend mode is a cosmetic preference — not added to undo history."""
        return False

    def _apply_mode(self, db_service: DatabaseService, mode: str) -> None:
        """Write *mode* into the raster layer metadata.

        Args:
            db_service: Database service.
            mode: Blend mode name to persist.
        """
        repo = db_service.map_repo
        map_obj = repo.get_map(self.map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {self.map_id}")
        raster_layers = _get_raster_layers(map_obj)
        for rl in raster_layers:
            if rl.get("node_id") == self.node_id:
                rl["blend_mode"] = mode
                break
        _set_raster_layers(map_obj, raster_layers)
        repo.insert_map(map_obj)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the new blend mode.

        Args:
            db_service: Database service.

        Returns:
            CommandResult indicating success or failure.
        """
        try:
            self._apply_mode(db_service, self.new_mode)
            self._is_executed = True
            logger.debug(
                "SetRasterBlendModeCommand.execute: node_id=%s mode=%s",
                self.node_id,
                self.new_mode,
            )
            return CommandResult(
                success=True,
                message="Blend mode updated.",
                command_name="SetRasterBlendModeCommand",
            )
        except Exception as e:
            logger.error("SetRasterBlendModeCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetRasterBlendModeCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the previous blend mode.

        Args:
            db_service: Database service.
        """
        if self._is_executed:
            self._apply_mode(db_service, self.old_mode)
            self._is_executed = False
            logger.debug(
                "SetRasterBlendModeCommand.undo: node_id=%s restored mode=%s",
                self.node_id,
                self.old_mode,
            )

    def to_dict(self) -> Dict:
        """Serialise to a JSON-friendly dict."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "new_mode": self.new_mode,
            "old_mode": self.old_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SetRasterBlendModeCommand":
        """Deserialise from a dict.

        Args:
            data: Dict produced by :meth:`to_dict`.

        Returns:
            New :class:`SetRasterBlendModeCommand` instance.
        """
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            new_mode=data.get("new_mode", "Normal"),
            old_mode=data.get("old_mode", "Normal"),
        )


class SetRasterSnapshotCommand(BaseCommand):
    """Record a snapshot file path at a specific lore date in raster metadata.

    The actual PNG file is written by MapHandler before this command is
    emitted.  This command only persists the metadata mapping
    ``{str(lore_date): rel_path}`` inside
    ``maps.attributes["raster_layers"][n]["snapshots"]``.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        lore_date: The lore timeline date at which this snapshot was taken.
        rel_file_path: Relative path from world root to the snapshot PNG.
        old_snapshots: The ``snapshots`` dict *before* this change (for undo).
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        lore_date: float,
        rel_file_path: str,
        old_snapshots: Dict[str, str],
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.lore_date = lore_date
        self.rel_file_path = rel_file_path
        self.old_snapshots = old_snapshots

    def _apply_snapshots(
        self, db_service: DatabaseService, snapshots: Dict[str, str]
    ) -> None:
        """Write *snapshots* dict into the raster layer metadata.

        Args:
            db_service: Database service.
            snapshots: Snapshot dict to persist (``{str_lore_date: rel_path}``).
        """
        repo = db_service.map_repo
        map_obj = repo.get_map(self.map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {self.map_id}")
        raster_layers = _get_raster_layers(map_obj)
        for rl in raster_layers:
            if rl.get("node_id") == self.node_id:
                rl["snapshots"] = snapshots
                break
        _set_raster_layers(map_obj, raster_layers)
        repo.insert_map(map_obj)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the new snapshot path to the raster layer metadata.

        Args:
            db_service: Database service.

        Returns:
            CommandResult indicating success or failure.
        """
        try:
            new_snapshots = dict(self.old_snapshots)
            new_snapshots[str(self.lore_date)] = self.rel_file_path
            self._apply_snapshots(db_service, new_snapshots)
            self._is_executed = True
            logger.debug(
                "SetRasterSnapshotCommand.execute: node_id=%s lore_date=%.2f path=%s",
                self.node_id,
                self.lore_date,
                self.rel_file_path,
            )
            return CommandResult(
                success=True,
                message="Snapshot recorded.",
                command_name="SetRasterSnapshotCommand",
            )
        except Exception as e:
            logger.error("SetRasterSnapshotCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetRasterSnapshotCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the snapshot dict to its previous state.

        Args:
            db_service: Database service.
        """
        if self._is_executed:
            self._apply_snapshots(db_service, dict(self.old_snapshots))
            self._is_executed = False
            logger.debug(
                "SetRasterSnapshotCommand.undo: node_id=%s restored %d snapshots",
                self.node_id,
                len(self.old_snapshots),
            )

    def to_dict(self) -> Dict:
        """Serialise to a JSON-friendly dict."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "lore_date": self.lore_date,
            "rel_file_path": self.rel_file_path,
            "old_snapshots": self.old_snapshots,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SetRasterSnapshotCommand":
        """Deserialise from a dict.

        Args:
            data: Dict produced by :meth:`to_dict`.

        Returns:
            New :class:`SetRasterSnapshotCommand` instance.
        """
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            lore_date=data["lore_date"],
            rel_file_path=data["rel_file_path"],
            old_snapshots=data.get("old_snapshots", {}),
        )
