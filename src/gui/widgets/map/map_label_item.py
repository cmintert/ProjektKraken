"""Shared theme-aware label item for map features."""

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.theme_manager import ThemeManager


class MapLabelItem(QGraphicsObject):
    """Render a compact map label with a theme-aware pill background."""

    def __init__(self, text: str, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._font = QFont("Segoe UI", 8)
        self._font.setBold(True)
        self._padding_x = 6
        self._padding_y = 2
        self._rect = QRectF()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self._update_rect()

    def _update_rect(self) -> None:
        metrics = QFontMetrics(self._font)
        text_rect = metrics.boundingRect(self._text)
        width = text_rect.width() + self._padding_x * 2
        height = text_rect.height() + self._padding_y * 2
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, float(width), float(height))

    def boundingRect(self) -> QRectF:
        """Return the device-space pill bounds."""
        return self._rect

    def setText(self, text: str) -> None:
        """Replace the label text and recompute its bounds."""
        if self._text == text:
            return
        self._text = text
        self._update_rect()
        self.update()

    def refresh_theme(self) -> None:
        """Schedule repaint after the active theme changes."""
        self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paint the pill using current theme colors."""
        del option, widget
        theme = ThemeManager().get_theme()
        background = QColor(theme.get("surface", "#1A1A1A"))
        text_color = QColor(theme.get("text_main", "#FFFFFF"))
        border = QColor(theme.get("border", "#333333"))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(background))
        painter.setPen(QPen(border, 1))
        radius = self._rect.height() / 2.0
        painter.drawRoundedRect(self._rect, radius, radius)
        painter.setFont(self._font)
        painter.setPen(QPen(text_color))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
