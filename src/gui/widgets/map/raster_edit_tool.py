"""Raster Edit Tool for the Map Graphics View.

Manages interactive raster editing: brush painting, flood fill,
gradient painting, and value sampling.  Follows the same delegation
pattern as :class:`DrawingTool` — the parent
:class:`MapGraphicsView` calls ``handle_mouse_*`` and the tool
returns ``True`` when it consumes the event.
"""

import logging
import weakref
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsView,
)

from src.app.constants import MAP_LAYER_Z_UI_OVERLAY
from src.app.ui_constants import RASTER_DAB_SPACING_FACTOR
from src.core.raster_paint import RasterPaintMode, brush_bounds
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.raster_layer_item import RasterLayerItem

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)


class RasterEditMode(Enum):
    """Sub-modes for the raster editing tool."""

    BRUSH = auto()
    FILL = auto()
    GRADIENT = auto()
    SAMPLE = auto()


GRADIENT_SUB_LINEAR = "linear"
GRADIENT_SUB_RADIAL = "radial"
GRADIENT_SUB_REFLECTED = "reflected"


class _TiledStrokeJournal:
    """Capture touched pixels lazily in clipped 256×256 tiles."""

    TILE_SIZE = 256

    def __init__(self, array: np.ndarray) -> None:
        self._shape = array.shape
        self._dtype = array.dtype
        self._before: dict[tuple[int, int], np.ndarray] = {}
        self._strength: dict[tuple[int, int], np.ndarray] = {}

    def capture_bounds(
        self,
        array: np.ndarray,
        bounds: tuple[int, int, int, int],
    ) -> None:
        """Snapshot tiles intersecting inclusive *bounds* once."""
        min_col, min_row, max_col, max_row = bounds
        first_x = min_col // self.TILE_SIZE
        last_x = max_col // self.TILE_SIZE
        first_y = min_row // self.TILE_SIZE
        last_y = max_row // self.TILE_SIZE
        for tile_y in range(first_y, last_y + 1):
            for tile_x in range(first_x, last_x + 1):
                key = (tile_x, tile_y)
                if key in self._before:
                    continue
                x0, y0, x1, y1 = self._tile_bounds(key)
                self._before[key] = array[y0 : y1 + 1, x0 : x1 + 1].copy()
                self._strength[key] = np.zeros(
                    (y1 - y0 + 1, x1 - x0 + 1),
                    dtype=np.float32,
                )

    def before_region(
        self,
        bounds: tuple[int, int, int, int],
    ) -> np.ndarray:
        """Assemble a dab-sized baseline from captured tile snapshots."""
        return self._assemble(bounds, self._before)

    def strength_region(
        self,
        bounds: tuple[int, int, int, int],
    ) -> np.ndarray:
        """Assemble current per-pixel maximum coverage for one dab."""
        return self._assemble(bounds, self._strength)

    def store_strength(
        self,
        bounds: tuple[int, int, int, int],
        strength: np.ndarray,
    ) -> None:
        """Write a dab-sized maximum-coverage region back into tile storage."""
        self._scatter(bounds, strength, self._strength)

    def patches(self, array: np.ndarray) -> list[dict[str, Any]]:
        """Return ordered serializable tile patches for changed tiles."""
        result: list[dict[str, Any]] = []
        for key in sorted(self._before, key=lambda item: (item[1], item[0])):
            x0, y0, x1, y1 = self._tile_bounds(key)
            before = self._before[key]
            after = array[y0 : y1 + 1, x0 : x1 + 1].copy()
            if np.array_equal(before, after):
                continue
            result.append(
                {
                    "region": (x0, y0, x1, y1),
                    "shape": after.shape,
                    "dtype": str(after.dtype),
                    "before_bytes": before.tobytes(),
                    "after_bytes": after.tobytes(),
                }
            )
        return result

    def _tile_bounds(
        self,
        key: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        tile_x, tile_y = key
        height, width = self._shape[:2]
        x0 = tile_x * self.TILE_SIZE
        y0 = tile_y * self.TILE_SIZE
        return (
            x0,
            y0,
            min(width - 1, x0 + self.TILE_SIZE - 1),
            min(height - 1, y0 + self.TILE_SIZE - 1),
        )

    def _assemble(
        self,
        bounds: tuple[int, int, int, int],
        source: dict[tuple[int, int], np.ndarray],
    ) -> np.ndarray:
        min_col, min_row, max_col, max_row = bounds
        suffix = self._shape[2:]
        result = np.empty(
            (max_row - min_row + 1, max_col - min_col + 1, *suffix),
            dtype=next(iter(source.values())).dtype,
        )
        self._scatter_from_tiles(bounds, result, source)
        return result

    def _scatter_from_tiles(
        self,
        bounds: tuple[int, int, int, int],
        result: np.ndarray,
        source: dict[tuple[int, int], np.ndarray],
    ) -> None:
        min_col, min_row, max_col, max_row = bounds
        for key, tile in source.items():
            x0, y0, x1, y1 = self._tile_bounds(key)
            ix0, iy0 = max(min_col, x0), max(min_row, y0)
            ix1, iy1 = min(max_col, x1), min(max_row, y1)
            if ix0 > ix1 or iy0 > iy1:
                continue
            result[
                iy0 - min_row : iy1 - min_row + 1,
                ix0 - min_col : ix1 - min_col + 1,
            ] = tile[
                iy0 - y0 : iy1 - y0 + 1,
                ix0 - x0 : ix1 - x0 + 1,
            ]

    def _scatter(
        self,
        bounds: tuple[int, int, int, int],
        region: np.ndarray,
        destination: dict[tuple[int, int], np.ndarray],
    ) -> None:
        min_col, min_row, max_col, max_row = bounds
        for key, tile in destination.items():
            x0, y0, x1, y1 = self._tile_bounds(key)
            ix0, iy0 = max(min_col, x0), max(min_row, y0)
            ix1, iy1 = min(max_col, x1), min(max_row, y1)
            if ix0 > ix1 or iy0 > iy1:
                continue
            tile[
                iy0 - y0 : iy1 - y0 + 1,
                ix0 - x0 : ix1 - x0 + 1,
            ] = region[
                iy0 - min_row : iy1 - min_row + 1,
                ix0 - min_col : ix1 - min_col + 1,
            ]


class RasterEditTool:
    """Interactive raster editing delegated from MapGraphicsView.

    Args:
        view: The parent MapGraphicsView.
    """

    def __init__(self, view: "MapGraphicsView") -> None:
        self._view = view

        # State
        self._active: bool = False
        self._mode: RasterEditMode = RasterEditMode.BRUSH
        self._active_node_id: Optional[str] = None
        # Tracks the currently selected raster node even outside edit mode,
        # so that the SAMPLE tool can probe without requiring edit activation.
        self._preview_node_id: Optional[str] = None

        # Tool settings
        self._brush_size: int = 8
        self._paint_value: int = 1
        self._paint_color: tuple[int, int, int, int] = (255, 255, 255, 255)
        self._fill_tolerance: int = 0
        self._gradient_from: int | tuple[int, int, int, int] = 0
        self._gradient_to: int | tuple[int, int, int, int] = 1
        self._falloff: float = 0.0
        self._falloff_curve: str = "cosine"
        self._brush_opacity: float = 1.0

        # Gradient sub-mode
        self._gradient_sub_mode: str = GRADIENT_SUB_LINEAR

        # Brush stroke accumulation
        self._stroke_active: bool = False
        self._stroke_dirty: Optional[tuple[int, int, int, int]] = None
        self._stroke_journal: Optional[_TiledStrokeJournal] = None

        # Dab spacing: last position where a dab was actually placed
        self._last_dab_pos: Optional[tuple[float, float]] = None

        # Gradient state
        self._gradient_start: Optional[QPointF] = None

        # Last known cursor position in scene coordinates
        self._last_cursor_scene_pos: Optional[QPointF] = None

        # Cursor overlay
        self._cursor_item: Optional[QGraphicsEllipseItem] = None

        # Cached theme colors — refreshed once at construction and on theme change
        self._cursor_hex: str = "#E8E8E8"
        self._refresh_theme_colors()
        tool_ref = weakref.ref(self)

        def refresh_theme_colors(_: dict) -> None:
            tool = tool_ref()
            if tool is not None:
                tool._refresh_theme_colors()

        ThemeManager().theme_changed.connect(refresh_theme_colors)

    def _refresh_theme_colors(self) -> None:
        """Update cached cursor color from the current theme.

        Called once at construction and whenever ``ThemeManager.theme_changed``
        fires.  Keeps ``_update_cursor()`` free of per-call ``get_theme()``
        lookups.
        """
        theme = ThemeManager().get_theme()
        self._cursor_hex = theme.get("text_main", "#E8E8E8")
        # Invalidate the existing cursor item so colors are refreshed on next move
        if self._cursor_item is not None:
            self._remove_cursor()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True when raster editing mode is on."""
        return self._active

    @property
    def mode(self) -> RasterEditMode:
        """Current editing sub-mode."""
        return self._mode

    @mode.setter
    def mode(self, value: RasterEditMode) -> None:
        self._mode = value

    @property
    def brush_size(self) -> int:
        """Brush radius in buffer pixels."""
        return self._brush_size

    @brush_size.setter
    def brush_size(self, value: int) -> None:
        self._brush_size = max(1, min(value, 128))

    @property
    def paint_value(self) -> int:
        """Value to paint (0–65535)."""
        return self._paint_value

    @paint_value.setter
    def paint_value(self, value: int) -> None:
        self._paint_value = max(0, min(value, 65535))

    @property
    def paint_color(self) -> tuple[int, int, int, int]:
        """Active straight-alpha RGBA colour."""
        return self._paint_color

    @paint_color.setter
    def paint_color(self, value: tuple[int, int, int, int]) -> None:
        self._paint_color = tuple(
            max(0, min(int(channel), 255)) for channel in value
        )  # type: ignore[assignment]

    @property
    def fill_tolerance(self) -> int:
        """Connected-fill tolerance in raw channel/value units."""
        return self._fill_tolerance

    @fill_tolerance.setter
    def fill_tolerance(self, value: int) -> None:
        self._fill_tolerance = max(0, min(int(value), 65535))

    def set_gradient_targets(
        self,
        start: int | tuple[int, int, int, int],
        end: int | tuple[int, int, int, int],
    ) -> None:
        """Set explicit From and To targets used by gradient tools."""
        self._gradient_from = start
        self._gradient_to = end

    @property
    def falloff(self) -> float:
        """Brush falloff (0.0 = hard, 1.0 = full linear)."""
        return self._falloff

    @falloff.setter
    def falloff(self, value: float) -> None:
        self._falloff = max(0.0, min(value, 1.0))

    @property
    def falloff_curve(self) -> str:
        """Falloff curve shape: ``"linear"``, ``"cosine"``, or ``"gaussian"``."""
        return self._falloff_curve

    @falloff_curve.setter
    def falloff_curve(self, value: str) -> None:
        if value in ("linear", "cosine", "gaussian"):
            self._falloff_curve = value
        else:
            logger.warning("Unknown falloff_curve %r, keeping %r", value, self._falloff_curve)

    @property
    def brush_opacity(self) -> float:
        """Global brush opacity multiplier (0.0 = transparent, 1.0 = full)."""
        return self._brush_opacity

    @brush_opacity.setter
    def brush_opacity(self, value: float) -> None:
        self._brush_opacity = max(0.0, min(1.0, value))

    @property
    def active_node_id(self) -> Optional[str]:
        """Node ID of the raster layer being edited."""
        return self._active_node_id

    def set_gradient_sub_mode(self, sub_mode: str) -> None:
        """Set the gradient sub-mode (linear, radial, or reflected).

        Args:
            sub_mode: One of ``GRADIENT_SUB_LINEAR``, ``GRADIENT_SUB_RADIAL``,
                or ``GRADIENT_SUB_REFLECTED``.
        """
        self._gradient_sub_mode = sub_mode
        logger.debug("set_gradient_sub_mode: sub_mode=%s", sub_mode)

    def set_preview_node_id(self, node_id: Optional[str]) -> None:
        """Update the selected raster node for passive SAMPLE probing.

        Call this whenever the selected raster layer changes so that
        the SAMPLE tool can probe without requiring active edit mode.

        Args:
            node_id: Node ID of the selected raster layer, or ``None``.
        """
        self._preview_node_id = node_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_editing(self, node_id: str) -> None:
        """Enter raster editing mode for a specific layer.

        Args:
            node_id: The raster layer node ID to edit.
        """
        logger.debug(
            "start_editing: node_id=%s mode=%s brush_size=%d paint_value=%d falloff=%.2f",
            node_id,
            self._mode.name,
            self._brush_size,
            self._paint_value,
            self._falloff,
        )
        item = self._view._raster_items.get(node_id)
        if item is None:
            logger.warning(
                "start_editing: node_id=%s not found in _raster_items (keys=%s)",
                node_id,
                list(self._view._raster_items.keys()),
            )
            return
        logger.debug(
            "start_editing: item found buffer=%dx%d",
            item.buffer.width,
            item.buffer.height,
        )
        self._active = True
        self._active_node_id = node_id
        self._preview_node_id = node_id  # keep for passive probing after stop
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        logger.info("Raster edit started: %s (mode=%s)", node_id, self._mode.name)

    def stop_editing(self) -> None:
        """Exit raster editing mode."""
        if self._stroke_active:
            self._finish_stroke()
        self._active = False
        self._active_node_id = None
        self._gradient_start = None
        self._remove_cursor()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        logger.info("Raster edit stopped")

    # ------------------------------------------------------------------
    # Mouse event handlers (return True if consumed)
    # ------------------------------------------------------------------

    def handle_mouse_press(self, scene_pos: QPointF) -> bool:
        """Handle a left-click in raster edit mode.

        Args:
            scene_pos: Click position in scene coordinates.

        Returns:
            True if the event was consumed.
        """
        if not self._active:
            if self._mode == RasterEditMode.SAMPLE:
                return self._try_sample_passively(scene_pos)
            return False

        item = self._get_active_item()
        if item is None:
            logger.warning(
                "handle_mouse_press: no active item for node_id=%s (registered=%s)",
                self._active_node_id,
                list(self._view._raster_items.keys()),
            )
            return False

        norm = self._scene_to_norm(scene_pos)
        if norm is None:
            logger.debug(
                "handle_mouse_press: scene_pos=(%.1f,%.1f) outside map bounds "
                "(pixmap_item=%s)",
                scene_pos.x(),
                scene_pos.y(),
                bool(self._view.pixmap_item),
            )
            return False

        logger.debug(
            "handle_mouse_press: mode=%s pos=(%.1f,%.1f) norm=(%.3f,%.3f) "
            "value=%d brush_size=%d",
            self._mode.name,
            scene_pos.x(),
            scene_pos.y(),
            norm[0],
            norm[1],
            self._paint_value,
            self._brush_size,
        )

        if self._mode == RasterEditMode.BRUSH:
            self._begin_stroke(item)
            self._last_dab_pos = (norm[0], norm[1])
            self._apply_brush(item, norm[0], norm[1])
            return True

        if self._mode == RasterEditMode.FILL:
            self._apply_fill(item, norm[0], norm[1])
            return True

        if self._mode == RasterEditMode.GRADIENT:
            self._gradient_start = scene_pos
            logger.debug(
                "handle_mouse_press: GRADIENT start set to (%.1f,%.1f)",
                scene_pos.x(),
                scene_pos.y(),
            )
            return True

        if self._mode == RasterEditMode.SAMPLE:
            self._apply_sample(item, norm[0], norm[1])
            return True

        return False

    def handle_mouse_move(self, scene_pos: QPointF) -> bool:
        """Handle mouse movement in raster edit mode.

        Args:
            scene_pos: Current mouse position in scene coordinates.

        Returns:
            True if the event was consumed.
        """
        if not self._active:
            return False

        self._update_cursor(scene_pos)

        if self._mode == RasterEditMode.BRUSH and self._stroke_active:
            item = self._get_active_item()
            if item is None:
                return True
            norm = self._scene_to_norm(scene_pos)
            if norm is not None:
                logger.debug(
                    "handle_mouse_move: BRUSH stroke paint at norm=(%.3f,%.3f)",
                    norm[0],
                    norm[1],
                )
                self._emit_dabs(item, norm[0], norm[1])
            else:
                logger.debug(
                    "handle_mouse_move: out-of-bounds at (%.1f,%.1f), skipping paint",
                    scene_pos.x(),
                    scene_pos.y(),
                )
            return True

        return True  # consume to prevent panning

    def handle_mouse_release(self, scene_pos: QPointF) -> bool:
        """Handle mouse release in raster edit mode.

        Args:
            scene_pos: Release position in scene coordinates.

        Returns:
            True if the event was consumed.
        """
        if not self._active:
            return False

        if self._mode == RasterEditMode.BRUSH and self._stroke_active:
            self._finish_stroke()
            return True

        if self._mode == RasterEditMode.GRADIENT and self._gradient_start is not None:
            item = self._get_active_item()
            if item is not None:
                self._apply_gradient(item, self._gradient_start, scene_pos)
            self._gradient_start = None
            return True

        return False

    def handle_key_escape(self) -> bool:
        """Handle Escape key — exit editing mode.

        Emits ``raster_edit_externally_stopped`` so the layer panel can
        reset its toggle button to match the tool state.

        Returns:
            True if the event was consumed.
        """
        if self._active:
            self.stop_editing()
            import shiboken6

            if shiboken6.isValid(self._view):
                self._view.raster_edit_externally_stopped.emit()
            return True
        return False

    # ------------------------------------------------------------------
    # Brush stroke accumulation
    # ------------------------------------------------------------------

    def _begin_stroke(self, item: RasterLayerItem) -> None:
        """Begin lazy tile capture without copying the complete raster."""
        buf = item.buffer
        self._stroke_active = True
        self._stroke_dirty = None
        self._stroke_journal = _TiledStrokeJournal(buf.editable_data)
        self._last_dab_pos = None
        logger.debug(
            "_begin_stroke: node_id=%s buffer=%dx%d",
            self._active_node_id,
            buf.width,
            buf.height,
        )

    def _apply_brush(
        self,
        item: RasterLayerItem,
        x_norm: float,
        y_norm: float,
        update_display: bool = True,
    ) -> tuple[int, int, int, int]:
        """Paint a single brush dab and optionally refresh the display.

        Args:
            item: The active raster layer item.
            x_norm: Horizontal position in normalised [0, 1] space.
            y_norm: Vertical position in normalised [0, 1] space.
            update_display: When ``True`` (default) immediately calls
                ``item.update_region`` so the stroke appears on screen.
                Pass ``False`` when batching multiple dabs — the caller
                is responsible for a single ``update_region`` call.

        Returns:
            Dirty region ``(min_col, min_row, max_col, max_row)``.
        """
        buf = item.buffer
        journal = self._stroke_journal
        if journal is None:
            raise RuntimeError("Brush dab started without a stroke journal")
        center_col, center_row = buf._norm_to_pixel(x_norm, y_norm)
        dirty = brush_bounds(
            buf.editable_data.shape,
            center_col,
            center_row,
            self._brush_size,
        )
        journal.capture_bounds(buf.editable_data, dirty)
        if buf.raster_mode is RasterPaintMode.DISCRETE:
            dirty = buf.paint_brush(
                x_norm,
                y_norm,
                self._brush_size,
                self._paint_value,
            )
        else:
            baseline = journal.before_region(dirty)
            strength = journal.strength_region(dirty)
            if buf.raster_mode is RasterPaintMode.RGBA:
                dirty = buf.paint_color_brush(
                    x_norm,
                    y_norm,
                    self._brush_size,
                    self._paint_color,
                    hardness=1.0 - self._falloff,
                    opacity=self._brush_opacity,
                    falloff_curve=self._falloff_curve,
                    stroke_before=baseline,
                    stroke_strength_map=strength,
                )
            else:
                dirty = buf.paint_brush(
                    x_norm,
                    y_norm,
                    self._brush_size,
                    self._paint_value,
                    self._falloff,
                    falloff_curve=self._falloff_curve,
                    opacity=self._brush_opacity,
                    stroke_before=baseline,
                    stroke_strength_map=strength,
                )
            journal.store_strength(dirty, strength)
        logger.debug(
            "_apply_brush: pos=(%.3f,%.3f) radius=%d value=%d dirty=%s",
            x_norm,
            y_norm,
            self._brush_size,
            self._paint_value,
            dirty,
        )

        # Expand accumulated stroke dirty region
        if self._stroke_dirty is None:
            self._stroke_dirty = dirty
        else:
            self._stroke_dirty = (
                min(self._stroke_dirty[0], dirty[0]),
                min(self._stroke_dirty[1], dirty[1]),
                max(self._stroke_dirty[2], dirty[2]),
                max(self._stroke_dirty[3], dirty[3]),
            )

        if update_display:
            item.update_region(dirty)

        return dirty

    def _emit_dabs(self, item: RasterLayerItem, x_norm: float, y_norm: float) -> None:
        """Paint interpolated dabs from the last placed dab to *x_norm/y_norm*.

        Interpolates positions at ``RASTER_DAB_SPACING_FACTOR * brush_size``
        pixel intervals so that fast mouse movement does not leave visible gaps
        between dabs.

        Args:
            item: The active raster layer item.
            x_norm: Current horizontal position in normalised [0, 1] space.
            y_norm: Current vertical position in normalised [0, 1] space.
        """
        if self._last_dab_pos is None:
            # First move after press — place a dab directly and track position
            self._apply_brush(item, x_norm, y_norm)
            self._last_dab_pos = (x_norm, y_norm)
            return

        buf = item.buffer
        lx, ly = self._last_dab_pos

        # Convert both positions to pixel space for metric distance
        dx_px = (x_norm - lx) * buf.width
        dy_px = (y_norm - ly) * buf.height
        dist_px = float(np.hypot(dx_px, dy_px))

        spacing_px = max(1.0, self._brush_size * RASTER_DAB_SPACING_FACTOR)
        if dist_px < spacing_px:
            # Haven't moved far enough for a new dab yet
            return

        # How many evenly-spaced dabs fit between last position and current?
        n_dabs = int(dist_px / spacing_px)
        total_steps = dist_px / spacing_px  # may be fractional

        # Paint all dabs without triggering per-dab Qt renders, then do a
        # single blit covering the union of all dirty regions.
        union: Optional[tuple[int, int, int, int]] = None
        for i in range(1, n_dabs + 1):
            t = i / total_steps
            xi = lx + t * (x_norm - lx)
            yi = ly + t * (y_norm - ly)
            d = self._apply_brush(item, xi, yi, update_display=False)
            if union is None:
                union = d
            else:
                union = (
                    min(union[0], d[0]),
                    min(union[1], d[1]),
                    max(union[2], d[2]),
                    max(union[3], d[3]),
                )

        if union is not None:
            item.update_region(union)

        # Advance last_dab_pos to the position of the last placed dab (not
        # the current mouse position) so carry-over spacing is continuous.
        t_last = n_dabs / total_steps
        self._last_dab_pos = (
            lx + t_last * (x_norm - lx),
            ly + t_last * (y_norm - ly),
        )

    def _finish_stroke(self) -> None:
        """Emit a paint command for the completed stroke."""
        item = self._get_active_item()
        self._stroke_active = False

        journal = self._stroke_journal
        if item is None or journal is None or self._stroke_dirty is None:
            logger.debug(
                "_finish_stroke: nothing to commit (item=%s journal=%s dirty=%s)",
                item is not None,
                journal is not None,
                self._stroke_dirty,
            )
            self._stroke_journal = None
            self._stroke_dirty = None
            return

        patches = journal.patches(item.buffer.editable_data)
        logger.debug(
            "_finish_stroke: node_id=%s dirty=%s tile_patches=%d",
            self._active_node_id,
            self._stroke_dirty,
            len(patches),
        )

        if patches:
            self._emit_stroke_completed(self._active_node_id or "", patches)

        self._stroke_journal = None
        self._stroke_dirty = None
        self._last_dab_pos = None

    # ------------------------------------------------------------------
    # Fill
    # ------------------------------------------------------------------

    def _apply_fill(self, item: RasterLayerItem, x_norm: float, y_norm: float) -> None:
        """Flood fill at the clicked position."""
        buf = item.buffer
        seed_val = buf.sample_at(x_norm, y_norm)
        logger.debug(
            "_apply_fill: pos=(%.3f,%.3f) seed_value=%s buffer=%dx%d",
            x_norm,
            y_norm,
            seed_val,
            buf.width,
            buf.height,
        )
        tolerance = min(
            self._fill_tolerance,
            255 if buf.raster_mode is RasterPaintMode.RGBA else 65535,
        )
        dirty = buf.connected_fill_bounds(x_norm, y_norm, tolerance)
        if dirty is None:
            return
        journal = _TiledStrokeJournal(buf.editable_data)
        journal.capture_bounds(buf.editable_data, dirty)
        target: int | tuple[int, int, int, int] = (
            self._paint_color
            if buf.raster_mode is RasterPaintMode.RGBA
            else self._paint_value
        )
        dirty = buf.fill_connected(x_norm, y_norm, target, tolerance)
        if dirty is None:
            return
        logger.debug("_apply_fill: dirty_region=%s", dirty)
        item.update_region(dirty)
        patches = journal.patches(buf.editable_data)
        if patches:
            self._emit_stroke_completed(self._active_node_id or "", patches)

    # ------------------------------------------------------------------
    # Gradient
    # ------------------------------------------------------------------

    def _apply_gradient(
        self, item: RasterLayerItem, start: QPointF, end: QPointF
    ) -> None:
        """Paint a gradient between two scene points.

        Dispatches to linear, radial, or reflected sub-mode based on
        ``_gradient_sub_mode``.
        """
        n0 = self._scene_to_norm(start)
        n1 = self._scene_to_norm(end)
        if n0 is None or n1 is None:
            logger.warning(
                "_apply_gradient: could not normalize points start=%s n0=%s end=%s n1=%s",
                start,
                n0,
                end,
                n1,
            )
            return

        logger.debug(
            "_apply_gradient: sub_mode=%s n0=(%.3f,%.3f) n1=(%.3f,%.3f) "
            "value_end=%d width_px=%d",
            self._gradient_sub_mode,
            n0[0],
            n0[1],
            n1[0],
            n1[1],
            self._paint_value,
            self._brush_size,
        )
        buf = item.buffer
        if buf.raster_mode is RasterPaintMode.DISCRETE:
            logger.warning("Gradient ignored for discrete raster %s", item.node_id)
            return
        journal = _TiledStrokeJournal(buf.editable_data)
        full_bounds = (0, 0, buf.width - 1, buf.height - 1)
        journal.capture_bounds(buf.editable_data, full_bounds)
        gradient_from = self._gradient_from
        gradient_to = self._gradient_to
        if buf.raster_mode is RasterPaintMode.RGBA:
            if not isinstance(gradient_from, tuple):
                gradient_from = self._paint_color
            if not isinstance(gradient_to, tuple):
                gradient_to = self._paint_color
        else:
            if isinstance(gradient_from, tuple):
                gradient_from = 0
            if isinstance(gradient_to, tuple):
                gradient_to = self._paint_value
        dirty = buf.paint_explicit_gradient(
            n0,
            n1,
            gradient_from,
            gradient_to,
            kind=self._gradient_sub_mode,
            width_px=self._brush_size,
        )
        if dirty is None:
            return

        logger.debug("_apply_gradient: dirty_region=%s", dirty)

        item.update_region(dirty)
        patches = journal.patches(buf.editable_data)
        if patches:
            self._emit_stroke_completed(self._active_node_id or "", patches)

    # ------------------------------------------------------------------
    # Sample / probe
    # ------------------------------------------------------------------

    def _try_sample_passively(self, scene_pos: QPointF) -> bool:
        """Probe a raster layer value without being in active edit mode.

        Uses *_preview_node_id* (set when a raster layer is selected) to
        identify which layer to probe.  Falls back to the first available
        raster item if no preview node is known.

        Args:
            scene_pos: Click position in scene coordinates.

        Returns:
            True if a value was probed and the signal emitted.
        """
        node_id = self._preview_node_id
        if not node_id:
            return False

        item = self._view._raster_items.get(node_id)
        if item is None:
            return False

        norm = self._scene_to_norm(scene_pos)
        if norm is None:
            return False

        value = item.buffer.sample_at(norm[0], norm[1])
        logger.debug(
            "_try_sample_passively: pos=(%.3f,%.3f) value=%s node_id=%s",
            norm[0],
            norm[1],
            value,
            node_id,
        )
        self._view.raster_value_probed.emit(node_id, value, norm[0], norm[1])
        return True

    def _apply_sample(
        self, item: RasterLayerItem, x_norm: float, y_norm: float
    ) -> None:
        """Read the value at the given position and emit a probe signal."""
        value = item.buffer.sample_at(x_norm, y_norm)
        if isinstance(value, tuple) and len(value) == 4:
            self._paint_color = (
                value[0],
                value[1],
                value[2],
                value[3],
            )
        else:
            self._paint_value = value
        logger.debug(
            "_apply_sample: pos=(%.3f,%.3f) value=%s node_id=%s",
            x_norm,
            y_norm,
            value,
            self._active_node_id,
        )
        self._view.raster_value_probed.emit(
            self._active_node_id or "", value, x_norm, y_norm
        )

    # ------------------------------------------------------------------
    # Cursor overlay
    # ------------------------------------------------------------------

    def _update_cursor(self, scene_pos: QPointF) -> None:
        """Update the visual brush circle at the cursor position."""
        self._last_cursor_scene_pos = scene_pos
        if self._mode not in (RasterEditMode.BRUSH, RasterEditMode.GRADIENT):
            self._remove_cursor()
            return

        item = self._get_active_item()
        if item is None:
            self._remove_cursor()
            return

        # Convert brush radius from buffer pixels to scene pixels
        scene_rect = item.scene_rect
        buf_w = max(1, item.buffer.width)
        px_per_scene = scene_rect.width() / buf_w
        radius_scene = self._brush_size * px_per_scene

        if self._cursor_item is None:
            _cursor_color = QColor(self._cursor_hex)
            _cursor_color.setAlpha(180)
            _fill_color = QColor(self._cursor_hex)
            _fill_color.setAlpha(30)
            pen = QPen(_cursor_color, 1.5)
            brush = QBrush(_fill_color)
            self._cursor_item = QGraphicsEllipseItem()
            self._cursor_item.setPen(pen)
            self._cursor_item.setBrush(brush)
            self._cursor_item.setZValue(MAP_LAYER_Z_UI_OVERLAY + 2)
            self._view.graphics_scene.addItem(self._cursor_item)

        self._cursor_item.setRect(
            QRectF(
                scene_pos.x() - radius_scene,
                scene_pos.y() - radius_scene,
                radius_scene * 2,
                radius_scene * 2,
            )
        )
        self._cursor_item.setVisible(True)

    def _remove_cursor(self) -> None:
        """Remove the brush cursor overlay from the scene."""
        if self._cursor_item is not None:
            scene = self._view.graphics_scene
            if scene is not None:
                scene.removeItem(self._cursor_item)
            self._cursor_item = None

    def refresh_cursor(self) -> None:
        """Re-draw the cursor overlay at the last known position.

        Call after zoom or brush size changes so the overlay circle
        stays in sync with the current view transform and tool settings.
        """
        if self._last_cursor_scene_pos is not None and self._active:
            self._update_cursor(self._last_cursor_scene_pos)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit_stroke_completed(
        self,
        node_id: str,
        patches_or_region: list[dict[str, Any]] | tuple[int, int, int, int],
        before_bytes: bytes | None = None,
        after_bytes: bytes | None = None,
    ) -> None:
        """Emit ``raster_stroke_completed`` only when the view is still valid.

        Guards against RuntimeError when the C++ view object has already been
        deleted during teardown.

        Args:
            node_id: Raster layer node ID.
            patches_or_region: Serializable patch collection, or one legacy
                dirty rectangle.
            before_bytes: Legacy region bytes before the operation.
            after_bytes: Legacy region bytes after the operation.
        """
        import shiboken6

        if not shiboken6.isValid(self._view):
            logger.debug("_emit_stroke_completed: view already deleted, skipping emit")
            return
        if isinstance(patches_or_region, tuple):
            item = self._get_active_item()
            if item is None or before_bytes is None or after_bytes is None:
                return
            min_col, min_row, max_col, max_row = patches_or_region
            shape: tuple[int, ...]
            if item.buffer.pixel_format.value == "rgba8":
                shape = (max_row - min_row + 1, max_col - min_col + 1, 4)
            else:
                shape = (max_row - min_row + 1, max_col - min_col + 1)
            patches = [
                {
                    "region": patches_or_region,
                    "shape": shape,
                    "dtype": str(item.buffer.editable_data.dtype),
                    "before_bytes": before_bytes,
                    "after_bytes": after_bytes,
                }
            ]
        else:
            patches = patches_or_region
        try:
            self._view.raster_stroke_completed.emit(node_id, patches)
        except RuntimeError:
            logger.debug("_emit_stroke_completed: RuntimeError during emit, skipping")

    def _get_active_item(self) -> Optional[RasterLayerItem]:
        """Look up the active RasterLayerItem from the view's registry."""
        if self._active_node_id is None:
            logger.debug("_get_active_item: no active_node_id set")
            return None
        item = self._view._raster_items.get(self._active_node_id)
        if item is None:
            logger.warning(
                "_get_active_item: node_id=%s not in _raster_items (registered=%s)",
                self._active_node_id,
                list(self._view._raster_items.keys()),
            )
        return item

    def _scene_to_norm(self, scene_pos: QPointF) -> Optional[tuple[float, float]]:
        """Convert scene coordinates to normalised [0, 1] coordinates.

        Returns:
            (x_norm, y_norm) or None if not over the map pixmap.
        """
        if not self._view.pixmap_item:
            logger.debug(
                "_scene_to_norm: pixmap_item is None — coordinate system not set up"
            )
            return None
        try:
            norm = self._view.coord_system.to_normalized(scene_pos)
            x, y = norm[0], norm[1]
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return (x, y)
            logger.debug(
                "_scene_to_norm: (%.1f,%.1f) → norm=(%.3f,%.3f) out of [0,1] range",
                scene_pos.x(),
                scene_pos.y(),
                x,
                y,
            )
        except Exception as exc:
            logger.debug(
                "_scene_to_norm: exception converting (%.1f,%.1f): %s",
                scene_pos.x(),
                scene_pos.y(),
                exc,
            )
        return None
