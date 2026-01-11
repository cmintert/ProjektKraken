"""
MainWindow Class.

The main application window that manages UI components, database workers,
and signal/slot connections.
"""

from typing import Optional

# NOTE: PySide6 Fully Qualified Enum Paths
# =========================================
# This codebase uses fully qualified enum paths for all Qt enums, which is
# the official PySide6 6.4+ recommendation for proper type checking.
#
# Examples:
#   Qt.ConnectionType.QueuedConnection  (not Qt.ConnectionType.QueuedConnection)
#   Qt.MouseButton.LeftButton           (not Qt.MouseButton.LeftButton)
#   Qt.AlignmentFlag.AlignCenter        (not Qt.AlignmentFlag.AlignCenter)
#
# This ensures Pyright can properly type-check Qt enum usage while maintaining
# full runtime compatibility. See docs/PYSIDE6_ENUM_SOLUTION.md for details.
#
# Remaining ~500 reportAttributeAccessIssue errors are for QMessageBox/QDialog
# constants and other Qt classes that haven't been updated yet.
from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    QSettings,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from src.app.ai_search_manager import AISearchManager
from src.app.command_coordinator import CommandCoordinator
from src.app.connection_manager import ConnectionManager
from src.app.constants import (
    DEFAULT_DB_NAME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)
from src.app.data_handler import DataHandler
from src.app.longform_manager import LongformManager
from src.app.map_handler import MapHandler
from src.app.timeline_grouping_manager import TimelineGroupingManager
from src.app.ui_manager import UIManager
from src.app.worker_manager import WorkerManager
from src.commands.entity_commands import (
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.logging_config import get_logger
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog
from src.gui.dialogs.filter_dialog import FilterDialog
from src.gui.widgets.ai_search_panel import AISearchPanelWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view import GraphWidget
from src.gui.widgets.longform_editor import LongformEditorWidget
from src.gui.widgets.map_widget import MapWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    The main application window.

    Acts as the central controller for the UI, managing:
    - Dockable widgets (Lists, Editors, Timeline).
    - DatabaseWorker thread for async operations.
    - Signal/Slot connections between UI and persistent storage.

    Adheres to "Dumb UI" philosophy: logic delegates to Worker/Commands.
    """

    # Signal to send commands to worker thread
    command_requested = Signal(object)
    # Signal to request filtering
    filter_requested = Signal(dict)
    # Signal to request graph data load
    load_graph_data_requested = Signal(
        object, object
    )  # (tags: list|None, rel_types: list|None)

    def __init__(self, capture_layout_on_exit: bool = False) -> None:
        """
        Initializes the MainWindow.

        Args:
            capture_layout_on_exit: If True, saves current layout as default on exit.
        """
        super().__init__()

        self.capture_layout_on_exit = capture_layout_on_exit

        # Load active database for title
        settings = QSettings()
        active_db = settings.value(SETTINGS_ACTIVE_DB_KEY, DEFAULT_DB_NAME)

        self.setWindowTitle(f"{WINDOW_TITLE} - {active_db}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # ... (rest of init unchanged until closeEvent)

        # 0. Initialize Data Handler (signals-based, no window reference)
        self.data_handler = DataHandler()

        # 1. Init Services (Worker Thread)
        self.worker_manager = WorkerManager(self)
        self.worker_manager.init_worker()

        # 2. Init Widgets
        self.unified_list = UnifiedListWidget()
        self.event_editor = EventEditorWidget(self)
        self.entity_editor = EntityEditorWidget(self)

        # Connect dirty signals to update dock titles
        self.event_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.event_editor, dirty)
        )
        self.entity_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.entity_editor, dirty)
        )
        self.timeline = TimelineWidget()
        self.map_widget = MapWidget()

        # AI Search Panel
        self.ai_search_panel = AISearchPanelWidget()

        # Graph Widget
        self.graph_widget = GraphWidget()
        self.graph_widget.node_clicked.connect(self._on_item_selected)

        self.cached_event_count: Optional[int] = None

        # Filter Configuration
        self.filter_config: dict = {}  # For Project Explorer
        self.longform_filter_config: dict = {}  # For Longform editor

        # Data Cache for Unified List
        self._cached_events = []
        self._cached_entities = []
        self._cached_longform_sequence = []
        self.calendar_converter = None

        # Pending Selection (for creation flow)
        # Pending Selection (for creation flow)
        self._pending_select_id = None
        self._pending_select_type = None

        # Track last selection for undoing on cancel
        self._last_selected_id = None
        self._last_selected_type = None

        # Debounce timer for graph reload
        self._graph_reload_timer: QTimer | None = None

        self.longform_editor = LongformEditorWidget(db_path=self.db_path)

        # Initialize Map Handler
        self.map_handler = MapHandler(self)

        # Initialize Timeline Grouping Manager
        self.grouping_manager = TimelineGroupingManager(self)

        # Initialize AI Search Manager
        self.ai_search_manager = AISearchManager(self)

        # Initialize Longform Manager
        self.longform_manager = LongformManager(self)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 3. Setup UI Layout via UIManager
        self.ui_manager = UIManager(self)
        self.ui_manager.setup_docks(
            {
                "unified_list": self.unified_list,
                "event_editor": self.event_editor,
                "entity_editor": self.entity_editor,
                "timeline": self.timeline,
                "longform_editor": self.longform_editor,
                "map_widget": self.map_widget,
                "ai_search_panel": self.ai_search_panel,
                "graph_widget": self.graph_widget,
            }
        )

        # 4. Initialize Connection Manager
        self.connection_manager = ConnectionManager(self)
        self.connection_manager.connect_all()

        # 5. Initialize Command Coordinator
        self.command_coordinator = CommandCoordinator(self)
        self.command_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar Time Labels
        self.lbl_world_time = QLabel("World: --")
        self.lbl_world_time.setMinimumWidth(250)
        self.lbl_world_time.setStyleSheet("color: #3498db; font-weight: bold;")  # Blue
        self.status_bar.addPermanentWidget(self.lbl_world_time)

        self.lbl_playhead_time = QLabel("Playhead: --")
        self.lbl_playhead_time.setMinimumWidth(250)
        self.lbl_playhead_time.setStyleSheet(
            "color: #e74c3c; font-weight: bold;"
        )  # Red
        self.status_bar.addPermanentWidget(self.lbl_playhead_time)

        # File Menu
        self.ui_manager.create_file_menu(self.menuBar())

        # Timeline Menu (New)
        self.ui_manager.create_timeline_menu(self.menuBar())

        # View Menu
        self.ui_manager.create_view_menu(self.menuBar())

        # Settings Menu (Consolidated AI Search here)
        self.ui_manager.create_settings_menu(self.menuBar())

        # 5. Initialize Database (deferred to ensure event loop is running)
        QTimer.singleShot(
            100,
            lambda: QMetaObject.invokeMethod(
                self.worker, "initialize_db", Qt.ConnectionType.QueuedConnection
            ),
        )

        # 6. Restore Window State
        self._restore_window_state()

    @property
    def list_dock(self) -> QDockWidget:
        """
        Gets the project list dock widget.

        Returns:
            QDockWidget: The dock widget containing the unified list.
        """
        return self.ui_manager.docks.get("list")

    @property
    def editor_dock(self) -> QDockWidget:
        """
        Gets the event editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the event editor.
        """
        return self.ui_manager.docks.get("event")

    @property
    def entity_editor_dock(self) -> QDockWidget:
        """
        Gets the entity editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the entity editor.
        """
        return self.ui_manager.docks.get("entity")

    @property
    def timeline_dock(self) -> QDockWidget:
        """
        Gets the timeline dock widget.

        Returns:
            QDockWidget: The dock widget containing the timeline.
        """
        return self.ui_manager.docks.get("timeline")

    @property
    def longform_dock(self) -> QDockWidget:
        """
        Gets the longform editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the longform editor.
        """
        return self.ui_manager.docks.get("longform")

    @property
    def map_dock(self) -> QDockWidget:
        """
        Gets the map dock widget.

        Returns:
            QDockWidget: The dock widget containing the map.
        """
        return self.ui_manager.docks.get("map")

    def _restore_window_state(self) -> None:
        """Restores window geometry and state from settings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        geometry = settings.value("geometry")
        state = settings.value("windowState")

        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        else:
            self.ui_manager.reset_layout()

    def update_item(self, data: dict) -> None:
        """
        Placeholder for generalized update.

        Currently unused as we split update_event/entity.
        """
        pass

    def load_data(self) -> None:
        """Refreshes both events and entities."""
        self.load_events()
        self.load_entities()
        self.load_longform_sequence()
        self.load_graph_data()

    def load_longform_sequence(self) -> None:
        """
        Loads the longform sequence, applying active filters if any.
        """
        self.longform_manager.load_longform_sequence()

    @Slot(list)
    def _on_longform_sequence_loaded(self, sequence: list) -> None:
        """
        Handler for when longform sequence is loaded.
        """
        self.longform_manager.on_longform_sequence_loaded(sequence)

    def _on_item_selected(self, item_type: str, item_id: str) -> None:
        """Handles selection from unified list or longform editor."""
        # Handle plural table names from longform editor
        if item_type == "events":
            item_type = "event"
        elif item_type == "entities":
            item_type = "entity"

        # Avoid redundant reloading and unsaved changes checks if selecting the same item
        if item_id == self._last_selected_id and item_type == self._last_selected_type:
            return

        if item_type == "event":
            if not self.check_unsaved_changes(self.event_editor):
                # Attempt to revert - simplified for now, strictly just return
                # Visually the list might differ from detailed view if we just return
                return

            self.ui_manager.docks["event"].raise_()
            self.load_event_details(item_id)
            self._last_selected_id = item_id
            self._last_selected_type = "event"

        elif item_type == "entity":
            if not self.check_unsaved_changes(self.entity_editor):
                return

            self.ui_manager.docks["entity"].raise_()
            self.load_entity_details(item_id)
            self._last_selected_id = item_id
            self._last_selected_type = "entity"

        # Save selection for persistence
        if self._last_selected_id and self._last_selected_type:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, self._last_selected_id)
            settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, self._last_selected_type)

    def check_unsaved_changes(self, editor: QWidget) -> bool:
        """
        Checks if the editor has unsaved changes and prompts the user.

        Args:
            editor: The editor widget to check.

        Returns:
            bool: True if safe to proceed (Saved, Discarded, or Clean).
                  False if User Cancelled.
        """
        if (
            not hasattr(editor, "has_unsaved_changes")
            or not editor.has_unsaved_changes()
        ):
            return True

        # Determine readable name
        editor_name = "Item"
        if editor == self.event_editor:
            editor_name = "Event"
        elif editor == self.entity_editor:
            editor_name = "Entity"

        reply = QMessageBox.warning(
            self,
            "Unsaved Changes",
            f"You have unsaved changes in the {editor_name} Editor.\n"
            "Do you want to save them before proceeding?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Save:
            # Trigger save
            # We assume _on_save calls standard save mechanism
            if hasattr(editor, "_on_save"):
                editor._on_save()
            return True
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def _on_editor_dirty_changed(self, editor: QWidget, dirty: bool) -> None:
        """Updates the dock title with an asterisk if dirty."""
        dock_key = None
        base_title = ""

        # Determine which dock
        if editor == self.event_editor:
            dock_key = "event"
            # Get base title from constants (need to import or hardcode fallback)
            # Assuming UIManager set it initially. We can read current and strip *.
            base_title = "Event Inspector"
        elif editor == self.entity_editor:
            dock_key = "entity"
            base_title = "Entity Inspector"

        if dock_key:
            dock = self.ui_manager.docks.get(dock_key)
            if dock:
                new_title = base_title + (" *" if dirty else "")
                dock.setWindowTitle(new_title)

    @Slot(str, str)
    def _on_item_delete_requested(self, item_type: str, item_id: str) -> None:
        """Handles deletion request from unified list."""
        if item_type == "event":
            self.delete_event(item_id)
        elif item_type == "entity":
            self.delete_entity(item_id)

    @Slot(str)
    def update_status_message(self, message: str) -> None:
        """
        Updates the status bar message and sets cursor to Wait.

        Args:
            message (str): The message to display.
        """
        self.worker_manager.update_status_message(message)

    def clear_status_message(self, message: str) -> None:
        """
        Clears the status bar message after a delay and restores cursor.

        Args:
            message (str): The final completion message.
        """
        self.worker_manager.clear_status_message(message)

    @Slot(str)
    def show_error_message(self, message: str) -> None:
        """
        Displays an error message in the status bar and logs it.

        Args:
            message (str): The error description.
        """
        self.worker_manager.show_error_message(message)

    @Slot(bool)
    def on_db_initialized(self, success: bool) -> None:
        """
        Handler for database initialization result.

        Args:
            success (bool): True if connection succeeded, False otherwise.
        """
        self.worker_manager.on_db_initialized(success)

    def _request_calendar_config(self) -> None:
        """Requests loading of the active calendar config from the worker."""
        QMetaObject.invokeMethod(
            self.worker, "load_calendar_config", Qt.ConnectionType.QueuedConnection
        )

    @Slot(object)
    def on_calendar_config_loaded(self, config: object) -> None:
        """
        Handler for calendar config loaded from worker.

        Args:
            config: CalendarConfig or None.
        """
        try:
            from src.core.calendar import CalendarConfig, CalendarConverter

            if config:
                converter = CalendarConverter(config)
            else:
                # Use default if no active config
                default_config = CalendarConfig.create_default()
                converter = CalendarConverter(default_config)

            self.event_editor.set_calendar_converter(converter)
            self.timeline.set_calendar_converter(converter)
            self.map_widget.set_calendar_converter(converter)

            # Set calendar converter for timeline display in entity editor
            from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget

            TimelineDisplayWidget.set_calendar_converter(converter)

            # Check if UIManager has a pending calendar dialog
            self.ui_manager.show_calendar_dialog(config)

            # Save converter for status bar formatting
            self.calendar_converter = converter

            # Refresh status bar labels now that we have a converter
            if hasattr(self, "timeline"):
                self.update_world_time_label(self.timeline.get_current_time())
                self.update_playhead_time_label(self.timeline.get_playhead_time())

        except Exception as e:
            logger.warning(f"Failed to initialize calendar converter: {e}")

    def _request_current_time(self) -> None:
        """Requests loading of the current time from the worker."""
        QMetaObject.invokeMethod(
            self.worker, "load_current_time", Qt.ConnectionType.QueuedConnection
        )

    @Slot(float)
    def on_current_time_loaded(self, time: float) -> None:
        """
        Handler for current time loaded from worker.

        Args:
            time (float): The current time in lore_date units.
        """
        self.timeline.set_current_time(time)
        logger.debug(f"Current time loaded: {time}")

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """
        Handler for when current time is changed in the timeline.
        Saves the new value to the database.

        Args:
            time (float): The new current time in lore_date units.
        """
        QMetaObject.invokeMethod(
            self.worker,
            "save_current_time",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(float, time),
        )
        logger.debug(f"Current time changed to: {time}")

        # Update entity editor's timeline display with NOW marker
        self.entity_editor.timeline_display.set_current_time(time)
        self.update_world_time_label(time)

    @Slot()
    def on_return_to_present(self) -> None:
        """
        Exits "Viewing Past/Future State" mode.
        Hides the playhead and reloads the current entity in editable mode.
        """
        # Set playhead to "Current Time" (Visual indicator that we are at "Now")
        current_time = self.timeline.get_current_time()
        self.timeline.set_playhead_time(current_time)

        # Reload entity in normal editable mode
        if self.entity_editor.isVisible() and self.entity_editor._current_entity_id:
            self.load_entity_details(self.entity_editor._current_entity_id)

    def update_world_time_label(self, time_val: float) -> None:
        """Updates the blue world time label."""
        text = self._format_time_string(time_val)
        self.lbl_world_time.setText(f"World: {text}")

    def update_playhead_time_label(self, time_val: float) -> None:
        """Updates the red playhead time label."""
        text = self._format_time_string(time_val)
        self.lbl_playhead_time.setText(f"Playhead: {text}")

    def _restore_last_selection(self) -> None:
        """Restores the last selected item from settings."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        last_id = settings.value(SETTINGS_LAST_ITEM_ID_KEY)
        last_type = settings.value(SETTINGS_LAST_ITEM_TYPE_KEY)

        if last_id and last_type:
            logger.info(f"Restoring last selection: {last_type} {last_id}")
            # Load details (this opens the editor)
            if last_type == "event":
                self.load_event_details(last_id)
                self.ui_manager.docks["event"].raise_()
            elif last_type == "entity":
                self.load_entity_details(last_id)
                self.ui_manager.docks["entity"].raise_()

            # Try to select in list
            # (might fail if list populate is slow, but editor is key)
            self.unified_list.select_item(last_type, last_id)

    def _format_time_string(self, time_val: float) -> str:
        """Formats time using calendar converter if available."""
        if self.calendar_converter:
            return self.calendar_converter.format_date(time_val)
        return f"{time_val:.2f}"

    def on_command_finished_reload_longform(self) -> None:
        """Handler to reload longform sequence after command completion."""
        self.longform_manager.on_command_finished_reload_longform()

    def _request_grouping_config(self) -> None:
        """Requests loading of the timeline grouping configuration."""
        self.grouping_manager.request_grouping_config()

    def on_grouping_config_loaded(self, config: dict) -> None:
        """
        Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.
        """
        self.grouping_manager.on_grouping_config_loaded(config)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handles application close event.
        Saves window geometry/state and strictly cleans up worker thread.
        Also checks for unsaved changes.
        """
        # Check unsaved changes
        for editor in [self.event_editor, self.entity_editor]:
            if not self.check_unsaved_changes(editor):
                event.ignore()
                return

        # Save State
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

        # Save as Default Layout if requested
        if self.capture_layout_on_exit:
            self.ui_manager.save_as_default_layout()

        # Save Persistent Widget States
        if hasattr(self, "timeline"):
            self.timeline.save_state()

        # Stop debounce timer to prevent callbacks during shutdown
        if self._graph_reload_timer is not None:
            self._graph_reload_timer.stop()

        # Cleanup Worker
        QMetaObject.invokeMethod(
            self.worker, "cleanup", Qt.ConnectionType.BlockingQueuedConnection
        )

        self.worker_thread.quit()
        if not self.worker_thread.wait(2000):  # 2000ms timeout
            logger.warning("Worker thread did not quit in time. Terminating...")
            self.worker_thread.terminate()
            self.worker_thread.wait()  # Wait for terminate to complete

        event.accept()

    # ----------------------------------------------------------------------
    # Methods that request data from Worker
    # ----------------------------------------------------------------------

    def seed_data(self) -> None:
        """
        Populate the database with initial data (Deprecated).
        Current implementation is a placeholder.
        """
        # Checking if empty is hard without async check.
        # For now, let's just skip automatic seeding in this refactor or make it
        # a command. Ideally, we should have a 'CheckEmpty' command or similar.
        pass

    # TimelineDataProvider interface implementation
    def get_group_metadata(
        self,
        tag_order: list[str],
        date_range: tuple[float, float] | None = None,
    ) -> list[dict]:
        """
        Get metadata for timeline grouping tags.

        Implements TimelineDataProvider protocol for timeline grouping.

        Args:
            tag_order: List of tag names to get metadata for.
            date_range: Optional (start_date, end_date) tuple for filtering.

        Returns:
            List of dicts containing tag metadata.
        """
        if hasattr(self, "gui_db_service"):
            return self.gui_db_service.get_group_metadata(
                tag_order=tag_order, date_range=date_range
            )
        return []

    def get_events_for_group(
        self, tag_name: str, date_range: tuple[float, float] | None = None
    ) -> list:
        """
        Get events that belong to a specific tag group.

        Implements TimelineDataProvider protocol for timeline grouping.

        Args:
            tag_name: Name of the tag to filter by.
            date_range: Optional (start_date, end_date) tuple for filtering.

        Returns:
            List of Event objects with the specified tag.
        """
        if hasattr(self, "gui_db_service"):
            return self.gui_db_service.get_events_for_group(
                tag_name=tag_name, date_range=date_range
            )
        return []

    def load_events(self) -> None:
        """Requests loading of all events."""
        QMetaObject.invokeMethod(
            self.worker, "load_events", Qt.ConnectionType.QueuedConnection
        )

    def load_entities(self) -> None:
        """Requests loading of all entities."""
        QMetaObject.invokeMethod(
            self.worker, "load_entities", Qt.ConnectionType.QueuedConnection
        )

    def load_event_details(self, event_id: str) -> None:
        """Requests loading details for a specific event."""
        # Note: If called from selection, we already checked.
        # But if called programmatically, we might want to check here too?
        # Actually _on_item_selected calls this.
        # But for robust safety, checking here is good, unless it causes double prompts.
        # Let's rely on the caller (selection/navigation) to guard,
        # as this is a "request" and checking UI state inside
        # a low-level request might be mixing concerns slightly.
        # However, to start simple, we guard at user-interaction points.

        QMetaObject.invokeMethod(
            self.worker,
            "load_event_details",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, event_id),
        )

    def load_entity_details(self, entity_id: str) -> None:
        """Requests loading details for a specific entity."""
        QMetaObject.invokeMethod(
            self.worker,
            "load_entity_details",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, entity_id),
        )

    def load_graph_data(self, filter_config: Optional[dict] = None) -> None:
        """
        Requests loading of graph data, optionally filtered.

        Args:
            filter_config: Optional dictionary with 'tags' and 'rel_types'.
                           If not provided, uses current widget config.
        """
        # Get config from widget if not provided
        if filter_config is None and self.graph_widget:
            filter_config = self.graph_widget.get_filter_config()

        tags = filter_config.get("tags") if filter_config else None
        rel_types = filter_config.get("rel_types") if filter_config else None

        # Emit signal with None supported (handled by Signal(object, object))
        self.load_graph_data_requested.emit(tags, rel_types)

    @Slot(list, list)
    def _on_graph_data_ready(self, nodes: list[dict], edges: list[dict]) -> None:
        """
        Updates the graph widget with loaded data.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.
        """
        if self.graph_widget:
            # Pass the last selected ID to preserve focus
            focus_id = self._last_selected_id
            self.graph_widget.display_graph(nodes, edges, focus_node_id=focus_id)

    @Slot(list, list)
    def _on_graph_metadata_ready(self, tags: list[str], rel_types: list[str]) -> None:
        """
        Updates the graph widget with available metadata.

        Args:
            tags: List of available tags.
            rel_types: List of available relation types.
        """
        if self.graph_widget:
            self.graph_widget.set_available_tags(tags)
            self.graph_widget.set_available_relation_types(rel_types)

    # DataHandler signal handlers (loose coupling via signals)
    @Slot(list)
    def _on_events_ready(self, events: list) -> None:
        """
        Handle events ready signal from DataHandler.

        Args:
            events: List of Event objects.
        """
        self._cached_events = events
        self.unified_list.set_data(self._cached_events, self._cached_entities)
        self.timeline.set_events(events)

        # Refresh graph to reflect changes (debounced)
        self._schedule_graph_refresh()

    @Slot(list)
    def _on_entities_ready(self, entities: list) -> None:
        """
        Handle entities ready signal from DataHandler.

        Args:
            entities: List of Entity objects.
        """
        self._cached_entities = entities
        self.unified_list.set_data(self._cached_events, self._cached_entities)

        # Refresh graph to reflect changes (debounced)
        self._schedule_graph_refresh()

    def _schedule_graph_refresh(self) -> None:
        """Schedules a debounced graph refresh to avoid double-loading."""
        if self._graph_reload_timer is None:
            self._graph_reload_timer = QTimer()
            self._graph_reload_timer.setSingleShot(True)
            self._graph_reload_timer.timeout.connect(self.load_graph_data)
        # Reset timer on each call (debounce)
        self._graph_reload_timer.start(100)  # 100ms debounce

    @Slot(list)
    def _on_suggestions_update(self, items: list) -> None:
        """
        Handle suggestions update request from DataHandler.

        Args:
            items: List of (id, name, type) tuples for completion.
        """
        self.event_editor.update_suggestions(items=items)
        self.entity_editor.update_suggestions(items=items)

    @Slot(object, list, list)
    def _on_event_details_ready(
        self, event: object, relations: list, incoming: list
    ) -> None:
        """
        Handle event details ready signal from DataHandler.

        Args:
            event: The Event object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.
        """
        self.event_editor.load_event(event, relations, incoming)

    @Slot(object, list, list)
    def _on_entity_details_ready(
        self, entity: object, relations: list, incoming: list
    ) -> None:
        """
        Handle entity details ready signal from DataHandler.

        Args:
            entity: The Entity object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.
        """
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(list)
    def _on_longform_sequence_ready(self, sequence: list) -> None:
        """
        Handle longform sequence ready signal from DataHandler.

        Args:
            sequence: List of longform items.
        """
        self._cached_longform_sequence = sequence
        self.longform_editor.load_sequence(sequence)

    @Slot(list)
    def _on_maps_ready(self, maps: list) -> None:
        """
        Handle maps ready signal from DataHandler.

        Args:
            maps: List of Map objects.
        """
        self.map_handler.on_maps_ready(maps)

    @Slot(str, list)
    def _on_markers_ready(self, map_id: str, processed_markers: list) -> None:
        """
        Handle markers ready signal from DataHandler.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.
        """
        self.map_handler.on_markers_ready(map_id, processed_markers)

    @Slot(str)
    def _on_dock_raise_requested(self, dock_name: str) -> None:
        """
        Handle dock raise request from DataHandler.

        Args:
            dock_name: Name of the dock to raise ("event", "entity", etc).
        """
        if dock_name in self.ui_manager.docks:
            self.ui_manager.docks[dock_name].raise_()

    @Slot(str, str)
    def _on_selection_requested(self, item_type: str, item_id: str) -> None:
        """
        Handle selection request from DataHandler.

        Args:
            item_type: Type of item ("event" or "entity").
            item_id: ID of the item to select.
        """
        self.unified_list.select_item(item_type, item_id)

    @Slot(str)
    def _on_command_failed(self, message: str) -> None:
        """
        Handle command failure notification from DataHandler.

        Args:
            message: Error message from the failed command.
        """
        QMessageBox.warning(self, "Command Failed", message)

    @Slot()
    def _on_reload_active_editor_relations(self) -> None:
        """
        Reload relations for whichever editor is currently active.

        This is called after relation or wiki link commands complete.
        """
        if self.event_editor._current_event_id:
            self.load_event_details(self.event_editor._current_event_id)
        if self.entity_editor._current_entity_id:
            self.load_entity_details(self.entity_editor._current_entity_id)

    def delete_event(self, event_id: str) -> None:
        """
        Deletes an event by emitting a delete command.

        Args:
            event_id (str): The ID of the event to delete.
        """
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def update_event(self, event_data: dict) -> None:
        """
        Updates an event with the provided data.

        Args:
            event_data (dict): Dictionary containing event data
                including the 'id' field.
        """
        event_id = event_data.get("id")
        if not event_id:
            logger.error("Attempted to update event without ID.")
            return

        cmd = UpdateEventCommand(event_id, event_data)
        self.command_requested.emit(cmd)

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            self.command_requested.emit(wiki_cmd)

    @Slot(str, float)
    def _on_event_date_changed(self, event_id: str, new_lore_date: float) -> None:
        """
        Handles event date changes from timeline dragging.
        Persists the new lore_date via UpdateEventCommand.

        Args:
            event_id: The ID of the event that was dragged.
            new_lore_date: The new lore_date value.
        """
        logger.debug(f"Event {event_id} date changed to {new_lore_date}")
        cmd = UpdateEventCommand(event_id, {"lore_date": new_lore_date})
        self.command_requested.emit(cmd)

    def create_entity(self) -> None:
        """
        Creates a new entity by emitting a create command.
        """
        if not self.check_unsaved_changes(self.entity_editor):
            return

        name, ok = QInputDialog.getText(self, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEntityCommand({"name": name.strip(), "type": "Concept"})
        self.command_requested.emit(cmd)

    def create_event(self) -> None:
        """
        Creates a new event by emitting a create command.
        """
        if not self.check_unsaved_changes(self.event_editor):
            return

        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEventCommand({"name": name.strip(), "lore_date": 0.0})
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id: str) -> None:
        """
        Deletes an entity by emitting a delete command.

        Args:
            entity_id (str): The ID of the entity to delete.
        """
        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    def update_entity(self, entity_data: dict) -> None:
        """
        Updates an entity with the provided data.

        Args:
            entity_data (dict): Dictionary containing entity data
                including the 'id' field.
        """
        entity_id = entity_data.get("id")
        if not entity_id:
            logger.error("Attempted to update entity without ID.")
            return

        cmd = UpdateEntityCommand(entity_id, entity_data)
        self.command_requested.emit(cmd)

        if "description" in entity_data:
            wiki_cmd = ProcessWikiLinksCommand(entity_id, entity_data["description"])
            self.command_requested.emit(wiki_cmd)

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: dict = None,
        bidirectional: bool = False,
    ) -> None:
        """
        Adds a relation between entities.

        Args:
            source_id (str): The ID of the source entity.
            target_id (str): The ID of the target entity.
            rel_type (str): The type of relation.
            attributes (dict, optional): Attributes for the relation.
            bidirectional (bool, optional): Whether the relation is
                bidirectional. Defaults to False.
        """
        cmd = AddRelationCommand(
            source_id,
            target_id,
            rel_type,
            attributes=attributes,
            bidirectional=bidirectional,
        )
        self.command_requested.emit(cmd)

    def load_maps(self) -> None:
        """Requests loading of all maps."""
        self.map_handler.load_maps()

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """
        Handler for when a map is selected in the widget.
        Loads the map image and requests markers.
        """
        self.map_handler.on_map_selected(map_id)

    def create_map(self) -> None:
        """Creates a new map via dialogs."""
        self.map_handler.create_map()

    def delete_map(self) -> None:
        """Deletes the currently selected map."""
        self.map_handler.delete_map()

    def create_marker(self, x: float, y: float) -> None:
        """
        Creates a new marker at the given normalized coordinates.
        Prompts user to select an Entity or Event.
        """
        self.map_handler.create_marker(x, y)

    def _on_marker_dropped(
        self, item_id: str, item_type: str, item_name: str, x: float, y: float
    ) -> None:
        """
        Handle marker creation from drag-drop.

        Args:
            item_id: ID of the dropped entity/event.
            item_type: 'entity' or 'event'.
            item_name: Display name of the item.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
        """
        self.map_handler.on_marker_dropped(item_id, item_type, item_name, x, y)

    def delete_marker(self, marker_id: str) -> None:
        """
        Deletes a marker.

        Args:
            marker_id: The object_id from the UI (not the actual marker.id).
        """
        self.map_handler.delete_marker(marker_id)

    @Slot(str, str)
    def _on_marker_clicked(self, marker_id: str, object_type: str) -> None:
        """
        Handle marker click from MapWidget.

        Args:
            marker_id: The ID of the item.
            object_type: 'event' or 'entity'.
        """
        self.map_handler.on_marker_clicked(marker_id, object_type)

    @Slot(str, str)
    def _on_marker_icon_changed(self, marker_id: str, icon: str) -> None:
        """
        Handle marker icon change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            icon: New icon filename
        """
        self.map_handler.on_marker_icon_changed(marker_id, icon)

    @Slot(str, str)
    def _on_marker_color_changed(self, marker_id: str, color: str) -> None:
        """
        Handle marker color change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            color: New color hex code
        """
        self.map_handler.on_marker_color_changed(marker_id, color)

    @Slot(str, float, float)
    def _on_marker_position_changed(self, marker_id: str, x: float, y: float) -> None:
        """
        Handle marker position change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            x: New normalized X coordinate
            y: New normalized Y coordinate
        """
        self.map_handler.on_marker_position_changed(marker_id, x, y)

    # ----------------------------------------------------------------------
    # Timeline Grouping Methods
    # ----------------------------------------------------------------------

    def _on_configure_grouping_requested(self) -> None:
        """Opens grouping configuration dialog by requesting data from worker thread."""
        self.grouping_manager.on_configure_grouping_requested()

    @Slot(list, object)
    def on_grouping_dialog_data_loaded(
        self, tags_data: list, current_config: dict
    ) -> None:
        """
        Handler for grouping dialog data loaded from worker.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.
        """
        self.grouping_manager.on_grouping_dialog_data_loaded(tags_data, current_config)

    @Slot(list, str)
    def _on_grouping_applied(self, tag_order: list, mode: str) -> None:
        """
        Handle grouping applied from dialog.

        Args:
            tag_order: List of tag names in order.
            mode: Grouping mode (DUPLICATE or FIRST_MATCH).
        """
        self.grouping_manager.on_grouping_applied(tag_order, mode)

    def _on_clear_grouping_requested(self) -> None:
        """Clears timeline grouping."""
        self.grouping_manager.on_clear_grouping_requested()

    @Slot(str)
    def _on_tag_color_change_requested(self, tag_name: str) -> None:
        """
        Handle tag color change from band context menu.

        Args:
            tag_name: The name of the tag to change color for.
        """
        self.grouping_manager.on_tag_color_change_requested(tag_name)

    @Slot(str)
    def _on_remove_from_grouping_requested(self, tag_name: str) -> None:
        """
        Remove a tag from current grouping.

        Args:
            tag_name: The name of the tag to remove.
        """
        self.grouping_manager.on_remove_from_grouping_requested(tag_name)

    @Slot()
    def show_filter_dialog(self) -> None:
        """Shows the advanced filter dialog."""
        # Get all tags from DB (Synchronous read from GUI DB Service is fine for metadata)
        tags = []
        if hasattr(self, "gui_db_service"):
            # db_service.get_active_tags returns list of dicts: need to extract names
            tag_dicts = self.gui_db_service.get_active_tags()
            tags = [t["name"] for t in tag_dicts]

        dialog = FilterDialog(
            self, available_tags=tags, current_config=self.filter_config
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_filter_config()
            self.filter_config = config  # Update local state

            # Save to settings
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue(SETTINGS_FILTER_CONFIG_KEY, config)

            logger.info(f"Applying filter: {config}")
            # Send to worker via signal (safer than invokeMethod for dicts)
            self.filter_requested.emit(config)

            # Update UI state
            has_filter = bool(config.get("include") or config.get("exclude"))
            self.unified_list.set_filter_active(has_filter)

    @Slot()
    def clear_filter(self) -> None:
        """
        Clears the current filter configuration and reloads data.
        """
        logger.info("Clearing filters")
        self.filter_config = {}

        # Clear settings
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.remove(SETTINGS_FILTER_CONFIG_KEY)

        # Update UI state
        self.unified_list.set_filter_active(False)
        self.status_bar.showMessage("Filters cleared.")

        # Reload full data
        self.load_data()

    @Slot()
    def show_longform_filter_dialog(self) -> None:
        """Shows filter dialog for the Longform editor (independent state)."""
        self.longform_manager.show_longform_filter_dialog()

    @Slot()
    def clear_longform_filter(self) -> None:
        """Clears the longform filter and reloads the longform view."""
        self.longform_manager.clear_longform_filter()

    @Slot(list, list)
    def _on_filter_results_ready(self, events: list, entities: list) -> None:
        """
        Handler for filter results.
        Updates the Unified List with filtered data.
        """
        self.unified_list.set_data(events, entities)
        count = len(events) + len(entities)
        self.status_bar.showMessage(f"Filter applied. Found {count} items.")

    def remove_relation(self, rel_id: str) -> None:
        """
        Removes a relation by its ID.

        Args:
            rel_id (str): The ID of the relation to remove.
        """
        cmd = RemoveRelationCommand(rel_id)
        self.command_requested.emit(cmd)

    def update_relation(
        self, rel_id: str, target_id: str, rel_type: str, attributes: dict = None
    ) -> None:
        """
        Updates an existing relation.

        Args:
            rel_id (str): The ID of the relation to update.
            target_id (str): The new target entity ID.
            rel_type (str): The new relation type.
            attributes (dict, optional): The new attributes.
        """
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type, attributes=attributes)
        self.command_requested.emit(cmd)

    def navigate_to_entity(self, target: str) -> None:
        """
        Navigates to the entity or event with the given name or ID.

        Handles both ID-based links (UUIDs) and legacy name-based links.
        Uses cached entities and events for quick lookup.

        Args:
            target (str): Entity/event name or UUID.
        """
        logger.info(f"Navigating to target: {target}")

        # Check if target is a valid UUID format
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        is_uuid = uuid_pattern.match(target) is not None

        if is_uuid:
            # ID-based navigation - direct lookup
            entity = next((e for e in self._cached_entities if e.id == target), None)
            if entity:
                if not self.check_unsaved_changes(self.entity_editor):
                    return
                self.load_entity_details(entity.id)
                return

            event = next((e for e in self._cached_events if e.id == target), None)
            if event:
                if not self.check_unsaved_changes(self.event_editor):
                    return
                self.load_event_details(event.id)
                return

            # ID not found - broken link
            QMessageBox.warning(
                self,
                "Broken Link",
                f"The linked item (ID: {target[:8]}...) no longer exists.",
            )
        else:
            # Name-based navigation (legacy) - case-insensitive match
            entity = next(
                (e for e in self._cached_entities if e.name.lower() == target.lower()),
                None,
            )

            if entity:
                if not self.check_unsaved_changes(self.entity_editor):
                    return
                self.load_entity_details(entity.id)
                return

            # Also check events for name-based links
            event = next(
                (e for e in self._cached_events if e.name.lower() == target.lower()),
                None,
            )

            if event:
                if not self.check_unsaved_changes(self.event_editor):
                    return
                self.load_event_details(event.id)
                return

            # Name not found - Prompt for Creation
            self._prompt_create_missing_target(target)

    def _prompt_create_missing_target(self, target_name: str) -> None:
        """
        Prompts the user to create a missing entity or event from a broken link.

        Args:
            target_name (str): The name of the missing item.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Target Not Found")
        msg.setText(f"Item '{target_name}' does not exist.")
        msg.setInformativeText("Would you like to create it?")

        btn_entity = msg.addButton("Create Entity", QMessageBox.ButtonRole.AcceptRole)
        btn_event = msg.addButton("Create Event", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QMessageBox.StandardButton.Cancel)

        msg.exec()

        clicked = msg.clickedButton()

        if clicked == btn_entity:
            # Create Entity
            if not self.check_unsaved_changes(self.entity_editor):
                return

            # Use target name as default
            cmd = CreateEntityCommand({"name": target_name, "type": "Concept"})
            self.command_requested.emit(cmd)
            # We rely on on_command_finished to handle selection/loading
            # But we need to ensure the new item is selected.
            # CreateEntityCommand result handling in on_command_finished
            # sets _pending_select_id, which should handle it.

        elif clicked == btn_event:
            # Create Event
            if not self.check_unsaved_changes(self.event_editor):
                return

            cmd = CreateEventCommand({"name": target_name, "lore_date": 0.0})
            self.command_requested.emit(cmd)

    def promote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """
        Promotes a longform entry by reducing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to promote.
            old_meta (dict): Previous longform metadata for undo.
        """
        self.longform_manager.promote_longform_entry(table, row_id, old_meta)

    def demote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """
        Demotes a longform entry by increasing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to demote.
            old_meta (dict): Previous longform metadata for undo.
        """
        self.longform_manager.demote_longform_entry(table, row_id, old_meta)

    def move_longform_entry(
        self, table: str, row_id: str, old_meta: dict, new_meta: dict
    ) -> None:
        """
        Moves a longform entry to a new position.

        Args:
            table (str): Table name.
            row_id (str): ID.
            old_meta (dict): Old metadata.
            new_meta (dict): New metadata with position/parent/depth.
        """
        self.longform_manager.move_longform_entry(table, row_id, old_meta, new_meta)

    def export_longform_document(self) -> None:
        """
        Exports the current longform document to Markdown.
        Opens a file dialog for the user to choose save location.
        """
        self.longform_manager.export_longform_document()

    def toggle_auto_relation_setting(self, checked: bool) -> None:
        """
        Toggles the auto-create relations setting.

        Args:
            checked (bool): The new state of the setting.
        """
        from src.app.constants import SETTINGS_AUTO_RELATION_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue(SETTINGS_AUTO_RELATION_KEY, checked)
        logger.info(f"Auto-Create Relations setting set to: {checked}")

    # =========================================================================
    # AI Search Panel & Settings Methods
    # =========================================================================

    @Slot()
    def show_ai_settings_dialog(self) -> None:
        """Shows the AI Settings dialog."""
        self.ai_search_manager.show_ai_settings_dialog()

    @Slot(str)
    def _on_ai_settings_rebuild_requested(self, object_type: str) -> None:
        """Handle rebuild request from dialog."""
        self.ai_search_manager.on_ai_settings_rebuild_requested(object_type)

    @Slot(str, str, int)
    def perform_semantic_search(
        self, query: str, object_type_filter: str, top_k: int
    ) -> None:
        """
        Perform semantic search and display results.

        Args:
            query: Search query text.
            object_type_filter: Filter by 'entity' or 'event', or empty for all.
            top_k: Number of results to return.
        """
        self.ai_search_manager.perform_semantic_search(query, object_type_filter, top_k)

    @Slot(str)
    def rebuild_search_index(self, object_type: str) -> None:
        """
        Rebuild the semantic search index.

        Args:
            object_type: Type to rebuild ('all', 'entity', 'event').
        """
        self.ai_search_manager.rebuild_search_index(object_type)

    @Slot(str, str)
    def _on_search_result_selected(self, object_type: str, object_id: str) -> None:
        """
        Handle selection of a search result.

        Args:
            object_type: 'entity' or 'event'.
            object_id: Object UUID.
        """
        self.ai_search_manager.on_search_result_selected(object_type, object_id)

    @Slot()
    def refresh_search_index_status(self) -> None:
        """Refresh the search index status display."""
        self.ai_search_manager.refresh_search_index_status()

    @Slot()
    def show_database_manager(self) -> None:
        """Shows the Database Manager dialog."""
        dialog = DatabaseManagerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # If accepted, it means a restart is required (implied by select button)
            # We can offer to restart immediately or just close.
            # The dialog already warns user to restart.
            # We could do auto-restart:
            # qApp.quit()
            # QProcess.startDetached(sys.executable, sys.argv)
            pass

    @Slot(float)
    def _on_playhead_changed(self, time: float) -> None:
        """
        Refreshes entity inspector based on playhead time.
        """
        # Store current playhead time for use in _on_entity_state_resolved
        self._current_playhead_time = time

        if self.entity_editor.isVisible() and self.entity_editor._current_entity_id:
            QMetaObject.invokeMethod(
                self.worker,
                "resolve_entity_state",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, self.entity_editor._current_entity_id),
                Q_ARG(float, time),
            )

    @Slot(str, dict)
    def _on_entity_state_resolved(self, entity_id: str, attributes: dict) -> None:
        """
        Updates entity editor with resolved state.
        """
        # Pass playhead time for timeline highlighting
        playhead_time = getattr(self, "_current_playhead_time", None)
        self.entity_editor.display_temporal_state(entity_id, attributes, playhead_time)
