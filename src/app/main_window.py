"""MainWindow Class.

The main application window that manages UI components, database workers, and
signal/slot connections.
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
from PySide6.QtGui import QCloseEvent, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStatusBar,
    QWidget,
    QGraphicsOpacityEffect,
)

from src.app.ai_search_manager import AISearchManager
from src.app.command_coordinator import CommandCoordinator
from src.app.connection_manager import ConnectionManager
from src.app.constants import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    FOCUS_MODE_OPACITY,
    SETTINGS_ACTIVE_DB_KEY,
    SETTINGS_AUTO_RELATION_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    UI_DOCK_RESTORE_DELAY_MS,
    UI_INIT_DELAY_MS,
    UI_OPTIONAL_DOCK_DELAY_MS,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)
from src.app.coordinators.backup_coordinator import BackupCoordinator
from src.app.coordinators.fast_inject_coordinator import FastInjectCoordinator
from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox
from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.app.coordinators.time_coordinator import TimeCoordinator
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
from src.commands.composite_command import CompositeCommand
from src.core.fast_inject import FastInjectManager
from src.core.logging_config import get_logger
from src.core.paths import get_worlds_dir
from src.gui.dialogs.database_manager_dialog import DatabaseManagerDialog
from src.gui.dialogs.filter_dialog import FilterDialog
from src.gui.dialogs.import_preview_dialog import ImportPreviewDialog
from src.gui.mixins.layout_guard import LayoutGuardMixin
from src.gui.widgets.ai_search_panel import AISearchPanelWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view.graph_widget import GraphWidget
from src.gui.widgets.longform import LongformEditorWidget
from src.gui.widgets.map_widget import MapWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget
from PySide6.QtCore import QObject, QEvent

logger = get_logger(__name__)


class GlobalShortcutFilter(QObject):
    """Event filter that intercepts global keyboard shortcuts.

    Installed on QApplication to capture Ctrl+Z (Undo) and Ctrl+Y/Ctrl+Shift+Z
    (Redo) before individual widgets can consume them.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the filter with a reference to the main window.

        Args:
            main_window: The MainWindow instance to route commands to.

        """
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter key events and intercept global shortcuts.

        Args:
            obj: The object receiving the event.
            event: The event to filter.

        Returns:
            True if the event was handled (consumed), False otherwise.

        """
        if event.type() == QEvent.Type.KeyPress:
            key_event = event  # type: QKeyEvent
            key = key_event.key()
            modifiers = key_event.modifiers()

            # Check for Ctrl+Z (Undo)
            if key == Qt.Key.Key_Z and modifiers == Qt.KeyboardModifier.ControlModifier:
                if hasattr(self.main_window, "coordinator"):
                    if self.main_window.coordinator.can_undo():
                        self.main_window.coordinator.undo()
                        return True  # Consume the event

            # Check for Ctrl+Y (Redo)
            if key == Qt.Key.Key_Y and modifiers == Qt.KeyboardModifier.ControlModifier:
                if hasattr(self.main_window, "coordinator"):
                    if self.main_window.coordinator.can_redo():
                        self.main_window.coordinator.redo()
                        return True  # Consume the event

            # Check for Ctrl+Shift+Z (Redo alternative)
            if key == Qt.Key.Key_Z and modifiers == (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            ):
                if hasattr(self.main_window, "coordinator"):
                    if self.main_window.coordinator.can_redo():
                        self.main_window.coordinator.redo()
                        return True  # Consume the event

            # Check for Ctrl+E (Create Event)
            if key == Qt.Key.Key_E and modifiers == Qt.KeyboardModifier.ControlModifier:
                if hasattr(self.main_window, "list_widget"):
                    self.main_window.list_widget.action_create_event.trigger()
                    return True

            # Check for Ctrl+I (Create Entity)
            if key == Qt.Key.Key_I and modifiers == Qt.KeyboardModifier.ControlModifier:
                if hasattr(self.main_window, "list_widget"):
                    self.main_window.list_widget.action_create_entity.trigger()
                    return True

            # Check for Ctrl+M (Create Map)
            if key == Qt.Key.Key_M and modifiers == Qt.KeyboardModifier.ControlModifier:
                if hasattr(self.main_window, "list_widget"):
                    self.main_window.list_widget.action_create_map.trigger()
                    return True

        return False  # Don't consume, let event propagate


class MainWindow(QMainWindow, LayoutGuardMixin):
    """The main application window.

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
        """Initializes the MainWindow using three-phase initialization.

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

        # Apply Windows Title Bar Style based on current theme
        try:
            from src.gui.utils.window_utils import apply_windows_title_bar_style
            from src.core.theme_manager import ThemeManager

            # Apply based on current theme
            theme_name = ThemeManager().current_theme_name
            dark_mode = "dark" in theme_name.lower()
            apply_windows_title_bar_style(self, dark_mode=dark_mode)

            # Connect to theme changes to update title bar
            ThemeManager().theme_changed.connect(self._on_theme_changed_for_titlebar)
        except Exception as e:
            logger.warning(f"Failed to apply title bar style: {e}")

        # Phase 2: UI skeleton (no data dependencies)
        self._init_widgets_skeleton()
        logger.debug("Phase 2: Widget skeleton created")

        # Phase 3: Deferred initialization (after event loop starts)
        QTimer.singleShot(UI_INIT_DELAY_MS, self._complete_initialization)
        logger.debug("Phase 3: Deferred initialization scheduled")

        # Install global shortcut filter for Undo/Redo
        from PySide6.QtWidgets import QApplication

        self._global_shortcut_filter = GlobalShortcutFilter(self)
        if app := QApplication.instance():
            app.installEventFilter(self._global_shortcut_filter)
            logger.debug("Global shortcut filter installed")

    def _init_core_services(self) -> None:
        """Phase 1: Initialize core services and infrastructure.

        Sets up data handler, worker thread, and basic window properties.
        No widgets or UI elements created here.
        """
        # Load active world name for title
        settings = QSettings()
        active_world_name = settings.value(SETTINGS_ACTIVE_DB_KEY, "Default World")

        self.setWindowTitle(f"{WINDOW_TITLE} - {active_world_name}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Current world reference (will be set by worker_manager)
        self.setWindowTitle(f"{WINDOW_TITLE} - {active_world_name}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Current world reference (will be set by worker_manager)
        self.current_world = None
        # Default db_path to empty string for safe initialization/mocking
        self.db_path = ""

        # Connect Theme Manager Signal
        try:
            from src.core.theme_manager import ThemeManager

            tm = ThemeManager()
            tm.theme_changed.connect(self._update_window_style)
        except Exception as e:
            logger.warning(f"Failed to connect theme signal: {e}")

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
        self._graph_reload_timer: QTimer | None = None
        self._import_progress_dialog: Optional["QProgressDialog"] = None

    def _update_window_style(self, theme_data: dict) -> None:
        """Updates the Windows title bar style based on the current theme.

        Args:
            theme_data: The dictionary containing theme colors.
        """
        try:
            from PySide6.QtGui import QColor

            from src.gui.utils.window_utils import apply_windows_title_bar_style

            app_bg = theme_data.get("app_bg", "#2B2B2B")
            text_main = theme_data.get("text_main", "#E0E0E0")

            # Determine if dark mode (simple heuristic or based on theme name logic)
            # Generally, if app_bg is dark, we want dark mode.
            bg_color = QColor(app_bg)
            is_dark = bg_color.lightness() < 128

            apply_windows_title_bar_style(
                self,
                dark_mode=is_dark,
                title_color=bg_color,
                text_color=QColor(text_main),
            )
        except Exception as e:
            logger.warning(f"Failed to update window style: {e}")

    def _create_status_label(self, text: str, color: str) -> QLabel:
        """Creates a styled status bar label."""
        lbl = QLabel(text)
        lbl.setMinimumWidth(250)
        lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.status_bar.addPermanentWidget(lbl)
        return lbl

    def _init_widgets_skeleton(self) -> None:
        """Phase 2: Create UI skeleton without data dependencies.

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

        # Create History Panel (Phase 3)
        from src.gui.widgets.history_panel import HistoryPanelWidget

        self.history_panel = HistoryPanelWidget()

        # Create Toast Notification (Sprint 1)
        self._last_drag_drop_command_id = None  # Track last drag-drop command for toast

        # Initialize Managers
        self.map_handler = MapHandler(self)
        self.grouping_manager = TimelineGroupingManager(self)
        self.ai_settings_dialog = None
        self.ai_search_manager = AISearchManager(self)
        self.longform_manager = LongformManager(self)

        # Initialize Fast Inject Manager
        # We need the world path.
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        active_world = settings.value(SETTINGS_ACTIVE_DB_KEY, "Default World")
        world_path = get_worlds_dir() / active_world
        self.fast_inject_manager = FastInjectManager(world_path)

        # Pass project root to editors for proper gallery path resolution
        self.event_editor.set_project_root(world_path)
        self.entity_editor.set_project_root(world_path)

        # Initialize Coordinators (Phase 1)
        self.fast_inject_coordinator = FastInjectCoordinator(self)
        self.navigation_coordinator = NavigationCoordinator(self)
        self.backup_coordinator = BackupCoordinator(self)
        self.time_coordinator = TimeCoordinator(self)

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
                "history_panel": self.history_panel,
            }
        )

        # Central Widget
        self.setCentralWidget(QWidget())
        self.centralWidget().hide()

        # Status Bar Time Labels
        self.lbl_world_time = self._create_status_label("World: --", "#3498db")
        self.lbl_playhead_time = self._create_status_label("Playhead: --", "#e74c3c")

        # Create Menus
        self.ui_manager.create_file_menu(self.menuBar())
        self.ui_manager.create_edit_menu(self.menuBar())  # Add Edit menu
        self.ui_manager.create_timeline_menu(self.menuBar())
        self.ui_manager.create_view_menu(self.menuBar())
        self.ui_manager.create_settings_menu(self.menuBar())
        self.ui_manager.create_help_menu(self.menuBar())

        # Initialize Longform auto-refresh state (default: True)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        auto_refresh = settings.value("longform_auto_refresh", True, type=bool)
        self.longform_editor.set_refresh_button_visible(not auto_refresh)

    def _complete_initialization(self) -> None:
        """Phase 3: Complete initialization after event loop starts.

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
        self.coordinator = self.command_coordinator  # Alias for shorter access
        self.command_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )
        # Connect undo/redo signals to worker
        self.command_coordinator.undo_requested.connect(
            self.worker.run_undo, Qt.ConnectionType.QueuedConnection
        )
        self.command_coordinator.redo_requested.connect(
            self.worker.run_redo, Qt.ConnectionType.QueuedConnection
        )
        # Update UI when history changes
        self.command_coordinator.history_changed.connect(
            self.ui_manager.update_undo_redo_state
        )
        # Connect history panel to coordinator
        self.command_coordinator.history_changed.connect(self._update_history_panel)
        # Connect history panel buttons to coordinator
        self.history_panel.undo_clicked.connect(self.command_coordinator.undo)
        self.history_panel.redo_clicked.connect(self.command_coordinator.redo)
        self.history_panel.clear_history_clicked.connect(
            self.command_coordinator.clear_history
        )
        # Connect worker's command results to coordinator for undo stack management
        self.worker.command_finished.connect(
            self.command_coordinator.on_command_result,
            Qt.ConnectionType.QueuedConnection,
        )

        # Connect undo/redo menu actions (deferred from Phase 2)
        self.ui_manager.connect_undo_redo_actions()

        # Connect editor dirty signals (these are safe to connect early)
        self.event_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.event_editor, dirty)
        )
        self.entity_editor.dirty_changed.connect(
            lambda dirty: self._on_editor_dirty_changed(self.entity_editor, dirty)
        )

        # Connect Fast Inject Signals (Delegated to Coordinator)
        self.entity_editor.inject_ui_requested.connect(
            self.fast_inject_coordinator.request_fast_inject_for_entity
        )
        self.entity_editor.create_template_requested.connect(
            self.fast_inject_coordinator.request_create_template
        )
        self.event_editor.inject_ui_requested.connect(
            self.fast_inject_coordinator.request_fast_inject_for_event
        )
        self.event_editor.create_template_requested.connect(
            self.fast_inject_coordinator.request_create_template
        )

        # Connect Summary Generation Signals
        self.entity_editor.summary_generation_requested.connect(
            self.worker_manager.generate_summary
        )
        self.event_editor.summary_generation_requested.connect(
            self.worker_manager.generate_summary
        )

        # Initialize Focus Mode
        self._init_focus_mode()

        # Connect to worker's command_finished to show toast for
        # drag-drop relations (Sprint 1)
        self.worker.command_finished.connect(
            self._on_command_finished_check_toast, Qt.ConnectionType.QueuedConnection
        )

        # Connect Coordinator Signals
        self.fast_inject_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )
        self.fast_inject_coordinator.status_message_requested.connect(
            lambda msg, timeout: self.status_bar.showMessage(msg, timeout)
        )

        # Initialize Database
        QMetaObject.invokeMethod(
            self.worker, "initialize_db", Qt.ConnectionType.QueuedConnection
        )

        # Apply initial Windows Title Bar Style (deferred until window is ready)
        try:
            from src.core.theme_manager import ThemeManager

            self._update_window_style(ThemeManager().get_theme())
        except Exception as e:
            logger.warning(f"Failed to apply initial title bar style: {e}")

        # Restore Window State
        self._restore_window_state()

        # Restore Selection (delegated)
        self.navigation_coordinator.restore_last_selection()

        # Connect Timeline Selection (Sync to Global)
        self.timeline.event_selected.connect(
            lambda eid: self.navigation_coordinator.on_item_selected("event", eid)
        )

        logger.debug("Initialization complete")

    @property
    def list_dock(self) -> QDockWidget:
        """Gets the project list dock widget.

        Returns:
            QDockWidget: The dock widget containing the unified list.

        """
        return self.ui_manager.docks.get("list")

    @property
    def editor_dock(self) -> QDockWidget:
        """Gets the event editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the event editor.

        """
        return self.ui_manager.docks.get("event")

    @property
    def entity_editor_dock(self) -> QDockWidget:
        """Gets the entity editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the entity editor.

        """
        return self.ui_manager.docks.get("entity")

    @property
    def timeline_dock(self) -> QDockWidget:
        """Gets the timeline dock widget.

        Returns:
            QDockWidget: The dock widget containing the timeline.

        """
        return self.ui_manager.docks.get("timeline")

    @property
    def longform_dock(self) -> QDockWidget:
        """Gets the longform editor dock widget.

        Returns:
            QDockWidget: The dock widget containing the longform editor.

        """
        return self.ui_manager.docks.get("longform")

    @property
    def map_dock(self) -> QDockWidget:
        """Gets the map dock widget.

        Returns:
            QDockWidget: The dock widget containing the map.

        """
        return self.ui_manager.docks.get("map")

    def _restore_window_state(self) -> None:
        """Restores window geometry and state using staged approach.

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
                "Crash flag detected - considering safety measures "
                "(logging only for now)"
            )
            # We could force reset here if enabled

        # Stage 2: Critical docks after defined delay
        QTimer.singleShot(UI_DOCK_RESTORE_DELAY_MS, self._restore_critical_docks)

        # Stage 3: Optional docks after longer delay
        QTimer.singleShot(UI_OPTIONAL_DOCK_DELAY_MS, self._restore_optional_docks)

    def _restore_geometry(self) -> None:
        """Stage 1: Restore window geometry immediately.

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
        if geometry := settings.value("geometry"):
            # Use Guard implementation
            if self.guard_restore_geometry(geometry):
                logger.debug("Window geometry restored safely")
            else:
                logger.warning("Failed to restore window geometry")
        else:
            logger.debug("No saved geometry found")

    def _restore_critical_docks(self) -> None:
        """Stage 2: Restore critical docks and their state.

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
        if state := settings.value("windowState"):
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
        """Stage 3: Restore optional dock configurations.

        Optional docks: longform, map, AI search, graph.
        These enhance functionality but aren't critical for startup.
        """
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Restore Advanced Filter for Unified List
        if filter_config := settings.value(SETTINGS_FILTER_CONFIG_KEY):
            self.unified_list.set_advanced_filter(filter_config)
            logger.debug("Advanced filter configuration restored")

        # Optional docks are already positioned by restoreState in stage 2
        # This stage is for any additional configuration
        logger.debug("Optional dock restoration complete")

    def _validate_dock_state(self) -> bool:
        """Ensures all expected docks are accessible after restoration.

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
        """Placeholder for generalized update.

        Currently unused as we split update_event/entity.
        """
        pass

    def load_data(self) -> None:
        """Refreshes data and active editors."""
        self.load_events()
        self.load_entities()
        self.load_longform_sequence()
        self.load_graph_data()
        self.load_completer_data()

        # Reload active editors to ensure they reflect current state (e.g. after undo)
        # This prevents the editor from holding onto "future" state that might be
        # auto-saved, restoring the undone change.
        if (
            hasattr(self.event_editor, "_current_event_id")
            and self.event_editor._current_event_id
        ):
            self.load_event_details(self.event_editor._current_event_id)

        if (
            hasattr(self.entity_editor, "_current_entity_id")
            and self.entity_editor._current_entity_id
        ):
            self.load_entity_details(self.entity_editor._current_entity_id)

    def load_completer_data(self) -> None:
        """Requests loading of completer data."""
        QMetaObject.invokeMethod(
            self.worker, "load_completer_data", Qt.ConnectionType.QueuedConnection
        )

    def load_longform_sequence(self) -> None:
        """Loads the longform sequence, applying active filters if any."""
        self.longform_manager.load_longform_sequence()

    @Slot(list)
    def _on_longform_sequence_loaded(self, sequence: list) -> None:
        """Handler for when longform sequence is loaded."""
        self.longform_manager.on_longform_sequence_loaded(sequence)

    # Removed: set_global_selection logic moved to NavigationCoordinator

    # Removed: _on_item_selected logic moved to NavigationCoordinator

    def check_unsaved_changes(self, editor: QWidget) -> bool:
        """Checks if the editor has unsaved changes and prompts the user.

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
            if dock := self.ui_manager.docks.get(dock_key):
                new_title = base_title + (" *" if dirty else "")
                dock.setWindowTitle(new_title)

    @Slot(str, str)
    def _on_item_delete_requested(self, item_type: str, item_id: str) -> None:
        """Handles deletion request from unified list."""
        if item_type == "event":
            self.delete_event(item_id)
        elif item_type == "entity":
            self.delete_entity(item_id)

    @Slot()
    def _update_history_panel(self) -> None:
        """Update the history panel with current undo/redo stacks."""
        try:
            if hasattr(self, "history_panel") and hasattr(self, "command_coordinator"):
                self.history_panel.update_history(
                    self.command_coordinator.undo_stack,
                    self.command_coordinator.redo_stack,
                )
        except Exception as e:
            logger.error(f"Failed to update history panel: {e}")

    @Slot(str)
    def update_status_message(self, message: str) -> None:
        """Updates the status bar message and sets cursor to Wait.

        Args:
            message (str): The message to display.

        """
        self.worker_manager.update_status_message(message)

    def clear_status_message(self, message: str) -> None:
        """Clears the status bar message after a delay and restores cursor.

        Args:
            message (str): The final completion message.

        """
        self.worker_manager.clear_status_message(message)

    @Slot(str)
    def show_error_message(self, message: str) -> None:
        """Displays an error message in the status bar and logs it.

        Args:
            message (str): The error description.

        """
        self.worker_manager.show_error_message(message)

    @Slot(bool)
    def on_db_initialized(self, success: bool) -> None:
        """Handler for database initialization result.

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
        """Handler for calendar config loaded from worker.

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
            self.unified_list.set_calendar_converter(converter)

            # Set calendar converter for timeline display in entity editor
            from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget

            TimelineDisplayWidget.set_calendar_converter(converter)

            # Check if UIManager has a pending calendar dialog
            self.ui_manager.show_calendar_dialog(config)

            # Save converter for status bar formatting
            self.calendar_converter = converter

            # Refresh status bar labels now that we have a converter
            # Refresh status bar labels now that we have a converter
            if hasattr(self, "time_coordinator"):
                self.time_coordinator.update_world_time_label(
                    self.timeline.get_current_time()
                )
                self.time_coordinator.update_playhead_time_label(
                    self.timeline.get_playhead_time()
                )

        except Exception as e:
            logger.warning(f"Failed to initialize calendar converter: {e}")

    def _request_current_time(self) -> None:
        """Requests loading of the current time from the worker."""
        QMetaObject.invokeMethod(
            self.worker, "load_current_time", Qt.ConnectionType.QueuedConnection
        )

    @Slot(float)
    def on_current_time_loaded(self, time: float) -> None:
        """Handler for current time loaded from worker.

        Args:
            time (float): The current time in lore_date units.

        """
        self.timeline.set_current_time(time)
        logger.debug(f"Current time loaded: {time}")

    @Slot()
    def toggle_auto_relation_setting(self) -> None:
        """Toggles the auto-creation of relations from wikilinks."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        current = settings.value(SETTINGS_AUTO_RELATION_KEY, False, type=bool)
        new_value = not current
        settings.setValue(SETTINGS_AUTO_RELATION_KEY, new_value)
        logger.info(f"Auto-relation setting set to: {new_value}")

    @Slot()
    def toggle_longform_auto_refresh(self) -> None:
        """Toggles the auto-refresh setting for Longform Editor."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        # Default to True
        current = settings.value("longform_auto_refresh", True, type=bool)
        new_value = not current
        settings.setValue("longform_auto_refresh", new_value)

        logger.info(f"Longform auto-refresh set to: {new_value}")

        # Update UI state immediately
        if hasattr(self, "longform_editor") and self.longform_editor:
            self.longform_editor.set_refresh_button_visible(not new_value)

        # If turned on, do an immediate refresh to ensure sync
        if new_value:
            self.longform_manager.load_longform_sequence()

    @Slot()
    def _on_auto_refresh_longform(self) -> None:
        """Reloads longform sequence if auto-refresh is enabled."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        # Default to True
        if settings.value("longform_auto_refresh", True, type=bool):
            logger.debug("Auto-refreshing longform editor")
            self.longform_manager.load_longform_sequence()

    def on_command_finished_reload_longform(self) -> None:
        """Handler to reload longform sequence after command completion."""
        self.longform_manager.on_command_finished_reload_longform()

    def _request_grouping_config(self) -> None:
        """Requests loading of the timeline grouping configuration."""
        self.grouping_manager.request_grouping_config()

    def on_grouping_config_loaded(self, config: dict) -> None:
        """Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.

        """
        self.grouping_manager.on_grouping_config_loaded(config)

    def _on_theme_changed_for_titlebar(self, theme_dict: dict) -> None:
        """Update Windows title bar style when theme changes.

        Args:
            theme_dict: The new theme dictionary from ThemeManager.
        """
        try:
            from src.gui.utils.window_utils import apply_windows_title_bar_style
            from src.core.theme_manager import ThemeManager

            # Determine if new theme is dark
            theme_name = ThemeManager().current_theme_name
            dark_mode = "dark" in theme_name.lower()
            apply_windows_title_bar_style(self, dark_mode=dark_mode)
        except Exception as e:
            logger.warning(f"Failed to update title bar style on theme change: {e}")

    def _init_focus_mode(self) -> None:
        """Initialize focus mode connections and keyboard shortcut.

        Connects the focus_mode_changed signals from both entity and event
        editor description widgets to the focus mode handler.
        Sets up Ctrl+Shift+F keyboard shortcut to toggle focus mode.
        """
        from src.gui.utils.shortcut_manager import ShortcutManager

        # Initialize focus mode state
        self._focus_mode_active = False

        # Connect focus mode signals from both editors
        self.entity_editor.desc_edit.focus_mode_changed.connect(
            self._on_focus_mode_changed
        )
        self.event_editor.desc_edit.focus_mode_changed.connect(
            self._on_focus_mode_changed
        )

        # Set up keyboard shortcut (Ctrl+Shift+F)
        from PySide6.QtGui import QAction

        self.action_focus_mode = QAction("Toggle Focus Mode", self)
        self.action_focus_mode.setShortcut(ShortcutManager.FOCUS_MODE.key_sequence)
        self.action_focus_mode.setShortcutContext(
            Qt.ShortcutContext.ApplicationShortcut
        )
        self.action_focus_mode.triggered.connect(self._toggle_focus_mode_from_shortcut)
        self.addAction(self.action_focus_mode)

    @Slot(bool)
    def _on_focus_mode_changed(self, active: bool) -> None:
        """Handle focus mode toggle from editors.

        Dims or restores dock widgets when focus mode is toggled.

        Args:
            active: True if focus mode is being activated, False otherwise.
        """
        self._focus_mode_active = active

        # Get all docks except the ones containing the active editor
        opacity = FOCUS_MODE_OPACITY if active else 1.0

        # Determine which editor is active to exclude it from dimming
        active_editor_dock_name = None
        if (
            self.entity_editor.isVisible()
            and self.entity_editor.desc_edit._focus_mode_active
        ):
            active_editor_dock_name = "entity"
        elif (
            self.event_editor.isVisible()
            and self.event_editor.desc_edit._focus_mode_active
        ):
            active_editor_dock_name = "event"

        for dock_name, dock in self.ui_manager.docks.items():
            if dock is not None:
                # Skip the active editor's dock
                if active and dock_name == active_editor_dock_name:
                    dock.setGraphicsEffect(None)
                    continue

                # Apply opacity effect to all other docks
                if active:
                    # Special handling for GraphWidget, MapWidget, TimelineWidget
                    # These widgets handle opacity internally to avoid artifacts
                    widget = dock.widget()
                    if isinstance(widget, (GraphWidget, MapWidget, TimelineWidget)):
                        widget.set_opacity(opacity)
                        dock.setGraphicsEffect(None)
                    else:
                        effect = QGraphicsOpacityEffect(dock)
                        effect.setOpacity(opacity)
                        dock.setGraphicsEffect(effect)
                else:
                    # Reset opacity for custom widgets
                    widget = dock.widget()
                    if isinstance(widget, (GraphWidget, MapWidget, TimelineWidget)):
                        widget.set_opacity(1.0)
                    dock.setGraphicsEffect(None)

                    dock.setGraphicsEffect(None)

    @Slot()
    def _toggle_focus_mode_from_shortcut(self) -> None:
        """Toggle focus mode via keyboard shortcut.

        Toggles the FC button in whichever editor is currently visible/active.
        Prioritizes entity editor if both are visible.
        """
        # Determine which editor is currently active/visible
        entity_dock = self.ui_manager.docks.get("entity")
        event_dock = self.ui_manager.docks.get("event")

        target_editor = None

        # Check entity editor first
        if entity_dock and entity_dock.isVisible():
            target_editor = self.entity_editor.desc_edit
        # Fall back to event editor
        elif event_dock and event_dock.isVisible():
            target_editor = self.event_editor.desc_edit
        # If neither visible, default to entity editor
        else:
            target_editor = self.entity_editor.desc_edit

        # Toggle the button state (which will emit the signal)
        if target_editor:
            target_editor.btn_focus.setChecked(not target_editor.btn_focus.isChecked())
            target_editor.toggle_focus_mode()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handles application close event.

        Saves window geometry/state and strictly cleans up worker thread. Also checks
        for unsaved changes.
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
        """Populate the database with initial data (Deprecated).

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
        """Get metadata for timeline grouping tags.

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
        """Get events that belong to a specific tag group.

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
        """Requests loading of graph data, optionally filtered.

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
        """Updates the graph widget with loaded data.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.

        """
        if self.graph_widget:
            # Pass the last selected ID to preserve focus
            focus_id = self.navigation_coordinator.selected_id
            self.graph_widget.display_graph(nodes, edges, focus_node_id=focus_id)

    @Slot(list, list)
    def _on_graph_metadata_ready(self, tags: list[str], rel_types: list[str]) -> None:
        """Updates the graph widget with available metadata.

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
        """Handle events ready signal from DataHandler.

        Args:
            events: List of Event objects.

        """
        self._cached_events = events
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)
        logger.info(f"DEBUG: _on_events_ready received {len(events)} events")
        self.unified_list.set_data(self._cached_events, self._cached_entities)
        self.timeline.set_events(events)

        # Refresh graph to reflect changes (debounced)
        self._schedule_graph_refresh()

    @Slot(list)
    def _on_entities_ready(self, entities: list) -> None:
        """Handle entities ready signal from DataHandler.

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
        """Handle suggestions update request from DataHandler.

        Args:
            items: List of (id, name, type) tuples for completion.

        """
        self.event_editor.update_suggestions(items=items)
        self.entity_editor.update_suggestions(items=items)

    @Slot(object, list, list)
    def _on_event_details_ready(
        self, event: object, relations: list, incoming: list
    ) -> None:
        """Handle event details ready signal from DataHandler.

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
        """Handle entity details ready signal from DataHandler.

        Args:
            entity: The Entity object.
            relations: List of outgoing relations.
            incoming: List of incoming relations.

        """
        self.entity_editor.load_entity(entity, relations, incoming)

    @Slot(list)
    def _on_longform_sequence_ready(self, sequence: list) -> None:
        """Handle longform sequence ready signal from DataHandler.

        Args:
            sequence: List of longform items.

        """
        self._cached_longform_sequence = sequence
        self.longform_editor.load_sequence(sequence)

    @Slot(list)
    def _on_maps_ready(self, maps: list) -> None:
        """Handle maps ready signal from DataHandler.

        Args:
            maps: List of Map objects.

        """
        self.map_handler.on_maps_ready(maps)

    @Slot(str, list)
    def _on_markers_ready(self, map_id: str, processed_markers: list) -> None:
        """Handle markers ready signal from DataHandler.

        Args:
            map_id: The map ID these markers belong to.
            processed_markers: List of dicts with marker data.

        """
        self.map_handler.on_markers_ready(map_id, processed_markers)

    @Slot(str)
    def _on_dock_raise_requested(self, dock_name: str) -> None:
        """Handle dock raise request from DataHandler.

        Args:
            dock_name: Name of the dock to raise ("event", "entity", etc).

        """
        if dock_name in self.ui_manager.docks:
            self.ui_manager.docks[dock_name].raise_()

    @Slot(str, str)
    def _on_selection_requested(self, item_type: str, item_id: str) -> None:
        """Handle selection request from DataHandler.

        Args:
            item_type: Type of item ("event" or "entity").
            item_id: ID of the item to select.

        """
        self.unified_list.select_item(item_type, item_id)

    @Slot(str)
    def _on_command_failed(self, message: str) -> None:
        """Handle command failure notification from DataHandler.

        Args:
            message: Error message from the failed command.

        """
        QMessageBox.warning(self, "Command Failed", message)

    @Slot()
    def _on_reload_active_editor_relations(self) -> None:
        """Reload relations for whichever editor is currently active.

        This is called after relation or wiki link commands complete.
        """
        logger.debug(
            f"[MainWindow] _on_reload_active_editor_relations: "
            f"event_id={self.event_editor._current_event_id}, "
            f"entity_id={self.entity_editor._current_entity_id}, "
            f"active_type={self.navigation_coordinator.selected_type}"
        )

        # Only reload the currently selected type to prevent focus jumping
        # If we reload both, the DataHandler triggers 'raise_dock' for each,
        # causing the last one loaded (usually Entity) to steal focus.
        if (
            self.navigation_coordinator.selected_type == "event"
            and self.event_editor._current_event_id
        ):
            logger.debug("[MainWindow] Reloading active event details")
            self.load_event_details(self.event_editor._current_event_id)

        elif (
            self.navigation_coordinator.selected_type == "entity"
            and self.entity_editor._current_entity_id
        ):
            logger.debug("[MainWindow] Reloading active entity details")
            self.load_entity_details(self.entity_editor._current_entity_id)

        # If active type is none or mismatch, we might want to reload both safely?
        # But generally, we only care about what the user is looking at.

    def delete_event(self, event_id: str) -> None:
        """Deletes an event by emitting a delete command.

        Args:
            event_id (str): The ID of the event to delete.

        """
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def update_event(self, event_data: dict) -> None:
        """Updates an event with the provided data.

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

        cmds = []
        cmds.append(UpdateEventCommand(event_id, event_data))

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            cmds.append(wiki_cmd)

        if len(cmds) > 1:
            desc = f"Update Event '{event_data.get('name', '?')}'"
            cmd = CompositeCommand(cmds, description=desc)
            logger.debug("[MainWindow] Emitting CompositeCommand (Update+Wiki)")
        else:
            cmd = cmds[0]
            logger.debug(f"[MainWindow] Emitting {cmd.__class__.__name__}")

        self.command_requested.emit(cmd)

    @Slot(str, float)
    def _on_event_date_changed(self, event_id: str, new_lore_date: float) -> None:
        """Handles event date changes from timeline dragging. Persists the new lore_date
        via UpdateEventCommand.

        Args:
            event_id: The ID of the event that was dragged.
            new_lore_date: The new lore_date value.

        """
        logger.debug(f"Event {event_id} date changed to {new_lore_date}")
        cmd = UpdateEventCommand(event_id, {"lore_date": new_lore_date})
        self.command_requested.emit(cmd)

    @Slot(object)
    def _on_command_finished_check_toast(self, result) -> None:
        """Check if completed command was a drag-drop relation and show toast.

        Args:
            result: CommandResult object from worker.
        """
        # Check if this was a drag-drop relation command
        if not result.success:
            return

        command = result.data.get("command")
        if command is None:
            return

        # Check if this is the drag-drop command we're tracking
        if id(command) == self._last_drag_drop_command_id:
            # This was our drag-drop command, show toast
            self._show_relation_created_toast()
            # Clear the tracking ID
            self._last_drag_drop_command_id = None

    def _show_relation_created_toast(self) -> None:
        """Show toast notification for successful relation creation."""
        # Use AutoClosingMessageBox for consistency with deletion toast (themed + timed)
        msg = "Relation created.\n\n(Ctrl+Z to Undo)"
        popup = AutoClosingMessageBox("Success", msg, 1500, parent=self)
        popup.exec()

        logger.debug("Drag-drop relation toast displayed")

    def create_entity(self) -> None:
        """Creates a new entity by emitting a create command."""
        if not self.check_unsaved_changes(self.entity_editor):
            return

        name, ok = QInputDialog.getText(self, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEntityCommand({"name": name.strip(), "type": "Concept"})
        self.command_requested.emit(cmd)

    def create_event(self) -> None:
        """Creates a new event by emitting a create command."""
        if not self.check_unsaved_changes(self.event_editor):
            return

        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEventCommand({"name": name.strip(), "lore_date": 0.0})
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id: str) -> None:
        """Deletes an entity by emitting a delete command.

        Args:
            entity_id (str): The ID of the entity to delete.

        """
        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    def update_entity(self, entity_data: dict) -> None:
        """Updates an entity with the provided data.

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

        cmds = []
        cmds.append(UpdateEntityCommand(entity_id, entity_data))

        if "description" in entity_data:
            wiki_cmd = ProcessWikiLinksCommand(entity_id, entity_data["description"])
            cmds.append(wiki_cmd)

        if len(cmds) > 1:
            desc = f"Update Entity '{entity_data.get('name', '?')}'"
            cmd = CompositeCommand(cmds, description=desc)
            logger.debug("[MainWindow] Emitting CompositeCommand (Update+Wiki)")
        else:
            cmd = cmds[0]
            logger.debug(f"[MainWindow] Emitting {cmd.__class__.__name__}")

        self.command_requested.emit(cmd)

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: dict = None,
        bidirectional: bool = False,
    ) -> None:
        """Adds a relation between entities.

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

        # Mark this command as a drag-drop command for toast display
        # (This handles both drag-drop and manual creation, which is acceptable usually,
        # or we could add a flag if strictly needed only for drag-drop.
        # For now, showing toast for all relation creations is good UX.)
        self._last_drag_drop_command_id = id(cmd)

        self.command_requested.emit(cmd)

    def load_maps(self) -> None:
        """Requests loading of all maps."""
        self.map_handler.load_maps()

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Handler for when a map is selected in the widget.

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
        """Creates a new marker at the given normalized coordinates.

        Prompts user to select an Entity or Event.
        """
        self.map_handler.create_marker(x, y)

    def _on_marker_dropped(
        self, item_id: str, item_type: str, item_name: str, x: float, y: float
    ) -> None:
        """Handle marker creation from drag-drop.

        Args:
            item_id: ID of the dropped entity/event.
            item_type: 'entity' or 'event'.
            item_name: Display name of the item.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].

        """
        self.map_handler.on_marker_dropped(item_id, item_type, item_name, x, y)

    def delete_marker(self, marker_id: str) -> None:
        """Deletes a marker.

        Args:
            marker_id: The object_id from the UI (not the actual marker.id).

        """
        self.map_handler.delete_marker(marker_id)

    @Slot(str, str)
    def _on_marker_clicked(self, marker_id: str, object_type: str) -> None:
        """Handle marker click from MapWidget.

        Args:
            marker_id: The ID of the item.
            object_type: 'event' or 'entity'.

        """
        self.map_handler.on_marker_clicked(marker_id, object_type)

    @Slot(str, str)
    def _on_marker_icon_changed(self, marker_id: str, icon: str) -> None:
        """Handle marker icon change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            icon: New icon filename

        """
        self.map_handler.on_marker_icon_changed(marker_id, icon)

    @Slot(str, str)
    def _on_marker_color_changed(self, marker_id: str, color: str) -> None:
        """Handle marker color change from MapWidget.

        Args:
            marker_id: ID of the marker (actually object_id from view)
            color: New color hex code

        """
        self.map_handler.on_marker_color_changed(marker_id, color)

    @Slot(str, float, float)
    def _on_marker_position_changed(self, marker_id: str, x: float, y: float) -> None:
        """Handle marker position change from MapWidget.

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
        """Handler for completer data loaded from worker.

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
        """Handler for grouping dialog data loaded from worker.

        Args:
            tags_data: List of dicts with 'name', 'color', 'count' for each tag.
            current_config: Current grouping config dict or None.

        """
        self.grouping_manager.on_grouping_dialog_data_loaded(tags_data, current_config)

    @Slot(list, str)
    def _on_grouping_applied(self, tag_order: list, mode: str) -> None:
        """Handle grouping applied from dialog.

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
        """Handle tag color change from band context menu.

        Args:
            tag_name: The name of the tag to change color for.

        """
        self.grouping_manager.on_tag_color_change_requested(tag_name)

    @Slot(str)
    def _on_remove_from_grouping_requested(self, tag_name: str) -> None:
        """Remove a tag from current grouping.

        Args:
            tag_name: The name of the tag to remove.

        """
        self.grouping_manager.on_remove_from_grouping_requested(tag_name)

    @Slot()
    def show_filter_dialog(self) -> None:
        """Shows the advanced filter dialog."""
        # Get all tags from DB (Synchronous read from GUI DB Service is fine
        # for metadata)
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
            # Send to worker via signal if needed, but for now UnifiedList
            # handles it locally
            # self.filter_requested.emit(config) # kept if other widgets need it?
            # Actually, user wants widgets to maintain own settings.
            # If Graph/Timeline need it, they should have their own.
            # For now, we update UnifiedList directly.
            self.unified_list.set_advanced_filter(config)

            # Update UI state (handled by set_advanced_filter)
            # has_filter = bool(config.get("include") or config.get("exclude"))
            # self.unified_list.set_filter_active(has_filter)

    @Slot()
    def clear_filter(self) -> None:
        """Clears the current filter configuration."""
        logger.info("Clearing filters")
        self.unified_list.set_advanced_filter({})

        # Clear settings
        from PySide6.QtCore import QSettings

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        settings.remove(SETTINGS_FILTER_CONFIG_KEY)

        self.status_bar.showMessage("Filters cleared.")
        self.load_data()

    @Slot()
    def show_longform_filter_dialog(self) -> None:
        """Shows filter dialog for the Longform editor (independent state)."""
        self.longform_manager.show_longform_filter_dialog()

    def clear_longform_filter(self) -> None:
        """Clears the longform filter and reloads the longform view."""
        self.longform_manager.clear_longform_filter()

    @Slot(list, list)
    def _on_filter_results_ready(self, events: list, entities: list) -> None:
        """Handler for filter results.

        Updates the Unified List with filtered data.
        """
        self.unified_list.set_data(events, entities)
        count = len(events) + len(entities)
        self.status_bar.showMessage(f"Filter applied. Found {count} items.")

    def remove_relation(self, rel_id: str) -> None:
        """Removes a relation by its ID.

        Args:
            rel_id (str): The ID of the relation to remove.

        """
        cmd = RemoveRelationCommand(rel_id)
        self.command_requested.emit(cmd)

    def update_relation(
        self, rel_id: str, target_id: str, rel_type: str, attributes: dict = None
    ) -> None:
        """Updates an existing relation.

        Args:
            rel_id (str): The ID of the relation to update.
            target_id (str): The new target entity ID.
            rel_type (str): The new relation type.
            attributes (dict, optional): The new attributes.

        """
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type, attributes=attributes)
        self.command_requested.emit(cmd)

    # Removed: navigate_to_entity/prompt_create moved to NavigationCoordinator

    def promote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Promotes a longform entry by reducing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to promote.
            old_meta (dict): Previous longform metadata for undo.

        """
        self.longform_manager.promote_longform_entry(table, row_id, old_meta)

    def demote_longform_entry(self, table: str, row_id: str, old_meta: dict) -> None:
        """Demotes a longform entry by increasing its depth.

        Args:
            table (str): Table name ("events" or "entities").
            row_id (str): ID of the item to demote.
            old_meta (dict): Previous longform metadata for undo.

        """
        self.longform_manager.demote_longform_entry(table, row_id, old_meta)

    def move_longform_entry(
        self, table: str, row_id: str, old_meta: dict, new_meta: dict
    ) -> None:
        """Moves a longform entry to a new position.

        Args:
            table (str): Table name.
            row_id (str): ID.
            old_meta (dict): Old metadata.
            new_meta (dict): New metadata with position/parent/depth.

        """
        self.longform_manager.move_longform_entry(table, row_id, old_meta, new_meta)

    def export_longform_document(self) -> None:
        """Exports the current longform document to Markdown.

        Opens a file dialog for the user to choose save location.
        """
        self.longform_manager.export_longform_document()

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
        """Perform semantic search and display results.

        Args:
            query: Search query text.
            object_type_filter: Filter by 'entity' or 'event', or empty for all.
            top_k: Number of results to return.

        """
        self.ai_search_manager.perform_semantic_search(query, object_type_filter, top_k)

    @Slot(str)
    def rebuild_search_index(self, object_type: str) -> None:
        """Rebuild the semantic search index.

        Args:
            object_type: Type to rebuild ('all', 'entity', 'event').

        """
        self.ai_search_manager.rebuild_search_index(object_type)

    @Slot(str, str)
    def _on_search_result_selected(self, object_type: str, object_id: str) -> None:
        """Handle selection of a search result.

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
    def import_item_requested(self) -> None:
        """Handles the request to import an item from a JSON file.

        This method:
        1. Opens a file dialog to select a JSON file
        2. Parses the JSON content (no DB access needed)
        3. Shows a preview dialog
        4. If confirmed, sends the parsed data to the worker thread for import
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Item", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            # 1. Read and Parse (no DB access needed)
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = f.read()

            from src.services.import_service import ImportService

            parsed_data = ImportService.parse_only(json_content)

            # 2. Show Preview Dialog
            dialog = ImportPreviewDialog(self, parsed_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 3. Send to worker thread for DB operations
                # Serialize to JSON string since Q_ARG doesn't support dict
                import json

                parsed_json = json.dumps(parsed_data)
                options = dialog.get_options()
                options_json = json.dumps(options)

                QMetaObject.invokeMethod(
                    self.worker,
                    "run_import",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, parsed_json),
                    Q_ARG(str, options_json),
                )

                # Show progress dialog
                from src.gui.dialogs.progress_dialog import ProgressDialog

                self._import_progress_dialog = ProgressDialog(
                    "Importing data...\n\nThis may take a moment for large files.",
                    parent=self,
                    cancelable=False,
                    title="Import in Progress",
                )
                self.status_bar.showMessage("Importing...", 0)

        except Exception as e:
            logger.exception("Import error")
            QMessageBox.critical(
                self,
                "Import Error",
                f"An unexpected error occurred during import: {e}\n\n"
                "Your existing data is safe and unchanged.\n\n"
                "Possible causes:\n"
                "• Invalid file format or corrupted data\n"
                "• Unsupported import format\n"
                "• File encoding issues (try UTF-8)\n\n"
                "To fix:\n"
                "1. Check that the file is a valid import format\n"
                "2. Verify file is not corrupted\n"
                "3. Check application logs for detailed error\n"
                "4. Try exporting and re-importing a small test dataset",
            )

    @Slot(object)
    def _on_import_finished(self, result: object) -> None:
        """Handles the completion of an import operation.

        Args:
            result: ImportResult from the worker thread.

        """
        # Close progress dialog if open
        if self._import_progress_dialog:
            self._import_progress_dialog.finish()
            self._import_progress_dialog = None

        self.status_bar.clearMessage()

        if result.success:
            msg = (
                "Import Successful!\n\n"
                f"Entities: {len(result.created_entities)}\n"
                f"Events: {len(result.created_events)}\n"
                f"Relations: {len(result.created_relations)}"
            )
            if result.warnings:
                msg += "\n\nWarnings:\n" + "\n".join(result.warnings[:5])
                if len(result.warnings) > 5:
                    msg += f"\n...and {len(result.warnings) - 5} more."

            QMessageBox.information(self, "Import Complete", msg)
        else:
            err_msg = "\n".join(result.errors[:10])
            if len(result.errors) > 10:
                err_msg += f"\n...and {len(result.errors) - 10} more errors."

            QMessageBox.critical(
                self,
                "Import Failed",
                f"Import completed with errors. No data was imported.\n\n"
                f"Errors ({len(result.errors)} total):\n{err_msg}\n\n"
                "What to do:\n"
                "1. Fix the errors in your source file\n"
                "2. Check file format matches expected structure\n"
                "3. Try importing a smaller subset first\n"
                "4. Consult documentation for import format details",
            )

    @Slot(str, object)
    def _on_summary_generated_result(self, item_id: str, summary_data: object) -> None:
        """Handles asynchronous summary generation result.

        Args:
            item_id: The ID of the item the summary is for.
            summary_data: The generated SummaryData object.

        """
        # Determine target editor logic
        # Simple check: Does EntityEditor currently hold this ID?
        if self.entity_editor._current_entity_id == item_id:
            self.entity_editor.on_summary_generated(summary_data)
            return

        # Does EventEditor hold it?
        if self.event_editor._current_event_id == item_id:
            self.event_editor.on_summary_generated(summary_data)
            return

        # Warn if neither (user navigated away?)
        self.show_error_message(
            f"Summary generated for {item_id}, but item is no longer active in editor."
        )
