"""
Unified List Widget Module.

Provides a unified list view displaying both events and entities with
filtering and color-coded differentiation.
"""

import json
import logging
from typing import List, Union

from PySide6.QtCore import QMimeData, QSize, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QDrag
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

KRAKEN_ITEM_MIME_TYPE = "application/x-kraken-item"

logger = logging.getLogger(__name__)


class DraggableListWidget(QListWidget):
    """
    A QListWidget that supports dragging items with custom MIME data.

    Drag data format (JSON):
        {"id": "uuid", "type": "event|entity", "name": "Display Name"}
    """

    def __init__(self, parent: QWidget = None) -> None:
        """Initialize with drag enabled."""
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """
        Override to provide custom MIME data for dragged items.

        Args:
            supportedActions: The drag actions supported.
        """
        item = self.currentItem()
        if not item:
            return

        # Extract item data (stored via setData in _render_list)
        item_id = item.data(Qt.ItemDataRole.UserRole)
        item_type = item.data(Qt.ItemDataRole.UserRole + 1)
        item_name = item.data(Qt.ItemDataRole.UserRole + 2)  # We'll add this

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
    show_filter_dialog_requested = Signal()  # Request to open filter dialog
    clear_filter_requested = Signal()  # Request to clear filters

    def __init__(self, parent: QWidget = None) -> None:
        """
        Initializes the UnifiedListWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(main_layout)

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

        main_layout.addLayout(top_bar)

        # Search Bar (Live filtering)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search names, descriptions, tags...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        main_layout.addWidget(self.search_bar)

        # Filter Row (Dynamic Types and Tags)
        filter_row = QHBoxLayout()

        # Category filter (Events/Entities)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Items", "Events Only", "Entities Only"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_combo)

        # Advanced Filter Button
        self.btn_filter = QPushButton("Filter...")
        self.btn_filter.clicked.connect(self.show_filter_dialog_requested.emit)
        filter_row.addWidget(self.btn_filter)

        # Clear Filters button - keeps concept but might need to signal to clear backend
        # filter. For now, we'll keep it to clear the backend filter via signal
        # if needed, or just reload all. Actually, "Clear Filters" usually means
        # "Show All".
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear_filters.clicked.connect(self._request_clear_filters)
        filter_row.addWidget(self.btn_clear_filters)

        main_layout.addLayout(filter_row)

        # List (with drag support)
        self.list_widget = DraggableListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        main_layout.addWidget(self.list_widget)

        # Empty State
        self.empty_label = QLabel("No Items Loaded")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(StyleHelper.get_empty_state_style())
        main_layout.addWidget(self.empty_label)
        self.empty_label.hide()

        # Data Cache
        self._events: List[Event] = []
        self._entities: List[Entity] = []
        self._search_term = ""  # Track current search term

        # Filter State
        # self._active_types: set = set()  # Removed: Backend handled
        # self._active_tags: set = set()   # Removed: Backend handled

        # Colors - use ThemeManager for theme-aware colors
        # TODO: Migrate to fully dynamic theme updates with
        # ThemeManager.theme_changed signal
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        self.color_event = QColor(theme["accent_secondary"])
        self.color_entity = QColor(theme["primary"])

        self._render_list()

    def set_data(self, events: List[Event], entities: List[Entity]) -> None:
        """
        Sets the data to display in the list.

        Args:
            events (List[Event]): List of events to display.
            entities (List[Entity]): List of entities to display.
        """
        logger.debug(
            f"[UnifiedList] set_data called with {len(events)} events, "
            f"{len(entities)} entities"
        )
        self._events = events
        self._entities = entities

        self._render_list()

    @Slot()
    @Slot()
    def _request_clear_filters(self) -> None:
        """
        Requests clearing backend filters.
        """
        self.clear_filter_requested.emit()

    def set_filter_active(self, active: bool) -> None:
        """
        Updates the filter button appearance to indicate active filter.

        Args:
            active: True if a filter is currently applied.
        """
        if active:
            # Use theme-aware styling or a distinct color
            # For now, a simple border/background tint
            self.btn_filter.setStyleSheet(
                "background-color: #2c3e50; border: 2px solid #3498db; "
                "font-weight: bold;"
            )
            self.btn_filter.setText("Filter (Active)")
        else:
            self.btn_filter.setStyleSheet("")
            self.btn_filter.setText("Filter...")

    # _clear_filters removed as it's replaced by backend refresh

    def _render_list(self) -> None:
        """
        Renders the list based on current filter and data.
        Preserves selection during refresh.
        """
        # Capture current selection
        current_id = None
        current_type = None
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            current_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            current_type = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)
            logger.debug(
                f"[UnifiedList] Capturing current selection: "
                f"{current_type}/{current_id}"
            )

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
                item.setData(Qt.ItemDataRole.UserRole, entity.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, "entity")
                item.setData(Qt.ItemDataRole.UserRole + 2, entity.name)  # For drag
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
                item.setData(Qt.ItemDataRole.UserRole, event.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, "event")
                item.setData(Qt.ItemDataRole.UserRole + 2, event.name)  # For drag
                item.setForeground(QBrush(self.color_event))
                self.list_widget.addItem(item)
                has_items = True

        if has_items:
            self.list_widget.show()
            self.empty_label.hide()

            # Restore selection if possible
            if current_id and current_type:
                found = False
                for index in range(self.list_widget.count()):
                    item = self.list_widget.item(index)
                    if (
                        item.data(Qt.ItemDataRole.UserRole) == current_id
                        and item.data(Qt.ItemDataRole.UserRole + 1) == current_type
                    ):
                        # Block signals to prevent re-triggering selection logic
                        self.list_widget.blockSignals(True)
                        self.list_widget.setCurrentItem(item)
                        self.list_widget.blockSignals(False)

                        logger.debug(
                            f"[UnifiedList] Restored selection: "
                            f"{current_type}/{current_id}"
                        )
                        found = True
                        break
                if not found:
                    logger.debug(
                        f"[UnifiedList] Could not restore selection: "
                        f"{current_type}/{current_id}"
                    )
        else:
            self.list_widget.hide()
            self.empty_label.show()

    @Slot(str)
    @Slot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """
        Handles search bar text changes for live filtering.

        Args:
            text (str): The search text.
        """
        self._search_term = text.lower().strip()
        self._render_list()

    def _matches_search(self, obj: Union[Event, Entity]) -> bool:
        """
        Checks if an object matches the current search term.
        Delegates to shared SearchUtils.

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if matches search (or no search active).
        """
        from src.core.search_utils import SearchUtils

        return SearchUtils.matches_search(obj, self._search_term)

    def _passes_filters(self, obj: Union[Event, Entity]) -> bool:
        """
        Checks if an object passes all active filters (search).

        Note: Backend filtering (tags/types) is already applied to
        self._events/_entities. This only checks local text search.

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if passes all filters.
        """
        # Only check search term
        if not self._matches_search(obj):
            return False

        return True

    @Slot(str)
    @Slot(str)
    def _on_filter_changed(self, text: str) -> None:
        """
        Handles filter combo box changes.

        Args:
            text (str): The selected filter text.
        """
        self._render_list()

    @Slot()
    @Slot()
    def _on_selection_changed(self) -> None:
        """
        Handles item selection changes in the list.
        """
        items = self.list_widget.selectedItems()
        if items:
            item = items[0]
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            logger.debug(f"[UnifiedList] Selection changed to: {item_type}/{item_id}")
            self.item_selected.emit(item_type, item_id)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    @Slot()
    @Slot()
    def _on_delete_clicked(self) -> None:
        """
        Handles delete button clicks.
        """
        items = self.list_widget.selectedItems()
        if items:
            item = items[0]
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            self.delete_requested.emit(item_type, item_id)

    def select_item(self, item_type: str, item_id: str) -> None:
        """
        Programmatically selects an item in the list.
        Auto-switches filter if item not visible.

        Args:
            item_type (str): "event" or "entity".
            item_id (str): The ID of the item to select.
        """

        def find_and_select() -> bool:
            """
            Inner function to search list and select matching item.

            Searches all items in the list widget for one matching the given
            type and ID, then selects and scrolls to it.
            """
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if (
                    item.data(Qt.ItemDataRole.UserRole) == item_id
                    and item.data(Qt.ItemDataRole.UserRole + 1) == item_type
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

    def minimumSizeHint(self) -> QSize:
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable project explorer.
        """
        return QSize(250, 200)  # Width for list items, height for toolbar + items

    def sizeHint(self) -> QSize:
        """
        Preferred size for the project explorer.

        Returns:
            QSize: Comfortable working size for browsing items.
        """
        return QSize(350, 500)  # Comfortable browsing size
