"""Commands for raster (heatmap) layer operations.

Handles creation, deletion, and painting on raster layers.
Raster metadata is persisted inside ``maps.attributes["raster_layers"]``
and the pixel data lives in 16-bit PNG files on disk.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import numpy as np

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.layer_commands import DeleteLayerSubtreeCommand
from src.core.map import MapLayerNode
from src.core.map_constants import MAP_LAYER_TYPE_GROUP, MAP_LAYER_TYPE_RASTER
from src.core.map_state import RasterPatch
from src.core.raster_grid import (
    apply_rgba_patch,
    apply_value_patch,
    encode_rgba_png,
    encode_value_png,
    load_rgba_grid,
    load_value_grid,
)
from src.core.raster_mapping import make_empty_vem, validate_no_overlaps
from src.services.command_artifact_store import CommandArtifactStore
from src.services.db_service import DatabaseService
from src.services.raster_asset_service import RasterAssetService
from src.services.raster_import_helpers import (
    choose_resample,
    detect_greyscale,
    normalize_to_uint16,
    quantize_discrete_rgb,
)

logger = logging.getLogger(__name__)


class RasterBufferProtocol(Protocol):
    """Minimal legacy paint-buffer interface, without a GUI dependency."""

    @property
    def width(self) -> int:
        """Return the raster width in pixels."""
        ...

    @property
    def height(self) -> int:
        """Return the raster height in pixels."""
        ...

    def _norm_to_pixel(self, x_norm: float, y_norm: float) -> tuple[int, int]: ...

    def get_region(
        self, min_col: int, min_row: int, max_col: int, max_row: int
    ) -> np.ndarray:
        """Return a rectangular pixel region."""
        ...

    def set_region(
        self, min_col: int, min_row: int, region_data: np.ndarray
    ) -> None:
        """Replace a rectangular pixel region."""
        ...

    def paint_brush(
        self,
        center_x: float,
        center_y: float,
        radius_px: int,
        value: int,
        falloff: float,
    ) -> None:
        """Apply one legacy brush dab to the buffer."""
        ...


def _sanitize_filename(name: str, fallback: str) -> str:
    """Produce a safe filename base from *name*.

    Strips path components, replaces unsafe characters, and falls back
    to *fallback* if the result is empty or a reserved name.
    """
    base = Path(name).name  # strip directory components
    base = re.sub(r"[^\w.\-]", "_", base)  # keep alnum, underscore, hyphen, dot
    base = re.sub(r"_+", "_", base).strip("_")  # collapse runs
    if not base or base in {".", ".."}:
        base = fallback
    return base


def _default_gradient() -> dict[str, Any]:
    """Return the canonical black-to-white value-raster gradient."""
    return {
        "type": "gradient",
        "gradient_stops": [
            {"position": 0.0, "color": "#000000FF"},
            {"position": 1.0, "color": "#FFFFFFFF"},
        ],
    }


def _get_raster_layers(map_obj: Any) -> List[Dict[str, Any]]:
    """Extract the raster_layers list from a Map's attributes."""
    attrs = map_obj.attributes or {}
    return list(attrs.get("raster_layers", []))


def _set_raster_layers(map_obj: Any, raster_layers: List[Dict[str, Any]]) -> None:
    """Write the raster_layers list back into a Map's attributes."""
    attrs = dict(map_obj.attributes) if map_obj.attributes else {}
    attrs["raster_layers"] = raster_layers
    map_obj.attributes = attrs


def _apply_display_mapping(
    color_map: Dict[str, Any],
    *,
    display_min: Optional[float],
    display_max: Optional[float],
    unit: str,
    format_str: str,
    scale: str,
) -> None:
    """Merge real-world display-mapping fields into a color_map dict.

    Mutates *color_map* in place.  Only sets a field when the corresponding
    argument is non-default, so older maps without display mapping continue
    to round-trip unchanged.

    Args:
        color_map: The color_map dict to augment.
        display_min: Real-world value for the lowest pixel (None skips).
        display_max: Real-world value for the highest pixel (None skips).
        unit: Unit label (empty string skips).
        format_str: Python format string (empty string skips).
        scale: ``"linear"`` or ``"log"`` (empty string skips).
    """
    if display_min is not None:
        color_map["display_min"] = float(display_min)
    if display_max is not None:
        color_map["display_max"] = float(display_max)
    if unit:
        color_map["unit"] = unit
    if format_str and format_str != "{:.2f}":
        color_map["format_str"] = format_str
    if scale and scale != "linear":
        color_map["scale"] = scale


class CreateRasterLayerCommand(BaseCommand):
    """Create a new raster layer: blank PNG, layer node, and metadata.

    On execute, the command:
    1. Creates a 16-bit PNG in ``<world>/rasters/`` (blank or from *import_path*).
    2. Adds a :class:`MapLayerNode` (type ``"raster"``) to the layer tree.
    3. Appends raster metadata to ``maps.attributes["raster_layers"]``.

    Args:
        map_id: ID of the parent map.
        name: Human-readable layer name.
        width: Buffer width in pixels.
        height: Buffer height in pixels.
        mode: ``"discrete"``, ``"continuous"``, or ``"color"``.
        default_value: Initial fill value (0–65535); ignored for *color* mode
            and when *import_path* is set.
        world_root: Absolute path to the world directory (for file storage).
        import_path: Optional filesystem path to an image to import as layer data.
            When set, the image is scaled to ``width × height``.
            Discrete mode: colour images with ≤ 256 unique colours get an auto-palette;
            images with more colours are quantized to 256 via PIL.
            Continuous mode: image is converted to grayscale uint16.
            Color mode: image is stored as-is (8-bit RGBA PNG); original colours
            are preserved exactly.
        display_min: Optional real-world value corresponding to the lowest
            pixel value (e.g. ``-4000.0`` for a DEM's deepest point).
        display_max: Optional real-world value corresponding to the highest
            pixel value.
        unit: Optional unit label (e.g. ``"m"``, ``"°C"``).
        format_str: Optional Python format string for display values
            (e.g. ``"{:.1f}"``).  Empty string means "use default".
        scale: Optional interpolation scale — ``"linear"`` or ``"log"``.
            Empty string means "use default" (linear).

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
        import_path: str = "",
        display_min: Optional[float] = None,
        display_max: Optional[float] = None,
        unit: str = "",
        format_str: str = "",
        scale: str = "",
    ) -> None:
        """Initialize creation of a raster layer and backing asset."""
        super().__init__()
        self.map_id = map_id
        self.name = name
        self.width = width
        self.height = height
        self.mode = mode
        self.default_value = default_value
        self.world_root = world_root
        self.import_path = import_path
        self.display_min = display_min
        self.display_max = display_max
        self.unit = unit
        self.format_str = format_str
        self.scale = scale

        # Generated on execute
        self._node_id: str = str(uuid.uuid4())
        self._file_path: str = ""
        self._raster_metadata: Dict[str, Any] = {}
        self._file_manifest: dict[str, str] = {}

    def execute(self, db_service: DatabaseService) -> CommandResult:  # noqa: C901
        """Create the raster file, layer node, and persist metadata.

        Args:
            db_service: The database service.

        Returns:
            CommandResult with ``data["node_id"]`` and ``data["file_path"]``.

        """
        logger.debug(
            "CreateRasterLayerCommand.execute: map_id=%s name=%r size=%dx%d "
            "mode=%s default_value=%d world_root=%r import_path=%r",
            self.map_id,
            self.name,
            self.width,
            self.height,
            self.mode,
            self.default_value,
            self.world_root,
            self.import_path or None,
        )
        restored_from_manifest = False
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if not map_obj:
                logger.error("CreateRasterLayerCommand: map not found: %s", self.map_id)
                return CommandResult(
                    success=False,
                    message="Map not found.",
                    command_name="CreateRasterLayerCommand",
                )
            if not self.world_root:
                self.world_root = str(Path(db_service.get_db_file_path()).parent)
            if self._file_manifest and self._raster_metadata:
                CommandArtifactStore(Path(self.world_root)).restore(
                    self._file_manifest
                )
                restored_from_manifest = True
                self._file_manifest = {}
                if map_obj.layers is None:
                    map_obj.layers = MapLayerNode(name="Root")
                map_obj.layers.children.append(
                    MapLayerNode(
                        name=self.name,
                        layer_type=MAP_LAYER_TYPE_RASTER,
                        id=self._node_id,
                    )
                )
                raster_layers = _get_raster_layers(map_obj)
                raster_layers.append(dict(self._raster_metadata))
                _set_raster_layers(map_obj, raster_layers)
                attrs = dict(map_obj.attributes or {})
                attrs["layers"] = map_obj.layers.to_dict()
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)
                self._is_executed = True
                return CommandResult(
                    success=True,
                    message=f"Raster layer '{self.name}' restored.",
                    command_name="CreateRasterLayerCommand",
                    data={
                        "node_id": self._node_id,
                        "file_path": self._file_path,
                    },
                )
            logger.debug(
                "CreateRasterLayerCommand: got map %r (attrs keys=%s)",
                map_obj.name,
                list((map_obj.attributes or {}).keys()),
            )

            # 1. Create buffer (blank or from imported image) and save to disk
            auto_palette_entries: list = []
            if self.mode == "color":
                # Color mode: preserve original RGB pixels as 8-bit RGBA PNG.
                from PIL import Image as PilImage

                if self.import_path:
                    img_c = PilImage.open(self.import_path).convert("RGBA")
                    img_c = img_c.resize(
                        (self.width, self.height), PilImage.Resampling.LANCZOS
                    )
                else:
                    # Blank transparent image
                    img_c = PilImage.new(
                        "RGBA", (self.width, self.height), (0, 0, 0, 0)
                    )
                rgba_arr = np.array(img_c, dtype=np.uint8)
                raster_dir = Path(self.world_root) / "rasters"
                safe_base = _sanitize_filename(self.name, self._node_id[:8])
                filename = f"{safe_base}_{self._node_id[:8]}.png"
                abs_path = raster_dir / filename
                if not abs_path.resolve().is_relative_to(raster_dir.resolve()):
                    raise ValueError(f"Path traversal detected: {abs_path}")
                self._file_path = f"rasters/{filename}"
                RasterAssetService(
                    Path(self.world_root)
                ).atomic_write_bytes(
                    self._file_path, encode_rgba_png(rgba_arr)
                )

                # Add layer node
                node = MapLayerNode(
                    name=self.name,
                    layer_type=MAP_LAYER_TYPE_RASTER,
                    id=self._node_id,
                )
                if map_obj.layers is None:
                    map_obj.layers = MapLayerNode(
                        name="Root", layer_type=MAP_LAYER_TYPE_GROUP
                    )
                map_obj.layers.children.append(node)

                # Raster metadata for color mode
                now = time.time()
                raster_layers = _get_raster_layers(map_obj)
                self._raster_metadata = {
                    "node_id": self._node_id,
                    "file_path": self._file_path,
                    "resolution": [self.width, self.height],
                    "mode": "color",
                    "color_map": {"type": "passthrough"},
                    "created_at": now,
                    "modified_at": now,
                    "schema_version": 2,
                }
                raster_layers.append(dict(self._raster_metadata))
                _set_raster_layers(map_obj, raster_layers)
                attrs = dict(map_obj.attributes) if map_obj.attributes else {}
                attrs["layers"] = map_obj.layers.to_dict()
                map_obj.attributes = attrs
                db_service.map_repo.insert_map(map_obj)
                self._is_executed = True

                return CommandResult(
                    success=True,
                    message=f"Color raster layer '{self.name}' created.",
                    command_name="CreateRasterLayerCommand",
                    data={"node_id": self._node_id, "file_path": self._file_path},
                )

            if self.import_path:
                from PIL import Image as PilImage

                img: PilImage.Image = PilImage.open(self.import_path)
                # Normalise I;16 (raw 16-bit mode) to I before resize so PIL
                # handles it correctly on all platforms.
                if img.mode == "I;16":
                    img = img.convert("I")

                _is_grey_mode = detect_greyscale(img)

                _resample = choose_resample(
                    mode=self.mode, is_greyscale=_is_grey_mode
                )
                img_resized = img.resize((self.width, self.height), _resample)
                is_greyscale = _is_grey_mode or img_resized.mode in ("L", "LA", "I")

                if self.mode == "discrete" and not is_greyscale:
                    arr16, auto_palette_entries = quantize_discrete_rgb(img_resized)
                else:
                    arr16 = normalize_to_uint16(img_resized)

            else:
                arr16 = np.full(
                    (self.height, self.width),
                    self.default_value,
                    dtype=np.uint16,
                )
            raster_dir = Path(self.world_root) / "rasters"
            safe_base = _sanitize_filename(self.name, self._node_id[:8])
            filename = f"{safe_base}_{self._node_id[:8]}.png"
            abs_path = raster_dir / filename
            if not abs_path.resolve().is_relative_to(raster_dir.resolve()):
                raise ValueError(f"Path traversal detected: {abs_path}")
            self._file_path = f"rasters/{filename}"
            logger.debug("CreateRasterLayerCommand: saving PNG → %s", abs_path)
            RasterAssetService(Path(self.world_root)).atomic_write_bytes(
                self._file_path, encode_value_png(arr16)
            )
            logger.debug(
                "CreateRasterLayerCommand: PNG saved OK (%d bytes)",
                abs_path.stat().st_size if abs_path.exists() else -1,
            )

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
            if auto_palette_entries:
                initial_color_map = {
                    "type": "palette",
                    "entries": [
                        {
                            "value": entry["value"],
                            "color": entry["color"],
                            "label": entry["label"],
                        }
                        for entry in auto_palette_entries
                    ],
                }
            elif self.import_path and self.mode != "discrete":
                # Build a multicolor gradient from the original RGB image so
                # the greyscale buffer renders close to the original colours.
                try:
                    from src.services.raster_image_analysis import (
                        gradient_from_rgb_image,
                    )

                    initial_color_map = gradient_from_rgb_image(img, 12)
                except Exception:
                    logger.debug(
                        "from_rgb_image failed; falling back to B/W gradient",
                        exc_info=True,
                    )
                    initial_color_map = _default_gradient()
            elif self.mode == "discrete":
                # Discrete layers start with an empty palette; the user
                # populates it via the palette editor.  A gradient here would
                # cause the editor to show an empty table and save back an
                # empty palette (making the layer invisible) when the user
                # just wants to add entity links.
                initial_color_map = {"type": "palette", "entries": []}
            else:
                initial_color_map = _default_gradient()

            # Apply display-mapping params (from dialog / inferred metadata)
            effective_min = self.display_min
            effective_max = self.display_max
            effective_unit = self.unit
            # Fallback: for continuous layers imported from a file, infer
            # real-world range from GeoTIFF metadata / float pixel stats when
            # the caller did not supply explicit values.
            if (
                self.mode == "continuous"
                and self.import_path
                and effective_min is None
                and effective_max is None
            ):
                try:
                    from src.services.raster_image_analysis import (
                        extract_value_metadata,
                    )

                    inferred = extract_value_metadata(self.import_path)
                except Exception:  # pragma: no cover - defensive
                    logger.debug(
                        "extract_value_metadata raised during create", exc_info=True
                    )
                    inferred = None
                if inferred is not None:
                    effective_min = inferred.min
                    effective_max = inferred.max
                    if not effective_unit:
                        effective_unit = inferred.unit

            _apply_display_mapping(
                initial_color_map,
                display_min=effective_min,
                display_max=effective_max,
                unit=effective_unit,
                format_str=self.format_str,
                scale=self.scale,
            )

            raster_meta: Dict[str, Any] = {
                "node_id": self._node_id,
                "file_path": self._file_path,
                "resolution": [self.width, self.height],
                "mode": self.mode,
                "default_value": self.default_value,
                "value_entity_map": make_empty_vem(self.mode),
                "color_map": initial_color_map,
                "created_at": now,
                "modified_at": now,
                "schema_version": 2,
            }
            self._raster_metadata = dict(raster_meta)
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
            if self._file_path and self.world_root:
                if restored_from_manifest:
                    self._file_manifest = CommandArtifactStore(
                        Path(self.world_root)
                    ).stash(self.command_id, [self._file_path])
                else:
                    failed_path = Path(self.world_root) / self._file_path
                    if failed_path.exists():
                        failed_path.unlink()
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
        stashed = False
        try:
            if self._file_path and self.world_root:
                self._file_manifest = CommandArtifactStore(
                    Path(self.world_root)
                ).stash(self.command_id, [self._file_path])
                stashed = True
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

            self._is_executed = False
            logger.info("Undid raster layer creation: %s", self._node_id)
        except Exception as e:
            if stashed and self._file_manifest:
                CommandArtifactStore(Path(self.world_root)).restore(
                    self._file_manifest
                )
                self._file_manifest = {}
            logger.error("Undo CreateRasterLayerCommand failed: %s", e)
            raise

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
            "import_path": self.import_path,
            "node_id": self._node_id,
            "file_path": self._file_path,
            "display_min": self.display_min,
            "display_max": self.display_max,
            "unit": self.unit,
            "format_str": self.format_str,
            "scale": self.scale,
            "raster_metadata": self._raster_metadata,
            "file_manifest": self._file_manifest,
            "is_executed": self._is_executed,
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
            import_path=data.get("import_path", ""),
            display_min=data.get("display_min"),
            display_max=data.get("display_max"),
            unit=data.get("unit", ""),
            format_str=data.get("format_str", ""),
            scale=data.get("scale", ""),
        )
        cmd._node_id = data.get("node_id", cmd._node_id)
        cmd._file_path = data.get("file_path", "")
        cmd._raster_metadata = dict(data.get("raster_metadata", {}))
        cmd._file_manifest = dict(data.get("file_manifest", {}))
        cmd._is_executed = bool(data.get("is_executed", cmd._file_path))
        return cmd


class DeleteRasterLayerCommand(BaseCommand):
    """Compatibility wrapper around canonical subtree deletion."""

    def __init__(
        self,
        map_id: str,
        node_id: str,
        world_root: str = "",
    ) -> None:
        """Initialize deletion of one raster layer."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.world_root = world_root
        self._delegate: Optional[DeleteLayerSubtreeCommand] = None

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Delete the raster and every nested asset through one implementation."""
        if self._delegate is None:
            self._delegate = DeleteLayerSubtreeCommand(
                self.map_id,
                self.node_id,
                self.world_root,
            )
            self._delegate.command_id = self.command_id
        result = self._delegate.execute(db_service)
        result.command_name = self.__class__.__name__
        self._is_executed = result.success
        return result

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore the exact original hierarchy and every owned raster file."""
        if self._delegate is None:
            return CommandResult(
                success=False,
                message="Raster deletion snapshot is unavailable.",
                command_name="Undo_DeleteRasterLayerCommand",
            )
        self._delegate.undo(db_service)
        self._is_executed = False
        return CommandResult(
            success=True,
            message="Raster layer restored.",
            command_name="Undo_DeleteRasterLayerCommand",
            data={
                "effects": [
                    {"kind": "map_state_changed", "map_id": self.map_id}
                ]
            },
        )

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "world_root": self.world_root,
            "delegate": self._delegate.to_dict() if self._delegate else None,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DeleteRasterLayerCommand":
        """Deserialize command from dictionary."""
        command = cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            world_root=data.get("world_root", ""),
        )
        if data.get("delegate"):
            command._delegate = DeleteLayerSubtreeCommand.from_dict(
                data["delegate"]
            )
        command._is_executed = bool(data.get("is_executed", command._delegate))
        return command


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
        """Initialize a legacy raster paint operation."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.center_x = center_x
        self.center_y = center_y
        self.radius_px = radius_px
        self.value = value
        self.falloff = falloff

        # Set by caller before execute
        self.buffer: Optional[RasterBufferProtocol] = None

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
    def is_undoable(self) -> bool:
        """Legacy live-paint commands are not independent undo entries."""
        return False

    @property
    def persist_to_history(self) -> bool:
        """Legacy live-paint commands are session-only."""
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
    """Undoable ordered tile-patch command for a completed raster stroke.

    The legacy single-region arguments remain supported so session history and
    older callers can be deserialized without migrating world data.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        dirty_region: tuple[int, int, int, int] | None = None,
        before_bytes: bytes = b"",
        after_bytes: bytes = b"",
        target_file: str = "",
        patches: Optional[List[RasterPatch]] = None,
        pixel_format: str = "value16",
    ) -> None:
        """Initialize an atomic raster stroke from tile patches."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.target_file = target_file
        if patches is None:
            if dirty_region is None:
                raise ValueError("A raster stroke requires at least one patch")
            width = dirty_region[2] - dirty_region[0] + 1
            height = dirty_region[3] - dirty_region[1] + 1
            dtype = "uint8" if pixel_format == "rgba8" else "uint16"
            shape = (height, width, 4) if dtype == "uint8" else (height, width)
            patches = [
                RasterPatch(
                    map_id=map_id,
                    node_id=node_id,
                    target_file=target_file,
                    region=dirty_region,
                    shape=shape,
                    dtype=dtype,
                    before_data=before_bytes,
                    after_data=after_bytes,
                )
            ]
        if not patches:
            raise ValueError("A raster stroke requires at least one patch")
        self.patches = list(patches)
        first = self.patches[0]
        self.dirty_region = first.region
        self._before_bytes = first.before_data
        self._after_bytes = first.after_data
        self._cancel_reason = ""

    def cancel(self, reason: str) -> None:
        """Prevent a queued dependent stroke from reaching persistence."""
        self._cancel_reason = reason

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the immutable after-patch without touching GUI state."""
        if self._cancel_reason:
            return CommandResult(
                success=False,
                message=self._cancel_reason,
                command_name="StrokeRasterCommand",
            )
        logger.debug(
            "StrokeRasterCommand.execute: node_id=%s dirty=%s before=%d bytes after=%d bytes",
            self.node_id,
            self.dirty_region,
            len(self._before_bytes),
            len(self._after_bytes),
        )
        try:
            self._apply_patches(db_service, "after")
            self._is_executed = True
            logger.debug("StrokeRasterCommand.execute: applied after-snapshot OK")
            return CommandResult(
                success=True,
                message="Stroke applied.",
                command_name="StrokeRasterCommand",
                data={"effects": self._effects("after")},
            )
        except Exception as e:
            logger.error("StrokeRasterCommand.execute failed: %s", e, exc_info=True)
            return CommandResult(
                success=False, message=str(e), command_name="StrokeRasterCommand"
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Persist and return the before-patch."""
        logger.debug(
            "StrokeRasterCommand.undo: node_id=%s dirty=%s",
            self.node_id,
            self.dirty_region,
        )
        if not self._is_executed:
            return CommandResult(
                success=False,
                message="Stroke is not currently applied.",
                command_name="Undo_StrokeRasterCommand",
            )
        self._apply_patches(db_service, "before")
        self._is_executed = False
        logger.debug("StrokeRasterCommand.undo: before-snapshot applied OK")
        return CommandResult(
            success=True,
            message="Stroke undone.",
            command_name="Undo_StrokeRasterCommand",
            data={"effects": self._effects("before")},
        )

    def _resolve_target(self, db_service: DatabaseService) -> str:
        if self.target_file:
            return self.target_file
        map_obj = db_service.map_repo.get_map(self.map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {self.map_id}")
        for metadata in (map_obj.attributes or {}).get("raster_layers", []):
            if metadata.get("node_id") == self.node_id:
                self.target_file = str(metadata.get("file_path", ""))
                break
        if not self.target_file:
            raise ValueError(f"Raster layer not found: {self.node_id}")
        return self.target_file

    def _apply_patches(
        self,
        db_service: DatabaseService,
        direction: str,
    ) -> None:
        """Apply all tile patches in stroke order and atomically replace PNG."""
        target_file = self._resolve_target(db_service)
        world_root = Path(db_service.get_db_file_path()).parent
        assets = RasterAssetService(world_root)
        target = assets.resolve(target_file)
        rgba = self.patches[0].dtype == "uint8"
        array = load_rgba_grid(str(target)) if rgba else load_value_grid(str(target))
        ordered = self.patches if direction == "after" else reversed(self.patches)
        for patch in ordered:
            raw = patch.after_data if direction == "after" else patch.before_data
            if rgba:
                array = apply_rgba_patch(array, patch.region, raw)
            else:
                array = apply_value_patch(array, patch.region, raw)
        encoded = encode_rgba_png(array) if rgba else encode_value_png(array)
        assets.atomic_write_bytes(target_file, encoded)

    def _effects(self, direction: str) -> List[Dict[str, Any]]:
        ordered = self.patches if direction == "after" else list(reversed(self.patches))
        return [
            {
                "kind": "raster_patch",
                "map_id": self.map_id,
                "node_id": self.node_id,
                "region": list(patch.region),
                "shape": list(patch.shape),
                "dtype": patch.dtype,
                "data": RasterPatch._encode(
                    patch.after_data if direction == "after" else patch.before_data
                ),
                "direction": direction,
            }
            for patch in ordered
        ]

    @property
    def is_undoable(self) -> bool:
        """Stroke commands are reversible in the current session."""
        return True

    @property
    def persist_to_history(self) -> bool:
        """Stroke byte patches are deliberately not persisted across restarts."""
        return False

    def to_dict(self) -> Dict:
        """Serialize the session patch for safe queued worker delivery."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "dirty_region": list(self.dirty_region),
            "target_file": self.target_file,
            "before_data": RasterPatch._encode(self._before_bytes),
            "after_data": RasterPatch._encode(self._after_bytes),
            "patches": [patch.to_dict() for patch in self.patches],
            "cancel_reason": self._cancel_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "StrokeRasterCommand":
        """Deserialize a worker-bound or in-session patch."""
        serialized_patches = data.get("patches")
        if serialized_patches:
            command = cls(
                map_id=data["map_id"],
                node_id=data["node_id"],
                target_file=data.get("target_file", ""),
                patches=[
                    RasterPatch.from_dict(patch_data)
                    for patch_data in serialized_patches
                ],
            )
        else:
            command = cls(
                map_id=data["map_id"],
                node_id=data["node_id"],
                dirty_region=tuple(data["dirty_region"]),
                before_bytes=RasterPatch._decode(
                    str(data.get("before_data", ""))
                )
                if data.get("before_data")
                else b"",
                after_bytes=RasterPatch._decode(
                    str(data.get("after_data", ""))
                )
                if data.get("after_data")
                else b"",
                target_file=data.get("target_file", ""),
            )
        command._cancel_reason = str(data.get("cancel_reason", ""))
        return command


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
        """Initialize a raster value-mapping update."""
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
            raise ValueError(
                f"SetRasterMappingCommand._set_mapping: node_id={self.node_id} "
                f"not found in raster_layers"
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
        """Initialize a raster blend-mode update."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.new_mode = new_mode
        self.old_mode = old_mode

    @property
    def is_undoable(self) -> bool:
        """Blend mode is a cosmetic preference — not added to undo history."""
        return False

    @property
    def persist_to_history(self) -> bool:
        """Blend mode updates are not persisted as command history."""
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

        Fetches the actual current blend mode from the DB before writing,
        so that ``undo()`` always restores the correct previous state
        regardless of what ``old_mode`` was passed to the constructor.

        Args:
            db_service: Database service.

        Returns:
            CommandResult indicating success or failure.
        """
        try:
            # Capture the actual current mode from DB before writing.
            repo = db_service.map_repo
            map_obj = repo.get_map(self.map_id)
            if map_obj is not None:
                raster_layers = _get_raster_layers(map_obj)
                for rl in raster_layers:
                    if rl.get("node_id") == self.node_id:
                        self.old_mode = rl.get("blend_mode", "Normal")
                        break
                else:
                    self.old_mode = "Normal"

            self._apply_mode(db_service, self.new_mode)
            self._is_executed = True
            logger.debug(
                "SetRasterBlendModeCommand.execute: node_id=%s mode=%s old_mode=%s",
                self.node_id,
                self.new_mode,
                self.old_mode,
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
    """Create a dated raster file and metadata entry as one command."""

    def __init__(
        self,
        map_id: str,
        node_id: str,
        lore_date: float,
        rel_file_path: str,
        old_snapshots: Dict[str, str],
        image_bytes: bytes = b"",
    ) -> None:
        """Initialize creation or replacement of a raster snapshot."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.lore_date = lore_date
        self.rel_file_path = rel_file_path
        self.old_snapshots = old_snapshots
        self._image_bytes = image_bytes
        self._old_file_manifest: dict[str, str] = {}
        self._new_file_manifest: dict[str, str] = {}

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
        """Create/restore the PNG and persist the full-precision date mapping."""
        world_root = Path(db_service.get_db_file_path()).parent
        assets = RasterAssetService(world_root)
        artifacts = CommandArtifactStore(world_root)
        old_path = ""
        for key, path in self.old_snapshots.items():
            try:
                if float(key) == self.lore_date:
                    old_path = path
                    break
            except (TypeError, ValueError):
                continue
        try:
            if old_path:
                self._old_file_manifest = artifacts.stash(
                    self.command_id, [old_path]
                )
            if self._new_file_manifest:
                artifacts.restore(self._new_file_manifest)
                self._new_file_manifest = {}
            elif self._image_bytes:
                assets.atomic_write_bytes(
                    self.rel_file_path, self._image_bytes
                )
            else:
                raise ValueError("Snapshot image data is unavailable")

            new_snapshots = dict(self.old_snapshots)
            new_snapshots[format(self.lore_date, ".17g")] = self.rel_file_path
            self._apply_snapshots(db_service, new_snapshots)
            self._is_executed = True
            self._image_bytes = b""
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
                data={
                    "effects": [
                        {
                            "kind": "raster_edit_target",
                            "node_id": self.node_id,
                            "file_path": self.rel_file_path,
                            "lore_date": self.lore_date,
                        }
                    ]
                },
            )
        except Exception as e:
            target = assets.resolve(self.rel_file_path)
            if target.exists():
                target.unlink()
            if self._old_file_manifest:
                artifacts.restore(self._old_file_manifest)
                self._old_file_manifest = {}
            logger.error("SetRasterSnapshotCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetRasterSnapshotCommand",
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore previous metadata and file ownership."""
        if not self._is_executed:
            return CommandResult(
                success=False,
                message="Raster state is not currently applied.",
                command_name="Undo_SetRasterSnapshotCommand",
            )
        world_root = Path(db_service.get_db_file_path()).parent
        artifacts = CommandArtifactStore(world_root)
        self._new_file_manifest = artifacts.stash(
            self.command_id, [self.rel_file_path]
        )
        try:
            if self._old_file_manifest:
                artifacts.restore(self._old_file_manifest)
                self._old_file_manifest = {}
            self._apply_snapshots(db_service, dict(self.old_snapshots))
        except Exception:
            if self._new_file_manifest:
                artifacts.restore(self._new_file_manifest)
                self._new_file_manifest = {}
            raise
        self._is_executed = False
        return CommandResult(
            success=True,
            message="Raster state removed.",
            command_name="Undo_SetRasterSnapshotCommand",
            data={
                "effects": [
                    {
                        "kind": "raster_edit_target_cleared",
                        "node_id": self.node_id,
                    }
                ]
            },
        )

    def to_dict(self) -> Dict:
        """Serialise to a JSON-friendly dict."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "lore_date": self.lore_date,
            "rel_file_path": self.rel_file_path,
            "old_snapshots": self.old_snapshots,
            "old_file_manifest": self._old_file_manifest,
            "new_file_manifest": self._new_file_manifest,
            "is_executed": self._is_executed,
            "image_data": (
                RasterPatch._encode(self._image_bytes)
                if self._image_bytes
                else ""
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SetRasterSnapshotCommand":
        """Deserialise from a dict.

        Args:
            data: Dict produced by :meth:`to_dict`.

        Returns:
            New :class:`SetRasterSnapshotCommand` instance.
        """
        command = cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            lore_date=data["lore_date"],
            rel_file_path=data["rel_file_path"],
            old_snapshots=data.get("old_snapshots", {}),
            image_bytes=(
                RasterPatch._decode(str(data["image_data"]))
                if data.get("image_data")
                else b""
            ),
        )
        command._old_file_manifest = dict(
            data.get("old_file_manifest", {})
        )
        command._new_file_manifest = dict(
            data.get("new_file_manifest", {})
        )
        command._is_executed = bool(data.get("is_executed", True))
        return command


class RemoveRasterSnapshotCommand(BaseCommand):
    """Remove a temporal raster snapshot entry and its PNG file.

    The deleted file is retained in the persistent command artifact store.
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        lore_date: float,
        world_root: str,
        old_snapshots: Dict[str, str],
        rel_file_path: str = "",
    ) -> None:
        """Initialize removal of a raster snapshot."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.lore_date = lore_date
        self.rel_file_path = rel_file_path
        self.world_root = world_root
        self.old_snapshots = old_snapshots

        self._deleted_key: str = ""
        self._artifact_manifest: dict[str, str] = {}

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Remove the snapshot metadata entry and delete the snapshot file."""
        world_root = (
            Path(self.world_root)
            if self.world_root
            else Path(db_service.get_db_file_path()).parent
        )
        artifacts = CommandArtifactStore(world_root)
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj is None:
                return CommandResult(
                    success=False,
                    message=f"Map not found: {self.map_id}",
                    command_name="RemoveRasterSnapshotCommand",
                )

            raster_layers = _get_raster_layers(map_obj)
            target_meta = next(
                (rl for rl in raster_layers if rl.get("node_id") == self.node_id),
                None,
            )
            if target_meta is None:
                return CommandResult(
                    success=False,
                    message=f"Raster layer not found: {self.node_id}",
                    command_name="RemoveRasterSnapshotCommand",
                )

            snapshots: Dict[str, str] = dict(target_meta.get("snapshots", {}))
            self._deleted_key = ""
            for key in snapshots:
                try:
                    if float(key) == self.lore_date:
                        self._deleted_key = str(key)
                        break
                except (TypeError, ValueError):
                    continue

            if not self._deleted_key:
                self._deleted_key = str(self.lore_date)

            if not self.rel_file_path:
                self.rel_file_path = self.old_snapshots.get(self._deleted_key, "")

            if self.rel_file_path:
                self._artifact_manifest = artifacts.stash(
                    self.command_id, [self.rel_file_path]
                )
            snapshots.pop(self._deleted_key, None)
            target_meta["snapshots"] = snapshots
            _set_raster_layers(map_obj, raster_layers)
            try:
                db_service.map_repo.insert_map(map_obj)
            except Exception:
                artifacts.restore(self._artifact_manifest)
                self._artifact_manifest = {}
                raise

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Snapshot deleted.",
                command_name="RemoveRasterSnapshotCommand",
                data={
                    "effects": [
                        {
                            "kind": "raster_edit_target_cleared",
                            "node_id": self.node_id,
                        }
                    ]
                },
            )
        except Exception as e:
            logger.error("RemoveRasterSnapshotCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="RemoveRasterSnapshotCommand",
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore the snapshot metadata and artifact."""
        if not self._is_executed:
            return CommandResult(
                success=False,
                message="Raster state is not currently deleted.",
                command_name="Undo_RemoveRasterSnapshotCommand",
            )

        world_root = (
            Path(self.world_root)
            if self.world_root
            else Path(db_service.get_db_file_path()).parent
        )
        artifacts = CommandArtifactStore(world_root)
        try:
            map_obj = db_service.map_repo.get_map(self.map_id)
            if map_obj is None:
                raise ValueError(f"Map not found: {self.map_id}")

            raster_layers = _get_raster_layers(map_obj)
            target_meta = next(
                (rl for rl in raster_layers if rl.get("node_id") == self.node_id),
                None,
            )
            if target_meta is None:
                raise ValueError(f"Raster layer not found: {self.node_id}")

            artifacts.restore(self._artifact_manifest)
            target_meta["snapshots"] = dict(self.old_snapshots)
            _set_raster_layers(map_obj, raster_layers)
            try:
                db_service.map_repo.insert_map(map_obj)
            except Exception:
                self._artifact_manifest = artifacts.stash(
                    self.command_id, [self.rel_file_path]
                )
                raise

            self._is_executed = False
            return CommandResult(
                success=True,
                message="Raster state restored.",
                command_name="Undo_RemoveRasterSnapshotCommand",
                data={
                    "effects": [
                        {
                            "kind": "raster_edit_target",
                            "node_id": self.node_id,
                            "file_path": self.rel_file_path,
                        }
                    ]
                },
            )
        except Exception:
            logger.exception("Undo RemoveRasterSnapshotCommand failed")
            raise

    def to_dict(self) -> Dict:
        """Serialize command to dictionary."""
        return {
            "map_id": self.map_id,
            "node_id": self.node_id,
            "lore_date": self.lore_date,
            "rel_file_path": self.rel_file_path,
            "world_root": self.world_root,
            "old_snapshots": self.old_snapshots,
            "deleted_key": self._deleted_key,
            "artifact_manifest": self._artifact_manifest,
            "is_executed": self._is_executed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RemoveRasterSnapshotCommand":
        """Deserialize command from dictionary."""
        command = cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            lore_date=data["lore_date"],
            rel_file_path=data.get("rel_file_path", ""),
            world_root=data.get("world_root", ""),
            old_snapshots=data.get("old_snapshots", {}),
        )
        command._deleted_key = str(data.get("deleted_key", ""))
        command._artifact_manifest = dict(data.get("artifact_manifest", {}))
        command._is_executed = bool(data.get("is_executed", True))
        return command


class SetRasterNotesCommand(BaseCommand):
    """Store text notes on a raster layer (persisted in raster metadata).

    Notes are undoable: undo restores the previous text.

    Args:
        map_id: Parent map ID.
        node_id: Raster layer node ID.
        notes: New notes text to persist.
        old_notes: Previous notes text (for undo).
    """

    def __init__(
        self,
        map_id: str,
        node_id: str,
        notes: str,
        old_notes: str = "",
    ) -> None:
        """Initialize a raster-layer notes update."""
        super().__init__()
        self.map_id = map_id
        self.node_id = node_id
        self.notes = notes
        self.old_notes = old_notes

    @property
    def is_undoable(self) -> bool:
        """Notes edits are undoable."""
        return True

    def _set_notes(self, db_service: DatabaseService, notes: str) -> None:
        """Write *notes* into the raster layer metadata.

        Args:
            db_service: Database service.
            notes: Notes text to persist.
        """
        repo = db_service.map_repo
        map_obj = repo.get_map(self.map_id)
        if map_obj is None:
            raise ValueError(f"Map not found: {self.map_id}")
        raster_layers = _get_raster_layers(map_obj)
        for rl in raster_layers:
            if rl.get("node_id") == self.node_id:
                rl["notes"] = notes
                break
        _set_raster_layers(map_obj, raster_layers)
        repo.insert_map(map_obj)

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Persist the new notes text.

        Args:
            db_service: Database service.

        Returns:
            CommandResult indicating success or failure.
        """
        try:
            self._set_notes(db_service, self.notes)
            self._is_executed = True
            logger.debug(
                "SetRasterNotesCommand.execute: node_id=%s notes=%r",
                self.node_id,
                self.notes[:40],
            )
            return CommandResult(
                success=True,
                data={"node_id": self.node_id, "notes": self.notes},
                message="Notes updated.",
                command_name="SetRasterNotesCommand",
            )
        except Exception as e:
            logger.error("SetRasterNotesCommand failed: %s", e, exc_info=True)
            return CommandResult(
                success=False,
                message=str(e),
                command_name="SetRasterNotesCommand",
            )

    def undo(self, db_service: DatabaseService) -> None:
        """Restore the previous notes text.

        Args:
            db_service: Database service.
        """
        if self._is_executed:
            self._set_notes(db_service, self.old_notes)
            self._is_executed = False
            logger.debug(
                "SetRasterNotesCommand.undo: node_id=%s restored notes=%r",
                self.node_id,
                self.old_notes[:40],
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        return {
            "type": "SetRasterNotesCommand",
            "map_id": self.map_id,
            "node_id": self.node_id,
            "notes": self.notes,
            "old_notes": self.old_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetRasterNotesCommand":
        """Deserialise from a dict.

        Args:
            data: Dict produced by :meth:`to_dict`.

        Returns:
            New :class:`SetRasterNotesCommand` instance.
        """
        return cls(
            map_id=data["map_id"],
            node_id=data["node_id"],
            notes=data["notes"],
            old_notes=data.get("old_notes", ""),
        )
