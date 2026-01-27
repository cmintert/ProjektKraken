"""Unified List Widget Module.

Provides a unified list view displaying both events and entities with filtering and
color-coded differentiation.
"""

import json
import logging
from typing import List, Optional, Union

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

from src.core.calendar import CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.gui.utils.style_helper import StyleHelper

KRAKEN_ITEM_MIME_TYPE = "application/x-kraken-item"

logger = logging.getLogger(__name__)


class DraggableListWidget(QListWidget):
    """A QListWidget that supports dragging items with custom MIME data.

    Drag data format (JSON):     {"id": "uuid", "type": "event|entity", "name": "Display
    Name"}
    """

    def __init__(self, parent: QWidget = None) -> None:
        """Initialize with drag enabled."""
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Override to provide custom MIME data for dragged items.

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
    """A unified list widget determining displaying both Events and Entities.

    Differentiates items by color.
    """

    # Signals
    item_selected = Signal(str, str)  # type ("event"|"entity"), id
    items_selected = Signal(list)  # list of (type, id) tuples for multi-selection
    refresh_requested = Signal()
    delete_requested = Signal(str, str)  # type, id
    create_event_requested = Signal()
    create_entity_requested = Signal()
    create_map_requested = Signal()
    show_filter_dialog_requested = Signal()  # Request to open filter dialog
    clear_filter_requested = Signal()  # Request to clear filters

    def __init__(self, parent: QWidget = None) -> None:
        """Initializes the UnifiedListWidget.

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
        # New Button with Menu
        from src.gui.utils.shortcut_manager import ShortcutManager

        self.btn_new = QPushButton("New...")
        self.new_menu = QMenu(self)

        # Create Event Action
        self.action_create_event = self.new_menu.addAction("Create Event")
        self.action_create_event.setShortcut(ShortcutManager.CREATE_EVENT.key_sequence)
        self.action_create_event.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.action_create_event.triggered.connect(self._create_event_trigger)
        self.addAction(
            self.action_create_event
        )  # IMPORTANT: Add to widget so it works in window

        # Create Entity Action
        self.action_create_entity = self.new_menu.addAction("Create Entity")
        self.action_create_entity.setShortcut(
            ShortcutManager.CREATE_ENTITY.key_sequence
        )
        self.action_create_entity.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.action_create_entity.triggered.connect(self._create_entity_trigger)
        self.addAction(self.action_create_entity)

        # Create Map Action
        self.action_create_map = self.new_menu.addAction("Create Map")
        self.action_create_map.setShortcut(ShortcutManager.CREATE_MAP.key_sequence)
        self.action_create_map.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.action_create_map.triggered.connect(self._create_map_trigger)
        self.addAction(self.action_create_map)

        self.btn_new.setMenu(self.new_menu)

        # Set Tooltip
        tooltip_text = (
            f"Create New Item\n"
            f"• {ShortcutManager.CREATE_EVENT.tooltip}\n"
            f"• {ShortcutManager.CREATE_ENTITY.tooltip}\n"
            f"• {ShortcutManager.CREATE_MAP.tooltip}"
        )
        self.btn_new.setToolTip(tooltip_text)

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

        # Sort dropdown
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Created", "Lore Date"])
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        filter_row.addWidget(self.sort_combo)

        # Sort direction toggle
        self.btn_sort_dir = QPushButton("↑")
        self.btn_sort_dir.setFixedWidth(30)
        self.btn_sort_dir.setToolTip("Toggle sort direction")
        self.btn_sort_dir.clicked.connect(self._toggle_sort_direction)
        filter_row.addWidget(self.btn_sort_dir)

        main_layout.addLayout(filter_row)

        # List (with drag support)
        self.list_widget = DraggableListWidget()
        self.list_widget.setStyleSheet(StyleHelper.get_checkbox_style())
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemChanged.connect(self._on_item_checkbox_changed)
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
        self._advanced_filter_config: dict = {}  # Advanced filter settings (tags)
        self._sort_ascending = True  # Sort direction
        self._calendar_converter: Optional[CalendarConverter] = None

        # Filter State
        # self._active_types: set = set()  # Removed: Backend handled
        # self._active_tags: set = set()   # Removed: Backend handled

        # Colors - use ThemeManager for theme-aware colors
        # TODO: Migrate to fully dynamic theme updates with
        # ThemeManager.theme_changed signal
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        self.color_event = QColor(theme.get("accent_secondary", "#0078D4"))
        self.color_entity = QColor(theme.get("primary", "#FF9900"))

        ThemeManager().theme_changed.connect(self._on_theme_changed)

        self._render_list()

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme change."""
        self.color_event = QColor(theme.get("accent_secondary", "#0078D4"))
        self.color_entity = QColor(theme.get("primary", "#FF9900"))
        # Re-apply checkbox style on theme change
        self.list_widget.setStyleSheet(StyleHelper.get_checkbox_style())
        self._render_list()

    def set_data(self, events: List[Event], entities: List[Entity]) -> None:
        """Sets the data to display in the list.

        Args:
            events (List[Event]): List of events to display.
            entities (List[Entity]): List of entities to display.

        """
        self._events = events
        self._entities = entities

        self._render_list()

    def set_calendar_converter(self, converter: Optional[CalendarConverter]) -> None:
        """Sets the calendar converter for formatting lore dates.

        Args:
            converter: CalendarConverter instance or None.

        """
        self._calendar_converter = converter
        self._render_list()

    def _format_compact_date(self, lore_date: float) -> str:
        """Formats a lore date as dd.mm.yyyy - hh:mm.

        Args:
            lore_date: The float lore date value.

        Returns:
            str: Formatted date string in dd.mm.yyyy - hh:mm format.

        """
        if not self._calendar_converter:
            return str(lore_date)

        cal_date = self._calendar_converter.from_float(lore_date)

        # Format as dd.mm.yyyy
        day_str = str(cal_date.day).zfill(2)
        month_str = str(cal_date.month).zfill(2)
        year_str = str(cal_date.year)
        date_part = f"{day_str}.{month_str}.{year_str}"

        # Format time from time_fraction (0.0 = midnight, 0.5 = noon)
        if cal_date.time_fraction > 0:
            total_minutes = int(cal_date.time_fraction * 24 * 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            time_part = f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}"
            return f"{date_part} - {time_part}"

        return date_part

    @Slot()
    @Slot()
    def _request_clear_filters(self) -> None:
        """Requests clearing backend filters."""
        self.clear_filter_requested.emit()

    def set_filter_active(self, active: bool) -> None:
        """Updates the filter button appearance to indicate active filter.

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

    def set_advanced_filter(self, config: dict) -> None:
        """Sets the advanced filter configuration (tags) and re-renders the list.

        Args:
            config: Filter configuration dict with 'include', 'include_mode', 'exclude',
                    'exclude_mode' keys.

        """
        self._advanced_filter_config = config or {}
        has_filter = bool(config.get("include") or config.get("exclude"))
        self.set_filter_active(has_filter)
        self._render_list()

    def get_advanced_filter_config(self) -> dict:
        """Returns the current advanced filter configuration.

        Returns:
            dict: The current filter configuration.

        """
        return self._advanced_filter_config

    # _clear_filters removed as it's replaced by backend refresh

    def _render_list(self) -> None:
        """Renders the list based on current filter and data.

        Preserves selection during refresh.
        """
        # Capture current selection
        current_id = None
        current_type = None
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            current_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            current_type = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)

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

        # Collect all items that pass filters
        filtered_items = []

        if show_entities:
            for entity in self._entities:
                if self._passes_filters(entity):
                    filtered_items.append(("entity", entity))

        if show_events:
            for event in self._events:
                if self._passes_filters(event):
                    filtered_items.append(("event", event))

        # Sort items based on current sort settings
        sort_field = self.sort_combo.currentText()
        reverse = not self._sort_ascending

        def get_sort_key(
            item_tuple: tuple[str, Union[Event, Entity]],
        ) -> Union[str, float]:
            item_type, obj = item_tuple
            if sort_field == "Name":
                return obj.name.lower()
            elif sort_field == "Created":
                return getattr(obj, "created_at", 0) or 0
            elif sort_field == "Lore Date":
                if item_type == "event":
                    return getattr(obj, "lore_date", float("inf")) or float("inf")
                else:
                    # Entities go to end when sorting by lore date
                    return float("inf") if not reverse else float("-inf")
            return obj.name.lower()

        filtered_items.sort(key=get_sort_key, reverse=reverse)

        # Render sorted items
        for item_type, obj in filtered_items:
            if item_type == "entity":
                label = f"{obj.name} ({obj.type})"
                color = self.color_entity
            else:
                # Format lore date in compact dd.mm.yyyy - hh:mm format
                if self._calendar_converter and obj.lore_date is not None:
                    date_str = self._format_compact_date(obj.lore_date)
                else:
                    date_str = str(obj.lore_date)
                label = f"[{date_str}] {obj.name}"
                color = self.color_event

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, obj.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, item_type)
            item.setData(Qt.ItemDataRole.UserRole + 2, obj.name)
            item.setForeground(QBrush(color))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
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
                        item.data(Qt.ItemDataRole.UserRole) == current_id
                        and item.data(Qt.ItemDataRole.UserRole + 1) == current_type
                    ):
                        # Block signals to prevent re-triggering selection logic
                        self.list_widget.blockSignals(True)
                        self.list_widget.setCurrentItem(item)
                        self.list_widget.blockSignals(False)

                        break
        else:
            self.list_widget.hide()
            self.empty_label.show()

    @Slot(str)
    @Slot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """Handles search bar text changes for live filtering.

        Args:
            text (str): The search text.

        """
        self._search_term = text.lower().strip()
        self._render_list()

    def _matches_search(self, obj: Union[Event, Entity]) -> bool:
        """Checks if an object matches the current search term. Delegates to shared
        SearchUtils.

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if matches search (or no search active).

        """
        from src.core.search_utils import SearchUtils

        return SearchUtils.matches_search(obj, self._search_term)

    def _passes_advanced_filters(self, obj: Union[Event, Entity]) -> bool:
        """Checks if an object passes the advanced tag filters.

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if passes all advanced filters.

        """
        if not self._advanced_filter_config:
            return True

        include_tags = self._advanced_filter_config.get("include", [])
        include_mode = self._advanced_filter_config.get("include_mode", "any")
        exclude_tags = self._advanced_filter_config.get("exclude", [])
        exclude_mode = self._advanced_filter_config.get("exclude_mode", "any")

        if not include_tags and not exclude_tags:
            return True

        item_tags = set(getattr(obj, "tags", []))

        # Exclude check
        if exclude_tags:
            if exclude_mode == "all":
                # Exclude if ALL excluded tags are present
                if all(tag in item_tags for tag in exclude_tags):
                    return False
            else:
                # Default "any": Exclude if ANY excluded tag is present
                if any(tag in item_tags for tag in exclude_tags):
                    return False

        # Include check
        if include_tags:
            if include_mode == "all":
                if not all(tag in item_tags for tag in include_tags):
                    return False
            else:
                # Default "any"
                if not any(tag in item_tags for tag in include_tags):
                    return False

        return True

    def _passes_filters(self, obj: Union[Event, Entity]) -> bool:
        """Checks if an object passes all active filters (search + advanced tags).

        Args:
            obj: Event or Entity object.

        Returns:
            bool: True if passes all filters.

        """
        # Check advanced tag filters
        if not self._passes_advanced_filters(obj):
            return False

        # Check search term
        if not self._matches_search(obj):
            return False

        return True

    @Slot(str)
    @Slot(str)
    def _on_filter_changed(self, text: str) -> None:
        """Handles filter combo box changes.

        Args:
            text (str): The selected filter text.

        """
        self._render_list()

    @Slot(str)
    def _on_sort_changed(self, text: str) -> None:
        """Handles sort combo box changes.

        Args:
            text (str): The selected sort field.

        """
        self._render_list()

    @Slot()
    def _toggle_sort_direction(self) -> None:
        """Toggles between ascending and descending sort order."""
        self._sort_ascending = not self._sort_ascending
        self.btn_sort_dir.setText("↑" if self._sort_ascending else "↓")
        self._render_list()

    @Slot(QListWidgetItem)
    def _on_item_checkbox_changed(self, item: QListWidgetItem) -> None:
        """Sync selection when checkbox is clicked.

        Args:
            item: The item whose checkbox changed.

        """
        # Block signals to prevent recursion
        self.list_widget.blockSignals(True)
        is_checked = item.checkState() == Qt.CheckState.Checked
        item.setSelected(is_checked)
        self.list_widget.blockSignals(False)

        # Trigger selection update manually
        self._on_selection_changed()

    @Slot()
    def _on_selection_changed(self) -> None:
        """Handles item selection changes in the list."""
        selected_items = self.list_widget.selectedItems()

        # Sync checkboxes with selection state
        self.list_widget.blockSignals(True)
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            is_selected = item.isSelected()
            item.setCheckState(
                Qt.CheckState.Checked if is_selected else Qt.CheckState.Unchecked
            )
        self.list_widget.blockSignals(False)

        if selected_items:
            # Collect all selected items for multi-selection signal
            selected_data = []
            for item in selected_items:
                item_id = item.data(Qt.ItemDataRole.UserRole)
                item_type = item.data(Qt.ItemDataRole.UserRole + 1)
                if item_id and item_type:
                    selected_data.append((item_type, item_id))

            # Emit multi-selection signal
            self.items_selected.emit(selected_data)

            # Backward compatibility: emit single selection for first item
            first_item = selected_items[0]
            item_id = first_item.data(Qt.ItemDataRole.UserRole)
            item_type = first_item.data(Qt.ItemDataRole.UserRole + 1)
            self.item_selected.emit(item_type, item_id)

            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    @Slot()
    def _on_delete_clicked(self) -> None:
        """Handles delete button clicks for single or multiple items."""
        from PySide6.QtWidgets import QMessageBox

        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        # Collect all selected items
        items_to_delete = []
        for item in selected_items:
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            item_name = item.text().split(" (")[0].split("] ")[-1]  # Extract name
            if item_id and item_type:
                items_to_delete.append((item_type, item_id, item_name))

        if not items_to_delete:
            return

        # Confirmation dialog
        count = len(items_to_delete)
        if count == 1:
            msg = f"Delete '{items_to_delete[0][2]}'?\n\nThis action cannot be undone."
        else:
            msg = f"Delete {count} items?\n\nThis action cannot be undone."

        reply = QMessageBox.warning(
            self,
            "Confirm Delete",
            msg,
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Emit delete signal for each item
            for item_type, item_id, _ in items_to_delete:
                self.delete_requested.emit(item_type, item_id)

    def select_item(self, item_type: str, item_id: str) -> None:
        """Programmatically selects an item in the list. Auto-switches filter if item
        not visible.

        Args:
            item_type (str): "event" or "entity".
            item_id (str): The ID of the item to select.

        """

        def find_and_select() -> bool:
            """Inner function to search list and select matching item.

            Searches all items in the list widget for one matching the given type and
            ID, then selects and scrolls to it.
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
        else:
            # If we didn't switch filters (or even if we did and it's still not
            # there due to another reason),
            # validation failed or item is truly gone/filtered by search.
            # We MUST clear selection to prevent "stale" selection from persisting.
            self.list_widget.clearSelection()

    def minimumSizeHint(self) -> QSize:
        """Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable project explorer.

        """
        return QSize(250, 200)  # Width for list items, height for toolbar + items

    def sizeHint(self) -> QSize:
        """Preferred size for the project explorer.

        Returns:
            QSize: Comfortable working size for browsing items.

        """
        return QSize(350, 500)  # Comfortable browsing size

    def _should_trigger_shortcut(self) -> bool:
        """Checks if a shortcut should overlap with text input.

        Returns:
            bool: True if safe to trigger, False if a text widget is focused.
        """
        from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit

        focus_widget = QApplication.focusWidget()
        if focus_widget and isinstance(
            focus_widget, (QTextEdit, QPlainTextEdit, QLineEdit)
        ):
            return False
        return True

    def _create_event_trigger(self) -> None:
        if self._should_trigger_shortcut():
            self.create_event_requested.emit()

    def _create_entity_trigger(self) -> None:
        if self._should_trigger_shortcut():
            self.create_entity_requested.emit()

    def _create_map_trigger(self) -> None:
        if self._should_trigger_shortcut():
            self.create_map_requested.emit()
