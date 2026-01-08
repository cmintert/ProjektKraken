"""
Map Marker Item Module.

Provides the MarkerItem class for rendering markers on the map.
"""

import logging
import os

# Forward declaration to avoid circular import
from typing import Any, Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QStyleOptionGraphicsItem,
    QWidget,
)


# Resolve marker icons path
MARKER_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "assets", "icons", "markers"
)

logger = logging.getLogger(__name__)


class MarkerItem(QGraphicsObject):
    """
    Draggable marker on a map with customizable SVG icon.

    Represents an entity or event at a specific location on the map.
    Emits signals through the parent MapGraphicsView when dragged.
    Supports custom SVG icons with fallback to colored circles.

    Signals:
        clicked: Emitted when the marker is clicked
                 (released within threshold distance).
                 Args: (marker_id: str, object_type: str)
    """

    clicked = Signal(str, str)

    MARKER_SIZE = 24  # Size of the marker icon
    COLORS = {
        "entity": QColor("#3498DB"),  # Blue
        "event": QColor("#F39C12"),  # Orange
        "default": QColor("#888888"),  # Gray
    }
    DEFAULT_ICON = "map-pin.svg"

    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> None:
        """
        Initializes a MarkerItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Label text for the marker (tooltip).
            pixmap_item: Reference to the map pixmap item for coordinate conversion.
            icon: Optional icon filename (e.g., 'castle.svg'). Falls back to circle.
        """
        super().__init__()

        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._icon_name = icon
        self._svg_renderer: Optional[QSvgRenderer] = None
        self._custom_color = color
        self._color = (
            QColor(color)
            if color
            else self.COLORS.get(object_type, self.COLORS["default"])
        )

        # Load icon if specified
        self._load_icon(icon)

        logger.debug(
            f"Created MarkerItem {marker_id} with label: {label}, icon: {icon}"
        )

        # Tooltip
        self.setToolTip(label)

        # Make draggable and selectable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

        # Cursor hint
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Z-value to appear on top of the map
        self.setZValue(10)

        # Drag tracking
        self._is_dragging = False
        self._drag_start_pos = None

    def _load_icon(self, icon_name: Optional[str]) -> None:
        """
        Loads an SVG icon for the marker.

        Args:
            icon_name: Filename of the icon (e.g., 'castle.svg').
        """
        if not icon_name:
            icon_name = self.DEFAULT_ICON

        icon_path = os.path.join(MARKER_ICONS_PATH, icon_name)
        if os.path.exists(icon_path):
            self._svg_renderer = QSvgRenderer(icon_path)
            if not self._svg_renderer.isValid():
                logger.warning(f"Invalid SVG file: {icon_path}")
                self._svg_renderer = None
            else:
                self._icon_name = icon_name
        else:
            logger.debug(f"Icon not found: {icon_path}, using fallback circle")
            self._svg_renderer = None

    def set_icon(self, icon_name: str) -> None:
        """
        Changes the marker's icon.

        Args:
            icon_name: Filename of the new icon.
        """
        self._load_icon(icon_name)
        self.update()

    def get_icon(self) -> Optional[str]:
        """
        Returns the current icon filename.

        Returns:
            Optional[str]: The icon filename or None if using fallback.
        """
        return self._icon_name

    def set_color(self, color: str) -> None:
        """
        Sets the custom color for the marker.

        Args:
            color: The hex color string (e.g., '#FF5733').
        """
        self._custom_color = color
        self._color = QColor(color)
        self.update()

    def get_color(self) -> Optional[str]:
        """
        Returns the current custom color.

        Returns:
            Optional[str]: The hex color string or None.
        """
        return self._custom_color

    def boundingRect(self) -> QRectF:
        """
        Returns the bounding rectangle for the marker.

        Returns:
            QRectF: The bounding rect centered on (0, 0).
        """
        half = self.MARKER_SIZE / 2
        return QRectF(-half, -half, self.MARKER_SIZE, self.MARKER_SIZE)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """
        Paints the marker, either as an SVG icon or fallback circle.

        Args:
            painter: The QPainter to use.
            option: Style options.
            widget: The widget being painted on.
        """
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()

        if self._svg_renderer and self._svg_renderer.isValid():
            self._draw_svg_icon(painter, rect)
        else:
            self._draw_fallback_circle(painter, rect)

    def _draw_svg_icon(self, painter: QPainter, rect: QRectF) -> None:
        """Draws the SVG icon, applying custom color tint if set."""
        # Draw shadow/background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
        painter.drawEllipse(rect.adjusted(2, 2, 2, 2))

        if self._custom_color:
            pixmap = self._render_svg_to_pixmap()
            self._tint_pixmap(pixmap, self._color)

            painter.drawPixmap(rect.toRect(), pixmap)
        else:
            # Standard SVG rendering (no tint)
            self._svg_renderer.render(painter, rect)

        # Draw selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

    def _render_svg_to_pixmap(self) -> QPixmap:
        """Renders the current SVG to a transparent QPixmap."""
        pixmap = QPixmap(int(self.MARKER_SIZE), int(self.MARKER_SIZE))
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        if self._svg_renderer:
            self._svg_renderer.render(p)
        p.end()
        return pixmap

    def _tint_pixmap(self, pixmap: QPixmap, color: QColor) -> None:
        """Tint a pixmap with the given color."""
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()

    def _draw_fallback_circle(self, painter: QPainter, rect: QRectF) -> None:
        """Draws a fallback colored circle."""
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track drag start."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = self.pos()
            logger.debug(
                f"Marker {self.marker_id} drag started at {self._drag_start_pos}"
            )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit position change on drag end, or clicked signal if distance small."""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        # Check for click vs drag
        if self._drag_start_pos is not None:
            dist = (self.pos() - self._drag_start_pos).manhattanLength()
            if dist < 3:
                # It's a click!
                self.clicked.emit(self.marker_id, self.object_type)
                logger.debug(f"Marker {self.marker_id} clicked.")

        if self._is_dragging:
            self._is_dragging = False
            self._handle_drag_end()

        super().mouseReleaseEvent(event)

    def _handle_drag_end(self) -> None:
        """Calculates normalized position and emits marker_moved signal."""
        if norm_pos := self._get_normalized_position():
            norm_x, norm_y = norm_pos
            # Emit only on release
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                # Use string check to avoid circular import
                if view.__class__.__name__ == "MapGraphicsView":
                    view.marker_moved.emit(self.marker_id, norm_x, norm_y)
                    logger.debug(
                        f"Marker {self.marker_id} drag ended at normalized "
                        f"({norm_x:.3f}, {norm_y:.3f})"
                    )

    def _get_normalized_position(self) -> Optional[tuple[float, float]]:
        """Calculates the current normalized position of the marker."""
        if not (self.pixmap_item and self.pixmap_item.pixmap()):
            return None

        scene_pos = self.pos()
        pixmap_rect = self.pixmap_item.sceneBoundingRect()

        rel_x = scene_pos.x() - pixmap_rect.left()
        rel_y = scene_pos.y() - pixmap_rect.top()

        width = pixmap_rect.width()
        height = pixmap_rect.height()

        norm_x = rel_x / width if width > 0 else 0.0
        norm_y = rel_y / height if height > 0 else 0.0

        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        return norm_x, norm_y

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Called when the item's state changes.

        Note: We no longer emit marker_moved here. Position updates
        are only emitted on mouseReleaseEvent to avoid flooding.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The processed value.
        """
        return super().itemChange(change, value)
