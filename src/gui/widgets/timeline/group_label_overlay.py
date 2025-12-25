"""
Group Label Overlay Module.

Provides a fixed overlay widget that displays tag lane labels on the left side
of the timeline view, remaining visible during horizontal scrolling.
"""

import logging
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
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

    def __init__(self, parent=None):
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

    def _on_theme_changed(self, theme):
        """Update theme and refresh."""
        self.theme = theme
        self.update()

    def set_labels(self, labels: List[Dict]):
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

    def clear_labels(self):
        """Clear all labels."""
        self._labels = []
        self.setVisible(False)
        self.update()

    def paintEvent(self, event):
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

            # Determine height based on collapse state
            label_height = 4 if is_collapsed else 24

            # Draw color indicator
            color.setAlphaF(0.8)
            painter.fillRect(0, int(y_pos), 4, label_height, color)

            # Draw text (only if expanded)
            if not is_collapsed:
                painter.setPen(QColor(self.theme["text_main"]))
                font = QFont()
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)

                # Clip text if too long
                text_rect = painter.fontMetrics().boundingRect(tag_name)
                max_width = self.LABEL_WIDTH - self.LABEL_PADDING - 8

                if text_rect.width() > max_width:
                    # Truncate with ellipsis
                    tag_name = painter.fontMetrics().elidedText(
                        tag_name, Qt.ElideRight, max_width
                    )

                painter.drawText(
                    self.LABEL_PADDING,
                    int(y_pos),
                    self.LABEL_WIDTH - self.LABEL_PADDING * 2,
                    label_height,
                    Qt.AlignVCenter | Qt.AlignLeft,
                    tag_name,
                )
