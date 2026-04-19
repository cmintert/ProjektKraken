"""Raster Edit Tool for the Map Graphics View.

Manages interactive raster editing: brush painting, flood fill,
gradient painting, and value sampling.  Follows the same delegation
pattern as :class:`DrawingTool` — the parent
:class:`MapGraphicsView` calls ``handle_mouse_*`` and the tool
returns ``True`` when it consumes the event.
"""

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsView,
)

from src.app.constants import MAP_LAYER_Z_UI_OVERLAY
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
        self._falloff: float = 0.0

        # Gradient sub-mode
        self._gradient_sub_mode: str = GRADIENT_SUB_LINEAR

        # Brush stroke accumulation
        self._stroke_active: bool = False
        self._stroke_before: Optional[np.ndarray] = None
        self._stroke_dirty: Optional[tuple[int, int, int, int]] = None

        # Gradient state
        self._gradient_start: Optional[QPointF] = None

        # Last known cursor position in scene coordinates
        self._last_cursor_scene_pos: Optional[QPointF] = None

        # Cursor overlay
        self._cursor_item: Optional[QGraphicsEllipseItem] = None

        # Cached theme colors — refreshed once at construction and on theme change
        self._cursor_hex: str = "#E8E8E8"
        self._refresh_theme_colors()
        ThemeManager().theme_changed.connect(lambda _: self._refresh_theme_colors())

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
    def falloff(self) -> float:
        """Brush falloff (0.0 = hard, 1.0 = full linear)."""
        return self._falloff

    @falloff.setter
    def falloff(self, value: float) -> None:
        self._falloff = max(0.0, min(value, 1.0))

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
                self._apply_brush(item, norm[0], norm[1])
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
        """Snapshot the full buffer before a stroke begins."""
        buf = item.buffer
        self._stroke_active = True
        self._stroke_before = buf.data.copy()
        self._stroke_dirty = None
        logger.debug(
            "_begin_stroke: node_id=%s buffer=%dx%d",
            self._active_node_id,
            buf.width,
            buf.height,
        )

    def _apply_brush(self, item: RasterLayerItem, x_norm: float, y_norm: float) -> None:
        """Paint a single brush dab and update display."""
        buf = item.buffer
        dirty = buf.paint_brush(
            x_norm, y_norm, self._brush_size, self._paint_value, self._falloff
        )
        logger.debug(
            "_apply_brush: pos=(%.3f,%.3f) radius=%d value=%d dirty=%s",
            x_norm,
            y_norm,
            self._brush_size,
            self._paint_value,
            dirty,
        )

        # Expand accumulated dirty region
        if self._stroke_dirty is None:
            self._stroke_dirty = dirty
        else:
            self._stroke_dirty = (
                min(self._stroke_dirty[0], dirty[0]),
                min(self._stroke_dirty[1], dirty[1]),
                max(self._stroke_dirty[2], dirty[2]),
                max(self._stroke_dirty[3], dirty[3]),
            )

        # Partial display update for responsiveness
        item.update_region(dirty)

    def _finish_stroke(self) -> None:
        """Emit a paint command for the completed stroke."""
        item = self._get_active_item()
        self._stroke_active = False

        if item is None or self._stroke_before is None or self._stroke_dirty is None:
            logger.debug(
                "_finish_stroke: nothing to commit (item=%s before=%s dirty=%s)",
                item is not None,
                self._stroke_before is not None,
                self._stroke_dirty,
            )
            self._stroke_before = None
            self._stroke_dirty = None
            return

        d = self._stroke_dirty
        before_region = self._stroke_before[d[1] : d[3] + 1, d[0] : d[2] + 1].copy()
        after_region = item.buffer.get_region(d[0], d[1], d[2], d[3])
        logger.debug(
            "_finish_stroke: node_id=%s dirty=%s before_bytes=%d after_bytes=%d",
            self._active_node_id,
            d,
            len(before_region.tobytes()),
            len(after_region.tobytes()),
        )

        # Emit signal for command creation
        self._emit_stroke_completed(
            self._active_node_id or "",
            d,
            before_region.tobytes(),
            after_region.tobytes(),
        )

        self._stroke_before = None
        self._stroke_dirty = None

    # ------------------------------------------------------------------
    # Fill
    # ------------------------------------------------------------------

    def _apply_fill(self, item: RasterLayerItem, x_norm: float, y_norm: float) -> None:
        """Flood fill at the clicked position."""
        buf = item.buffer
        seed_val = buf.get_value_at(x_norm, y_norm)
        logger.debug(
            "_apply_fill: pos=(%.3f,%.3f) seed_value=%d fill_value=%d buffer=%dx%d",
            x_norm,
            y_norm,
            seed_val,
            self._paint_value,
            buf.width,
            buf.height,
        )
        before = buf.data.copy()

        dirty = buf.flood_fill(x_norm, y_norm, self._paint_value)
        logger.debug("_apply_fill: dirty_region=%s", dirty)

        before_region = before[dirty[1] : dirty[3] + 1, dirty[0] : dirty[2] + 1].copy()
        after_region = buf.get_region(dirty[0], dirty[1], dirty[2], dirty[3])

        item.update_region(dirty)

        self._emit_stroke_completed(
            self._active_node_id or "",
            dirty,
            before_region.tobytes(),
            after_region.tobytes(),
        )

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
        before = buf.data.copy()

        if self._gradient_sub_mode == GRADIENT_SUB_RADIAL:
            dx = n1[0] - n0[0]
            dy = n1[1] - n0[1]
            radius_norm = float(np.sqrt(dx * dx + dy * dy))
            dirty = buf.paint_radial_gradient(
                n0[0], n0[1], radius_norm, self._paint_value, 0
            )
        elif self._gradient_sub_mode == GRADIENT_SUB_REFLECTED:
            dirty = buf.paint_reflected_gradient(
                n0[0],
                n0[1],
                n1[0],
                n1[1],
                self._paint_value,
                0,
                self._brush_size,
            )
        else:
            dirty = buf.paint_gradient(
                n0[0],
                n0[1],
                n1[0],
                n1[1],
                0,
                self._paint_value,
                self._brush_size,
            )

        logger.debug("_apply_gradient: dirty_region=%s", dirty)

        before_region = before[dirty[1] : dirty[3] + 1, dirty[0] : dirty[2] + 1].copy()
        after_region = buf.get_region(dirty[0], dirty[1], dirty[2], dirty[3])

        item.update_region(dirty)

        self._emit_stroke_completed(
            self._active_node_id or "",
            dirty,
            before_region.tobytes(),
            after_region.tobytes(),
        )

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

        value = item.buffer.get_value_at(norm[0], norm[1])
        logger.debug(
            "_try_sample_passively: pos=(%.3f,%.3f) value=%d node_id=%s",
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
        value = item.buffer.get_value_at(x_norm, y_norm)
        logger.debug(
            "_apply_sample: pos=(%.3f,%.3f) value=%d node_id=%s",
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
            self._view.scene.addItem(self._cursor_item)

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
            scene = self._view.scene
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
        dirty: tuple,
        before_bytes: bytes,
        after_bytes: bytes,
    ) -> None:
        """Emit ``raster_stroke_completed`` only when the view is still valid.

        Guards against RuntimeError when the C++ view object has already been
        deleted during teardown.

        Args:
            node_id: Raster layer node ID.
            dirty: ``(min_col, min_row, max_col, max_row)`` dirty rectangle.
            before_bytes: Buffer region bytes before the operation.
            after_bytes: Buffer region bytes after the operation.
        """
        import shiboken6

        if not shiboken6.isValid(self._view):
            logger.debug("_emit_stroke_completed: view already deleted, skipping emit")
            return
        try:
            self._view.raster_stroke_completed.emit(
                node_id, dirty, before_bytes, after_bytes
            )
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
