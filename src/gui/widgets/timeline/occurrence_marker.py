"""Accessible timeline marks with an exact date pin and adjacent Event labels."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QAbstractButton, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.temporal_geometry import TemporalGeometry
from src.gui.widgets.timeline.temporal_painter import paint_occurrence


def marker_label_fonts(font: QFont) -> tuple[QFont, QFont]:
    """Match the existing Event name and date typography."""
    name = QFont(font)
    name.setPointSize(10)
    name.setBold(True)
    caption = QFont(font)
    caption.setPointSize(8)
    caption.setBold(False)
    return name, caption


def marker_bounds(
    date_x: float, viewport_width: int, name: str, caption: str, font: QFont
) -> tuple[QRectF, float, float]:
    """Fit the label on either side without changing the date pin's coordinate."""
    main_font, caption_font = marker_label_fonts(font)
    text_width = min(
        320.0,
        max(0.0, viewport_width - 24.0),
        max(
            QFontMetricsF(main_font).horizontalAdvance(name),
            QFontMetricsF(caption_font).horizontalAdvance(caption),
        ),
    )
    label_x = date_x + 13
    if label_x + text_width > viewport_width - 4:
        label_x = date_x - 13 - text_width
    label_x = max(4.0, min(label_x, viewport_width - text_width - 4))
    left = max(0.0, min(date_x - 9, label_x))
    right = min(float(viewport_width), max(date_x + 9, label_x + text_width))
    return QRectF(left, 0, max(1.0, right - left), 40), label_x, text_width


class OccurrenceMarker(QAbstractButton):
    """Button semantics with Event glyph painting, not a rectangular button face."""

    def __init__(
        self, name: str, caption: str, parent: QWidget, *, pinned: bool = True
    ) -> None:
        """Retain keyboard/selection behavior and an unframed circular date pin."""
        super().__init__(parent)
        self.setText(name)
        self.caption = caption
        self.pinned = pinned
        self.anchor_x = 0.0
        self._label_x = 13.0
        self._label_width = 0.0
        self._pin_visible = True
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def place_at(self, date_x: float, viewport_width: int) -> None:
        """Align the circle center to the actual viewport date, even at an edge."""
        bounds, label_x, text_width = marker_bounds(
            date_x, viewport_width, self.text(), self.caption, self.font()
        )
        self.setGeometry(bounds.toAlignedRect())
        self.anchor_x = date_x - self.x()
        self._label_x = label_x - self.x()
        self._label_width = text_width
        self._pin_visible = 0 <= date_x <= viewport_width
        self.setAccessibleDescription(self.caption)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Reuse Event colors, strokes and typography with a circular exact mark."""
        theme = ThemeManager().get_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        boundary_role = (
            "focus_ring"
            if self.hasFocus()
            else "text_main"
            if self.isChecked()
            else "supporting_text"
        )
        if self.pinned and self._pin_visible:
            painter.save()
            painter.translate(self.anchor_x, 20)
            paint_occurrence(
                painter,
                TemporalGeometry("exact", -8, 8),
                QColor(theme["event_main"]),
                QColor(theme[boundary_role]),
                self.isChecked(),
                shape="circle",
            )
            painter.restore()
        name_font, caption_font = marker_label_fonts(self.font())
        painter.setFont(name_font)
        painter.setPen(
            QColor(theme["text_main" if self.isEnabled() else "supporting_text"])
        )
        prefix = (
            ""
            if self._pin_visible or not self.pinned
            else "← "
            if self.anchor_x < 0
            else "→ "
        )
        title = QFontMetricsF(name_font).elidedText(
            prefix + self.text(), Qt.TextElideMode.ElideRight, self._label_width
        )
        painter.drawText(QPointF(self._label_x, 18), title)
        painter.setFont(caption_font)
        painter.setPen(QColor(theme["supporting_caption"]))
        caption = QFontMetricsF(caption_font).elidedText(
            self.caption, Qt.TextElideMode.ElideRight, self._label_width
        )
        painter.drawText(QPointF(self._label_x, 30), caption)
        if self.hasFocus():
            painter.setPen(QPen(QColor(theme["focus_ring"]), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        painter.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter activates the same occurrence menu as pointer and Space."""
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)
