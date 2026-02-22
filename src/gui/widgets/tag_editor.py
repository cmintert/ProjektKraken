"""Tag Editor Widget Module.

Provides a list-based interface for managing tags on entities and events.
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCompleter,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.flow_layout import FlowLayout
from src.gui.widgets.tag_pill import TagPill


class TagEditorWidget(QWidget):
    """A widget for managing tags using a modern flow-based pill interface.

    Tags are displayed as rounded pills in a row, wrapping automatically.
    A text input field is integrated into the flow for adding new tags.

    Signals:
        tags_changed: Emitted when tags are added or removed.
    """

    tags_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the TagEditorWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        self._base_color: Optional[str] = None

        main_layout = QVBoxLayout(self)
        from src.gui.utils.style_helper import StyleHelper

        StyleHelper.apply_compact_spacing(main_layout)

        # Flow container for pills and input
        self.flow_container = QWidget()
        self.flow_layout = FlowLayout(self.flow_container)
        self.flow_layout.setSpacing(6)

        # Tag input - integrated into flow
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Add tag...")
        self.tag_input.setMinimumWidth(100)
        self.tag_input.setStyleSheet(StyleHelper.get_transparent_input_style())
        self.tag_input.returnPressed.connect(self._on_add)

        # We'll wrap the flow container in a styled frame to look like an input box
        self.container_frame = QWidget()
        self.container_frame.setStyleSheet(StyleHelper.get_input_field_style())
        frame_layout = QVBoxLayout(self.container_frame)
        frame_layout.setContentsMargins(4, 4, 4, 4)
        frame_layout.addWidget(self.flow_container)

        main_layout.addWidget(self.container_frame)

        # Initial state: just the input
        self.flow_layout.addWidget(self.tag_input)

    def set_base_color(self, color: str) -> None:
        """Sets the base color for tag pills.

        Args:
            color: Hex color string.
        """
        self._base_color = color
        # Refresh existing pills
        self.load_tags(self.get_tags())

    def load_tags(self, tags: List[str]) -> None:
        """Populates the widget with the given list of tags.

        Args:
            tags (list): List of tag strings.

        """
        # Clear existing pills (everything except the input)
        for i in reversed(range(self.flow_layout.count())):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if widget != self.tag_input:
                self.flow_layout.takeAt(i)
                widget.deleteLater()

        for tag in tags:
            self._add_pill(tag)

    def _add_pill(self, tag: str) -> None:
        """Creates and adds a TagPill to the flow.

        Args:
            tag: The tag text.
        """
        pill = TagPill(tag, base_color=self._base_color)
        pill.deleted.connect(self._on_pill_deleted)

        # Insert before the input field
        self.flow_layout.takeAt(self.flow_layout.count() - 1)
        self.flow_layout.addWidget(pill)
        self.flow_layout.addWidget(self.tag_input)

    def get_tags(self) -> List[str]:
        """Returns the current list of tags.

        Returns:
            list: List of tag strings.

        """
        tags = []
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, TagPill):
                tags.append(widget.text)
        return tags

    def update_suggestions(self, tags: List[str]) -> None:
        """Updates the tag completer with new suggestions.

        Args:
            tags: List of existing tags for completion.

        """
        completer = QCompleter(tags, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.tag_input.setCompleter(completer)

    @Slot()
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
        self._add_pill(raw_tag)

        self.tag_input.clear()
        self.tags_changed.emit()

    @Slot(str)
    def _on_pill_deleted(self, tag: str) -> None:
        """Handles removing a tag pill.

        Args:
            tag: The text of the tag to remove.
        """
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, TagPill) and widget.text == tag:
                self.flow_layout.takeAt(i)
                widget.deleteLater()
                self.tags_changed.emit()
                break
