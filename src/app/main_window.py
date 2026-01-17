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
    QApplication,
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
from src.gui.mixins.layout_guard import LayoutGuardMixin
from src.gui.widgets.ai_search_panel import AISearchPanelWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view import GraphWidget
from src.gui.widgets.longform_editor import LongformEditorWidget
from src.gui.widgets.map_widget import MapWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

logger = get_logger(__name__)


class MainWindow(QMainWindow, LayoutGuardMixin):
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
        Initializes the MainWindow using three-phase initialization.

        Phase 1: Core services (data handler, worker thread)
        Phase 2: UI skeleton (widgets, layout, menus)
        Phase 3: Deferred completion (DB init, signals, state restoration)

        Args:
            capture_layout_on_exit: If True, saves current layout as default on exit.
        """
        super().__init__()
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        logger.debug("MainWindow initialization started")

        self.capture_layout_on_exit = capture_layout_on_exit

        # Phase 1: Core infrastructure
        self._init_core_services()
        logger.debug("Phase 1: Core services initialized")

        # Phase 2: UI skeleton (no data dependencies)
        self._init_widgets_skeleton()
        logger.debug("Phase 2: Widget skeleton created")

        # Phase 3: Deferred initialization (after event loop starts)
        QTimer.singleShot(100, self._complete_initialization)
        logger.debug("Phase 3: Deferred initialization scheduled")

    def _init_core_services(self) -> None:
        """
        Phase 1: Initialize core services and infrastructure.

        Sets up data handler, worker thread, and basic window properties.
        No widgets or UI elements created here.
        """
        # Load active world name for title
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, "Default World")

        self.setWindowTitle(f"{WINDOW_TITLE} - {active_world_name}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Current world reference (will be set by worker_manager)
        self.current_world = None

        # Initialize Data Handler (signals-based, no window reference)
        self.data_handler = DataHandler()

        # Initialize backup service (will be properly connected after DB init)
        self.backup_service = None

        # Init Services (Worker Thread)
        self.worker_manager = WorkerManager(self)
        self.worker_manager.init_worker()

        # Initialize state variables
        self.cached_event_count: Optional[int] = None
        self.longform_filter_config: dict = {}
        self._cached_events = []
        self._cached_entities = []
        self._cached_longform_sequence = []
        self.calendar_converter = None
        self._pending_select_id = None
        self._pending_select_type = None
        self._last_selected_id = None
        self._last_selected_type = None
        self._graph_reload_timer: QTimer | None = None

    def _init_widgets_skeleton(self) -> None:
        """
        Phase 2: Create UI skeleton without data dependencies.

        Creates all widgets, sets up layout, and creates menus.
        Does NOT connect signals or load data.
        """
        # Create Widgets (no data access during construction)
        self.unified_list = UnifiedListWidget()
        self.event_editor = EventEditorWidget(self)
        self.entity_editor = EntityEditorWidget(self)
        self.timeline = TimelineWidget()
        self.map_widget = MapWidget()
        self.ai_search_panel = AISearchPanelWidget()
        self.graph_widget = GraphWidget()
        self.longform_editor = LongformEditorWidget(db_path=self.db_path)

        # Initialize Managers
        self.map_handler = MapHandler(self)
        self.grouping_manager = TimelineGroupingManager(self)
        self.ai_settings_dialog = None
        self.ai_search_manager = AISearchManager(self)
        self.longform_manager = LongformManager(self)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Setup UI Layout via UIManager
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

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar Time Labels
        self.lbl_world_time = QLabel("World: --")
        self.lbl_world_time.setMinimumWidth(250)
        self.lbl_world_time.setStyleSheet("color: #3498db; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.lbl_world_time)

        self.lbl_playhead_time = QLabel("Playhead: --")
        self.lbl_playhead_time.setMinimumWidth(250)
        self.lbl_playhead_time.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.lbl_playhead_time)

        # Create Menus
        self.ui_manager.create_file_menu(self.menuBar())
        self.ui_manager.create_timeline_menu(self.menuBar())
        self.ui_manager.create_view_menu(self.menuBar())
        self.ui_manager.create_settings_menu(self.menuBar())

    def _complete_initialization(self) -> None:
        """
        Phase 3: Complete initialization after event loop starts.

        Initializes database, connects signals, restores state.
        Called via QTimer.singleShot after event loop is running.
        """
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        logger.debug("Completing initialization (Phase 3)")

        # Initialize Connection Manager and connect signals
        self.connection_manager = ConnectionManager(self)
        stats = self.connection_manager.connect_all()
        logger.info(
            f"Signal connections: {stats['total_succeeded']}/{stats['total_attempted']}"
        )

        # Initialize Command Coordinator
        self.command_coordinator = CommandCoordinator(self)
        self.command_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )

        # Connect editor dirty signals (these are safe to connect early)
        self.event_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.event_editor, dirty)
        )
        self.entity_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.entity_editor, dirty)
        )

        # Connect graph widget node clicked (was connected in old init)
        self.graph_widget.node_clicked.connect(self._on_item_selected)

        # Initialize Database
        QMetaObject.invokeMethod(
            self.worker, "initialize_db", Qt.ConnectionType.QueuedConnection
        )

        # Restore Window State
        self._restore_window_state()

        logger.debug("Initialization complete")

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
        """
        Restores window geometry and state using staged approach.

        Stage 1: Immediate - Restore geometry only
        Stage 2: 100ms - Restore critical docks (list, editors, timeline)
        Stage 3: 500ms - Restore optional docks (longform, map, AI, graph)
        """
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        logger.debug("Starting staged layout restoration")

        # Stage 1: Immediate geometry restoration
        self._restore_geometry()

        # Check for crash loop / blocked docks immediately
        if self.guard_check_crash_flag():
            logger.info(
                "Crash flag detected - considering safety measures (logging only for now)"
            )
            # We could force reset here if enabled

        # Stage 2: Critical docks after 100ms
        QTimer.singleShot(100, self._restore_critical_docks)

        # Stage 3: Optional docks after 500ms
        QTimer.singleShot(500, self._restore_optional_docks)

    def _restore_geometry(self) -> None:
        """
        Stage 1: Restore window geometry immediately.

        This provides instant visual feedback to the user.
        """
        from src.app.constants import LAYOUT_VERSION, SETTINGS_LAYOUT_VERSION_KEY
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Check layout version compatibility
        saved_version = settings.value(SETTINGS_LAYOUT_VERSION_KEY, "0.0.0")

        if saved_version != LAYOUT_VERSION:
            logger.warning(
                f"Layout version mismatch: saved={saved_version}, "
                f"current={LAYOUT_VERSION}. Will use default layout."
            )
            # Don't restore anything, will reset in critical docks stage
            return

        # Restore geometry only (fast)
        geometry = settings.value("geometry")
        if geometry:
            # Use Guard implementation
            if self.guard_restore_geometry(geometry):
                logger.debug("Window geometry restored safely")
            else:
                logger.warning("Failed to restore window geometry")
        else:
            logger.debug("No saved geometry found")

    def _restore_critical_docks(self) -> None:
        """
        Stage 2: Restore critical docks and their state.

        Critical docks: list, event editor, entity editor, timeline.
        These are essential for basic functionality.
        """
        from src.app.constants import LAYOUT_VERSION, SETTINGS_LAYOUT_VERSION_KEY
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        saved_version = settings.value(SETTINGS_LAYOUT_VERSION_KEY, "0.0.0")

        # If version mismatch, reset layout
        if saved_version != LAYOUT_VERSION:
            logger.info("Resetting to default layout due to version mismatch")
            self.ui_manager.reset_layout()
            settings.setValue(SETTINGS_LAYOUT_VERSION_KEY, LAYOUT_VERSION)
            return

        # Restore window state (includes dock positions)
        state = settings.value("windowState")
        if state:
            if self.restoreState(state):
                logger.debug("Critical docks state restored")

                # Validate critical docks are present
                if not self._validate_dock_state():
                    logger.warning("Critical dock validation failed, resetting layout")
                    self.ui_manager.reset_layout()
                    settings.setValue(SETTINGS_LAYOUT_VERSION_KEY, LAYOUT_VERSION)
            else:
                logger.warning("Failed to restore window state, using default layout")
                self.ui_manager.reset_layout()
                settings.setValue(SETTINGS_LAYOUT_VERSION_KEY, LAYOUT_VERSION)
        else:
            logger.info("No saved state found, using default layout")
            self.ui_manager.reset_layout()
            settings.setValue(SETTINGS_LAYOUT_VERSION_KEY, LAYOUT_VERSION)

    def _restore_optional_docks(self) -> None:
        """
        Stage 3: Restore optional dock configurations.

        Optional docks: longform, map, AI search, graph.
        These enhance functionality but aren't critical for startup.
        """
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Restore Advanced Filter for Unified List
        filter_config = settings.value(SETTINGS_FILTER_CONFIG_KEY)
        if filter_config:
            self.unified_list.set_advanced_filter(filter_config)
            logger.debug("Advanced filter configuration restored")

        # Optional docks are already positioned by restoreState in stage 2
        # This stage is for any additional configuration
        logger.debug("Optional dock restoration complete")

    def _validate_dock_state(self) -> bool:
        """
        Ensures all expected docks are accessible after restoration.

        Returns:
            bool: True if all critical docks are present and valid, False otherwise.
        """
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)

        # Define critical docks that must be present
        expected_docks = ["list", "event", "entity", "timeline"]
        missing_docks = []
        invalid_docks = []

        for dock_key in expected_docks:
            dock = self.ui_manager.docks.get(dock_key)
            if dock is None:
                missing_docks.append(dock_key)
                logger.error(f"Critical dock missing after restoration: {dock_key}")
            elif not isinstance(dock, QDockWidget):
                invalid_docks.append(dock_key)
                logger.error(f"Invalid dock type for {dock_key}: {type(dock)}")
            elif dock.widget() is None:
                invalid_docks.append(dock_key)
                logger.error(f"Dock {dock_key} has no widget")

        if missing_docks or invalid_docks:
            logger.error(
                f"Dock validation failed - Missing: {missing_docks}, "
                f"Invalid: {invalid_docks}"
            )
            return False

        logger.debug("Dock state validation passed")
        return True

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
        self.load_completer_data()

    def load_completer_data(self) -> None:
        """Requests loading of completer data."""
        QMetaObject.invokeMethod(
            self.worker, "load_completer_data", Qt.ConnectionType.QueuedConnection
        )

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

    def set_global_selection(self, item_type: str, item_id: str) -> None:
        """
        Centralized method to handle global item selection.

        Synchronizes all UI components:
        - Editors
        - Unified List (Project Explorer)
        - Graph Focus
        - Timeline Selection
        - Last Selected State

        Args:
            item_type (str): 'event' or 'entity' (or 'events'/'entities').
            item_id (str): The ID of the item to select.
        """
        # 1. Normalize type
        if item_type == "events":
            item_type = "event"
        elif item_type == "entities":
            item_type = "entity"

        # 2. Avoid redundant updates if already selected
        if item_id == self._last_selected_id and item_type == self._last_selected_type:
            return

        # 3. Check for unsaved changes before switching context
        # Determine target editor to check
        target_editor = (
            self.event_editor if item_type == "event" else self.entity_editor
        )
        if not self.check_unsaved_changes(target_editor):
            return

        # 4. Perform Selection & UI Updates
        logger.debug(f"[MainWindow] Global selection: {item_type}/{item_id}")

        self._last_selected_id = item_id
        self._last_selected_type = item_type

        # Update Settings
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, item_id)
        settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, item_type)

        if item_type == "event":
            self.ui_manager.docks["event"].raise_()
            self.load_event_details(item_id)
            # Sync Timeline (if method exists)
            # if hasattr(self.timeline, "select_event"):
            #     self.timeline.select_event(item_id)

        elif item_type == "entity":
            self.ui_manager.docks["entity"].raise_()
            self.load_entity_details(item_id)

        # 5. Sync Project Explorer (Unified List)
        # This ensures the list highlights the item even if selected via Graph/Link
        self.unified_list.select_item(item_type, item_id)

        # 6. Sync Graph (Focus Node)
        # Prevent infinite loop if this call came from graph click?
        # GraphWidget.focus_node usually checks if already focused.
        # But we need to be careful. For now, we trust the graph to handle re-focus efficiently.
        # self.graph_widget.focus_node(item_id) # TO BE IMPLEMENTED in GraphWidget if needed

    def _on_item_selected(self, item_type: str, item_id: str) -> None:
        """Handles selection from unified list or longform editor."""
        self.set_global_selection(item_type, item_id)

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
        from src.app.constants import LAYOUT_VERSION, SETTINGS_LAYOUT_VERSION_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue(SETTINGS_LAYOUT_VERSION_KEY, LAYOUT_VERSION)

        # Save as Default Layout if requested
        if self.capture_layout_on_exit:
            self.ui_manager.save_as_default_layout()

        # Save Persistent Widget States
        if hasattr(self, "timeline"):
            self.timeline.save_state()

        # Stop debounce timer to prevent callbacks during shutdown
        if self._graph_reload_timer is not None:
            self._graph_reload_timer.stop()

        # Stop auto-backup timer if running
        if self.backup_service is not None:
            self.backup_service.stop_auto_backup()

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
        logger.debug(
            f"[MainWindow] _on_reload_active_editor_relations: "
            f"event_id={self.event_editor._current_event_id}, "
            f"entity_id={self.entity_editor._current_entity_id}, "
            f"active_type={self._last_selected_type}"
        )

        # Only reload the currently selected type to prevent focus jumping
        # If we reload both, the DataHandler triggers 'raise_dock' for each,
        # causing the last one loaded (usually Entity) to steal focus.
        if self._last_selected_type == "event" and self.event_editor._current_event_id:
            logger.debug("[MainWindow] Reloading active event details")
            self.load_event_details(self.event_editor._current_event_id)

        elif (
            self._last_selected_type == "entity"
            and self.entity_editor._current_entity_id
        ):
            logger.debug("[MainWindow] Reloading active entity details")
            self.load_entity_details(self.entity_editor._current_entity_id)

        # If active type is none or mismatch, we might want to reload both safely?
        # But generally, we only care about what the user is looking at.

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
        logger.info(
            f"[MainWindow] update_event: id={event_id}, "
            f"name='{event_data.get('name', '?')}'"
        )
        if not event_id:
            logger.error("[MainWindow] update_event aborted - no ID")
            return

        cmd = UpdateEventCommand(event_id, event_data)
        logger.debug("[MainWindow] Emitting UpdateEventCommand")
        self.command_requested.emit(cmd)

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            logger.debug("[MainWindow] Emitting ProcessWikiLinksCommand")
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
        logger.info(
            f"[MainWindow] update_entity: id={entity_id}, "
            f"name='{entity_data.get('name', '?')}'"
        )
        # Log full data for debugging
        logger.debug(f"[MainWindow] Entity data keys: {list(entity_data.keys())}")
        if "description" in entity_data:
            desc_preview = (
                entity_data["description"][:100]
                if entity_data["description"]
                else "(empty)"
            )
            logger.debug(f"[MainWindow] Description preview: {desc_preview}")

        if not entity_id:
            logger.error("[MainWindow] update_entity aborted - no ID")
            return

        cmd = UpdateEntityCommand(entity_id, entity_data)
        logger.debug("[MainWindow] Emitting UpdateEntityCommand")
        self.command_requested.emit(cmd)

        if "description" in entity_data:
            wiki_cmd = ProcessWikiLinksCommand(entity_id, entity_data["description"])
            logger.debug("[MainWindow] Emitting ProcessWikiLinksCommand")
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

    def on_completer_data_loaded(
        self,
        tags: list[str],
        rel_types: list[str],
        attr_keys: list[str],
        entity_types: list[str],
    ) -> None:
        """
        Handler for completer data loaded from worker.
        Updates suggestions in both Entity and Event editors.
        """
        # Update Entity Editor
        self.entity_editor.update_tag_suggestions(tags)
        self.entity_editor.update_attribute_suggestions(attr_keys)
        self.entity_editor.update_relation_type_suggestions(rel_types)
        self.entity_editor.update_entity_type_suggestions(entity_types)

        # Update Event Editor
        self.event_editor.update_tag_suggestions(tags)
        self.event_editor.update_attribute_suggestions(attr_keys)
        self.event_editor.update_relation_type_suggestions(rel_types)

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
            self,
            available_tags=tags,
            current_config=self.unified_list.get_advanced_filter_config(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_filter_config()
            # self.filter_config = config  # Removed

            # Save to settings
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            settings.setValue(SETTINGS_FILTER_CONFIG_KEY, config)

            logger.info(f"Applying filter: {config}")
            # Send to worker via signal if needed, but for now UnifiedList handles it locally
            # self.filter_requested.emit(config) # kept if other widgets need it?
            # Actually, user wants widgets to maintain own settings.
            # If Graph/Timeline need it, they should have their own.
            # For now, we update UnifiedList directly.
            self.unified_list.set_advanced_filter(config)

            # Update UI state (handled by set_advanced_filter)
            # has_filter = bool(config.get("include") or config.get("exclude"))
            # self.unified_list.set_filter_active(has_filter)

    def clear_filter(self) -> None:
        """
        Clears the current filter configuration and reloads data.
        """
        logger.info("Clearing filters")
        self.unified_list.set_advanced_filter({})

        # Clear settings
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.remove(SETTINGS_FILTER_CONFIG_KEY)

        # Update UI state - handled by set_advanced_filter
        self.status_bar.showMessage("Filters cleared.")

        # Reload full data? Not strictly needed if we just clear the filter,
        # but if we want to ensure sync...
        # Actually set_advanced_filter triggers re-render.
        # But if the user expects a "Reload", we can keep it.
        # Let's keep load_data() to be safe, though likely redundant for the list itself.
        self.load_data()
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
                self.set_global_selection("entity", entity.id)
                return

            event = next((e for e in self._cached_events if e.id == target), None)
            if event:
                self.set_global_selection("event", event.id)
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
                self.set_global_selection("entity", entity.id)
                return

            # Also check events for name-based links
            event = next(
                (e for e in self._cached_events if e.name.lower() == target.lower()),
                None,
            )

            if event:
                self.set_global_selection("event", event.id)
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

    @Slot()
    def create_manual_backup(self) -> None:
        """Creates a manual backup with optional description."""
        if self.backup_service is None:
            QMessageBox.warning(
                self, "Backup Unavailable", "Backup service is not initialized."
            )
            return

        # Ask user for optional description
        description, ok = QInputDialog.getText(
            self, "Create Backup", "Backup description (optional):"
        )
        if not ok:
            return  # User cancelled

        from src.services.backup_service import BackupType

        # Create backup
        self.status_bar.showMessage("Creating backup...")
        QApplication.processEvents()

        metadata = self.backup_service.create_backup(
            backup_type=BackupType.MANUAL, description=description
        )

        if metadata:
            self.status_bar.showMessage(
                f"Backup created: {metadata.backup_path.name}", 5000
            )
            QMessageBox.information(
                self,
                "Backup Created",
                f"Backup created successfully!\n\n"
                f"Location: {metadata.backup_path}\n"
                f"Size: {metadata.size / 1024:.1f} KB",
            )
        else:
            self.status_bar.showMessage("Backup failed", 5000)
            QMessageBox.critical(
                self,
                "Backup Failed",
                "Failed to create backup. Check logs for details.",
            )

    @Slot()
    def restore_from_backup(self) -> None:
        """Restores database from a backup file."""
        if self.backup_service is None:
            QMessageBox.warning(
                self, "Backup Unavailable", "Backup service is not initialized."
            )
            return

        from PySide6.QtWidgets import QFileDialog

        # Get backup file from user
        backup_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File",
            str(self.backup_service.config.backup_dir or ""),
            "Kraken Database (*.kraken)",
        )

        if not backup_file:
            return  # User cancelled

        from pathlib import Path

        # Warn user about restoration
        reply = QMessageBox.question(
            self,
            "Restore Backup",
            "Restoring will replace the current database.\n"
            "A safety backup will be created first.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Restore backup
        self.status_bar.showMessage("Restoring from backup...")
        QApplication.processEvents()

        success = self.backup_service.restore_backup(
            Path(backup_file), Path(self.db_path)
        )

        if success:
            self.status_bar.showMessage("Restore completed", 5000)
            QMessageBox.information(
                self,
                "Restore Complete",
                "Database restored successfully!\n\n"
                "The application will now close. Please restart to use the restored database.",
            )
            # Close application so user can restart
            self.close()
        else:
            self.status_bar.showMessage("Restore failed", 5000)
            QMessageBox.critical(
                self,
                "Restore Failed",
                "Failed to restore backup. Check logs for details.",
            )

    @Slot()
    def show_backup_location(self) -> None:
        """Opens the backup directory in the system file explorer."""
        if self.backup_service is None:
            QMessageBox.warning(
                self, "Backup Unavailable", "Backup service is not initialized."
            )
            return

        import os
        import subprocess
        import sys
        from pathlib import Path

        from src.core.paths import get_backup_directory

        # Use configured backup directory if set, otherwise use default
        if self.backup_service.config.backup_dir:
            backup_dir = Path(self.backup_service.config.backup_dir)
        else:
            backup_dir = get_backup_directory()

        backup_dir_str = str(backup_dir)
        logger.debug(f"show_backup_location: backup_dir = {backup_dir_str}")

        # Ensure directory exists - use os.makedirs for explicit creation
        try:
            os.makedirs(backup_dir_str, exist_ok=True)
            logger.debug("show_backup_location: os.makedirs completed")
        except OSError as e:
            logger.error(f"Failed to create backup directory: {e}")
            QMessageBox.warning(
                self,
                "Backup Location Error",
                f"Could not create backup directory:\n{backup_dir_str}\n\nError: {e}",
            )
            return

        # Verify directory actually exists before opening
        exists = os.path.isdir(backup_dir_str)
        logger.debug(f"show_backup_location: exists check = {exists}")
        if not exists:
            logger.error(f"Backup directory does not exist: {backup_dir_str}")
            QMessageBox.warning(
                self,
                "Backup Location Error",
                f"Backup directory could not be created:\n{backup_dir_str}",
            )
            return

        logger.info(f"Opening backup location: {backup_dir_str}")

        # Open directory in file explorer
        try:
            if sys.platform == "win32":
                # Use os.startfile on Windows - more reliable than subprocess
                os.startfile(backup_dir_str)
            elif sys.platform == "darwin":
                subprocess.run(["open", backup_dir_str], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", backup_dir_str], check=False)
        except Exception as e:
            logger.error(f"Failed to open backup directory: {e}")
            QMessageBox.information(
                self, "Backup Location", f"Backup directory:\n{backup_dir_str}"
            )

    @Slot()
    def show_backup_settings(self) -> None:
        """Opens the backup settings dialog and applies changes to BackupService."""
        from pathlib import Path

        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
        from src.core.backup_config import BackupConfig
        from src.gui.dialogs.backup_settings_dialog import (
            BACKUP_AUTO_SAVE_INTERVAL_KEY,
            BACKUP_AUTO_SAVE_RETENTION_KEY,
            BACKUP_CUSTOM_DIR_KEY,
            BACKUP_DAILY_RETENTION_KEY,
            BACKUP_ENABLED_KEY,
            BACKUP_EXTERNAL_PATH_KEY,
            BACKUP_MANUAL_RETENTION_KEY,
            BACKUP_VACUUM_BEFORE_KEY,
            BACKUP_VERIFY_AFTER_KEY,
            BACKUP_WEEKLY_RETENTION_KEY,
            BackupSettingsDialog,
        )

        dialog = BackupSettingsDialog(self)

        def apply_settings() -> None:
            """Apply dialog settings to BackupService."""
            if self.backup_service is None:
                return

            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

            # Build config from QSettings
            custom_dir = settings.value(BACKUP_CUSTOM_DIR_KEY, "")
            external_path = settings.value(BACKUP_EXTERNAL_PATH_KEY, "")

            config = BackupConfig(
                enabled=settings.value(BACKUP_ENABLED_KEY, True, type=bool),
                auto_save_interval_minutes=int(
                    settings.value(BACKUP_AUTO_SAVE_INTERVAL_KEY, 5)
                ),
                auto_save_retention_count=int(
                    settings.value(BACKUP_AUTO_SAVE_RETENTION_KEY, 12)
                ),
                daily_retention_count=int(
                    settings.value(BACKUP_DAILY_RETENTION_KEY, 7)
                ),
                weekly_retention_count=int(
                    settings.value(BACKUP_WEEKLY_RETENTION_KEY, 4)
                ),
                manual_retention_count=int(
                    settings.value(BACKUP_MANUAL_RETENTION_KEY, -1)
                ),
                verify_after_backup=settings.value(
                    BACKUP_VERIFY_AFTER_KEY, True, type=bool
                ),
                vacuum_before_backup=settings.value(
                    BACKUP_VACUUM_BEFORE_KEY, False, type=bool
                ),
                backup_dir=Path(custom_dir) if custom_dir else None,
                external_backup_path=Path(external_path) if external_path else None,
            )

            self.backup_service.update_config(config)
            logger.info("Backup settings applied to service")

        dialog.settings_changed.connect(apply_settings)
        dialog.exec()

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
