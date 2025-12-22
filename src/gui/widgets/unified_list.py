"""
Unified List Widget Module.

Provides a unified list view displaying both events and entities with
filtering and color-coded differentiation.
"""

import json
from typing import List

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDrag
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.entities import Entity
from src.core.events import Event
from src.gui.utils.style_helper import StyleHelper

# Custom MIME type for Kraken items (DRY: reusable across drop targets)
KRAKEN_ITEM_MIME_TYPE = "application/x-kraken-item"


class DraggableListWidget(QListWidget):
    """
    A QListWidget that supports dragging items with custom MIME data.

    Drag data format (JSON):
        {"id": "uuid", "type": "event|entity", "name": "Display Name"}
    """

    def __init__(self, parent=None):
        """Initialize with drag enabled."""
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)

    def startDrag(self, supportedActions):
        """
        Override to provide custom MIME data for dragged items.

        Args:
            supportedActions: The drag actions supported.
        """
        item = self.currentItem()
        if not item:
            return

        # Extract item data (stored via setData in _render_list)
        item_id = item.data(Qt.UserRole)
        item_type = item.data(Qt.UserRole + 1)
        item_name = item.data(Qt.UserRole + 2)  # We'll add this

        if not item_id or not item_type:
            return

        # Build MIME data
        data = {"id": item_id, "type": item_type, "name": item_name or item.text()}

        mime_data = QMimeData()
        mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(data).encode("utf-8"))

        # Also set plain text for debugging/compatibility
        mime_data.setText(f"{item_type}:{item_id}")

        # Create and execute drag
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)


class UnifiedListWidget(QWidget):
    """
    A unified list widget determining displaying both Events and Entities.
    Differentiates items by color.
    """

    # Signals
    item_selected = Signal(str, str)  # type ("event"|"entity"), id
    refresh_requested = Signal()
    delete_requested = Signal(str, str)  # type, id
    create_event_requested = Signal()
    create_entity_requested = Signal()

    def __init__(self, parent=None):
        """
        Initializes the UnifiedListWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(self.layout)

        # Toolbar
        top_bar = QHBoxLayout()

        # New Button with Menu
        self.btn_new = QPushButton("New...")
        self.new_menu = QMenu(self)
        self.new_menu.addAction(
            "Create Event", lambda: self.create_event_requested.emit()
        )
        self.new_menu.addAction(
            "Create Entity", lambda: self.create_entity_requested.emit()
        )
        self.btn_new.setMenu(self.new_menu)
        top_bar.addWidget(self.btn_new)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        top_bar.addWidget(self.btn_refresh)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setEnabled(False)
        top_bar.addWidget(self.btn_delete)

        self.layout.addLayout(top_bar)

        # Search Bar (Live filtering)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search names, descriptions, tags...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        self.layout.addWidget(self.search_bar)

        # Filter Row (Dynamic Types and Tags)
        filter_row = QHBoxLayout()

        # Category filter (Events/Entities)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Items", "Events Only", "Entities Only"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_combo)

        # Types filter button with checkable menu
        self.btn_types = QPushButton("Types")
        self.types_menu = QMenu(self)
        self.btn_types.setMenu(self.types_menu)
        filter_row.addWidget(self.btn_types)

        # Tags filter button with checkable menu
        self.btn_tags = QPushButton("Tags")
        self.tags_menu = QMenu(self)
        self.btn_tags.setMenu(self.tags_menu)
        filter_row.addWidget(self.btn_tags)

        # Clear Filters button
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        filter_row.addWidget(self.btn_clear_filters)

        self.layout.addLayout(filter_row)

        # List (with drag support)
        self.list_widget = DraggableListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.layout.addWidget(self.list_widget)

        # Empty State
        self.empty_label = QLabel("No Items Loaded")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(StyleHelper.get_empty_state_style())
        self.layout.addWidget(self.empty_label)
        self.empty_label.hide()

        # Data Cache
        self._events: List[Event] = []
        self._entities: List[Entity] = []
        self._search_term = ""  # Track current search term

        # Filter State
        self._available_types: set = set()  # All types found in data
        self._available_tags: set = set()  # All tags found in data
        self._active_types: set = set()  # Currently selected types for filtering
        self._active_tags: set = set()  # Currently selected tags for filtering

        # Colors - use ThemeManager for theme-aware colors
        # TODO: Migrate to fully dynamic theme updates with ThemeManager.theme_changed signal
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        self.color_event = QColor(theme["accent_secondary"])
        self.color_entity = QColor(theme["primary"])

        self._render_list()

    def set_data(self, events: List[Event], entities: List[Entity]):
        """
        Sets the data to display in the list.

        Extracts available types and tags from the data and rebuilds
        the filter menus dynamically.

        Args:
            events (List[Event]): List of events to display.
            entities (List[Entity]): List of entities to display.
        """
        self._events = events
        self._entities = entities

        # Extract available types and tags
        self._extract_types_and_tags()

        # Rebuild filter menus
        self._rebuild_filter_menus()

        self._render_list()

    def _extract_types_and_tags(self):
        """
        Scans events and entities to extract all unique types and tags.
        """
        self._available_types = set()
        self._available_tags = set()

        for entity in self._entities:
            self._available_types.add(entity.type)
            for tag in entity.tags:
                self._available_tags.add(tag)

        for event in self._events:
            self._available_types.add(event.type)
            for tag in event.tags:
                self._available_tags.add(tag)

    def _rebuild_filter_menus(self):
        """
        Rebuilds the Types and Tags filter menus based on available data.

        Preserves currently active selections where possible.
        """
        # Rebuild Types menu
        self.types_menu.clear()
        for type_name in sorted(self._available_types):
            action = QAction(type_name, self)
            action.setCheckable(True)
            action.setChecked(type_name in self._active_types)
            action.triggered.connect(
                lambda checked, t=type_name: self._on_type_toggled(t, checked)
            )
            self.types_menu.addAction(action)

        # Rebuild Tags menu
        self.tags_menu.clear()
        for tag_name in sorted(self._available_tags):
            action = QAction(tag_name, self)
            action.setCheckable(True)
            action.setChecked(tag_name in self._active_tags)
            action.triggered.connect(
                lambda checked, t=tag_name: self._on_tag_toggled(t, checked)
            )
            self.tags_menu.addAction(action)

        # Update button labels to show active count
        self._update_filter_button_labels()

    def _on_type_toggled(self, type_name: str, checked: bool):
        """
        Handles type filter toggle.

        Args:
            type_name: The type that was toggled.
            checked: Whether it's now checked.
        """
        if checked:
            self._active_types.add(type_name)
        else:
            self._active_types.discard(type_name)
        self._update_filter_button_labels()
        self._render_list()

    def _on_tag_toggled(self, tag_name: str, checked: bool):
        """
        Handles tag filter toggle.

        Args:
            tag_name: The tag that was toggled.
            checked: Whether it's now checked.
        """
        if checked:
            self._active_tags.add(tag_name)
        else:
            self._active_tags.discard(tag_name)
        self._update_filter_button_labels()
        self._render_list()

    def _update_filter_button_labels(self):
        """
        Updates filter button labels to show active filter count.
        """
        type_count = len(self._active_types)
        tag_count = len(self._active_tags)

        if type_count > 0:
            self.btn_types.setText(f"Types ({type_count})")
        else:
            self.btn_types.setText("Types")

        if tag_count > 0:
            self.btn_tags.setText(f"Tags ({tag_count})")
        else:
            self.btn_tags.setText("Tags")

    def _clear_filters(self):
        """
        Clears all active type and tag filters.
        """
        self._active_types.clear()
        self._active_tags.clear()
        self._rebuild_filter_menus()
        self._render_list()

    def _render_list(self):
        """
        Renders the list based on current filter and data.
        Preserves selection during refresh.
        """
        # Capture current selection
        current_id = None
        current_type = None
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            current_id = selected_items[0].data(Qt.UserRole)
            current_type = selected_items[0].data(Qt.UserRole + 1)

        self.list_widget.clear()

        filter_mode = self.filter_combo.currentText()
        show_events = filter_mode in ["All Items", "Events Only"]
        show_entities = filter_mode in ["All Items", "Entities Only"]

        items_to_show = []

        if show_events:
            for event in self._events:
                items_to_show.append(
                    {
                        "type": "event",
                        "obj": event,
                        "sort_key": str(event.lore_date),  # Sort events by date?
                    }
                )

        if show_entities:
            for entity in self._entities:
                items_to_show.append(
                    {"type": "entity", "obj": entity, "sort_key": entity.name}
                )

        # Sort? For now, mixed sort might be weird.
        # Let's just append blocks or simple sort.
        # Simple approach: Entities first (alphabetical),
        # then Events (chronological)?
        # Or mixed list? "Unify" usually implies mixed.
        # User request didn't specify sort. Let's stick to simple append
        # for now to be safe, or separate blocks like the current UI
        # but in one list.
        # Actually, let's keep them somewhat grouped for clarity until
        # a unified timeline sort is requested.

        has_items = False

        if show_entities and self._entities:
            # Header item? No, user said differentiated by color.
            for entity in self._entities:
                # Apply all filters (search, type, tag)
                if not self._passes_filters(entity):
                    continue
                label = f"{entity.name} ({entity.type})"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, entity.id)
                item.setData(Qt.UserRole + 1, "entity")
                item.setData(Qt.UserRole + 2, entity.name)  # For drag
                item.setForeground(QBrush(self.color_entity))
                self.list_widget.addItem(item)
                has_items = True

        if show_events and self._events:
            for event in self._events:
                # Apply all filters (search, type, tag)
                if not self._passes_filters(event):
                    continue
                label = f"[{event.lore_date}] {event.name}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, event.id)
                item.setData(Qt.UserRole + 1, "event")
                item.setData(Qt.UserRole + 2, event.name)  # For drag
                item.setForeground(QBrush(self.color_event))
                self.list_widget.addItem(item)
                has_items = True

        if has_items:
            self.list_widget.show()
            self.empty_label.hide()

            # Restore selection if possible
            if current_id and current_type:
                for index in range(self.list_widget.count()):
                    item = self.list_widget.item(index)
                    if (
                        item.data(Qt.UserRole) == current_id
                        and item.data(Qt.UserRole + 1) == current_type
                    ):
                        self.list_widget.setCurrentItem(item)
                        break
        else:
            self.list_widget.hide()
            self.empty_label.show()

    def _on_search_text_changed(self, text: str):
        """
        Handles search bar text changes for live filtering.

        Args:
            text (str): The search text.
        """
        self._search_term = text.lower().strip()
        self._render_list()

    def _matches_search(self, obj) -> bool:
        """
        Checks if an object matches the current search term.
        Performs full text search on name, type, description, tags, and attributes.

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if matches search (or no search active).
        """
        if not self._search_term:
            return True

        term = self._search_term

        # 1. Name
        if term in obj.name.lower():
            return True

        # 2. Type
        if hasattr(obj, "type") and term in obj.type.lower():
            return True

        # 3. Description
        if hasattr(obj, "description") and term in obj.description.lower():
            return True

        # 4. Tags
        if hasattr(obj, "tags"):
            for tag in obj.tags:
                if term in tag.lower():
                    return True

        # 5. String Attributes
        if hasattr(obj, "attributes"):
            for value in obj.attributes.values():
                if isinstance(value, str) and term in value.lower():
                    return True

        return False

    def _passes_filters(self, obj) -> bool:
        """
        Checks if an object passes all active filters (search, type, tag).

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if passes all filters.
        """
        # First check search term
        if not self._matches_search(obj):
            return False

        # Check type filter (if any types selected)
        if self._active_types:
            if obj.type not in self._active_types:
                return False

        # Check tag filter (if any tags selected, item must have at least one)
        if self._active_tags:
            item_tags = set(obj.tags)
            if not item_tags.intersection(self._active_tags):
                return False

        return True

    def _on_filter_changed(self, text):
        """
        Handles filter combo box changes.

        Args:
            text (str): The selected filter text.
        """
        self._render_list()

    def _on_selection_changed(self):
        """
        Handles item selection changes in the list.
        """
        items = self.list_widget.selectedItems()
        if items:
            item = items[0]
            item_id = item.data(Qt.UserRole)
            item_type = item.data(Qt.UserRole + 1)
            self.item_selected.emit(item_type, item_id)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    def _on_delete_clicked(self):
        """
        Handles delete button clicks.
        """
        items = self.list_widget.selectedItems()
        if items:
            item = items[0]
            item_id = item.data(Qt.UserRole)
            item_type = item.data(Qt.UserRole + 1)
            self.delete_requested.emit(item_type, item_id)

    def select_item(self, item_type: str, item_id: str):
        """
        Programmatically selects an item in the list.
        Auto-switches filter if item not visible.

        Args:
            item_type (str): "event" or "entity".
            item_id (str): The ID of the item to select.
        """

        def find_and_select():
            """
            Inner function to search list and select matching item.

            Searches all items in the list widget for one matching the given
            type and ID, then selects and scrolls to it.
            """
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if (
                    item.data(Qt.UserRole) == item_id
                    and item.data(Qt.UserRole + 1) == item_type
                ):
                    self.list_widget.setCurrentItem(item)
                    self.list_widget.scrollToItem(item)
                    return True
            return False

        if find_and_select():
            return

        # If not found, check if filter is blocking it
        current_filter = self.filter_combo.currentText()

        # If filter is restrictive, might need to switch
        should_switch = False
        if item_type == "event" and current_filter == "Entities Only":
            should_switch = True
        elif item_type == "entity" and current_filter == "Events Only":
            should_switch = True

        if should_switch:
            # Switch to All Items is safest
            self.filter_combo.setCurrentText("All Items")
            # Signal should trigger _render_list synchronously
            find_and_select()

    def minimumSizeHint(self):
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable project explorer.
        """
        from PySide6.QtCore import QSize

        return QSize(250, 200)  # Width for list items, height for toolbar + items

    def sizeHint(self):
        """
        Preferred size for the project explorer.

        Returns:
            QSize: Comfortable working size for browsing items.
        """
        from PySide6.QtCore import QSize

        return QSize(350, 500)  # Comfortable browsing size
