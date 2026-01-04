"""
Group Label Overlay Module.

Provides a fixed overlay widget that displays tag lane labels on the left side
of the timeline view, remaining visible during horizontal scrolling.
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPolygonF
from PySide6.QtWidgets import QWidget

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class GroupLabelOverlay(QWidget):
    """
    An overlay widget that displays fixed tag lane labels.

    This widget sits on top of the QGraphicsView and renders labels
    that remain fixed on the left edge during horizontal scrolling.
    """

    LABEL_WIDTH = 150
    LABEL_PADDING = 8

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the GroupLabelOverlay.

        Args:
            parent: Parent widget (should be the TimelineView)
        """
        super().__init__(parent)

        # Make the widget transparent to mouse events except for labels
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Labels data: list of dicts with 'tag_name', 'y_pos', 'color', 'is_collapsed'
        self._labels: List[Dict] = []

        # Theme
        self.theme = ThemeManager().get_theme()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

        # Start invisible
        self.setVisible(False)

    def _on_theme_changed(self, theme: Dict) -> None:
        """Update theme and refresh."""
        self.theme = theme
        self.update()

    def set_labels(self, labels: List[Dict]) -> None:
        """
        Set the labels to display.

        Args:
            labels: List of dicts with keys:
                - 'tag_name': str
                - 'y_pos': float (Y position in view coordinates)
                - 'color': str (hex color)
                - 'is_collapsed': bool
        """
        self._labels = labels
        self.setVisible(len(labels) > 0)
        self.update()

    def clear_labels(self) -> None:
        """Clear all labels."""
        self._labels = []
        self.setVisible(False)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the labels."""
        if not self._labels:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw each label
        for label_data in self._labels:
            tag_name = label_data["tag_name"]
            y_pos = label_data["y_pos"]
            color = QColor(label_data["color"])
            is_collapsed = label_data.get("is_collapsed", False)

            # Skip if label is outside visible area
            if y_pos < -30 or y_pos > self.height():
                continue

            # Constant height regardless of collapse state
            label_height = 24

            # Draw color indicator
            color.setAlphaF(0.8)
            painter.fillRect(0, int(y_pos), 4, label_height, color)

            # Draw chevron indicator
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.theme["text_main"]))

            center_x = self.LABEL_PADDING + 4
            center_y = int(y_pos) + (label_height // 2)

            from PySide6.QtCore import QPointF

            if is_collapsed:
                # Triangle pointing right (▶)
                points = [
                    QPointF(center_x - 3, center_y - 4),
                    QPointF(center_x + 3, center_y),
                    QPointF(center_x - 3, center_y + 4),
                ]
            else:
                # Triangle pointing down (▼)
                points = [
                    QPointF(center_x - 4, center_y - 3),
                    QPointF(center_x + 4, center_y - 3),
                    QPointF(center_x, center_y + 3),
                ]

            painter.drawPolygon(QPolygonF(points))

            # Draw text (always show title even when collapsed)
            painter.setPen(QColor(self.theme["text_main"]))
            font = QFont()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)

            # Clip text if too long
            text_offset = self.LABEL_PADDING + 14
            max_width = self.LABEL_WIDTH - text_offset - 8
            display_name = tag_name

            if painter.fontMetrics().horizontalAdvance(display_name) > max_width:
                # Truncate with ellipsis
                display_name = painter.fontMetrics().elidedText(
                    display_name, Qt.ElideRight, max_width
                )

            painter.drawText(
                text_offset,
                int(y_pos),
                max_width,
                label_height,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                display_name,
            )
