"""Drag Pill Widget.

A floating widget that follows the cursor during drag operations,
displaying the item being dragged with icon, name, and type.
"""

import logging
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStyle, QStyleOption, QWidget


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

        # Name label
        self.name_label = QLabel(self.item_name)
        self.name_label.setMinimumWidth(20)
        self.name_label.setMaximumWidth(100)
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.name_label)

        # Type label
        self.type_label = QLabel(f"({self.item_type})")
        layout.addWidget(self.type_label)

    def _apply_theme(self) -> None:
        """Apply unified pill styling using StyleHelper."""
        from src.gui.utils.style_helper import StyleHelper

        style = StyleHelper.get_pill_style(
            object_name="DragPill", has_delete=False, height=40
        )
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
        """Ensure QSS styling (background, border-radius) is rendered correctly."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def hide(self) -> None:
        """Hide the drag pill widget."""
        super().hide()
        logger.debug("DragPill hidden")
