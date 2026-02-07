"""Drag Pill Widget.

A floating widget that follows the cursor during drag operations,
displaying the item being dragged with icon, name, and type.
"""

import logging
from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class DragPill(QWidget):
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

        # Start hidden
        self.hide()

    def _setup_ui(self) -> None:
        """Set up the UI layout and components.

        Creates a frameless, floating window with icon, name, and type labels
        arranged horizontally.
        """
        # Set window flags for floating, frameless, always-on-top window
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Icon label
        self.icon_label = QLabel(self.ICONS.get(self.item_type, "📄"))
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)

        # Name label
        self.name_label = QLabel(self.item_name)
        self.name_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.name_label)

        # Type label
        self.type_label = QLabel(f"({self.item_type})")
        self.type_label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(self.type_label)

        # Set size constraints
        self.setMaximumWidth(200)
        self.setFixedHeight(40)
        self.adjustSize()

    def _apply_theme(self) -> None:
        """Apply theme colors to the widget.

        Retrieves colors from ThemeManager and applies them to the background,
        borders, and text. Also adds a drop shadow effect for depth.
        """
        theme_manager = ThemeManager()
        theme = theme_manager.get_theme()

        # Get theme colors
        surface = theme.get("surface", "#323232")
        border = theme.get("border", "#454545")
        text_main = theme.get("text_main", "#E0E0E0")
        text_dim = theme.get("text_dim", "#9E9E9E")

        # Apply stylesheet
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_main};
            }}
            """
        )

        # Update text colors
        self.name_label.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; color: {text_main};"
        )
        self.type_label.setStyleSheet(f"font-size: 10pt; color: {text_dim};")

        # Add shadow effect
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 76))  # rgba(0, 0, 0, 0.3)
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
        """Update the drag pill position during drag.

        Args:
            position: New base position (usually cursor position).
        """
        offset_position = position + self.cursor_offset
        self.move(offset_position)

    def hide(self) -> None:
        """Hide the drag pill widget."""
        super().hide()
        logger.debug("DragPill hidden")
