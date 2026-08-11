"""Map Marker Item Module.

Provides the MarkerItem class for rendering markers on the map.
"""

import logging
import os
from pathlib import Path

# Forward declaration to avoid circular import
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.app.constants import MAP_TEMPORAL_GHOST_OPACITY, TEMPORAL_FUTURE_OPACITY
from src.core.style_constants import BASE_SIZE
from src.core.theme_manager import ThemeManager
from src.gui.utils.svg_utils import apply_svg_inline_styles, svg_file_to_string
from src.services.visual_resolver import VisualResolver

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

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


class MarkerLabelItem(QGraphicsObject):
    """Custom graphics item for marker labels that displays a themed background pill."""

    def __init__(self, text: str, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._font = QFont("Segoe UI", 8)
        self._font.setBold(True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIgnoresTransformations)

        self._padding_x = 6
        self._padding_y = 2
        self._rect = QRectF()
        self._update_rect()

    def _update_rect(self) -> None:
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(self._text)
        width = text_rect.width() + self._padding_x * 2
        height = text_rect.height() + self._padding_y * 2
        self._rect = QRectF(0, 0, float(width), float(height))
        self.prepareGeometryChange()

    def boundingRect(self) -> QRectF:
        return self._rect

    def setText(self, text: str) -> None:
        if self._text != text:
            self._text = text
            self._update_rect()
            self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        theme = ThemeManager().get_theme()
        bg_color = QColor(theme.get("surface", "#1A1A1A"))
        text_color = QColor(theme.get("text_main", "#FFFFFF"))
        border_color = QColor(theme.get("border", "#333333"))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the pill background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))

        radius = self._rect.height() / 2.0
        painter.drawRoundedRect(self._rect, radius, radius)

        # Draw the text
        painter.setFont(self._font)
        painter.setPen(QPen(text_color))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)


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
            resolved = VisualResolver.resolve_fill(self._visual_attributes, object_type)
            self._color = QColor(resolved)

        # Temporal State
        self.lore_date = lore_date
        self.is_future = False
        self.is_past = False
        self.has_keyframes = False
        self._layer_opacity = 1.0
        self._temporal_ghost = False
        self._movable_before_temporal_ghost = True

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
        self._drag_start_pos: Optional[QPointF] = None

        # Lore priority – set externally before a layout pass.
        self.connection_count: int = 0

        # Text Label - pill background (hidden until first layout pass)
        self._label_item = MarkerLabelItem(label, self)
        self._label_item.setVisible(False)

    def apply_label_position(
        self, local_x: float, local_y: float, is_visible: bool
    ) -> None:
        """Applies a computed label position and visibility.

        Called by :class:`LabelManager` after each layout pass.

        Args:
            local_x: X offset in local (marker) coordinates.
            local_y: Y offset in local (marker) coordinates.
            is_visible: Whether the label should be shown.
        """
        self._label_item.setPos(local_x, local_y)
        self._label_item.setVisible(is_visible)

    def _load_icon(self, icon_name: Optional[str]) -> None:
        """Loads an SVG icon for the marker.

        Reads the SVG file, applies inline styles (fill color from
        ``_custom_color``), and loads the styled SVG into the renderer.

        Args:
            icon_name: Filename of the icon (e.g., 'castle.svg').
        """
        if not icon_name:
            icon_name = self.DEFAULT_ICON

        icon_path = os.path.join(MARKER_ICONS_PATH, icon_name)
        if not os.path.exists(icon_path):
            logger.debug(f"Icon not found: {icon_path}, using fallback circle")
            self._svg_renderer = None
            return

        # Read raw SVG content
        svg_content = svg_file_to_string(Path(icon_path))
        if not svg_content:
            self._svg_renderer = None
            return

        # Cache the raw SVG for re-styling later
        self._raw_svg = svg_content
        self._icon_name = icon_name

        # Apply inline styles and load
        self._apply_and_load_svg()

    def _apply_and_load_svg(self) -> None:
        """Applies inline styles to cached SVG and loads into renderer."""
        if not hasattr(self, "_raw_svg") or not self._raw_svg:
            return

        from src.core.style_constants import V_BORDER, V_BORDER_WIDTH, V_SIZE_SCALE

        fill = self._custom_color  # May be a hex string or "none"
        stroke = self._visual_attributes.get(V_BORDER)
        stroke_width = self._visual_attributes.get(V_BORDER_WIDTH)
        scale = self._visual_attributes.get(V_SIZE_SCALE)

        # Convert "none" border to explicit stroke:none in SVG
        stroke_val = stroke if stroke else None
        stroke_width_val = (
            int(stroke_width) if stroke_width is not None and stroke != "none" else None
        )
        scale_val = float(scale) if scale is not None else None

        styled = apply_svg_inline_styles(
            self._raw_svg,
            fill_color=fill,
            stroke_color=stroke_val,
            stroke_width=stroke_width_val,
            scale=scale_val,
        )

        renderer = QSvgRenderer(QByteArray(styled.encode("utf-8")))
        if renderer.isValid():
            self._svg_renderer = renderer
        else:
            logger.warning("Failed to load styled SVG into renderer")
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
        # Re-style SVG with new fill color
        self._apply_and_load_svg()
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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not state)
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

        self._apply_effective_opacity()

        self.update()

    def set_layer_opacity(self, opacity: float) -> None:
        """Set inherited layer opacity without replacing temporal styling."""
        self._layer_opacity = max(0.0, min(1.0, float(opacity)))
        self._apply_effective_opacity()

    def set_temporal_ghost(self, enabled: bool) -> None:
        """Enable the selectable, non-movable authoring ghost treatment."""
        enabled = bool(enabled)
        if enabled == self._temporal_ghost:
            return
        self._temporal_ghost = enabled
        if enabled:
            self._movable_before_temporal_ghost = bool(
                self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            )
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        else:
            self.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                self._movable_before_temporal_ghost,
            )
        self._apply_effective_opacity()
        self.update()

    @property
    def is_temporal_ghost(self) -> bool:
        """Whether this marker is rendered as an authoring ghost."""
        return self._temporal_ghost

    def _apply_effective_opacity(self) -> None:
        """Compose layer, future-state, and ghost opacity factors."""
        future_factor = TEMPORAL_FUTURE_OPACITY if self.is_future else 1.0
        ghost_factor = MAP_TEMPORAL_GHOST_OPACITY if self._temporal_ghost else 1.0
        self.setOpacity(self._layer_opacity * future_factor * ghost_factor)

    def _get_effective_color(self) -> QColor:
        """Returns the color modified by current state.

        For example, deseaturates the color if the marker is in the future.

        Returns:
            QColor: The effective color to use for painting.
        """
        color = QColor(self._color)

        if self.is_future:
            # Desaturate significantly for future state
            h, s, lightness, a = cast(
                tuple[float, float, float, float], color.getHslF()
            )
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
        from src.core.style_constants import V_FILL

        self._visual_attributes = attrs
        # Re-resolve color unless a custom color is explicitly set.
        # "none" is a valid explicit value (transparent fill).
        fill_override = attrs.get(V_FILL)
        if fill_override is not None:
            # Explicit fill in attributes takes priority
            self._custom_color = fill_override
            if fill_override != "none":
                self._color = QColor(fill_override)
        elif not self._custom_color:
            resolved = VisualResolver.resolve_fill(
                self._visual_attributes, self.object_type
            )
            self._color = QColor(resolved)
        # Re-style SVG with updated visual attributes
        self._apply_and_load_svg()
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()

        if self._svg_renderer and self._svg_renderer.isValid():
            self._draw_svg_icon(painter, rect)
        else:
            self._draw_fallback_circle(painter, rect)

        if self._temporal_ghost:
            ghost_pen = QPen(QColor(255, 255, 255), 1.5, Qt.PenStyle.DashLine)
            ghost_pen.setCosmetic(True)
            painter.setPen(ghost_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(1.0, 1.0, -1.0, -1.0))

    def _draw_svg_icon(self, painter: QPainter, rect: QRectF) -> None:
        """Draws the SVG icon with inline styles already applied.

        Args:
            painter: The painter to draw with.
            rect: The rectangle to draw into.
        """
        # SVG already has inline fill/stroke styles applied via _apply_and_load_svg
        renderer = cast(QSvgRenderer, self._svg_renderer)
        renderer.render(painter, rect)

        if self.has_keyframes:
            self._draw_keyframe_indicator(painter)

        # Draw selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

    def _draw_fallback_circle(self, painter: QPainter, rect: QRectF) -> None:
        """Draws a fallback colored circle.

        Args:
            painter: The painter to draw with.
            rect: The rectangle to draw into.
        """
        from src.core.style_constants import V_BORDER, V_BORDER_WIDTH, V_FILL

        border_color_str = VisualResolver.resolve_border_color(
            self._visual_attributes, self.object_type
        )
        border_width = VisualResolver.resolve_border_width(self._visual_attributes)
        no_border = (
            self._visual_attributes.get(V_BORDER) == "none"
            or self._visual_attributes.get(V_BORDER_WIDTH) == 0
            or border_width == 0
        )
        if no_border:
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setPen(QPen(QColor(border_color_str), border_width))

        no_fill = (
            self._custom_color == "none"
            or self._visual_attributes.get(V_FILL) == "none"
        )
        if no_fill:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
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

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(primary_color))
        painter.drawEllipse(
            QRectF(
                -indicator_size / 2,
                y_pos,
                indicator_size,
                indicator_size,
            )
        )

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
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

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
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
                    cast("MapGraphicsView", view).marker_moved.emit(
                        self.marker_id, norm_x, norm_y
                    )
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
