"""Detail-map footprint overlay item for the map scene.

Renders the projected outline of a registered detail map on the parent
map's canvas.  In normal mode a click navigates to that detail map.  In
edit mode four corner handles and a rotation handle let the user adjust
the placement live; the command is only dispatched on confirm.

Coordinate model
----------------
All internal coordinates are in **scene pixels** (0…image_width,
0…image_height).  The registration dict uses normalised parent-space
[0, 1]².  The item converts on the fly using the ``image_w`` / ``image_h``
it receives at construction.

The item is placed at (0, 0) in the scene and its bounding rect covers
the full image, so Qt never clips it prematurely.  The ``shape()``
override restricts the mouse-event hit area to the visible polygon (plus
handle circles in edit mode).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.app.constants import MAP_LAYER_Z_FOOTPRINTS
from src.core.theme_manager import ThemeManager
from src.services.map_nesting_service import MapNestingService

# Handle geometry
_HANDLE_RADIUS = 6.0  # scene-pixel radius for corner/rotation handles
_ROTATION_HANDLE_OFFSET = 32.0  # px from top-mid, outward along normal
_LABEL_PADDING_H = 8.0
_LABEL_PADDING_V = 4.0
_LABEL_FONT_SIZE = 9

# Drag zones
_ZONE_NONE = 0
_ZONE_BODY = 1
_ZONE_CORNER_TL = 2
_ZONE_CORNER_TR = 3
_ZONE_CORNER_BR = 4
_ZONE_CORNER_BL = 5
_ZONE_ROTATE = 6


class DetailMapFootprintItem(QGraphicsObject):
    """Scene item that shows a registered detail map's footprint.

    Args:
        detail_map_id: ID of the detail map this footprint represents.
        name: Display name shown in the label plate.
        parent_map_id: ID of the parent map (needed on confirm).
        registration: Aspect-locked-affine registration dict.
        image_w: Width of the parent map image in scene pixels.
        image_h: Height of the parent map image in scene pixels.
        parent: Parent QGraphicsItem (usually None).

    """

    detail_map_clicked = Signal(str)
    """Emitted with the detail map ID when clicked in non-edit mode."""

    registration_changed = Signal(dict)
    """Emitted during drag with the live registration dict."""

    def __init__(
        self,
        detail_map_id: str,
        name: str,
        parent_map_id: str,
        registration: Dict[str, Any],
        image_w: float,
        image_h: float,
        parent: Optional[QGraphicsObject] = None,
    ) -> None:
        super().__init__(parent)
        self._detail_map_id = detail_map_id
        self._name = name
        self._parent_map_id = parent_map_id
        self._registration: Dict[str, Any] = dict(registration)
        self._iw = image_w
        self._ih = image_h

        self._edit_mode = False
        self._pre_edit_registration: Optional[Dict[str, Any]] = None

        self._drag_zone = _ZONE_NONE
        self._drag_start_scene: Optional[QPointF] = None
        self._drag_start_reg: Optional[Dict[str, Any]] = None

        self.setZValue(MAP_LAYER_Z_FOOTPRINTS)
        self.setAcceptHoverEvents(False)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsFocusable, False)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def detail_map_id(self) -> str:
        """Return the detail map ID."""
        return self._detail_map_id

    @property
    def parent_map_id(self) -> str:
        """Return the parent map ID."""
        return self._parent_map_id

    def current_registration(self) -> Dict[str, Any]:
        """Return a copy of the current (possibly in-progress) registration."""
        return dict(self._registration)

    def update_registration(self, registration: Dict[str, Any]) -> None:
        """Replace the registration and repaint.

        Args:
            registration: New aspect-locked-affine registration dict.

        """
        self._registration = dict(registration)
        self._invalidate_shape_cache()
        self.update()

    # ------------------------------------------------------------------
    # Edit mode
    # ------------------------------------------------------------------

    def set_edit_mode(self, enabled: bool) -> None:
        """Enter or leave interactive edit mode.

        Entering edit mode saves the current registration so it can be
        restored on cancel.

        Args:
            enabled: ``True`` to enter edit mode, ``False`` to leave.

        """
        self._edit_mode = enabled
        if enabled:
            self._pre_edit_registration = dict(self._registration)
            self.setAcceptHoverEvents(True)
        else:
            self._pre_edit_registration = None
            self.setAcceptHoverEvents(False)
            self._drag_zone = _ZONE_NONE
        self._invalidate_shape_cache()
        self.update()

    def cancel_edit(self) -> None:
        """Restore the pre-edit registration and leave edit mode."""
        if self._pre_edit_registration is not None:
            self._registration = dict(self._pre_edit_registration)
        self.set_edit_mode(False)

    def nudge(
        self, dx_norm: float, dy_norm: float
    ) -> None:
        """Translate the footprint centre by a normalised delta.

        Args:
            dx_norm: Horizontal delta in normalised [0, 1] units.
            dy_norm: Vertical delta in normalised [0, 1] units.

        """
        reg = dict(self._registration)
        cx = reg["master_center_norm"]["x"] + dx_norm
        cy = reg["master_center_norm"]["y"] + dy_norm
        reg["master_center_norm"] = {
            "x": max(0.0, min(1.0, cx)),
            "y": max(0.0, min(1.0, cy)),
        }
        self._registration = reg
        self._invalidate_shape_cache()
        self.update()

    def rotate(self, delta_deg: float) -> None:
        """Rotate the footprint by a delta in degrees (clockwise positive).

        Args:
            delta_deg: Degrees to add to the current rotation.

        """
        reg = dict(self._registration)
        reg["rotation_deg"] = (
            float(reg.get("rotation_deg", 0.0)) + delta_deg
        ) % 360.0
        self._registration = reg
        self._invalidate_shape_cache()
        self.update()

    # ------------------------------------------------------------------
    # Qt item interface
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        """Return the full image rect so Qt never clips the item.

        Returns:
            QRectF covering ``(0, 0, image_w, image_h)``.

        """
        return QRectF(0.0, 0.0, self._iw, self._ih)

    def shape(self) -> QPainterPath:
        """Return the actual hit-test shape (polygon + handles in edit mode).

        Returns:
            QPainterPath for mouse event hit testing.

        """
        if self._shape_cache is not None:
            return self._shape_cache
        path = QPainterPath()
        corners = self._scene_corners()
        if not corners:
            self._shape_cache = path
            return path
        poly = QPolygonF([QPointF(*c) for c in corners])
        path.addPolygon(poly)
        path.closeSubpath()
        if self._edit_mode:
            for h in self._handle_positions():
                path.addEllipse(QPointF(*h), _HANDLE_RADIUS, _HANDLE_RADIUS)
        self._shape_cache = path
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Draw the footprint fill, outline, label, and edit handles.

        Args:
            painter: The QPainter to use for drawing.
            option: Style option (unused but required by signature).
            widget: The widget being painted on (unused).

        """
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = ThemeManager().get_theme()
        accent = theme.get("accent_secondary", "#4DA6FF")
        primary = theme.get("primary", "#FF9900")

        corners = self._scene_corners()
        if not corners:
            return
        poly = QPolygonF([QPointF(*c) for c in corners])

        # Fill
        fill_color = QColor(accent)
        fill_color.setAlpha(45)
        painter.setBrush(QBrush(fill_color))

        # Outline
        outline_color = QColor(accent)
        outline_color.setAlpha(200)
        outline_w = 2.5 if self._edit_mode else 1.5
        painter.setPen(QPen(outline_color, outline_w))
        painter.drawPolygon(poly)

        # Label plate (top-left corner area of footprint, always drawn)
        self._draw_label(painter, corners, theme)

        # Edit handles
        if self._edit_mode:
            self._draw_edit_handles(painter, corners, primary)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle press — start drag in edit mode, or record click in normal mode.

        Args:
            event: The scene mouse event.

        """
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return

        pos = event.pos()

        if self._edit_mode:
            zone = self._hit_zone(pos)
            if zone != _ZONE_NONE:
                self._drag_zone = zone
                self._drag_start_scene = pos
                self._drag_start_reg = dict(self._registration)
                event.accept()
                return
        else:
            # Accept so we can detect the release
            event.accept()
            return

        event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Update the registration live during a drag.

        Args:
            event: The scene mouse event.

        """
        if not self._edit_mode or self._drag_zone == _ZONE_NONE:
            event.ignore()
            return

        pos = event.pos()
        assert self._drag_start_scene is not None
        assert self._drag_start_reg is not None

        reg = dict(self._drag_start_reg)

        if self._drag_zone == _ZONE_BODY:
            dx = (pos.x() - self._drag_start_scene.x()) / self._iw
            dy = (pos.y() - self._drag_start_scene.y()) / self._ih
            cx = reg["master_center_norm"]["x"] + dx
            cy = reg["master_center_norm"]["y"] + dy
            reg["master_center_norm"] = {
                "x": max(0.0, min(1.0, cx)),
                "y": max(0.0, min(1.0, cy)),
            }

        elif _ZONE_CORNER_TL <= self._drag_zone <= _ZONE_CORNER_BL:
            cx_px = reg["master_center_norm"]["x"] * self._iw
            cy_px = reg["master_center_norm"]["y"] * self._ih
            start_dist = math.hypot(
                self._drag_start_scene.x() - cx_px,
                self._drag_start_scene.y() - cy_px,
            )
            curr_dist = math.hypot(pos.x() - cx_px, pos.y() - cy_px)
            if start_dist > 1e-6:
                new_scale = reg["scale_norm"] * (curr_dist / start_dist)
                reg["scale_norm"] = max(0.01, new_scale)

        elif self._drag_zone == _ZONE_ROTATE:
            cx_px = reg["master_center_norm"]["x"] * self._iw
            cy_px = reg["master_center_norm"]["y"] * self._ih
            start_angle = math.degrees(
                math.atan2(
                    self._drag_start_scene.x() - cx_px,
                    cy_px - self._drag_start_scene.y(),
                )
            )
            curr_angle = math.degrees(
                math.atan2(pos.x() - cx_px, cy_px - pos.y())
            )
            delta = curr_angle - start_angle
            reg["rotation_deg"] = (
                float(self._drag_start_reg["rotation_deg"]) + delta
            ) % 360.0

        self._registration = reg
        self._invalidate_shape_cache()
        self.registration_changed.emit(dict(reg))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Finish drag or emit clicked signal.

        Args:
            event: The scene mouse event.

        """
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return

        if self._edit_mode:
            if self._drag_zone != _ZONE_NONE:
                self._drag_zone = _ZONE_NONE
                self._drag_start_scene = None
                self._drag_start_reg = None
                event.accept()
                return
        else:
            pos = event.pos()
            if self.shape().contains(pos):
                self.detail_map_clicked.emit(self._detail_map_id)
                event.accept()
                return

        event.ignore()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    _shape_cache: Optional[QPainterPath] = None

    def _invalidate_shape_cache(self) -> None:
        self._shape_cache = None
        self.prepareGeometryChange()

    def _scene_corners(self) -> List[Tuple[float, float]]:
        """Return footprint corners in scene (pixel) coordinates."""
        try:
            norm_corners = MapNestingService.footprint_corners(self._registration)
        except Exception:
            return []
        return [(c[0] * self._iw, c[1] * self._ih) for c in norm_corners]

    def _rotation_handle_pos(
        self, corners: List[Tuple[float, float]]
    ) -> Tuple[float, float]:
        """Compute the rotation handle position for given corners.

        Args:
            corners: Four corner points in scene pixels (TL, TR, BR, BL).

        Returns:
            ``(x, y)`` in scene pixels.

        """
        # Top edge midpoint
        top_mid_x = (corners[0][0] + corners[1][0]) / 2.0
        top_mid_y = (corners[0][1] + corners[1][1]) / 2.0
        # Normal direction: perpendicular to top edge, pointing away from centre
        theta = math.radians(
            float(self._registration.get("rotation_deg", 0.0))
        )
        # In y-down space, "up" for a rotation θ is (-sin θ, -cos θ)
        nx = -math.sin(theta)
        ny = -math.cos(theta)
        return (
            top_mid_x + nx * _ROTATION_HANDLE_OFFSET,
            top_mid_y + ny * _ROTATION_HANDLE_OFFSET,
        )

    def _handle_positions(self) -> List[Tuple[float, float]]:
        """Return corner handle + rotation handle positions.

        Returns:
            5-element list: [TL, TR, BR, BL, rotation].

        """
        corners = self._scene_corners()
        if not corners:
            return []
        return corners + [self._rotation_handle_pos(corners)]

    def _hit_zone(self, pos: QPointF) -> int:
        """Return the drag zone at ``pos``, or ``_ZONE_NONE``.

        Args:
            pos: Point in item (scene) coordinates.

        Returns:
            One of the ``_ZONE_*`` constants.

        """
        handles = self._handle_positions()
        if not handles:
            return _ZONE_NONE
        zone_ids = [
            _ZONE_CORNER_TL,
            _ZONE_CORNER_TR,
            _ZONE_CORNER_BR,
            _ZONE_CORNER_BL,
            _ZONE_ROTATE,
        ]
        for h, z in zip(handles, zone_ids):
            if math.hypot(pos.x() - h[0], pos.y() - h[1]) <= _HANDLE_RADIUS + 2:
                return z
        # Body drag — check polygon containment
        corners = self._scene_corners()
        path = QPainterPath()
        path.addPolygon(QPolygonF([QPointF(*c) for c in corners]))
        path.closeSubpath()
        if path.contains(pos):
            return _ZONE_BODY
        return _ZONE_NONE

    def _draw_label(
        self,
        painter: QPainter,
        corners: List[Tuple[float, float]],
        theme: dict,
    ) -> None:
        """Draw the map name label near the top-left corner of the footprint.

        Args:
            painter: Active painter.
            corners: Scene pixel corners (TL, TR, BR, BL).
            theme: Theme dict.

        """
        font = QFont("Segoe UI", _LABEL_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetricsF(font)
        text = self._name
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        rect_w = tw + _LABEL_PADDING_H * 2
        rect_h = th + _LABEL_PADDING_V * 2

        # Position: slightly inside the top-left corner
        lx = corners[0][0] + 4.0
        ly = corners[0][1] + 4.0

        bg = QColor(theme.get("app_bg", "#2B2B2B"))
        bg.setAlpha(200)
        border = QColor(theme.get("accent_secondary", "#4DA6FF"))
        border.setAlpha(180)
        text_col = QColor(theme.get("text_main", "#E0E0E0"))

        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1.0))
        painter.drawRoundedRect(
            QRectF(lx, ly, rect_w, rect_h), 3.0, 3.0
        )
        painter.setPen(QPen(text_col))
        painter.drawText(
            QRectF(
                lx + _LABEL_PADDING_H,
                ly + _LABEL_PADDING_V,
                tw,
                th,
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

    def _draw_edit_handles(
        self,
        painter: QPainter,
        corners: List[Tuple[float, float]],
        primary_hex: str,
    ) -> None:
        """Draw the four corner handles and the rotation handle.

        Args:
            painter: Active painter.
            corners: Scene pixel corners (TL, TR, BR, BL).
            primary_hex: Hex colour string for handles.

        """
        handles = self._handle_positions()
        if not handles:
            return

        handle_fill = QColor(primary_hex)
        handle_fill.setAlpha(220)
        handle_border = QColor("#ffffff")
        handle_border.setAlpha(200)

        # Line from top-mid to rotation handle
        top_mid = QPointF(
            (corners[0][0] + corners[1][0]) / 2.0,
            (corners[0][1] + corners[1][1]) / 2.0,
        )
        rot_h = handles[-1]
        painter.setPen(QPen(handle_border, 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(top_mid, QPointF(*rot_h))

        # Corner + rotation handles
        painter.setPen(QPen(handle_border, 1.5))
        painter.setBrush(QBrush(handle_fill))
        for i, h in enumerate(handles):
            painter.drawEllipse(
                QPointF(*h), _HANDLE_RADIUS, _HANDLE_RADIUS
            )
