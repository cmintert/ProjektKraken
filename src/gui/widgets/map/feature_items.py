"""Map Feature Item Module.

Provides QGraphicsItem subclasses for rendering non-point map features:
- ``PathItem``: renders a polyline (stroke only) for river/road features.
- ``RegionItem``: renders a closed polygon (fill + stroke) for territory features.

Both item types share a common base that stores the feature metadata,
handles selection highlight, click detection, and label placement at
the anchor coordinate.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsSimpleTextItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

logger = logging.getLogger(__name__)

# Default visual style constants
DEFAULT_STROKE_COLOR = "#3498DB"
DEFAULT_STROKE_WIDTH = 2.0
DEFAULT_FILL_COLOR = "#3498DB40"  # 25% alpha
DEFAULT_DASH_PATTERN: List[float] = []  # solid line
DEFAULT_REGION_STROKE_COLOR = "#2C3E50"
DEFAULT_REGION_FILL_COLOR = "#3498DB30"

# Selection highlight
SELECTION_PEN_COLOR = "#FFFFFF"
SELECTION_PEN_WIDTH = 2.0

# Label styling
LABEL_FONT_FAMILY = "Segoe UI"
LABEL_FONT_SIZE = 9
LABEL_COLOR = "#333333"


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
    ) -> None:
        """Initialise the feature item base.

        Args:
            marker_id: Unique identifier for this feature.
            object_type: 'entity' or 'event'.
            label: Display label.
            pixmap_item: Reference to map pixmap (for coordinate conversion).
            geometry: List of normalised coordinate dicts ``[{x, y}, ...]``.
            style: Optional visual-override dict.
            description: Optional tooltip text.
            lore_date: Optional temporal date for future/past fading.

        """
        super().__init__()
        self.marker_id = marker_id
        self.object_type = object_type
        self.label = label
        self.pixmap_item = pixmap_item
        self._geometry = geometry
        self._style = style or {}
        self.lore_date = lore_date

        # Temporal state
        self.is_future = False
        self.is_past = False

        # Click detection
        self._drag_start_pos: Optional[QPointF] = None

        # Flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(8)  # Below point markers (10), above map bg (0)
        self.setToolTip(description or label)

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
        self.setOpacity(0.7 if is_future else 1.0)
        self.update()

    # ------------------------------------------------------------------
    # Mouse interaction (click detection)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Records press position for click-vs-drag detection.

        Args:
            event: The mouse press event.

        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.mapToScene(event.position())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emits ``clicked`` if the mouse barely moved.

        Args:
            event: The mouse release event.

        """
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            end = self.mapToScene(event.position())
            dist = (end - self._drag_start_pos).manhattanLength()
            if dist < 5:
                self.clicked.emit(self.marker_id, self.object_type)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


class PathItem(_FeatureItemBase):
    """Renders a polyline (path / line) on the map.

    The item is positioned at (0, 0) in scene coordinates; all vertices
    are stored as absolute scene positions computed from normalised
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
        )
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._scene_points: List[QPointF] = []
        self._path = QPainterPath()
        self._build_path()

        # Label (child item — auto-managed)
        self._label_item = QGraphicsSimpleTextItem(label, self)
        self._label_item.setBrush(QBrush(QColor(LABEL_COLOR)))
        font = QFont(LABEL_FONT_FAMILY, LABEL_FONT_SIZE)
        font.setBold(True)
        self._label_item.setFont(font)
        self._label_item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self._position_label()

    def _build_path(self) -> None:
        """Converts normalised geometry → scene-coordinates QPainterPath."""
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

    def _position_label(self) -> None:
        """Places the label at the anchor position."""
        if not self.pixmap_item:
            return
        rect = self.pixmap_item.sceneBoundingRect()
        ax = rect.left() + self._anchor_x * rect.width()
        ay = rect.top() + self._anchor_y * rect.height()
        label_rect = self._label_item.boundingRect()
        self._label_item.setPos(ax - label_rect.width() / 2, ay + 4)

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
        stroker.setWidth(max(self._stroke_width() + 6, 10))  # min 10px hit area
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
        )
        self._anchor_x = anchor_x
        self._anchor_y = anchor_y
        self._polygon = QPolygonF()
        self._build_polygon()

        # Label (child item)
        self._label_item = QGraphicsSimpleTextItem(label, self)
        self._label_item.setBrush(QBrush(QColor(LABEL_COLOR)))
        font = QFont(LABEL_FONT_FAMILY, LABEL_FONT_SIZE)
        font.setBold(True)
        self._label_item.setFont(font)
        self._label_item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self._position_label()

    def _build_polygon(self) -> None:
        """Converts normalised geometry → scene-coordinates QPolygonF."""
        if not self.pixmap_item or not self._geometry:
            return
        rect = self.pixmap_item.sceneBoundingRect()
        points: List[QPointF] = []
        for pt in self._geometry:
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            points.append(QPointF(sx, sy))
        self._polygon = QPolygonF(points)

    def _position_label(self) -> None:
        """Places the label at the anchor (centroid)."""
        if not self.pixmap_item:
            return
        rect = self.pixmap_item.sceneBoundingRect()
        ax = rect.left() + self._anchor_x * rect.width()
        ay = rect.top() + self._anchor_y * rect.height()
        label_rect = self._label_item.boundingRect()
        self._label_item.setPos(ax - label_rect.width() / 2, ay - label_rect.height() / 2)

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
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(self._polygon)

        # Fill + stroke
        painter.setBrush(QBrush(self._fill_color(DEFAULT_REGION_FILL_COLOR)))
        painter.setPen(self._make_pen(DEFAULT_REGION_STROKE_COLOR))
        painter.drawPolygon(self._polygon)
