"""Shared occurrence and presence painting for full items and compact groups."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.temporal_geometry import TemporalGeometry


def _window_brush(geometry: TemporalGeometry, color: QColor) -> QBrush:
    """Use an uncapped fade only where no historical bound is asserted."""
    gradient = QLinearGradient(geometry.left, 0, geometry.right, 0)
    transparent = QColor(Qt.GlobalColor.transparent)
    faint = color
    if geometry.mode == "one_sided" and geometry.cap_left:
        gradient.setColorAt(0, faint)
        gradient.setColorAt(1, transparent)
    elif geometry.mode == "one_sided":
        gradient.setColorAt(0, transparent)
        gradient.setColorAt(1, faint)
    else:
        gradient.setColorAt(0, transparent)
        gradient.setColorAt(0.5, faint)
        gradient.setColorAt(1, transparent)
    return QBrush(gradient)


def _paint_window(
    painter: QPainter, geometry: TemporalGeometry, color: QColor, boundary: QColor
) -> None:
    """Draw finite bounds and open sides without inventing endpoints."""
    rect = QRectF(geometry.left, -6, geometry.right - geometry.left, 12)
    painter.save()
    theme = ThemeManager().get_theme()
    if geometry.mode in {"soft", "one_sided"}:
        painter.setOpacity(float(theme["timeline_halo_opacity"]))
        brush = _window_brush(geometry, color)
        painter.fillRect(rect, brush)
    else:
        painter.setOpacity(float(theme["timeline_window_opacity"]))
        painter.fillRect(rect, color)
    painter.restore()
    pen = QPen(boundary, 1)
    pen.setCosmetic(True)
    pen.setStyle(Qt.PenStyle.DotLine)
    painter.setPen(pen)
    if geometry.left < geometry.marker_x - 5:
        painter.drawLine(QPointF(geometry.left, 0), QPointF(geometry.marker_x - 5, 0))
    if geometry.marker_x + 5 < geometry.right:
        painter.drawLine(QPointF(geometry.marker_x + 5, 0), QPointF(geometry.right, 0))
    painter.setPen(QPen(boundary, 1))
    if geometry.cap_left:
        painter.drawLine(QPointF(geometry.left, -6), QPointF(geometry.left, 6))
    if geometry.cap_right:
        painter.drawLine(QPointF(geometry.right, -6), QPointF(geometry.right, 6))


def paint_occurrence(
    painter: QPainter,
    geometry: TemporalGeometry,
    color: QColor,
    boundary: QColor,
    selected: bool = False,
) -> None:
    """Render identical temporal grammar in event items and collapsed bands."""
    painter.save()
    if geometry.mode == "unresolved":
        painter.setPen(QPen(boundary, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(geometry.left, -8, geometry.right - geometry.left, 16)
        painter.drawEllipse(rect)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
    else:
        if geometry.mode != "exact":
            _paint_window(painter, geometry, color, boundary)
        half = 8 if geometry.mode == "exact" else 5
        x = geometry.marker_x
        diamond = QPolygonF(
            [
                QPointF(x, -half),
                QPointF(x + half, 0),
                QPointF(x, half),
                QPointF(x - half, 0),
            ]
        )
        pen = QPen(boundary, 2 if selected else 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(
            QBrush(color) if geometry.mode == "exact" else QBrush(Qt.BrushStyle.NoBrush)
        )
        painter.drawPolygon(diamond)
    painter.restore()


def paint_presence(
    painter: QPainter,
    geometry: TemporalGeometry,
    color: QColor,
    boundary: QColor,
    height: float = 12,
    selected: bool = False,
) -> None:
    """Keep possible presence hatched and guaranteed presence solid."""
    painter.setPen(QPen(boundary, 2 if selected else 1))
    painter.setBrush(QBrush(boundary, Qt.BrushStyle.BDiagPattern))
    painter.drawRect(
        QRectF(geometry.left, -height / 2, geometry.right - geometry.left, height)
    )
    if geometry.certain_left is not None and geometry.certain_right is not None:
        painter.fillRect(
            QRectF(
                geometry.certain_left,
                -height / 2,
                geometry.certain_right - geometry.certain_left,
                height,
            ),
            color,
        )


def paint_measure(
    painter: QPainter, geometry: TemporalGeometry, theme: dict[str, str]
) -> None:
    """Draw a length ruler on its own neutral surface, detached from dates."""
    painter.fillRect(
        QRectF(geometry.left - 4, -9, geometry.right - geometry.left + 8, 18),
        QColor(theme["surface"]),
    )
    painter.setPen(QPen(QColor(theme["supporting_text"]), 1))
    painter.drawLine(QPointF(geometry.left, 0), QPointF(geometry.right, 0))
    for x, direction in ((geometry.left, 1), (geometry.right, -1)):
        painter.drawLine(QPointF(x, 0), QPointF(x + direction * 3, -3))
        painter.drawLine(QPointF(x, 0), QPointF(x + direction * 3, 3))
    if geometry.compact:
        center = (geometry.left + geometry.right) / 2
        painter.drawLine(QPointF(center - 1, 3), QPointF(center + 1, -3))
