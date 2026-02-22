"""Drag Pill Widget.

A floating widget that follows the cursor during drag operations,
displaying the item being dragged with icon, name, and type.
"""

import logging
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class DragPill(QFrame):
    """Floating widget that displays item information during drag operations.

    Shows an icon, item name, and item type, styled with theme colors.
    Follows the cursor with a configurable offset.
    """

    # Icon mapping for different item types
    ICONS = {
        "event": "⚡",
        "entity": "👤",
        "map": "🗺",
    }

    def __init__(
        self,
        item_name: str,
        item_type: str,
        cursor_offset: Optional[QPoint] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the drag pill widget.

        Args:
            item_name: Name of the item being dragged.
            item_type: Type of the item ('event', 'entity', etc.).
            cursor_offset: Offset from cursor position (default: QPoint(10, 10)).
            parent: Parent widget (usually None for floating window).
        """
        super().__init__(parent)
        self.item_name = item_name
        self.item_type = item_type
        self.cursor_offset = cursor_offset or QPoint(10, 10)

        self._setup_ui()
        self._apply_theme()

        # Cache painter data once (avoids repeated lookups in paintEvent)
        self._painter_data = StyleHelper.get_pill_painter_data(None)

        # Set size constraints and clamp width
        # Use sizeHint but cap at 200
        hint = self.sizeHint()
        width = min(hint.width(), 200)
        self.setFixedSize(width, 40)

        # Start hidden
        self.hide()

    def _setup_ui(self) -> None:
        """Set up the UI layout and components."""
        from PySide6.QtWidgets import QSizePolicy

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("DragPill")

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)  # Refined margins
        layout.setSpacing(8)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMaximumSize)

        # Icon label
        self.icon_label = QLabel(self.ICONS.get(self.item_type, "📄"))
        self.icon_label.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(self.icon_label)

        # Name label with text eliding instead of hard width cap
        self.name_label = QLabel()
        self.name_label.setMinimumWidth(20)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._full_name = self.item_name
        self.name_label.setText(self._full_name)
        layout.addWidget(self.name_label)

        # Type label
        self.type_label = QLabel(f"({self.item_type})")
        layout.addWidget(self.type_label)

    def _elide_name_text(self) -> None:
        """Elide the name label text to fit available width."""
        metrics = QFontMetrics(self.name_label.font())
        available = self.name_label.width()
        if available > 0:
            elided = metrics.elidedText(
                self._full_name, Qt.TextElideMode.ElideRight, available
            )
            self.name_label.setText(elided)

    def resizeEvent(self, event) -> None:
        """Re-elide name text when widget is resized."""
        super().resizeEvent(event)
        self._elide_name_text()

    def _apply_theme(self) -> None:
        """Apply unified pill styling using StyleHelper."""
        style = StyleHelper.get_pill_style(object_name="DragPill", has_delete=False)
        self.setStyleSheet(style)

        # Add shadow effect
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 76))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def show_at_position(self, position: QPoint) -> None:
        """Show the drag pill at the specified position.

        Args:
            position: Base position (usually cursor position).
        """
        # Apply offset and move to position
        offset_position = position + self.cursor_offset
        self.move(offset_position)
        self.show()
        self.raise_()

        logger.debug(
            f"DragPill shown at ({offset_position.x()}, {offset_position.y()})"
        )

    def update_position(self, position: QPoint) -> None:
        """Update the drag pill position during drag."""
        offset_position = position + self.cursor_offset
        self.move(offset_position)

    def paintEvent(self, event) -> None:
        """High-fidelity rendering of the drag pill shape with Antialiasing."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use cached color data
        r, g, b = (
            self._painter_data["r"],
            self._painter_data["g"],
            self._painter_data["b"],
        )

        # Define pill geometry
        rect = self.contentsRect().adjusted(2, 2, -2, -2)
        radius = rect.height() / 2

        # Create gradient
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, QColor(r, g, b, int(255 * 0.25)))
        gradient.setColorAt(1, QColor(r, g, b, int(255 * 0.15)))

        # Draw pill
        p.setBrush(QBrush(gradient))
        p.setPen(QPen(QColor(r, g, b, int(255 * 0.6)), 1))
        p.drawRoundedRect(rect, radius, radius)
        p.end()

    def hide(self) -> None:
        """Hide the drag pill widget."""
        super().hide()
        logger.debug("DragPill hidden")
