"""Continuous foreground frames for workspace surfaces."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from src.core.theme_manager import ThemeManager

_MIN_FRAME_SIZE = 2


class RoundedWorkspaceFrame(QWidget):
    """Paint a rounded outline and exterior cutout without covering its interior."""

    def __init__(
        self, parent: QWidget, radius: float, exterior_token: str = "border",
        border_width: float = 1.0,
    ) -> None:
        """Create an input-transparent frame above the parent's content."""
        super().__init__(parent)
        self._radius = radius
        self._border_width = border_width
        self._exterior_token = exterior_token
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        ThemeManager().theme_changed.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Join all edges and corners using one antialiased rounded path."""
        bounds = QRectF(self.rect())
        if bounds.width() < _MIN_FRAME_SIZE or bounds.height() < _MIN_FRAME_SIZE:
            return
        inset = self._border_width / 2.0
        outline = bounds.adjusted(inset, inset, -inset, -inset)
        if outline.isEmpty():
            return
        radius = max(
            0.0, min(self._radius - inset, outline.width() / 2, outline.height() / 2)
        )
        perimeter = QPainterPath()
        perimeter.addRoundedRect(outline, radius, radius)
        exterior = QPainterPath()
        exterior.addRect(bounds)
        exterior.addPath(perimeter)
        theme = ThemeManager().get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(exterior, QColor(theme[self._exterior_token]))
        painter.setPen(QPen(QColor(theme["border"]), self._border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(perimeter)
        painter.end()
