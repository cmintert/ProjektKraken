"""
Grouping Configuration Dialog Module.

Provides a dialog for configuring timeline grouping by tags.
Allows selecting tags, reordering them, choosing grouping mode,
and editing tag colors.
"""

import logging
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.commands.timeline_grouping_commands import (
    SetTimelineGroupingCommand,
    UpdateTagColorCommand,
)

logger = logging.getLogger(__name__)


class ColorSwatch(QFrame):
    """
    Clickable color swatch widget.
    Subclasses QFrame to avoid QPushButton styling issues.
    """

    clicked = Signal()

    def __init__(self, color: str, size: int = 16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"background-color: {color}; border: 1px solid #ccc; border-radius: 2px;"
        )

    def mouseReleaseEvent(self, event):
        """Emits clicked signal on mouse release."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def set_color(self, color: str):
        """Updates the swatch color."""
        self.setStyleSheet(
            f"background-color: {color}; border: 1px solid #ccc; border-radius: 2px;"
        )


class TagListItem(QWidget):
    """
    Custom widget for displaying a tag in the list with checkbox,
    color button, and event count.

    Signals:
        color_changed: Emitted when color button is clicked.
    """

    color_changed = Signal(str, str)  # tag_name, new_color

    def __init__(self, tag_name: str, tag_color: str, event_count: int, parent=None):
        """
        Initializes the TagListItem.

        Args:
            tag_name: The name of the tag.
            tag_color: Hex color string for the tag.
            event_count: Number of events with this tag.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.tag_name = tag_name
        self.tag_color = tag_color
        self.event_count = event_count

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # Checkbox
        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)

        # Color button (using ColorSwatch)
        self.color_button = ColorSwatch(tag_color, size=16)
        self.color_button.clicked.connect(self._on_color_button_clicked)
        layout.addWidget(self.color_button)

        # Tag name and count
        self.label = QLabel(f"{tag_name} ({event_count})")
        layout.addWidget(self.label, 1)

        self.setLayout(layout)

    def _on_color_button_clicked(self):
        """Opens color picker and updates button color."""
        color = QColorDialog.getColor(QColor(self.tag_color), self)
        if color.isValid():
            self.tag_color = color.name()
            self.color_button.set_color(self.tag_color)
            self.color_changed.emit(self.tag_name, self.tag_color)

    def is_checked(self) -> bool:
        """Returns whether the checkbox is checked."""
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        """Sets the checkbox state."""
        self.checkbox.setChecked(checked)

    def update_event_count(self, count: int):
        """Updates the event count display."""
        self.label.setText(f"{self.tag_name} ({count})")


class GroupingConfigDialog(QDialog):
    """
    Dialog for configuring timeline grouping.

    Allows users to:
    - Select which tags to group by
    - Reorder tags
    - Choose grouping mode (DUPLICATE vs FIRST_MATCH)
    - Edit tag colors
    """

    grouping_applied = Signal(list, str)  # tag_order, mode

    def __init__(self, tags_data, current_config, command_coordinator, parent=None):
        """
        Initializes the GroupingConfigDialog.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.
            command_coordinator: CommandCoordinator for executing commands.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.tags_data = tags_data
        self.current_config = current_config or {}
        self.command_coordinator = command_coordinator

        self.setWindowTitle("Configure Timeline Grouping")
        self.resize(500, 600)

        # Tag items keyed by tag name
        self.tag_items = {}

        self._setup_ui()
        self._load_tags()
        self._load_current_config()

    def _setup_ui(self):
        """Sets up the dialog UI."""
        layout = QVBoxLayout()

        # Instructions
        instructions = QLabel(
            "Select tags to group by and set their order.\n"
            "Use up/down buttons to reorder selected tags."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Tag list with up/down buttons
        list_layout = QHBoxLayout()

        # List widget
        self.list_widget = QListWidget()
        list_layout.addWidget(self.list_widget, 1)

        # Up/Down buttons
        button_layout = QVBoxLayout()
        self.btn_up = QPushButton("▲")
        self.btn_up.setToolTip("Move selected tag up")
        self.btn_up.clicked.connect(self._move_up)
        button_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setToolTip("Move selected tag down")
        self.btn_down.clicked.connect(self._move_down)
        button_layout.addWidget(self.btn_down)

        button_layout.addStretch()
        list_layout.addLayout(button_layout)

        layout.addLayout(list_layout)

        # Grouping mode
        mode_label = QLabel("Grouping Mode:")
        mode_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(mode_label)

        self.radio_duplicate = QRadioButton("Duplicate")
        self.radio_duplicate.setToolTip(
            "Events with multiple tags appear in all matching groups"
        )
        self.radio_duplicate.setChecked(True)
        layout.addWidget(self.radio_duplicate)

        self.radio_first_match = QRadioButton("First Match")
        self.radio_first_match.setToolTip(
            "Events appear only in the first matching group"
        )
        layout.addWidget(self.radio_first_match)

        # Button group for radio buttons
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_duplicate)
        self.mode_group.addButton(self.radio_first_match)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(
            self._on_apply_clicked
        )
        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def _load_tags(self):
        """Loads tags from provided data and populates the list."""
        try:
            for tag_data in self.tags_data:
                tag_name = tag_data["name"]
                tag_color = tag_data["color"]
                event_count = tag_data["count"]

                # Create list item
                item_widget = TagListItem(tag_name, tag_color, event_count)
                item_widget.color_changed.connect(self._on_tag_color_changed)

                list_item = QListWidgetItem(self.list_widget)
                list_item.setSizeHint(item_widget.sizeHint())
                self.list_widget.addItem(list_item)
                self.list_widget.setItemWidget(list_item, item_widget)

                self.tag_items[tag_name] = (list_item, item_widget)

            logger.debug(f"Loaded {len(self.tags_data)} tags into grouping dialog")

        except Exception as e:
            logger.error(f"Failed to load tags: {e}")

    def _load_current_config(self):
        """Loads the current grouping configuration and updates UI."""
        try:
            if self.current_config:
                tag_order = self.current_config.get("tag_order", [])
                mode = self.current_config.get("mode", "DUPLICATE")

                # Check tags in order
                for tag_name in tag_order:
                    if tag_name in self.tag_items:
                        _, widget = self.tag_items[tag_name]
                        widget.set_checked(True)

                # Reorder items to match tag_order
                self._reorder_items_by_tags(tag_order)

                # Set mode
                if mode == "FIRST_MATCH":
                    self.radio_first_match.setChecked(True)
                else:
                    self.radio_duplicate.setChecked(True)

                logger.debug(f"Loaded grouping config: {len(tag_order)} tags, {mode}")

        except Exception as e:
            logger.warning(f"Failed to load current grouping config: {e}")

    def _reorder_items_by_tags(self, tag_order: List[str]):
        """
        Reorders list items to match the given tag order.

        Args:
            tag_order: List of tag names in desired order.
        """
        # Move checked items to top in order
        for i, tag_name in enumerate(tag_order):
            if tag_name in self.tag_items:
                list_item, _ = self.tag_items[tag_name]
                current_row = self.list_widget.row(list_item)
                if current_row != i:
                    item = self.list_widget.takeItem(current_row)
                    self.list_widget.insertItem(i, item)
                    # Re-set widget
                    _, widget = self.tag_items[tag_name]
                    self.list_widget.setItemWidget(item, widget)

    def _move_up(self):
        """Moves the selected item up in the list."""
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            self._move_item(current_row, current_row - 1)

    def _move_down(self):
        """Moves the selected item down in the list."""
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1 and current_row >= 0:
            self._move_item(current_row, current_row + 1)

    def _move_item(self, source_row: int, target_row: int):
        """
        Moves an item from source_row to target_row by cloning and re-inserting.
        This avoids issues with takeItem causing widget destruction.
        """
        # 1. Get source item and widget
        source_item = self.list_widget.item(source_row)
        source_widget = self.list_widget.itemWidget(source_item)

        if not isinstance(source_widget, TagListItem):
            return

        # 2. Extract state
        tag_name = source_widget.tag_name
        tag_color = source_widget.tag_color
        event_count = source_widget.event_count
        is_checked = source_widget.is_checked()

        # 3. Insert New Item at Target
        # If moving down, we insert at target_row + 1 because the insertion happens
        # before the removal of the old item shifting indices?
        # Actually:
        # [A, B] -> Move A(0) to 1.
        # Insert A' at 2 -> [A, B, A']
        # Remove at 0 -> [B, A']
        # So for down: target_row + 1?
        # Let's use simple logic:
        # If target < source: Insert at target (shifts source to source+1). Remove source+1.
        # If target > source: Insert at target+1. Remove source.

        insert_row = target_row
        if target_row > source_row:
            insert_row = target_row + 1

        # Create new item/widget
        new_widget = TagListItem(tag_name, tag_color, event_count)
        new_widget.set_checked(is_checked)
        new_widget.color_changed.connect(self._on_tag_color_changed)

        new_item = QListWidgetItem()
        new_item.setSizeHint(new_widget.sizeHint())

        self.list_widget.insertItem(insert_row, new_item)
        self.list_widget.setItemWidget(new_item, new_widget)

        # Update tag_items mapping
        self.tag_items[tag_name] = (new_item, new_widget)

        # 4. Remove Old Item
        # If we inserted before source, source index increased by 1
        remove_row = source_row
        if insert_row <= source_row:
            remove_row += 1

        self.list_widget.takeItem(remove_row)
        # Old item/widget will be GC'd naturally

        # 5. Restore selection
        # Calculate new index of the moved item
        new_index = target_row
        self.list_widget.setCurrentRow(new_index)

    def _on_tag_color_changed(self, tag_name: str, color: str):
        """
        Handles tag color change.

        Args:
            tag_name: The name of the tag.
            color: New hex color string.
        """
        logger.debug(f"Tag color changed: {tag_name} -> {color}")

        # Execute UpdateTagColorCommand
        cmd = UpdateTagColorCommand(tag_name, color)
        self.command_coordinator.execute_command(cmd)

    def _on_apply_clicked(self):
        """Handles Apply button click."""
        self._apply_grouping()

    def _apply_grouping(self):
        """Applies the grouping configuration."""
        # Get selected tags in order
        tag_order = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, TagListItem) and widget.is_checked():
                tag_order.append(widget.tag_name)

        # Get mode
        mode = "FIRST_MATCH" if self.radio_first_match.isChecked() else "DUPLICATE"

        logger.info(f"Applying grouping: {len(tag_order)} tags, mode={mode}")

        # Execute SetTimelineGroupingCommand
        cmd = SetTimelineGroupingCommand(tag_order, mode)
        self.command_coordinator.execute_command(cmd)

        # Emit signal
        self.grouping_applied.emit(tag_order, mode)

    def accept(self):
        """Override accept to apply grouping before closing."""
        self._apply_grouping()
        super().accept()
