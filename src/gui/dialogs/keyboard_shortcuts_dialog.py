"""Keyboard Shortcuts Dialog.

Displays all available keyboard shortcuts in the application.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.shortcut_manager import ShortcutManager
from src.gui.utils.style_helper import StyleHelper


class KeyboardShortcutsDialog(QDialog):
    """Dialog displaying all keyboard shortcuts.

    Shows shortcuts organized by category with descriptions.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the keyboard shortcuts dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(StyleHelper.get_dialog_base_style())

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("Keyboard Shortcuts")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(StyleHelper.get_content_header_style())
        layout.addWidget(header)

        # Scroll Area for many shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(StyleHelper.get_scroll_area_style())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        StyleHelper.apply_standard_list_spacing(content_layout)
        content_layout.setSpacing(10)

        # --- Categories ---

        # Creation
        self._add_category(
            content_layout,
            "Creation",
            [
                ShortcutManager.CREATE_EVENT,
                ShortcutManager.CREATE_ENTITY,
                ShortcutManager.CREATE_MAP,
            ],
        )

        # Edit
        self._add_category(
            content_layout,
            "Edit",
            [
                ShortcutManager.UNDO,
                ShortcutManager.REDO,
            ],
        )

        # Search & Navigation
        self._add_category(
            content_layout,
            "Search & Navigation",
            [
                ShortcutManager.FIND,
                ShortcutManager.NAVIGATE_LINK,
            ],
        )

        # Drag & Drop
        self._add_category(
            content_layout,
            "Drag & Drop",
            [
                ShortcutManager.DROP_CHOOSE_TYPE,
            ],
        )

        # Text Formatting
        self._add_category(
            content_layout,
            "Text Formatting",
            [
                ShortcutManager.FORMAT_BOLD,
                ShortcutManager.FORMAT_ITALIC,
                ShortcutManager.FORMAT_H1,
                ShortcutManager.FORMAT_H2,
                ShortcutManager.FORMAT_H3,
                ShortcutManager.FORMAT_BODY,
            ],
        )

        # Outline Editor
        self._add_category(
            content_layout,
            "Outline Editor",
            [
                ShortcutManager.OUTLINE_PROMOTE,
                ShortcutManager.OUTLINE_DEMOTE,
            ],
        )

        # General
        self._add_category(
            content_layout,
            "General",
            [
                ShortcutManager.DESELECT,
            ],
        )

        # Map
        self._add_category(
            content_layout,
            "Map",
            [
                ShortcutManager.MAP_PAN,
            ],
        )

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Close Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet(StyleHelper.get_primary_button_style())
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _add_category(
        self, layout: QVBoxLayout, category_name: str, shortcuts: list
    ) -> None:
        """Add a category section with shortcuts.

        Args:
            layout: The layout to add to.
            category_name: Name of the category.
            shortcuts: List of KeyboardShortcut objects.
        """
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()

        # Category header
        category_label = QLabel(category_name)
        category_label.setStyleSheet(
            f"font-size: 12pt; font-weight: bold; "
            f"color: {theme['accent_secondary']}; padding-top: 5px;"
        )
        layout.addWidget(category_label)

        # Shortcuts in this category
        for shortcut in shortcuts:
            shortcut_widget = self._create_shortcut_row(
                shortcut.sequence, shortcut.description
            )
            layout.addWidget(shortcut_widget)

    def _create_shortcut_row(self, keys: str, description: str) -> QWidget:
        """Create a single shortcut row.

        Args:
            keys: The key combination (e.g., "Ctrl+E").
            description: What the shortcut does.

        Returns:
            Widget containing the shortcut display.
        """
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 2, 10, 2)

        # Key combination (styled like a button)
        key_label = QLabel(keys)
        key_label.setStyleSheet(StyleHelper.get_shortcut_key_style())
        key_label.setMinimumWidth(100)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(key_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("padding-left: 15px;")
        row_layout.addWidget(desc_label)

        row_layout.addStretch()

        return row
