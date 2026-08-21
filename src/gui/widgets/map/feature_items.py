"""Map Feature Item Module.

Provides QGraphicsItem subclasses for rendering non-point map features:
- ``PathItem``: renders a polyline (stroke only) for river/road features.
- ``RegionItem``: renders a closed polygon (fill + stroke) for territory features.

Both item types share a common base that stores the feature metadata,
handles selection highlight, click detection, and label placement at
the anchor coordinate.
"""

import logging
import math
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.gui.constants import (
    MAP_FEATURE_CLICK_THRESHOLD_PX,
    MAP_FEATURE_DEFAULT_DASH_PATTERN,
    MAP_FEATURE_DEFAULT_FILL_COLOR,
    MAP_FEATURE_DEFAULT_STROKE_COLOR,
    MAP_FEATURE_DEFAULT_STROKE_WIDTH,
    MAP_FEATURE_HIT_AREA_MARGIN,
    MAP_FEATURE_HOVER_DEBOUNCE_MS,
    MAP_FEATURE_LABEL_COLOR,
    MAP_FEATURE_LABEL_FONT_FAMILY,
    MAP_FEATURE_LABEL_FONT_SIZE,
    MAP_FEATURE_MIN_HIT_AREA_WIDTH,
    MAP_FEATURE_REGION_FILL_COLOR,
    MAP_FEATURE_REGION_STROKE_COLOR,
    MAP_FEATURE_SELECTION_PEN_COLOR,
    MAP_FEATURE_SELECTION_PEN_WIDTH,
    MAP_FEATURE_Z_VALUE,
    MAP_TEMPORAL_GHOST_OPACITY,
    TEMPORAL_FUTURE_OPACITY,
)
from src.gui.widgets.map.map_label_item import MapLabelItem

logger = logging.getLogger(__name__)

# Backward-compatible aliases so existing imports keep working
DEFAULT_STROKE_COLOR = MAP_FEATURE_DEFAULT_STROKE_COLOR
DEFAULT_STROKE_WIDTH = MAP_FEATURE_DEFAULT_STROKE_WIDTH
DEFAULT_FILL_COLOR = MAP_FEATURE_DEFAULT_FILL_COLOR
DEFAULT_DASH_PATTERN: List[float] = MAP_FEATURE_DEFAULT_DASH_PATTERN
DEFAULT_REGION_STROKE_COLOR = MAP_FEATURE_REGION_STROKE_COLOR
DEFAULT_REGION_FILL_COLOR = MAP_FEATURE_REGION_FILL_COLOR

SELECTION_PEN_COLOR = MAP_FEATURE_SELECTION_PEN_COLOR
SELECTION_PEN_WIDTH = MAP_FEATURE_SELECTION_PEN_WIDTH

HIT_AREA_MARGIN = MAP_FEATURE_HIT_AREA_MARGIN
MIN_HIT_AREA_WIDTH = MAP_FEATURE_MIN_HIT_AREA_WIDTH
METERS_PER_KILOMETER = 1000.0
SQUARE_METERS_PER_SQUARE_KILOMETER = 1_000_000.0

LABEL_FONT_FAMILY = MAP_FEATURE_LABEL_FONT_FAMILY
LABEL_FONT_SIZE = MAP_FEATURE_LABEL_FONT_SIZE
LABEL_COLOR = MAP_FEATURE_LABEL_COLOR

class _FeatureItemBase(QGraphicsObject):
    """Abstract base for vector map features (paths, regions).

    Provides common infrastructure: marker_id tracking, selection highlight,
    click emission, label placement, and style extraction from a dict.

    Signals:
        clicked: Emitted on click (marker_id, object_type).

    """

    clicked = Signal(str, str)

    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        geometry: List[Dict[str, float]],
        style: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        map_width_meters: float = 1_000_000.0,
    ) -> None:
        """Initialise the feature item base.

        Args:
            marker_id: Unique identifier for this feature.
            object_type: 'entity' or 'event'.
            label: Display label.
            pixmap_item: Reference to map pixmap (for coordinate conversion).
            geometry: List of normalized coordinate dicts ``[{x, y}, ...]``.
            style: Optional visual-override dict.
            description: Optional tooltip text.
            lore_date: Optional temporal date for future/past fading.
            map_width_meters: Real-world map width in meters for metric display.

        """
        super().__init__()
        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._geometry = geometry
        self._style = style or {}
        self.lore_date = lore_date
        self._description = description or ""
        self._map_width_meters = map_width_meters
        self._anchor_x = 0.0
        self._anchor_y = 0.0

        # Temporal state
        self.is_future = False
        self.is_past = False
        self._layer_opacity = 1.0
        self._temporal_ghost = False

        # Click detection
        self._drag_start_pos: Optional[QPointF] = None

        # Hover tooltip debounce
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(MAP_FEATURE_HOVER_DEBOUNCE_MS)
        self._hover_timer.timeout.connect(self._apply_hover_tooltip)

        # Flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(MAP_FEATURE_Z_VALUE)
        self.setToolTip(description or label)
        self.connection_count = 0
        self._label_item = MapLabelItem(label, self)
        self._label_item.setVisible(False)

    def label_anchor_scene_pos(self) -> QPointF:
        """Return the normalized feature anchor in scene coordinates."""
        rect = self.pixmap_item.sceneBoundingRect()
        return QPointF(
            rect.left() + self._anchor_x * rect.width(),
            rect.top() + self._anchor_y * rect.height(),
        )

    @staticmethod
    def label_clearance_px(_view_scale: float = 1.0) -> float:
        """Keep a small gap between geometry anchors and their labels."""
        return 4.0

    def apply_label_scene_position(
        self, scene_x: float, scene_y: float, _inv_scale: float
    ) -> None:
        """Place the label at a scene-space layout candidate."""
        position = QPointF(scene_x, scene_y)
        if self._label_item.pos() != position:
            self._label_item.setPos(position)
        if not self._label_item.isVisible():
            self._label_item.setVisible(True)

    def hide_layout_label(self) -> None:
        """Hide the label when no collision-free candidate exists."""
        if self._label_item.isVisible():
            self._label_item.setVisible(False)

    def _position_label(self) -> None:
        """Refresh the anchor and request collision-aware relayout."""
        anchor = self.label_anchor_scene_pos()
        label_rect = self._label_item.boundingRect()
        self._label_item.setPos(
            anchor.x() - label_rect.width() / 2.0,
            anchor.y() + self.label_clearance_px(),
        )
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            schedule = getattr(view, "_schedule_label_layout", None)
            if callable(schedule):
                schedule()

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    def _stroke_color(self, default: str = DEFAULT_STROKE_COLOR) -> QColor:
        """Returns the resolved stroke colour."""
        raw = self._style.get("stroke_color", default)
        return QColor(raw) if raw else QColor(default)

    def _stroke_width(self) -> float:
        """Returns the resolved stroke width."""
        return float(self._style.get("stroke_width", DEFAULT_STROKE_WIDTH))

    def _fill_color(self, default: str = DEFAULT_FILL_COLOR) -> QColor:
        """Returns the resolved fill colour."""
        raw = self._style.get("fill_color", default)
        return QColor(raw) if raw else QColor(default)

    def _dash_pattern(self) -> List[float]:
        """Returns the dash pattern list (empty = solid)."""
        return self._style.get("dash_pattern", DEFAULT_DASH_PATTERN)

    def _make_pen(self, default_color: str = DEFAULT_STROKE_COLOR) -> QPen:
        """Builds a QPen from the style dict.

        Args:
            default_color: Fallback hex colour for the stroke.

        Returns:
            Configured QPen.

        """
        pen = QPen(self._stroke_color(default_color))
        pen.setWidthF(self._stroke_width())
        pen.setCosmetic(True)  # width is in screen pixels, not scene units
        dash = self._dash_pattern()
        if dash:
            pen.setDashPattern(dash)
        if self._temporal_ghost:
            pen.setStyle(Qt.PenStyle.DashLine)
        return pen

    # ------------------------------------------------------------------
    # Temporal state
    # ------------------------------------------------------------------

    def set_temporal_state(self, is_future: bool, is_past: bool = False) -> None:
        """Updates visual state for temporal filtering.

        Args:
            is_future: True when the feature is "in the future".
            is_past: True when the feature is "in the past".

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
        """Enable the selectable, non-historical authoring treatment."""
        enabled = bool(enabled)
        if enabled == self._temporal_ghost:
            return
        self._temporal_ghost = enabled
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._apply_effective_opacity()
        self.update()

    @property
    def is_temporal_ghost(self) -> bool:
        """Whether this feature is rendered as an authoring ghost."""
        return self._temporal_ghost

    def _apply_effective_opacity(self) -> None:
        """Compose layer, future-state, and ghost opacity factors."""
        future_factor = TEMPORAL_FUTURE_OPACITY if self.is_future else 1.0
        ghost_factor = MAP_TEMPORAL_GHOST_OPACITY if self._temporal_ghost else 1.0
        self.setOpacity(self._layer_opacity * future_factor * ghost_factor)

    # ------------------------------------------------------------------
    # Mouse interaction (click detection)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Records press position for click-vs-drag detection.

        Args:
            event: The graphics scene mouse press event.

        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.scenePos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Emits ``clicked`` if the mouse barely moved.

        Args:
            event: The graphics scene mouse release event.

        """
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            end = event.scenePos()
            dist = (end - self._drag_start_pos).manhattanLength()
            if dist < MAP_FEATURE_CLICK_THRESHOLD_PX:
                self.clicked.emit(self.marker_id, self.object_type)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Hover tooltip (debounced)
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Starts the debounce timer for the hover tooltip.

        Args:
            event: The hover enter event.

        """
        self._hover_timer.start()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Cancels the debounce timer and resets tooltip.

        Args:
            event: The hover leave event.

        """
        self._hover_timer.stop()
        self.setToolTip(self._description or self.label)
        super().hoverLeaveEvent(event)

    def _map_height_meters(self) -> float:
        """Computes real-world map height from width and pixmap aspect ratio.

        Returns:
            Map height in meters (assumes square map when no pixmap).

        """
        if self.pixmap_item:
            rect = self.pixmap_item.boundingRect()
            if rect.width() > 0 and rect.height() > 0:
                aspect = rect.width() / rect.height()
                return self._map_width_meters / aspect
        return self._map_width_meters  # fallback: square

    @staticmethod
    def _format_metric_length(meters: float) -> str:
        """Formats a length value with appropriate metric unit.

        Args:
            meters: Distance in meters.

        Returns:
            Human-readable string with unit (m or km).

        """
        if meters >= METERS_PER_KILOMETER:
            return f"{meters / METERS_PER_KILOMETER:.2f} km"
        return f"{meters:.1f} m"

    @staticmethod
    def _format_metric_area(sq_meters: float) -> str:
        """Formats an area value with appropriate metric unit.

        Args:
            sq_meters: Area in square meters.

        Returns:
            Human-readable string with unit (m² or km²).

        """
        if sq_meters >= SQUARE_METERS_PER_SQUARE_KILOMETER:
            return f"{sq_meters / SQUARE_METERS_PER_SQUARE_KILOMETER:.2f} km²"
        return f"{sq_meters:.1f} m²"

    def _apply_hover_tooltip(self) -> None:
        """Builds a rich tooltip from spatial properties and description.

        Extracts the description and useful computed measurements from the
        geometry to display in the tooltip with metric units.
        """
        lines: List[str] = [f"<b>{self.label}</b>"]
        if self._description:
            lines.append(self._description)

        # Spatial properties
        props = self._compute_spatial_properties()
        if "length" in props:
            lines.append(f"Length: {self._format_metric_length(props['length'])}")
        if "area" in props:
            lines.append(f"Area: {self._format_metric_area(props['area'])}")
        if "perimeter" in props:
            lines.append(f"Perimeter: {self._format_metric_length(props['perimeter'])}")
        if props.get("calibration_required"):
            lines.append("Calibrate map to measure")

        tooltip_content = "<br>".join(lines)
        self.setToolTip(f"<div style='width: 150px;'>{tooltip_content}</div>")

    def _compute_spatial_properties(self) -> Dict[str, Any]:
        """Computes lightweight spatial properties for the tooltip.

        Returns:
            Dict with feature_type, vertex_count, and optional
            length/area/perimeter.

        """
        props: Dict[str, Any] = {}
        if not self._geometry:
            return props

        pts = [(p["x"], p["y"]) for p in self._geometry]
        props["vertex_count"] = len(pts)
        return props


class PathItem(_FeatureItemBase):
    """Renders a polyline (path / line) on the map.

    The item is positioned at (0, 0) in scene coordinates; all vertices
    are stored as absolute scene positions computed from normalized
    geometry + the pixmap_item bounds.

    """

    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        geometry: List[Dict[str, float]],
        anchor_x: float,
        anchor_y: float,
        style: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        map_width_meters: float = 0.0,
    ) -> None:
        """Initialise the PathItem.

        Args:
            marker_id: Unique feature identifier.
            object_type: 'entity' or 'event'.
            label: Display label placed at the anchor.
            pixmap_item: Map pixmap for coordinate conversion.
            geometry: Normalised coordinate dicts.
            anchor_x: Normalised anchor X (for label).
            anchor_y: Normalised anchor Y (for label).
            style: Visual overrides dict.
            description: Tooltip text.
            lore_date: Temporal date.
            map_width_meters: Real-world map width in meters.

        """
        super().__init__(
            marker_id,
            object_type,
            label,
            pixmap_item,
            geometry,
            style,
            description,
            lore_date,
            map_width_meters,
        )
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._scene_points: List[QPointF] = []
        self._path = QPainterPath()
        self._build_path()

    def _build_path(self) -> None:
        """Converts normalized geometry → scene-coordinates QPainterPath."""
        if not self.pixmap_item or not self._geometry:
            return
        rect = self.pixmap_item.sceneBoundingRect()
        self._scene_points = []
        self._path = QPainterPath()
        for i, pt in enumerate(self._geometry):
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            sp = QPointF(sx, sy)
            self._scene_points.append(sp)
            if i == 0:
                self._path.moveTo(sp)
            else:
                self._path.lineTo(sp)

    def set_geometry(
        self, geometry: List[Dict[str, float]], anchor_x: float, anchor_y: float
    ) -> None:
        """Replace geometry safely without recreating the graphics item."""
        self.prepareGeometryChange()
        self._geometry = [dict(point) for point in geometry]
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._build_path()
        self.update()

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle of the path.

        Returns:
            QRectF encompassing all vertices with stroke margin.

        """
        if self._path.isEmpty():
            return QRectF()
        margin = self._stroke_width() + SELECTION_PEN_WIDTH
        return self._path.boundingRect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        """Returns a widened shape for accurate hit-testing.

        Returns:
            QPainterPath with stroke width applied.

        """
        from PySide6.QtGui import QPainterPathStroker

        stroker = QPainterPathStroker()
        stroker.setWidth(
            max(self._stroke_width() + HIT_AREA_MARGIN, MIN_HIT_AREA_WIDTH)
        )
        return stroker.createStroke(self._path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paints the polyline.

        Args:
            painter: QPainter instance.
            option: Style options.
            widget: Target widget.

        """
        if self._path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Selection highlight
        if self.isSelected():
            sel_pen = QPen(QColor(SELECTION_PEN_COLOR), SELECTION_PEN_WIDTH + 2)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.drawPath(self._path)

        # Main stroke
        painter.setPen(self._make_pen())
        painter.drawPath(self._path)

    def _compute_spatial_properties(self) -> Dict[str, Any]:
        """Computes spatial properties for a path feature in metric units.

        Returns:
            Dict with feature_type, vertex_count, segment_count,
            and length (in meters).

        """
        props: Dict[str, Any] = {"feature_type": "path"}
        if not self._geometry:
            return props
        pts = [(p["x"], p["y"]) for p in self._geometry]
        props["vertex_count"] = len(pts)
        props["segment_count"] = max(0, len(pts) - 1)
        if self._map_width_meters <= 0:
            props["calibration_required"] = True
            return props
        w = self._map_width_meters
        h = self._map_height_meters()
        total = 0.0
        for i in range(len(pts) - 1):
            dx = (pts[i + 1][0] - pts[i][0]) * w
            dy = (pts[i + 1][1] - pts[i][1]) * h
            total += math.sqrt(dx * dx + dy * dy)
        props["length"] = total
        return props


class RegionItem(_FeatureItemBase):
    """Renders a closed polygon (region / territory) on the map.

    Similar to ``PathItem`` but closes the polygon and applies a fill.
    """

    def __init__(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        pixmap_item: QGraphicsPixmapItem,
        geometry: List[Dict[str, float]],
        anchor_x: float,
        anchor_y: float,
        style: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        map_width_meters: float = 0.0,
    ) -> None:
        """Initialise the RegionItem.

        Args:
            marker_id: Unique feature identifier.
            object_type: 'entity' or 'event'.
            label: Display label placed at the anchor.
            pixmap_item: Map pixmap for coordinate conversion.
            geometry: Normalised coordinate dicts.
            anchor_x: Normalised anchor X (for label).
            anchor_y: Normalised anchor Y (for label).
            style: Visual overrides dict.
            description: Tooltip text.
            lore_date: Temporal date.
            map_width_meters: Real-world map width in meters.

        """
        super().__init__(
            marker_id,
            object_type,
            label,
            pixmap_item,
            geometry,
            style,
            description,
            lore_date,
            map_width_meters,
        )
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._polygon = QPolygonF()
        self._build_polygon()

    def _build_polygon(self) -> None:
        """Converts normalized geometry → scene-coordinates QPolygonF."""
        if not self.pixmap_item or not self._geometry:
            return
        rect = self.pixmap_item.sceneBoundingRect()
        points: List[QPointF] = []
        for pt in self._geometry:
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            points.append(QPointF(sx, sy))
        self._polygon = QPolygonF(points)

    def set_geometry(
        self, geometry: List[Dict[str, float]], anchor_x: float, anchor_y: float
    ) -> None:
        """Replace geometry safely without recreating the graphics item."""
        self.prepareGeometryChange()
        self._geometry = [dict(point) for point in geometry]
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._build_polygon()
        self.update()

    # ------------------------------------------------------------------
    # QGraphicsItem interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle of the polygon.

        Returns:
            QRectF encompassing all vertices with stroke margin.

        """
        if self._polygon.isEmpty():
            return QRectF()
        margin = self._stroke_width() + SELECTION_PEN_WIDTH
        return self._polygon.boundingRect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        """Returns the polygon shape for hit testing.

        Returns:
            QPainterPath enclosing the filled polygon area.

        """
        path = QPainterPath()
        if not self._polygon.isEmpty():
            path.addPolygon(self._polygon)
            path.closeSubpath()
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paints the filled polygon.

        Args:
            painter: QPainter instance.
            option: Style options.
            widget: Target widget.

        """
        if self._polygon.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Selection highlight
        if self.isSelected():
            sel_pen = QPen(QColor(SELECTION_PEN_COLOR), SELECTION_PEN_WIDTH + 2)
            sel_pen.setCosmetic(True)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(self._polygon)

        # Fill + stroke
        painter.setBrush(
            Qt.BrushStyle.NoBrush
            if self._temporal_ghost
            else QBrush(self._fill_color(DEFAULT_REGION_FILL_COLOR))
        )
        painter.setPen(self._make_pen(DEFAULT_REGION_STROKE_COLOR))
        painter.drawPolygon(self._polygon)

    def _compute_spatial_properties(self) -> Dict[str, Any]:
        """Computes spatial properties for a region feature in metric units.

        Uses the Shoelace formula for area and sums Euclidean distances
        for perimeter, scaled to real-world meters.

        Returns:
            Dict with feature_type, vertex_count, segment_count,
            area (m²), and perimeter (m).

        """
        props: Dict[str, Any] = {"feature_type": "region"}
        if not self._geometry:
            return props
        pts = [(p["x"], p["y"]) for p in self._geometry]
        n = len(pts)
        props["vertex_count"] = n
        props["segment_count"] = n  # closed polygon
        if self._map_width_meters <= 0:
            props["calibration_required"] = True
            return props

        w = self._map_width_meters
        h = self._map_height_meters()

        # Shoelace area (scaled to real-world square meters)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            x0, y0 = pts[i][0] * w, pts[i][1] * h
            x1, y1 = pts[j][0] * w, pts[j][1] * h
            area += x0 * y1
            area -= x1 * y0
        props["area"] = abs(area) / 2.0

        # Perimeter (scaled to real-world meters)
        perimeter = 0.0
        for i in range(n):
            j = (i + 1) % n
            dx = (pts[j][0] - pts[i][0]) * w
            dy = (pts[j][1] - pts[i][1]) * h
            perimeter += math.sqrt(dx * dx + dy * dy)
        props["perimeter"] = perimeter
        return props
