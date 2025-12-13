"""
Unified List Widget Module.

Provides a unified list view displaying both events and entities with
filtering and color-coded differentiation.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from typing import List
from src.core.events import Event
from src.core.entities import Entity


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
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(16, 16, 16, 16)

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

        # Filter (Optional, good for unified lists)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Items", "Events Only", "Entities Only"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self.layout.addWidget(self.filter_combo)

        # List
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.layout.addWidget(self.list_widget)

        # Empty State
        self.empty_label = QLabel("No Items Loaded")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #757575; font-size: 14pt;")
        self.layout.addWidget(self.empty_label)
        self.empty_label.hide()

        # Data Cache
        self._events: List[Event] = []
        self._entities: List[Entity] = []

        # Colors (Hardcoded fallback, ideally from ThemeManager)
        # dark_mode values from themes.json
        self.color_event = QColor("#0078D4")  # accent_secondary
        self.color_entity = QColor("#FF9900")  # primary

        self._render_list()

    def set_data(self, events: List[Event], entities: List[Entity]):
        """
        Sets the data to display in the list.

        Args:
            events (List[Event]): List of events to display.
            entities (List[Entity]): List of entities to display.
        """
        self._events = events
        self._entities = entities
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
                label = f"{entity.name} ({entity.type})"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, entity.id)
                item.setData(Qt.UserRole + 1, "entity")
                item.setForeground(QBrush(self.color_entity))
                self.list_widget.addItem(item)
                has_items = True

        if show_events and self._events:
            for event in self._events:
                label = f"[{event.lore_date}] {event.name}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, event.id)
                item.setData(Qt.UserRole + 1, "event")
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
