"""Keyboard Shortcuts Dialog.

Displays all available keyboard shortcuts in the application.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.utils.shortcut_manager import ShortcutManager


class KeyboardShortcutsDialog(QDialog):
    """Dialog displaying all keyboard shortcuts.
    
    Shows shortcuts organized by category with descriptions.
    """
    
    def __init__(self, parent: QWidget = None) -> None:
        """Initialize the keyboard shortcuts dialog.
        
        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Keyboard Shortcuts")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(20)
        
        # Add shortcut categories
        self._add_category(content_layout, "Creation", [
            ShortcutManager.CREATE_EVENT,
            ShortcutManager.CREATE_ENTITY,
            ShortcutManager.CREATE_MAP,
        ])
        
        self._add_category(content_layout, "Search & Navigation", [
            ShortcutManager.FIND,
        ])
        
        self._add_category(content_layout, "Text Formatting", [
            ShortcutManager.FORMAT_BOLD,
            ShortcutManager.FORMAT_ITALIC,
            ShortcutManager.FORMAT_H1,
            ShortcutManager.FORMAT_H2,
            ShortcutManager.FORMAT_H3,
            ShortcutManager.FORMAT_BODY,
        ])
        
        self._add_category(content_layout, "Outline Editor", [
            ShortcutManager.OUTLINE_PROMOTE,
            ShortcutManager.OUTLINE_DEMOTE,
        ])
        
        # Add note about Ctrl+Click
        note_label = QLabel(
            "\nNote: Ctrl+Click on entity/event names to navigate"
        )
        note_label.setStyleSheet("color: gray; font-style: italic;")
        content_layout.addWidget(note_label)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _add_category(
        self, 
        layout: QVBoxLayout, 
        category_name: str, 
        shortcuts: list
    ) -> None:
        """Add a category section with shortcuts.
        
        Args:
            layout: The layout to add to.
            category_name: Name of the category.
            shortcuts: List of KeyboardShortcut objects.
        """
        # Category header
        category_label = QLabel(category_name)
        category_label.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: #2196F3; padding-top: 5px;"
        )
        layout.addWidget(category_label)
        
        # Shortcuts in this category
        for shortcut in shortcuts:
            shortcut_widget = self._create_shortcut_row(
                shortcut.sequence, 
                shortcut.description
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
        key_label.setStyleSheet(
            "background-color: #444; "
            "color: white; "
            "padding: 4px 12px; "
            "border-radius: 4px; "
            "font-family: monospace; "
            "font-weight: bold;"
        )
        key_label.setMinimumWidth(100)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(key_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("padding-left: 15px;")
        row_layout.addWidget(desc_label)
        
        row_layout.addStretch()
        
        return row
