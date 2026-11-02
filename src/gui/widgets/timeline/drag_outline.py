"""Cheap, explicitly provisional feedback independent of timing calculation."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsSimpleTextItem

from src.core.theme_manager import ThemeManager


class PendingDragOutline(QGraphicsRectItem):
    """An unvalidated outline; never an Event or a date authority."""

    def __init__(self, item: QGraphicsItem) -> None:
        """Measure the dragged appearance once and use neutral mode/focus roles."""
        super().__init__(item.boundingRect())
        theme = ThemeManager().get_theme()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(1000)
        pen = QPen(QColor(theme["focus_ring"]), 1.5, Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.backdrop = QGraphicsRectItem(self)
        self.backdrop.setPen(QPen(QColor(theme["mode_border"])))
        self.backdrop.setBrush(QBrush(QColor(theme["mode_bg"])))
        self.label = QGraphicsSimpleTextItem("Pending calculation", self.backdrop)
        self.label.setBrush(QBrush(QColor(theme["mode_text"])))
        self.backdrop.setPos(self.rect().left(), self.rect().top() - 24)
        self.set_status("Pending calculation")

    def refresh_theme(self, theme: dict[str, str]) -> None:
        """Keep a live pending outline on semantic roles after a theme switch."""
        self.setPen(QPen(QColor(theme["focus_ring"]), 1.5, Qt.PenStyle.DashLine))
        self.backdrop.setPen(QPen(QColor(theme["mode_border"])))
        self.backdrop.setBrush(QBrush(QColor(theme["mode_bg"])))
        self.label.setBrush(QBrush(QColor(theme["mode_text"])))

    def set_status(self, text: str) -> None:
        """Refresh small text only when its state changes."""
        if self.label.text() != text:
            self.label.setText(text)
        self.label.setPos(4, 2)
        self.backdrop.setRect(self.label.boundingRect().adjusted(0, 0, 8, 4))
