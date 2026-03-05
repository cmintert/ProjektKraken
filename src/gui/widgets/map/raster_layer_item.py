"""Raster Layer Item — QGraphicsPixmapItem for data-raster overlays.

Holds a :class:`~src.gui.widgets.map.map_data_buffer.MapDataBuffer` and
renders it as a colourised RGBA pixmap in the map's graphics scene.
"""

import logging
from typing import Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.app.constants import MAP_LAYER_Z_RASTER
from src.gui.widgets.map.map_data_buffer import ColorMap, MapDataBuffer

logger = logging.getLogger(__name__)


class RasterLayerItem(QGraphicsPixmapItem):
    """Scene item that renders a 16-bit raster buffer as a colourised overlay.

    The item is positioned and scaled to match the map background image
    bounding rect (scene coordinates).

    Args:
        buffer: The data buffer to visualise.
        color_map: Colour mapping for visualisation.
        scene_rect: The bounding rect of the map background pixmap
            in scene coordinates.  The raster will be stretched to
            fill this rect.
        node_id: Layer node ID for cross-referencing with the layer model.

    """

    def __init__(
        self,
        buffer: MapDataBuffer,
        color_map: ColorMap,
        scene_rect: QRectF,
        node_id: str = "",
    ) -> None:
        super().__init__()
        self._buffer = buffer
        self._color_map = color_map
        self._scene_rect = scene_rect
        self._node_id = node_id

        self.setZValue(MAP_LAYER_Z_RASTER)
        self.setPos(scene_rect.topLeft())

        # Initial render
        self.update_display()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def buffer(self) -> MapDataBuffer:
        """The underlying data buffer."""
        return self._buffer

    @property
    def color_map(self) -> ColorMap:
        """Current colour map."""
        return self._color_map

    @color_map.setter
    def color_map(self, value: ColorMap) -> None:
        self._color_map = value

    @property
    def node_id(self) -> str:
        """Layer node ID."""
        return self._node_id

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def update_display(self, color_map: Optional[ColorMap] = None) -> None:
        """Re-colourize the buffer and update the displayed pixmap.

        Args:
            color_map: Optional new colour map.  If ``None``, uses the
                existing one.

        """
        if color_map is not None:
            self._color_map = color_map

        qimage = self._buffer.colorize(self._color_map)
        pixmap = QPixmap.fromImage(qimage)

        # Scale pixmap to fill the scene rect
        if not self._scene_rect.isEmpty():
            pixmap = pixmap.scaled(
                int(self._scene_rect.width()),
                int(self._scene_rect.height()),
            )

        self.setPixmap(pixmap)

    def set_scene_rect(self, rect: QRectF) -> None:
        """Update the target scene rectangle and re-render.

        Args:
            rect: New bounding rect from the map background.

        """
        self._scene_rect = rect
        self.setPos(rect.topLeft())
        self.update_display()

    def update_region(
        self,
        dirty_region: tuple[int, int, int, int],
        color_map: Optional[ColorMap] = None,
    ) -> None:
        """Re-colourize only the dirty region and blit onto the existing pixmap.

        This avoids a full-buffer re-render after small edits such as
        brush strokes.

        Args:
            dirty_region: ``(min_col, min_row, max_col, max_row)`` in
                buffer pixel coordinates.
            color_map: Optional new colour map.  Uses existing if *None*.

        """
        if color_map is not None:
            self._color_map = color_map

        cmap = self._color_map
        min_col, min_row, max_col, max_row = dirty_region
        tile_img = self._buffer.colorize_region(
            cmap, min_col, min_row, max_col, max_row
        )

        current = self.pixmap()
        if current.isNull():
            self.update_display()
            return

        # Map buffer pixel coords → pixmap pixel coords (may differ if scaled)
        sx = current.width() / max(1, self._buffer.width)
        sy = current.height() / max(1, self._buffer.height)

        dest_x = int(min_col * sx)
        dest_y = int(min_row * sy)
        dest_w = int((max_col - min_col + 1) * sx)
        dest_h = int((max_row - min_row + 1) * sy)

        scaled_tile = QPixmap.fromImage(tile_img).scaled(dest_w, dest_h)

        painter = QPainter(current)
        # Erase the region first (compositing over old pixels)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(dest_x, dest_y, scaled_tile)
        painter.end()

        self.setPixmap(current)
