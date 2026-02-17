"""Map Marker Item Module.

Provides the MarkerItem class for rendering markers on the map.
"""

import logging
import os

# Forward declaration to avoid circular import
from typing import Any, Dict, Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsSimpleTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.style_constants import BASE_SIZE
from src.services.visual_resolver import VisualResolver

# Resolve marker icons path
MARKER_ICONS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "default_assets",
    "icons",
    "markers",
)

logger = logging.getLogger(__name__)


class MarkerItem(QGraphicsObject):
    """Draggable marker on a map with customizable SVG icon.

    Represents an entity or event at a specific location on the map.
    Emits signals through the parent MapGraphicsView when dragged.
    Supports custom SVG icons with fallback to colored circles.

    Attributes:
        clicked (Signal): Emitted when the marker is clicked (released within
            threshold distance). Arguments are (marker_id: str, object_type: str).
    """

    clicked = Signal(str, str)

    MARKER_SIZE = BASE_SIZE  # Size of the marker icon
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
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        visual_attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initializes a MarkerItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Label text for the marker (displayed below marker).
            pixmap_item: Reference to the map pixmap item for coordinate conversion.
            icon: Optional icon filename (e.g., 'castle.svg'). Falls back to circle.
            color: Optional color hex string.
            description: Optional description for tooltip. Falls back to label if empty.
            lore_date: Optional lore timestamp for temporal filtering.
            visual_attributes: Optional dict with ``_v_*`` visual override keys.
        """
        super().__init__()

        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._icon_name = icon
        self._svg_renderer: Optional[QSvgRenderer] = None
        self._custom_color = color
        self._visual_attributes: Dict[str, Any] = visual_attributes or {}

        # Resolve fill color via VisualResolver (user override → theme → fallback)
        if color:
            self._color = QColor(color)
        else:
            resolved = VisualResolver.resolve_fill(
                self._visual_attributes, object_type
            )
            self._color = QColor(resolved)

        # Temporal State
        self.lore_date = lore_date
        self.is_future = False
        self.is_past = False
        self.has_keyframes = False

        # Load icon if specified
        self._load_icon(icon)

        # Tooltip - use description if available, otherwise fall back to label
        tooltip_text = description or label
        self.setToolTip(f"<div style='width: 150px;'>{tooltip_text}</div>")

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

        # Text Label - dark grey for visibility on light/dark backgrounds
        self._label_item = QGraphicsSimpleTextItem(label, self)
        self._label_item.setBrush(QBrush(QColor("#333333")))  # Dark grey

        font = QFont("Segoe UI", 8)
        font.setBold(True)
        self._label_item.setFont(font)

        # Center the label below the marker
        self._update_label_position()

    def _update_label_position(self) -> None:
        """Centers the label below the marker."""
        rect = self._label_item.boundingRect()
        size = self.resolved_size
        # Center horizontally relative to 0 (marker center)
        x = -rect.width() / 2
        # Position vertically below the marker (size/2 is bottom edge)
        y = (size / 2) + 2  # 2px padding
        self._label_item.setPos(x, y)

    def _load_icon(self, icon_name: Optional[str]) -> None:
        """Loads an SVG icon for the marker.

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
        """Changes the marker's icon.

        Args:
            icon_name: Filename of the new icon.
        """
        self._load_icon(icon_name)
        self.update()

    def get_icon(self) -> Optional[str]:
        """Returns the current icon filename.

        Returns:
            Optional[str]: The icon filename or None if using fallback.
        """
        return self._icon_name

    def set_color(self, color: str) -> None:
        """Sets the custom color for the marker.

        Args:
            color: The hex color string (e.g., '#FF5733').
        """
        self._custom_color = color
        self._color = QColor(color)
        self.update()

    def get_color(self) -> Optional[str]:
        """Returns the current custom color.

        Returns:
            Optional[str]: The hex color string or None.
        """
        return self._custom_color

    def set_has_keyframes(self, state: bool) -> None:
        """Sets whether this marker has keyframes (trajectory).

        Args:
            state: True if trajectory exists, False otherwise.
        """
        if self.has_keyframes != state:
            self.has_keyframes = state
            self.update()

    def set_temporal_state(self, is_future: bool, is_past: bool = False) -> None:
        """Updates the marker's visual state based on its temporal relation.

        Args:
            is_future: If True, marker is in the future (dull/faded).
            is_past: If True, marker is in the past (reserved for "visited" styling).
        """
        if self.is_future == is_future and self.is_past == is_past:
            return

        self.is_future = is_future
        self.is_past = is_past

        # Update visual properties based on state
        if is_future:
            # Dulling effect: Reduced opacity (1.0 - 0.3 = 0.7)
            self.setOpacity(0.7)
            # Saturation change happens in paint() via color processing
        else:
            # Normal state: Vivid
            self.setOpacity(1.0)

        self.update()

    def _get_effective_color(self) -> QColor:
        """Returns the color modified by current state.

        For example, deseaturates the color if the marker is in the future.

        Returns:
            QColor: The effective color to use for painting.
        """
        color = QColor(self._color)

        if self.is_future:
            # Desaturate significantly for future state
            h, s, lightness, a = color.getHslF()
            # Reduce saturation by 20% (keep 80%) for a subtle fade
            # without becoming grey
            s = max(0.0, s * 0.8)
            lightness = min(1.0, lightness + 0.1)
            color = QColor.fromHslF(h, s, lightness, a)

        return color

    @property
    def resolved_size(self) -> int:
        """Returns the computed marker size (BASE_SIZE * scale).

        Returns:
            int: Pixel size of this marker.
        """
        return VisualResolver.resolve_size(self._visual_attributes)

    def set_visual_attributes(self, attrs: Dict[str, Any]) -> None:
        """Replaces the visual attributes and refreshes the marker.

        Args:
            attrs: New visual attributes dict.
        """
        self._visual_attributes = attrs
        # Re-resolve color unless a custom color is explicitly set
        if not self._custom_color:
            resolved = VisualResolver.resolve_fill(
                self._visual_attributes, self.object_type
            )
            self._color = QColor(resolved)
        self._update_label_position()
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle for the marker.

        Returns:
            QRectF: The bounding rect centered on (0, 0).
        """
        size = self.resolved_size
        half = size / 2
        return QRectF(-half, -half, size, size)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paints the marker, either as an SVG icon or fallback circle.

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
        """Draws the SVG icon, applying custom color tint if set.

        Args:
            painter: The painter to draw with.
            rect: The rectangle to draw into.
        """
        # removed shadow/background

        if self._custom_color:
            pixmap = self._render_svg_to_pixmap()
            self._tint_pixmap(pixmap, self._get_effective_color())

            painter.drawPixmap(rect.toRect(), pixmap)
        else:
            # Standard SVG rendering (no tint)
            self._svg_renderer.render(painter, rect)

        if self.has_keyframes:
            self._draw_keyframe_indicator(painter)

        # Draw selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

    def _render_svg_to_pixmap(self) -> QPixmap:
        """Renders the current SVG to a transparent QPixmap.

        Returns:
            QPixmap: The rendered SVG as a pixmap.
        """
        size = self.resolved_size
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        if self._svg_renderer:
            self._svg_renderer.render(p)
        p.end()
        return pixmap

    def _tint_pixmap(self, pixmap: QPixmap, color: QColor) -> None:
        """Tint a pixmap with the given color.

        Args:
            pixmap: The pixmap to tint.
            color: The color to use for tinting.
        """
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()

    def _draw_fallback_circle(self, painter: QPainter, rect: QRectF) -> None:
        """Draws a fallback colored circle.

        Args:
            painter: The painter to draw with.
            rect: The rectangle to draw into.
        """
        border_color = QColor(
            VisualResolver.resolve_border_color(
                self._visual_attributes, self.object_type
            )
        )
        border_width = VisualResolver.resolve_border_width(self._visual_attributes)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QBrush(self._get_effective_color()))
        painter.drawEllipse(rect)

        if self.has_keyframes:
            self._draw_keyframe_indicator(painter)

    def _draw_keyframe_indicator(self, painter: QPainter) -> None:
        """Draws a small dot indicator for markers with keyframes.

        Args:
            painter: The painter to draw with.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        primary_color = QColor(theme.get("primary", "#FF9900"))

        size = self.resolved_size
        # Position: Centered horizontally, slightly above the icon
        indicator_size = 8.0
        y_pos = -(size / 2) - 4 - (indicator_size / 2)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(primary_color))
        painter.drawEllipse(
            QRectF(
                -indicator_size / 2,
                y_pos,
                indicator_size,
                indicator_size,
            )
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track drag start.

        Args:
            event: The mouse event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = self.pos()
            logger.debug(
                f"Marker {self.marker_id} drag started at {self._drag_start_pos}"
            )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit position change on drag end, or clicked signal if distance small.

        Args:
            event: The mouse event.
        """
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
        """Calculates the current normalized position of the marker.

        Returns:
            Optional[tuple[float, float]]: A tuple of (normalized_x, normalized_y)
                values between 0.0 and 1.0, or None if calculation fails.
        """
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
        """Called when the item's state changes.

        Note: We no longer emit marker_moved here. Position updates
        are only emitted on mouseReleaseEvent to avoid flooding.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            Any: The processed value.
        """
        return super().itemChange(change, value)
