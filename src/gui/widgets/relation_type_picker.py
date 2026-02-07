"""Relation Type Picker Widget.

A popup widget that displays a list of available relation types
for selection during drag-and-drop operations.
"""

import logging
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class RelationTypePicker(QWidget):
    """Popup widget for selecting relation types during drag operations.

    Displays a list of relation types and allows quick selection.
    Typically shown when the Shift key is pressed during drag.
    """

    # Signal emitted when a type is selected
    type_selected = Signal(str)  # Emits the selected relation type

    def __init__(
        self,
        relation_types: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the relation type picker.

        Args:
            relation_types: List of available relation types. Defaults to ["related"].
            parent: Parent widget (usually None for floating window).
        """
        super().__init__(parent)

        # Store relation types, ensure "related" is always available
        if not relation_types:
            relation_types = ["related"]
        elif "related" not in relation_types:
            relation_types = ["related"] + list(relation_types)

        self.relation_types = relation_types
        self.selected_type = "related"  # Default selection

        self._setup_ui()
        self._apply_theme()

        # Start hidden
        self.hide()

    def _setup_ui(self) -> None:
        """Setup the UI layout and components."""
        # Set window flags for floating, frameless, always-on-top window
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup  # Automatically closes when clicking outside
        )

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create list widget
        self.list_widget = QListWidget()
        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # Add relation types to list
        for rel_type in self.relation_types:
            item = QListWidgetItem(rel_type)
            self.list_widget.addItem(item)

        # Select first item by default
        self.list_widget.setCurrentRow(0)

        # Connect signals
        self.list_widget.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.list_widget)

        # Set size constraints
        # Set size constraints
        from src.app.constants import (
            RELATION_PICKER_MAX_HEIGHT,
            RELATION_PICKER_MAX_WIDTH,
            RELATION_PICKER_MIN_HEIGHT,
            RELATION_PICKER_MIN_WIDTH,
        )

        self.setMinimumWidth(RELATION_PICKER_MIN_WIDTH)
        self.setMaximumWidth(RELATION_PICKER_MAX_WIDTH)
        self.setMinimumHeight(RELATION_PICKER_MIN_HEIGHT)
        self.setMaximumHeight(RELATION_PICKER_MAX_HEIGHT)

        # Install event filter for escape key
        self.installEventFilter(self)

    def _apply_theme(self) -> None:
        """Apply theme colors to the widget."""
        theme_manager = ThemeManager()
        theme = theme_manager.get_theme()

        # Get theme colors
        surface = theme.get("surface", "#323232")
        border = theme.get("border", "#454545")
        text_main = theme.get("text_main", "#E0E0E0")
        primary = theme.get("primary", "#FF9900")

        # Apply stylesheet to container
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            """
        )

        # Apply stylesheet to list widget
        self.list_widget.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {surface};
                border: none;
                color: {text_main};
                padding: 4px;
                font-size: 12pt;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 3px;
            }}
            QListWidget::item:hover {{
                background-color: rgba({primary.lstrip('#')}, 0.2);
            }}
            QListWidget::item:selected {{
                background-color: {primary};
                color: {surface};
                font-weight: bold;
            }}
            """
        )

    def show_at_position(self, position: QPoint) -> None:
        """Show the type picker at the specified position.

        Args:
            position: Position to show the picker (usually near cursor).
        """
        # Adjust size to fit content
        self.adjustSize()

        # Position near the specified point
        self.move(position)
        self.show()
        self.raise_()
        self.activateWindow()

        # Set focus to list widget for keyboard navigation
        self.list_widget.setFocus()

        logger.debug(f"RelationTypePicker shown at ({position.x()}, {position.y()})")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle item click event.

        Args:
            item: The clicked list item.
        """
        selected_type = item.text()
        self.selected_type = selected_type

        logger.info(f"Relation type selected: {selected_type}")

        # Emit signal
        self.type_selected.emit(selected_type)

        # Hide the picker
        self.hide()

    def eventFilter(self, obj: QWidget, event) -> bool:
        """Filter events to handle Escape key.

        Args:
            obj: Object that received the event.
            event: The event.

        Returns:
            True if event was handled, False otherwise.
        """
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True

        return super().eventFilter(obj, event)

    def hide(self) -> None:
        """Hide the type picker."""
        super().hide()
        logger.debug("RelationTypePicker hidden")
