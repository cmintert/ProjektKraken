"""Map Marker Item Module.

Provides the MarkerItem class for rendering markers on the map.
"""

import logging
import math
from pathlib import Path

# Forward declaration to avoid circular import
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, cast

from PySide6.QtCore import QByteArray, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainter,
    QPen,
    QPixmap,
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

from src.core.map_constants import DEFAULT_MARKER_ICONS_PATH
from src.core.marker_appearance import (
    MARKER_ICON_ANCHOR_ATTRIBUTE,
    MARKER_ICON_ID_ATTRIBUTE,
    MarkerAppearance,
    MarkerIconAnchor,
)
from src.core.marker_icon import MarkerIconDefinition, MarkerIconSource
from src.core.marker_sizing import (
    MARKER_SIZING_ATTRIBUTE,
    MARKER_SIZING_SOURCE_ATTRIBUTE,
    MarkerMapSizeUnit,
    MarkerSizingMode,
    MarkerSizingSettings,
    MarkerSizingSource,
)
from src.core.paths import get_resource_path
from src.core.style_constants import BASE_SIZE
from src.gui.constants import MAP_TEMPORAL_GHOST_OPACITY, TEMPORAL_FUTURE_OPACITY
from src.gui.utils.svg_utils import apply_svg_inline_styles, svg_file_to_string
from src.gui.widgets.map.edit_handles import DraggableEditHandle
from src.gui.widgets.map.map_label_item import MapLabelItem
from src.services.visual_resolver import VisualResolver

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)

# Keep this Kraken-owned rather than inheriting a platform-specific drag setting.
# The margin filters minor involuntary pointer movement before a marker relocates.
MARKER_DRAG_START_DISTANCE_PX = 12
_KEYFRAME_INDICATOR_SIZE_PX = 8.0
_METERS_PER_KILOMETER = 1000.0
_RASTER_ICON_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Compatibility alias for callers that imported the former local class.
MarkerLabelItem = MapLabelItem


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
    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        color: Optional[str] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        visual_attributes: Optional[Dict[str, Any]] = None,
        world_root: Optional[str] = None,
        marker_sizing: MarkerSizingSettings | None = None,
        map_width_meters: float = 0.0,
        icon_definition: MarkerIconDefinition | None = None,
    ) -> None:
        """Initializes a MarkerItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Label text for the marker (displayed below marker).
            pixmap_item: Reference to the map pixmap item for coordinate conversion.
            color: Optional color hex string.
            description: Optional description for tooltip. Falls back to label if empty.
            lore_date: Optional lore timestamp for temporal filtering.
            visual_attributes: Optional dict with ``_v_*`` visual override keys.
            world_root: Active portable world root for project icon resolution.
            marker_sizing: Optional per-marker sizing override.
            map_width_meters: Calibrated total map width, or zero.
            icon_definition: Resolved stable icon metadata, when available.
        """
        super().__init__()

        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._icon_definition = icon_definition
        self._svg_renderer: Optional[QSvgRenderer] = None
        self._raster_pixmap: Optional[QPixmap] = None
        self._raw_svg: Optional[str] = None
        self._icon_kind: Literal["svg", "raster", "fallback"] = "fallback"
        self._world_root = Path(world_root) if world_root is not None else None
        self._custom_color = color
        self._visual_attributes: Dict[str, Any] = visual_attributes or {}
        self._marker_sizing = marker_sizing or MarkerSizingSettings.from_attributes(
            self._visual_attributes
        )
        self._map_width_meters = max(0.0, float(map_width_meters))

        # Transient direct-edit state. Persistence happens only when the view
        # confirms the complete appearance edit.
        self._appearance_edit_snapshot: Optional[Dict[str, Any]] = None
        self._appearance_edit_icon: MarkerIconDefinition | None = None
        self._appearance_edit_was_movable = True
        self._resize_handle: Optional[DraggableEditHandle[str]] = None
        self._anchor_handle: Optional[DraggableEditHandle[str]] = None
        self._resize_reference_distance = 1.0
        self._resize_reference_size = MarkerSizingSettings()
        self._pending_anchor = MarkerIconAnchor()

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

        self._load_icon(icon_definition)

        # Tooltip - use description if available, otherwise fall back to label
        tooltip_text = description or label
        self.setToolTip(f"<div style='width: 150px;'>{tooltip_text}</div>")

        # Make draggable and selectable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self._apply_sizing_mode_flag()

        # Cursor hint
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Z-value to appear on top of the map
        self.setZValue(10)

        # Drag tracking
        self._is_dragging = False
        self._drag_started = False
        self._drag_start_pos: Optional[QPointF] = None
        self._drag_start_screen_pos: Optional[QPoint] = None

        # Lore priority – set externally before a layout pass.
        self.connection_count: int = 0

        # Text Label - pill background (hidden until first layout pass)
        self._label_item = MapLabelItem(label, self)
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
        position = QPointF(local_x, local_y)
        if self._label_item.pos() != position:
            self._label_item.setPos(position)
        if self._label_item.isVisible() != is_visible:
            self._label_item.setVisible(is_visible)

    def label_anchor_scene_pos(self) -> QPointF:
        """Return the scene anchor used by the shared label layout."""
        return self.scenePos()

    def label_clearance_px(self, view_scale: float = 1.0) -> float:
        """Return icon clearance around the label anchor in device pixels."""
        if self._marker_sizing.mode is MarkerSizingMode.MAP_RELATIVE:
            radius = self.resolved_size * max(0.0, float(view_scale)) / 2.0
        else:
            radius = self.resolved_size / 2.0
        return radius

    def label_obstacle_scene_rect(self, view_scale: float = 1.0) -> QRectF:
        """Return the actual rendered icon bounds in scene coordinates."""
        local_rect = self.rendered_symbol_rect()
        unit_scale = (
            1.0 / max(1e-9, float(view_scale))
            if self._marker_sizing.mode is MarkerSizingMode.SCREEN_FIXED
            else 1.0
        )
        anchor = self.scenePos()
        return QRectF(
            anchor.x() + local_rect.left() * unit_scale,
            anchor.y() + local_rect.top() * unit_scale,
            local_rect.width() * unit_scale,
            local_rect.height() * unit_scale,
        )

    def apply_label_scene_position(
        self, scene_x: float, scene_y: float, inv_scale: float
    ) -> None:
        """Place the device-space child label at a scene-space candidate."""
        anchor = self.scenePos()
        local_x = scene_x - anchor.x()
        local_y = scene_y - anchor.y()
        if self._marker_sizing.mode is MarkerSizingMode.SCREEN_FIXED:
            local_x /= inv_scale
            local_y /= inv_scale
        self.apply_label_position(
            local_x,
            local_y,
            True,
        )

    def hide_layout_label(self) -> None:
        """Hide the label when no collision-free candidate exists."""
        if self._label_item.isVisible():
            self._label_item.setVisible(False)

    def _resolve_icon_path(
        self, definition: MarkerIconDefinition
    ) -> Optional[Path]:
        """Resolve a catalog definition within its trusted asset root."""
        relative_path = Path(definition.asset_path)
        if relative_path.is_absolute() or relative_path.anchor:
            logger.warning("Rejected absolute marker icon path: %s", relative_path)
            return None

        if definition.source is MarkerIconSource.CUSTOM:
            if self._world_root is None:
                logger.debug("Cannot resolve project icon without a world root")
                return None
            trusted_root = (self._world_root / "assets" / "images").resolve()
            candidate = (self._world_root / relative_path).resolve()
        else:
            trusted_root = Path(
                get_resource_path(DEFAULT_MARKER_ICONS_PATH)
            ).resolve()
            candidate = (trusted_root / relative_path).resolve()

        try:
            candidate.relative_to(trusted_root)
        except ValueError:
            logger.warning(
                "Rejected marker icon outside trusted root: %s", relative_path
            )
            return None
        if not candidate.is_file():
            logger.debug("Icon not found: %s, using fallback circle", candidate)
            return None
        return candidate

    def _load_icon(self, definition: MarkerIconDefinition | None) -> None:
        """Load catalog artwork, falling back to the painted marker safely."""
        self._svg_renderer = None
        self._raster_pixmap = None
        self._raw_svg = None
        self._icon_kind = "fallback"

        self._icon_definition = definition
        if definition is None:
            return
        icon_path = self._resolve_icon_path(definition)
        if icon_path is None:
            return

        suffix = icon_path.suffix.lower()
        if suffix in _RASTER_ICON_EXTENSIONS:
            pixmap = QPixmap(str(icon_path))
            if pixmap.isNull():
                logger.warning("Failed to load raster marker icon: %s", icon_path)
                return
            self._raster_pixmap = pixmap
            self._icon_kind = "raster"
            return
        if suffix != ".svg":
            logger.warning("Unsupported marker icon type: %s", suffix)
            return

        # Read raw SVG content
        svg_content = svg_file_to_string(icon_path)
        if not svg_content:
            return

        # Cache the raw SVG for re-styling later
        self._raw_svg = svg_content
        # Apply inline styles and load
        self._apply_and_load_svg()

    def _apply_and_load_svg(self) -> None:
        """Applies inline styles to cached SVG and loads into renderer."""
        if not hasattr(self, "_raw_svg") or not self._raw_svg:
            return

        from src.core.style_constants import V_BORDER, V_BORDER_WIDTH

        fill = self._custom_color  # May be a hex string or "none"
        stroke = self._visual_attributes.get(V_BORDER)
        stroke_width = self._visual_attributes.get(V_BORDER_WIDTH)

        # Convert "none" border to explicit stroke:none in SVG
        stroke_val = stroke if stroke else None
        stroke_width_val = (
            int(stroke_width) if stroke_width is not None and stroke != "none" else None
        )
        styled = apply_svg_inline_styles(
            self._raw_svg,
            fill_color=fill,
            stroke_color=stroke_val,
            stroke_width=stroke_width_val,
        )

        renderer = QSvgRenderer(QByteArray(styled.encode("utf-8")))
        if renderer.isValid():
            self._svg_renderer = renderer
            self._icon_kind = "svg"
        else:
            logger.warning("Failed to load styled SVG into renderer")
            self._svg_renderer = None
            self._raw_svg = None
            self._icon_kind = "fallback"

    def set_icon_definition(self, definition: MarkerIconDefinition) -> None:
        """Apply resolved icon metadata and load its artwork."""
        self.prepareGeometryChange()
        self._load_icon(definition)
        self.update()

    @property
    def is_raster_icon(self) -> bool:
        """Whether the marker currently has a valid raster icon loaded."""
        return self._icon_kind == "raster"

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
    def resolved_size(self) -> float:
        """Return the marker diameter in its active coordinate space.

        Map markers resolve their size solely from :class:`MarkerSizingSettings`.
        ``_v_size_scale`` remains available for non-map consumers such as graph
        styling, but intentionally does not affect this calculation.

        Returns:
            Diameter in scene units for map-relative markers, or device pixels
            for screen-fixed markers.
        """
        if self._marker_sizing.mode is MarkerSizingMode.SCREEN_FIXED:
            return self._marker_sizing.screen_px
        image_width = self.pixmap_item.boundingRect().width()
        base_size = self._marker_sizing.map_diameter_scene_units(
            image_width,
            self._map_width_meters,
        )
        return max(0.1, base_size)

    def set_map_width_meters(self, map_width_meters: float) -> None:
        """Refresh this marker after its map calibration changes."""
        self.prepareGeometryChange()
        self._map_width_meters = max(0.0, float(map_width_meters))
        self._apply_sizing_mode_flag()
        self.update()

    def _apply_sizing_mode_flag(self) -> None:
        """Toggle view-transform participation for the configured mode."""
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
            self._marker_sizing.mode is MarkerSizingMode.SCREEN_FIXED,
        )

    def _current_view_scale(self) -> float:
        """Return the active view scale for cosmetic adornments."""
        scene = self.scene()
        if scene is None or not scene.views():
            return 1.0
        return max(1e-9, float(scene.views()[0].transform().m11()))

    def set_visual_attributes(self, attrs: Dict[str, Any]) -> None:
        """Replaces the visual attributes and refreshes the marker.

        Args:
            attrs: New visual attributes dict.
        """
        from src.core.style_constants import V_FILL

        self.prepareGeometryChange()
        self._visual_attributes = dict(attrs)
        self._refresh_icon_definition()
        self._marker_sizing = MarkerSizingSettings.from_attributes(attrs)
        self._apply_sizing_mode_flag()
        # Re-resolve color unless a custom color is explicitly set.
        # "none" is a valid explicit value (transparent fill).
        fill_override = attrs.get(V_FILL)
        self._custom_color = fill_override
        if fill_override is not None:
            # Explicit fill in attributes takes priority
            self._custom_color = fill_override
            if fill_override != "none":
                self._color = QColor(fill_override)
        else:
            resolved = VisualResolver.resolve_fill(
                self._visual_attributes, self.object_type
            )
            self._color = QColor(resolved)
        # Re-style SVG with updated visual attributes
        self._apply_and_load_svg()
        self.update()

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle for the marker.

        Returns:
            QRectF: The bounding rect centered on (0, 0).
        """
        return self.rendered_symbol_rect()

    def rendered_symbol_rect(self) -> QRectF:
        """Return the local rectangle occupied by rendered marker artwork."""
        width, height = self._resolved_artwork_size()
        anchor = self._resolved_icon_anchor()
        return QRectF(
            -anchor.x * width,
            -anchor.y * height,
            width,
            height,
        )

    def _resolved_artwork_size(self) -> tuple[float, float]:
        """Return artwork bounds while preserving SVG/raster aspect ratio."""
        size = self.resolved_size
        pixmap = self._raster_pixmap
        if pixmap is not None and not pixmap.isNull():
            source_width = float(pixmap.width())
            source_height = float(pixmap.height())
        elif self._svg_renderer is not None and self._svg_renderer.isValid():
            view_box = self._svg_renderer.viewBoxF()
            source_width = view_box.width()
            source_height = view_box.height()
        else:
            return size, size
        if source_width <= 0 or source_height <= 0:
            return size, size
        if source_width >= source_height:
            return size, size * source_height / source_width
        return size * source_width / source_height, size

    def _resolved_icon_anchor(self) -> MarkerIconAnchor:
        """Resolve an explicit marker anchor before the icon default."""
        payload = self._visual_attributes.get(MARKER_ICON_ANCHOR_ATTRIBUTE)
        if isinstance(payload, dict):
            return MarkerIconAnchor.from_dict(payload)
        if self._icon_definition is not None:
            return self._icon_definition.anchor
        return MarkerIconAnchor()

    def _refresh_icon_definition(self) -> None:
        """Resolve updated icon attributes from the owning view catalog."""
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            catalog = getattr(view, "marker_icon_catalog", None)
            resolver = getattr(catalog, "definition_or_default", None)
            if callable(resolver):
                definition = resolver(
                    self._visual_attributes.get(MARKER_ICON_ID_ATTRIBUTE)
                )
                current_id = (
                    self._icon_definition.id
                    if self._icon_definition is not None
                    else None
                )
                if definition.id != current_id:
                    self._load_icon(definition)
                return

    def appearance_payload(self) -> Dict[str, Any]:
        """Return this marker's validated copyable appearance."""
        return MarkerAppearance.from_attributes(self._visual_attributes).to_dict()

    def apply_appearance_payload(self, payload: Dict[str, Any]) -> None:
        """Apply a complete appearance locally without persistence."""
        appearance = MarkerAppearance.from_dict(payload)
        attributes = appearance.apply_to_attributes(self._visual_attributes)
        self.set_visual_attributes(attributes)
        self.update()

    @property
    def is_editing_appearance(self) -> bool:
        """Return whether direct resize/anchor handles are active."""
        return self._appearance_edit_snapshot is not None

    @property
    def appearance_edit_size_text(self) -> str:
        """Return the active creator-facing size for the appearance editor."""
        sizing = self._marker_sizing
        if sizing.mode is MarkerSizingMode.SCREEN_FIXED:
            return f"{sizing.screen_px:.0f} px"
        if sizing.map_unit is MarkerMapSizeUnit.METERS:
            if sizing.map_value >= _METERS_PER_KILOMETER:
                return f"{sizing.map_value / _METERS_PER_KILOMETER:g} km"
            return f"{sizing.map_value:g} m"
        return f"{sizing.map_value:g}% map width"

    @property
    def appearance_edit_anchor(self) -> MarkerIconAnchor:
        """Return the pending anchor currently shown by the appearance editor."""
        return self._pending_anchor

    def begin_appearance_edit(self) -> None:
        """Show resize and anchor handles and capture a cancellation snapshot."""
        if self.is_editing_appearance:
            return
        self._appearance_edit_snapshot = dict(self._visual_attributes)
        self._appearance_edit_icon = self._icon_definition
        self._appearance_edit_was_movable = bool(
            self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        )
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self._pending_anchor = self._resolved_icon_anchor()
        self._resize_reference_size = self._marker_sizing
        corner = self._resize_corner()
        self._resize_reference_distance = max(
            1e-6, math.hypot(corner.x(), corner.y())
        )

        self._resize_handle = DraggableEditHandle(
            "resize",
            self._preview_resize,
            lambda _handle_id: None,
        )
        self._resize_handle.setParentItem(self)
        self._resize_handle.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._resize_handle.setPos(corner)
        self._resize_handle.set_notifications_enabled(True)

        self._anchor_handle = DraggableEditHandle(
            "anchor",
            self._track_anchor_candidate,
            lambda _handle_id: None,
        )
        self._anchor_handle.setParentItem(self)
        self._anchor_handle.setCursor(Qt.CursorShape.CrossCursor)
        self._sync_anchor_handle()
        self._anchor_handle.set_notifications_enabled(True)

    def _resize_corner(self) -> QPointF:
        """Choose the artwork corner farthest from the current anchor."""
        rect = self.boundingRect()
        corners = (
            rect.bottomRight(),
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
        )
        return max(corners, key=lambda point: math.hypot(point.x(), point.y()))

    def finish_appearance_edit(self) -> Dict[str, Any] | None:
        """Apply the pending anchor and return one changed appearance payload."""
        snapshot = self._appearance_edit_snapshot
        if snapshot is None:
            return None
        before = MarkerAppearance.from_attributes(snapshot).to_dict()
        attributes = dict(self._visual_attributes)
        attributes[MARKER_ICON_ANCHOR_ATTRIBUTE] = self._pending_anchor.to_dict()
        self.set_visual_attributes(attributes)
        after = self.appearance_payload()
        self._clear_appearance_handles()
        return after if after != before else None

    def cancel_appearance_edit(self) -> None:
        """Restore the captured appearance and remove direct-edit handles."""
        snapshot = self._appearance_edit_snapshot
        icon = self._appearance_edit_icon
        if snapshot is None:
            return
        self.set_visual_attributes(snapshot)
        self._load_icon(icon)
        self._clear_appearance_handles()

    def _preview_resize(self, _handle_id: str, position: QPointF) -> None:
        """Preview uniform marker scaling without emitting a command."""
        distance = math.hypot(position.x(), position.y())
        multiplier = distance / self._resize_reference_distance
        sizing = self._resize_reference_size.with_scaled_active_size(
            multiplier,
            self._map_width_meters,
        )
        attributes = dict(self._visual_attributes)
        attributes[MARKER_SIZING_ATTRIBUTE] = sizing.to_dict()
        attributes[MARKER_SIZING_SOURCE_ATTRIBUTE] = MarkerSizingSource.CUSTOM.value
        self.set_visual_attributes(attributes)
        handle = self._resize_handle
        if handle is not None:
            handle.set_notifications_enabled(False)
            handle.setPos(self._resize_corner())
            handle.set_notifications_enabled(True)
        self._sync_anchor_handle()
        self._schedule_label_layout()
        self._refresh_appearance_tip()

    def _track_anchor_candidate(self, _handle_id: str, position: QPointF) -> None:
        """Track a normalized artwork anchor while leaving artwork stable."""
        rect = self.boundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        self._pending_anchor = MarkerIconAnchor(
            x=max(0.0, min(1.0, (position.x() - rect.left()) / rect.width())),
            y=max(0.0, min(1.0, (position.y() - rect.top()) / rect.height())),
        )
        self._refresh_appearance_tip()

    def _sync_anchor_handle(self) -> None:
        """Keep the candidate anchor attached to the same artwork point."""
        handle = self._anchor_handle
        if handle is None:
            return
        rect = self.boundingRect()
        handle.set_notifications_enabled(False)
        handle.setPos(
            rect.left() + self._pending_anchor.x * rect.width(),
            rect.top() + self._pending_anchor.y * rect.height(),
        )
        handle.set_notifications_enabled(True)

    def _clear_appearance_handles(self) -> None:
        """Remove transient handles and restore normal marker movement."""
        scene = self.scene()
        for handle in (self._resize_handle, self._anchor_handle):
            if handle is not None and scene is not None:
                scene.removeItem(handle)
        self._resize_handle = None
        self._anchor_handle = None
        self._appearance_edit_snapshot = None
        self._appearance_edit_icon = None
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
            self._appearance_edit_was_movable,
        )
        self._schedule_label_layout()

    def _schedule_label_layout(self) -> None:
        """Request a debounced label layout from the owning map view."""
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            schedule = getattr(view, "_schedule_label_layout", None)
            if callable(schedule):
                schedule()

    def _refresh_appearance_tip(self) -> None:
        """Refresh the live scale and anchor values in the owning map widget."""
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            refresh = getattr(view, "_refresh_mode_indicator", None)
            if callable(refresh):
                refresh()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paint the marker as SVG, raster artwork, or a fallback circle.

        Args:
            painter: The QPainter to use.
            option: Style options.
            widget: The widget being painted on.
        """
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()

        if self._svg_renderer and self._svg_renderer.isValid():
            self._draw_svg_icon(painter, rect)
        elif self._raster_pixmap is not None and not self._raster_pixmap.isNull():
            self._draw_raster_icon(painter, rect)
        else:
            self._draw_fallback_circle(painter, rect)

        if self.isSelected():
            selection_pen = QPen(QColor(255, 255, 255), 2)
            selection_pen.setCosmetic(True)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

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

    def _draw_raster_icon(self, painter: QPainter, rect: QRectF) -> None:
        """Draw a raster icon centred in the marker bounds without distortion."""
        pixmap = cast(QPixmap, self._raster_pixmap)
        source_rect = QRectF(pixmap.rect())
        if source_rect.isEmpty():
            self._draw_fallback_circle(painter, rect)
            return

        scale = min(
            rect.width() / source_rect.width(),
            rect.height() / source_rect.height(),
        )
        target_width = source_rect.width() * scale
        target_height = source_rect.height() * scale
        target_rect = QRectF(
            rect.center().x() - target_width / 2.0,
            rect.center().y() - target_height / 2.0,
            target_width,
            target_height,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(target_rect, pixmap, source_rect)
        painter.restore()

        if self.has_keyframes:
            self._draw_keyframe_indicator(painter)

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

        rect = self.boundingRect()
        # Position: centered above the rendered icon, regardless of anchor.
        adornment_scale = (
            1.0 / self._current_view_scale()
            if self._marker_sizing.mode is MarkerSizingMode.MAP_RELATIVE
            else 1.0
        )
        indicator_size = _KEYFRAME_INDICATOR_SIZE_PX * adornment_scale
        gap = 4.0 * adornment_scale
        y_pos = rect.top() - gap - (indicator_size / 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(primary_color))
        painter.drawEllipse(
            QRectF(
                rect.center().x() - indicator_size / 2,
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
        if self.is_editing_appearance:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_started = False
            self._drag_start_pos = self.pos()
            self._drag_start_screen_pos = event.screenPos()
            logger.debug(
                f"Marker {self.marker_id} drag started at {self._drag_start_pos}"
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Begin moving only after the Kraken marker drag safety margin."""
        if not self._is_dragging or self._drag_started:
            super().mouseMoveEvent(event)
            return

        if self._drag_start_screen_pos is None:
            event.accept()
            return

        distance = (event.screenPos() - self._drag_start_screen_pos).manhattanLength()
        if distance < MARKER_DRAG_START_DISTANCE_PX:
            event.accept()
            return

        self._drag_started = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Emit position change on drag end, or clicked signal if distance small.

        Args:
            event: The mouse event.
        """
        if self.is_editing_appearance:
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if not self._drag_started:
            self.clicked.emit(self.marker_id, self.object_type)
            logger.debug(f"Marker {self.marker_id} clicked.")

        if self._is_dragging and self._drag_started:
            self._is_dragging = False
            self._handle_drag_end()

        self._is_dragging = False
        self._drag_started = False
        self._drag_start_pos = None
        self._drag_start_screen_pos = None

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
