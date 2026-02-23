"""Tag Editor Widget Module.

Provides a list-based interface for managing tags on entities and events.
"""

from typing import List, Optional

from PySide6.QtCore import QStringListModel, Qt, Signal, Slot
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
        """
        Create a tag editor widget with a wrapping flow of tag "pill" widgets and an integrated text input that supports completion.
        
        Sets up the flow container and layout for tag pills, an inline QLineEdit for adding tags, a persistent QStringListModel-backed QCompleter for suggestions, and a styled frame around the flow. The widget starts with only the input present.
        
        Parameters:
            parent (QWidget | None): Optional parent widget.
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

        # Persistent completer + model (avoids QObject churn on each update)
        self._completer_model = QStringListModel(self)
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.tag_input.setCompleter(self._completer)

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
        """
        Set the base color used to style tag pills and update existing pills to reflect it.
        
        Parameters:
            color (str): Hex color string (e.g., "#RRGGBB") to apply as the pill base color.
        """
        self._base_color = color
        # Refresh existing pills
        self.load_tags(self.get_tags())

    def load_tags(self, tags: List[str]) -> None:
        """
        Replace the displayed tags with the provided list by creating a TagPill for each entry.
        
        This clears all existing tag pills (preserving the integrated input field) and adds new pills in the same order as the provided list so the input remains at the end.
        
        Parameters:
            tags (List[str]): List of tag strings to display; order determines left-to-right pill order.
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
        """
        Add a TagPill widget for the given tag into the flow layout immediately before the input field.
        
        The pill's `deleted` signal is connected to the widget's deletion handler so removing the pill emits updates.
        
        Parameters:
            tag (str): Text to display on the created tag pill.
        """
        pill = TagPill(tag, base_color=self._base_color)
        pill.deleted.connect(self._on_pill_deleted)

        # Insert before the input field
        self.flow_layout.takeAt(self.flow_layout.count() - 1)
        self.flow_layout.addWidget(pill)
        self.flow_layout.addWidget(self.tag_input)

    def get_tags(self) -> List[str]:
        """
        Get the current tag texts in display order.
        
        Returns:
            List[str]: Tag texts from the flow layout, in left-to-right wrapping order.
        """
        tags = []
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, TagPill):
                tags.append(widget.text)
        return tags

    def update_suggestions(self, tags: List[str]) -> None:
        """
        Update the autocomplete suggestions used by the tag input completer.
        
        Parameters:
            tags: Iterable of suggestion strings to set for the completer; replaces any previous suggestions.
        """
        self._completer_model.setStringList(tags)

    @Slot()
    def _on_add(self) -> None:
        """
        Add the tag currently entered in the input to the widget if valid and not a duplicate.
        
        Reads and trims the input text; if the result is non-empty and not already present, creates a new tag pill, clears the input, and emits the `tags_changed` signal.
        """
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
        """
        Remove the first tag pill whose text matches the provided tag and emit the `tags_changed` signal.
        
        Parameters:
            tag (str): The tag text to remove. If no matching pill exists, the method does nothing.
        """
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, TagPill) and widget.text == tag:
                self.flow_layout.takeAt(i)
                widget.deleteLater()
                self.tags_changed.emit()
                break
