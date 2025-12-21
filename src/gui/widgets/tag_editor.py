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
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TagEditorWidget(QWidget):
    """
    A widget for managing tags (list of strings).

    Provides an input field for adding tags and a list for viewing/removing them.

    Signals:
        tags_changed: Emitted when tags are added or removed.
    """

    tags_changed = Signal()

    def __init__(self, parent=None):
        """
        Initializes the TagEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Input row
        input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter tag and press Enter or Add...")
        self.tag_input.returnPressed.connect(self._on_add)
        input_layout.addWidget(self.tag_input)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._on_add)
        input_layout.addWidget(self.btn_add)

        self.layout.addLayout(input_layout)

        # Tag list
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SingleSelection)
        self.layout.addWidget(self.tag_list)

        # Remove button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._on_remove)
        btn_layout.addWidget(self.btn_remove)
        self.layout.addLayout(btn_layout)

    def load_tags(self, tags: list):
        """
        Populates the widget with the given list of tags.

        Args:
            tags (list): List of tag strings.
        """
        self.tag_list.clear()
        for tag in tags:
            item = QListWidgetItem(tag)
            item.setData(Qt.UserRole, tag)
            self.tag_list.addItem(item)

    def get_tags(self) -> list:
        """
        Returns the current list of tags.

        Returns:
            list: List of tag strings.
        """
        tags = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            tags.append(item.data(Qt.UserRole))
        return tags

    def _on_add(self):
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
        item.setData(Qt.UserRole, raw_tag)
        self.tag_list.addItem(item)

        self.tag_input.clear()
        self.tags_changed.emit()

    def _on_remove(self):
        """Handles removing the selected tag."""
        current_item = self.tag_list.currentItem()
        if current_item:
            row = self.tag_list.row(current_item)
            self.tag_list.takeItem(row)
            self.tags_changed.emit()
