"""
Tag Editor Widget Module.

Provides a list-based interface for managing tags on entities and events.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from typing import List, Optional

from src.gui.widgets.standard_buttons import StandardButton


class TagEditorWidget(QWidget):
    """
    A widget for managing tags (list of strings).

    Provides an input field for adding tags and a list for viewing/removing them.

    Signals:
        tags_changed: Emitted when tags are added or removed.
    """

    tags_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the TagEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(self.layout)

        # Toolbar with action buttons
        toolbar_layout = QHBoxLayout()
        self.btn_add = StandardButton("Add Tag")
        self.btn_add.clicked.connect(self._on_add)
        toolbar_layout.addWidget(self.btn_add)

        self.btn_remove = StandardButton("Remove")
        self.btn_remove.setStyleSheet(StyleHelper.get_destructive_button_style())
        self.btn_remove.clicked.connect(self._on_remove)
        toolbar_layout.addWidget(self.btn_remove)

        toolbar_layout.addStretch()
        self.layout.addLayout(toolbar_layout)

        # Input row
        input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter tag and press Enter...")
        self.tag_input.returnPressed.connect(self._on_add)
        input_layout.addWidget(self.tag_input)
        self.layout.addLayout(input_layout)

        # Tag list
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SingleSelection)
        self.layout.addWidget(self.tag_list)

    def load_tags(self, tags: List[str]) -> None:
        """
        Populates the widget with the given list of tags.

        Args:
            tags (list): List of tag strings.
        """
        self.tag_list.clear()
        for tag in tags:
            item = QListWidgetItem(tag)
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tag_list.addItem(item)

    def get_tags(self) -> List[str]:
        """
        Returns the current list of tags.

        Returns:
            list: List of tag strings.
        """
        tags = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            tags.append(item.data(Qt.ItemDataRole.UserRole))
        return tags

    def _on_add(self) -> None:
        """Handles adding a new tag."""
        raw_tag = self.tag_input.text().strip()
        if not raw_tag:
            return

        # Check for duplicates
        existing = self.get_tags()
        if raw_tag in existing:
            self.tag_input.clear()
            return

        # Add the tag
        item = QListWidgetItem(raw_tag)
        item.setData(Qt.ItemDataRole.UserRole, raw_tag)
        self.tag_list.addItem(item)

        self.tag_input.clear()
        self.tags_changed.emit()

    def _on_remove(self) -> None:
        """Handles removing the selected tag."""
        current_item = self.tag_list.currentItem()
        if current_item:
            row = self.tag_list.row(current_item)
            self.tag_list.takeItem(row)
            self.tags_changed.emit()
