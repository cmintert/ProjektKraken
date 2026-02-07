"""Relation Type Picker Widget.

A popup widget that displays a list of available relation types
for selection during drag-and-drop operations.
"""

import logging
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.standard_buttons import PrimaryButton, StandardButton

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

        # Sort types for better UX
        self.relation_types = sorted(relation_types)

        self._setup_ui()
        self._apply_theme()

        # Connect theme changes
        ThemeManager().theme_changed.connect(self._apply_theme)

        # Ensure the widget paints its background/border correctly
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Start hidden
        self.hide()

    def set_relation_types(self, relation_types: List[str]) -> None:
        """Update the list of available relation types.

        Args:
            relation_types: List of new relation types.
        """
        if not relation_types:
            relation_types = ["related"]
        elif "related" not in relation_types:
            relation_types = ["related"] + list(relation_types)

        self.relation_types = sorted(list(set(relation_types)))

        self.combo_box.clear()
        self.combo_box.addItems(self.relation_types)

        # Reset default
        self.combo_box.setCurrentText("related")

    def _setup_ui(self) -> None:
        """Setup the UI layout and components."""
        # Set window flags for floating, frameless, always-on-top window
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup
        )

        # Main layout is vertical to stack header and input row
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Add Header
        self.header_label = QLabel("Choose Relation Type")
        layout.addWidget(self.header_label)

        # Horizontal row for input and buttons
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        # Create combo box
        self.combo_box = QComboBox()
        self.combo_box.setEditable(True)
        self.combo_box.addItems(self.relation_types)

        # Set default selection
        self.combo_box.setCurrentText("related")

        # Install event filter on the line edit to capture keys
        self.combo_box.lineEdit().installEventFilter(self)

        input_layout.addWidget(self.combo_box, 1)

        # Create OK button
        self.ok_button = PrimaryButton("OK")
        self.ok_button.setFixedWidth(60)

        input_layout.addWidget(self.ok_button)

        # Create Cancel button
        self.cancel_button = StandardButton("Cancel")
        self.cancel_button.setFixedWidth(80)

        input_layout.addWidget(self.cancel_button)

        layout.addLayout(input_layout)

        # Connect signals
        self.combo_box.lineEdit().returnPressed.connect(self._on_confirmed)
        self.ok_button.clicked.connect(self._on_confirmed)
        self.cancel_button.clicked.connect(self.hide)

        # Set size constraints from constants
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
        app_bg = theme.get("app_bg", "#1E1E1E")
        border = theme.get("border", "#454545")
        text_main = theme.get("text_main", "#E0E0E0")
        text_dim = theme.get("text_dim", "#757575")
        primary = theme.get("primary", "#FF9900")

        # Apply stylesheet to container
        self.setStyleSheet(
            f"""
            QWidget#PickerContainer {{
                background-color: {app_bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel {{
                color: {text_dim};
                font-size: 10pt;
                font-weight: bold;
                border: none;
                background-color: transparent;
                padding-bottom: 2px;
            }}
            QComboBox {{
                background-color: {surface};
                color: {text_main};
                border: 1px solid {border};
                border-radius: 4px;
                padding-left: 8px;
                font-size: 11pt;
                min-height: 32px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {surface};
                color: {text_main};
                selection-background-color: {primary};
                selection-color: {surface};
                border: 1px solid {border};
            }}
            """
        )

        # Ensure child widgets don't inherit the PickerContainer border
        self.setObjectName("PickerContainer")

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

        # Set focus to combo box and select all text for easy replacement
        self.combo_box.setFocus()
        self.combo_box.lineEdit().selectAll()

        logger.debug(f"RelationTypePicker shown at ({position.x()}, {position.y()})")

    def _on_confirmed(self) -> None:
        """Handle confirmation via Enter or OK button."""
        selected_type = self.combo_box.currentText().strip()
        if not selected_type:
            return

        logger.info(f"Relation type confirmed: {selected_type}")

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
