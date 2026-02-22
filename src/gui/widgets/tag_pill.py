"""Tag Pill Widget Module.

Provides a rounded rectangular component for displaying a tag with a delete button.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from src.gui.utils.style_helper import StyleHelper


class TagPill(QFrame):
    """A rounded rectangular widget representing a tag.

    Displays the tag text and a small 'x' button to remove it.

    Signals:
        deleted(str): Emitted when the delete button is clicked, with the tag text.
    """

    deleted = Signal(str)

    def __init__(
        self,
        text: str,
        base_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initializes the TagPill.

        Args:
            text: The text to display on the pill.
            base_color: Optional hex color string for the pill's theme.
                        If None, uses accent_secondary from current theme.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.text = text
        self.base_color = base_color

        # Enforce fixed height for consistent pill shape
        self.setFixedHeight(32)

        # Enable QSS background support
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("TagPill")

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        """Sets up the layout and sub-widgets."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self.label = QLabel(self.text)
        font = self.label.font()
        font.setPointSize(10)
        self.label.setFont(font)
        layout.addWidget(self.label)

        self.btn_delete = QToolButton()
        self.btn_delete.setObjectName("TagPillDeleteButton")
        self.btn_delete.setText("✕")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setToolTip(f"Remove tag: {self.text}")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        # Note: Styling is now handled in StyleHelper via get_tag_pill_style
        layout.addWidget(self.btn_delete)

    def _apply_style(self) -> None:
        """Applies the pill styling using StyleHelper."""
        style = StyleHelper.get_pill_style(
            object_name="TagPill",
            base_color=self.base_color,
            has_delete=True,
        )
        self.setStyleSheet(style)

    def enterEvent(self, event) -> None:
        """Trigger repaint on hover enter."""
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        """Trigger repaint on hover leave."""
        super().leaveEvent(event)
        self.update()

    def _on_delete_clicked(self) -> None:
        """Handles the delete button click."""
        self.deleted.emit(self.text)

    def paintEvent(self, event) -> None:
        """High-fidelity rendering of the pill shape with Antialiasing."""
        from src.gui.utils.style_helper import StyleHelper

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get color data from StyleHelper
        data = StyleHelper.get_pill_painter_data(self.base_color)
        r, g, b = data["r"], data["g"], data["b"]

        # Hover state detection
        is_hovered = self.underMouse()
        alpha_start = 0.35 if is_hovered else 0.25
        alpha_end = 0.25 if is_hovered else 0.15
        border_alpha = 0.9 if is_hovered else 0.6
        border_color = (
            QColor(data["hex"])
            if is_hovered
            else QColor(r, g, b, int(255 * border_alpha))
        )

        # Define pill geometry (accounting for margin and border)
        rect = self.contentsRect().adjusted(2, 2, -2, -2)
        radius = rect.height() / 2

        # Create gradient
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, QColor(r, g, b, int(255 * alpha_start)))
        gradient.setColorAt(1, QColor(r, g, b, int(255 * alpha_end)))

        # Draw pill
        p.setBrush(QBrush(gradient))
        p.setPen(QPen(border_color, 1))
        p.drawRoundedRect(rect, radius, radius)
        p.end()


# Add Qt namespace import at the top
