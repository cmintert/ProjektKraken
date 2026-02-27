"""Unified List Widget Module.

Provides a unified list view displaying both events and entities with filtering and
color-coded differentiation.
"""

import json
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QMimeData, QSize, Qt, Signal, Slot
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.gui.models.explorer_filter_proxy import ExplorerFilterProxyModel
from src.gui.models.explorer_model import ExplorerModel
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.standard_buttons import DestructiveButton

KRAKEN_ITEM_MIME_TYPE = "application/x-kraken-item"


class DraggableListView(QListView):
    """A QListView that supports dragging items with custom MIME data.

    Drag data format (JSON): {"id": "uuid", "type": "event|entity", "name": "Display
    Name"}
    """

    def __init__(self, parent: QWidget = None) -> None:
        """Initialize with drag enabled."""
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QListView.DragOnly)
        self._drag_pill = None  # Will be created during drag
        self.setMouseTracking(True)  # Enable mouse tracking for hover effects

    drag_started = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Override to deselect items when clicking into free space.

        Args:
            event: The mouse event.

        """
        from PySide6.QtCore import QModelIndex

        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())

        super().mousePressEvent(event)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Override to provide custom MIME data for dragged items.

        Also shows a drag pill widget that follows the cursor.

        Args:
            supportedActions: The drag actions supported.

        """
        index = self.currentIndex()
        if not index.isValid():
            return

        self.drag_started.emit()

        # Get data from model using custom roles
        model = self.model()
        if not model:
            return

        # Need to map to source model if using proxy
        source_index = index
        if hasattr(model, "mapToSource"):
            source_index = model.mapToSource(index)
            source_model = model.sourceModel()
        else:
            source_model = model

        # Extract item data using custom roles
        item_id = source_model.data(source_index, ExplorerModel.ItemIdRole)
        item_type = source_model.data(source_index, ExplorerModel.ItemTypeRole)
        item_name = source_model.data(source_index, ExplorerModel.ItemNameRole)

        if not item_id or not item_type:
            return

        # Build MIME data
        data = {"id": item_id, "type": item_type, "name": item_name}

        mime_data = QMimeData()
        mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(data).encode("utf-8"))

        # Also set plain text for debugging/compatibility
        mime_data.setText(f"{item_type}:{item_id}")

        # Create drag pill widget to follow cursor
        from src.gui.widgets.drag_pill import DragPill

        # Create the pill but don't show it as a window
        pill = DragPill(item_name=item_name, item_type=item_type)
        # Force layout update to get correct size
        pill.adjustSize()

        # Render to pixmap
        pixmap = pill.grab()

        # Create and execute drag
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.setPixmap(pixmap)

        # Set hotspot to the pill's defined offset (default 10, 10)
        # This aligns the cursor with the defined hotspot on the pill
        drag.setHotSpot(pill.cursor_offset)

        drag.exec(Qt.CopyAction)

        # Clean up
        pill.deleteLater()

    def _on_drag_finished(self) -> None:
        """Clean up drag pill when drag finishes."""
        if self._drag_pill:
            self._drag_pill.hide()
            self._drag_pill.deleteLater()
            self._drag_pill = None


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
    status_message_requested = Signal(str, int)  # message, timeout_ms (Toast-like)
    drag_started = Signal()
    export_obsidian_requested = Signal(str, str)  # type, id

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
        self.btn_refresh.setToolTip("Refresh the list from the database")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        top_bar.addWidget(self.btn_refresh)

        self.btn_delete = DestructiveButton("Delete")
        self.btn_delete.setToolTip("Delete the selected item(s)")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_delete.setEnabled(False)
        top_bar.addWidget(self.btn_delete)

        main_layout.addLayout(top_bar)

        # Search Bar (Live filtering)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search names, descriptions, tags...")
        self.search_bar.setToolTip("Type to instantly filter items by text")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        main_layout.addWidget(self.search_bar)

        # Filter Row (Dynamic Types and Tags)
        filter_row = QHBoxLayout()

        # Category filter (Events/Entities)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Items", "Events Only", "Entities Only"])
        self.filter_combo.setToolTip("Filter items by base category")
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_combo)

        # Advanced Filter Button
        self.btn_filter = QPushButton("Filter...")
        self.btn_filter.setToolTip("Open advanced filtering options (tags, types)")
        self.btn_filter.clicked.connect(self.show_filter_dialog_requested.emit)
        filter_row.addWidget(self.btn_filter)

        # Clear Filters button - keeps concept but might need to signal to clear backend
        # filter. For now, we'll keep it to clear the backend filter via signal
        # if needed, or just reload all. Actually, "Clear Filters" usually means
        # "Show All".
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear_filters.setToolTip("Clear all active filters and search terms")
        self.btn_clear_filters.clicked.connect(self._request_clear_filters)
        filter_row.addWidget(self.btn_clear_filters)

        # Sort dropdown
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Created", "Lore Date", "Type"])
        self.sort_combo.setToolTip("Select property to sort items by")
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        filter_row.addWidget(self.sort_combo)

        # Sort direction toggle
        from src.core.theme_manager import ThemeManager
        from src.gui.utils.icon_loader import load_icon

        self.btn_sort_dir = QToolButton()
        self.btn_sort_dir.setToolTip("Toggle sort direction")
        theme = ThemeManager().get_theme()
        text_dim = theme.get("text_dim", "#808080")
        self.btn_sort_dir.setIcon(
            load_icon("default_assets/icons/ui_icons/arrow_up.svg", color=text_dim)
        )
        self.btn_sort_dir.setStyleSheet(StyleHelper.get_flat_tool_button_style())
        self.btn_sort_dir.clicked.connect(self._toggle_sort_direction)
        filter_row.addWidget(self.btn_sort_dir)

        # Hashed Colors toggle
        self.btn_hashed_colors = QToolButton()
        self.btn_hashed_colors.setToolTip("Toggle unique hashed colors for items")
        self.btn_hashed_colors.setCheckable(True)
        self.btn_hashed_colors.setStyleSheet(StyleHelper.get_flat_tool_button_style())
        self.btn_hashed_colors.setIcon(
            load_icon("default_assets/icons/ui_icons/palette.svg", color=text_dim)
        )
        self.btn_hashed_colors.clicked.connect(self._on_hashed_colors_toggled)
        filter_row.addWidget(self.btn_hashed_colors)

        main_layout.addLayout(filter_row)

        # Create model and proxy for virtualization
        self._model = ExplorerModel(self)
        self._proxy_model = ExplorerFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)

        # List (with drag support and virtualization)
        self.list_widget = DraggableListView()
        self.list_widget.setModel(self._proxy_model)
        self.list_widget.setStyleSheet(StyleHelper.get_checkbox_style())
        # Use SingleSelection to prevent box-select interfering with drag operations
        self.list_widget.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.list_widget.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.list_widget.drag_started.connect(self.drag_started)

        # Enable context menu on the list
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        main_layout.addWidget(self.list_widget)

        # Empty State
        self.empty_state = EmptyStateWidget(
            title="No Items Found",
            description=(
                "Your world is empty. Create events, entities, or maps to"
                " start building."
            ),
            parent=self,
        )
        self.empty_state.add_action(
            "Create Event", self.create_event_requested.emit, primary=True
        )
        self.empty_state.add_action(
            "Create Entity", self.create_entity_requested.emit, primary=True
        )
        main_layout.addWidget(self.empty_state)

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

        # Theme connection for checkbox style updates
        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)

        self._model.dataChanged.connect(self._update_delete_button_state)
        self._render_list()

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme change."""
        # Re-apply checkbox style on theme change
        self.list_widget.setStyleSheet(StyleHelper.get_checkbox_style())
        # Model handles color updates automatically

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
        self._model.set_calendar_converter(converter)
        # Model triggers dataChanged automatically

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
        self._proxy_model.set_advanced_filter(config)

    def get_advanced_filter_config(self) -> Dict[str, Any]:
        """Returns the current advanced filter configuration.

        Returns:
            Dict[str, Any]: Filter configuration dictionary containing:
                - 'include' (List[str], optional): Tags to include
                - 'exclude' (List[str], optional): Tags to exclude
                - Additional filter criteria as needed

        """
        return self._advanced_filter_config

    # _clear_filters removed as it's replaced by backend refresh

    def _render_list(self) -> None:
        """Renders the list based on current filter and data.

        Preserves selection during refresh.
        """
        # Capture current selection
        current_index = self.list_widget.currentIndex()
        current_id = None
        current_type = None

        if current_index.isValid():
            # Map through proxy to source model
            source_index = self._proxy_model.mapToSource(current_index)
            current_id = self._model.data(source_index, ExplorerModel.ItemIdRole)
            current_type = self._model.data(source_index, ExplorerModel.ItemTypeRole)

        # Update filter mode in proxy
        filter_mode = self.filter_combo.currentText()
        self._proxy_model.set_filter_mode(filter_mode)

        # Collect all items that pass filters (filter mode handled by proxy)
        show_events = filter_mode in ["All Items", "Events Only"]
        show_entities = filter_mode in ["All Items", "Entities Only"]

        items_to_display = []
        if show_entities:
            items_to_display.extend([("entity", e) for e in self._entities])
        if show_events:
            items_to_display.extend([("event", e) for e in self._events])

        # Sort items based on current sort settings
        sort_field = self.sort_combo.currentText()
        reverse = not self._sort_ascending

        def get_sort_key(
            item_tuple: tuple[str, Union[Event, Entity]],
        ) -> Union[str, float]:
            """Get sort key for an item based on current sort field.

            Args:
                item_tuple: Tuple of (item_type, item_object).

            Returns:
                Sort key value (string or float).
            """
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
            elif sort_field == "Type":
                t = getattr(obj, "type", "")
                return t.lower() if isinstance(t, str) else ""
            return obj.name.lower()

        items_to_display.sort(key=get_sort_key, reverse=reverse)

        # Update model with sorted items
        self._model.set_items(items_to_display)

        # Show/hide empty state
        has_items = self._proxy_model.rowCount() > 0
        if has_items:
            self.list_widget.show()
            self.empty_state.hide()

            # Restore selection if possible
            if current_id and current_type:
                restore_index = self._model.find_item_index(current_type, current_id)
                if restore_index:
                    # Map to proxy index
                    proxy_index = self._proxy_model.mapFromSource(restore_index)
                    if proxy_index.isValid():
                        self.list_widget.setCurrentIndex(proxy_index)
        else:
            self.list_widget.hide()
            self.empty_state.show()

    @Slot(str)
    @Slot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """Handles search bar text changes for live filtering.

        Args:
            text (str): The search text.

        """
        self._search_term = text.lower().strip()
        self._proxy_model.set_search_term(self._search_term)

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

        from src.core.theme_manager import ThemeManager
        from src.gui.utils.icon_loader import load_icon

        theme = ThemeManager().get_theme()
        text_dim = theme.get("text_dim", "#808080")

        icon_path = (
            "default_assets/icons/ui_icons/arrow_up.svg"
            if self._sort_ascending
            else "default_assets/icons/ui_icons/arrow_down.svg"
        )
        self.btn_sort_dir.setIcon(load_icon(icon_path, color=text_dim))

        self._render_list()

    @Slot(bool)
    def _on_hashed_colors_toggled(self, checked: bool) -> None:
        """Handles toggling the hashed colors mode.

        Args:
            checked: The toggle state of the button.
        """
        self._model.set_use_hashed_colors(checked)

    @Slot()
    def _show_context_menu(self, position: Any) -> None:
        """Show context menu for the selected list item.

        Args:
            position: The position where the context menu was requested.

        """
        index = self.list_widget.indexAt(position)
        if not index.isValid():
            return

        source_index = self._proxy_model.mapToSource(index)
        item_id = self._model.data(source_index, ExplorerModel.ItemIdRole)
        item_type = self._model.data(source_index, ExplorerModel.ItemTypeRole)

        if not item_id or not item_type:
            return

        menu = QMenu(self)
        export_action = menu.addAction("Export to Obsidian (.md)...")
        action = menu.exec(self.list_widget.viewport().mapToGlobal(position))

        if action == export_action:
            self.export_obsidian_requested.emit(item_type, item_id)

    @Slot()
    def _on_selection_changed(self) -> None:
        """Handles item selection changes in the list."""
        selection_model = self.list_widget.selectionModel()
        if not selection_model:
            return

        selected_indexes = selection_model.selectedIndexes()

        if selected_indexes:
            # Collect all selected items for multi-selection signal
            selected_data = []
            for index in selected_indexes:
                # Map through proxy to source
                source_index = self._proxy_model.mapToSource(index)
                item_id = self._model.data(source_index, ExplorerModel.ItemIdRole)
                item_type = self._model.data(source_index, ExplorerModel.ItemTypeRole)
                if item_id and item_type:
                    selected_data.append((item_type, item_id))

            # Emit multi-selection signal
            self.items_selected.emit(selected_data)

            # Backward compatibility: emit single selection for first item
            if selected_data:
                first_type, first_id = selected_data[0]
                self.item_selected.emit(first_type, first_id)

        self._update_delete_button_state()

    def _update_delete_button_state(self) -> None:
        """Update enable state of delete button based on selection or checks."""
        selection_model = self.list_widget.selectionModel()
        has_selection = selection_model and selection_model.hasSelection()
        has_checks = bool(self._model.get_checked_items())
        self.btn_delete.setEnabled(has_selection or has_checks)

    @Slot()
    def _on_delete_clicked(self) -> None:
        """Handles delete button clicks for single or multiple items."""

        selection_model = self.list_widget.selectionModel()
        if not selection_model:
            return

        # Try checked items first for multi-select
        checked_items = self._model.get_checked_items()
        items_to_delete = []

        if checked_items:
            for item_type, item_id in checked_items:
                # Find in cache to get name
                name = "Unknown"
                if item_type == "event":
                    obj = next((e for e in self._events if e.id == item_id), None)
                else:
                    obj = next((e for e in self._entities if e.id == item_id), None)
                if obj:
                    name = obj.name
                items_to_delete.append((item_type, item_id, name))
        else:
            # Fallback to selection
            selected_indexes = selection_model.selectedIndexes()
            for index in selected_indexes:
                # Map through proxy to source
                source_index = self._proxy_model.mapToSource(index)
                item_id = self._model.data(source_index, ExplorerModel.ItemIdRole)
                item_type = self._model.data(source_index, ExplorerModel.ItemTypeRole)
                item_name = self._model.data(source_index, ExplorerModel.ItemNameRole)
                if item_id and item_type:
                    items_to_delete.append((item_type, item_id, item_name))

        if not items_to_delete:
            return

        # Proceed with deletion immediately since it's undoable (Unblocking)
        for item_type, item_id, _ in items_to_delete:
            self.delete_requested.emit(item_type, item_id)

        # Show self-closing short delete confirmation modal (Unblocking UX)
        count = len(items_to_delete)
        if count == 1:
            msg = f"Deleted '{items_to_delete[0][2]}'.\n\n(Ctrl+Z to Undo)"
        else:
            msg = f"Deleted {count} items.\n\n(Ctrl+Z to Undo)"

        # Emit status bar message as secondary feedback
        self.status_message_requested.emit(msg.replace("\n\n", " "), 3000)

        # Show the auto-closing modal (1 second)
        popup = AutoClosingMessageBox("Deletion Success", msg, 1000, parent=self)
        popup.exec()

        # Optional: Clear check state after deletion to avoid stale references
        self._model._checked_ids.clear()
        self._update_delete_button_state()

    def select_item(self, item_type: str, item_id: str) -> None:
        """Programmatically selects an item in the list. Auto-switches filter if item
        not visible.

        Args:
            item_type (str): "event" or "entity".
            item_id (str): The ID of the item to select.

        """

        def find_and_select() -> bool:
            """Inner function to search model and select matching item.

            Searches the model for an item matching the given type and ID,
            then selects and scrolls to it.
            """
            # Find in source model
            source_index = self._model.find_item_index(item_type, item_id)
            if not source_index:
                return False

            # Map to proxy
            proxy_index = self._proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                return False

            # Select and scroll
            self.list_widget.setCurrentIndex(proxy_index)
            self.list_widget.scrollTo(proxy_index)
            return True

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
            # Clear selection if item truly not found
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
        """Trigger event creation if conditions are met."""
        if self._should_trigger_shortcut():
            self.create_event_requested.emit()

    def _create_entity_trigger(self) -> None:
        """Trigger entity creation if conditions are met."""
        if self._should_trigger_shortcut():
            self.create_entity_requested.emit()

    def _create_map_trigger(self) -> None:
        """Trigger map creation if conditions are met."""
        if self._should_trigger_shortcut():
            self.create_map_requested.emit()
