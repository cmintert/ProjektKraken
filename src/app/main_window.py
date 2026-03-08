"""MainWindow Class.

The main application window that manages UI components, database workers, and
signal/slot connections.
"""

from typing import Optional

# NOTE: Uses fully qualified PySide6 enum paths. See docs/PYSIDE6_ENUM_SOLUTION.md.
from PySide6.QtCore import (
    QEvent,
    QMetaObject,
    QObject,
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
    QLabel,
    QMainWindow,
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
    SETTINGS_AUTO_RELATION_KEY,
    SETTINGS_FILTER_CONFIG_KEY,
    UI_DOCK_RESTORE_DELAY_MS,
    UI_DOCK_VALIDATE_DELAY_MS,
    UI_INIT_DELAY_MS,
    UI_OPTIONAL_DOCK_DELAY_MS,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
    WINDOW_TITLE,
)
from src.app.coordinators.app_coordinator import AppCoordinator
from src.app.data_handler import DataHandler
from src.app.longform_manager import LongformManager
from src.app.map_handler import MapHandler
from src.app.timeline_grouping_manager import TimelineGroupingManager
from src.app.ui_manager import UIManager
from src.app.worker_manager import WorkerManager
from src.core.fast_inject import FastInjectManager
from src.core.logging_config import get_logger
from src.core.paths import get_worlds_dir
from src.gui.dialogs.filter_dialog import FilterDialog
from src.gui.mixins.layout_guard import LayoutGuardMixin
from src.gui.widgets.ai_search_panel import AISearchPanelWidget
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.graph_view import GraphWidget
from src.gui.widgets.longform import LongformEditorWidget
from src.gui.widgets.map_widget import MapWidget
from src.gui.widgets.timeline import TimelineWidget
from src.gui.widgets.unified_list import UnifiedListWidget

logger = get_logger(__name__)


class GlobalShortcutFilter(QObject):
    """Event filter that intercepts global keyboard shortcuts.

    Installed on QApplication to capture Ctrl+Z (Undo) and Ctrl+Y/Ctrl+Shift+Z
    (Redo) before individual widgets can consume them.

    Shortcuts are defined declaratively in ``_SHORTCUTS`` to keep the
    event filter body simple and data-driven.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the filter with a reference to the main window.

        Args:
            main_window: The MainWindow instance to route commands to.

        """
        super().__init__(main_window)
        self.main_window = main_window

        ctrl = Qt.KeyboardModifier.ControlModifier
        ctrl_shift = ctrl | Qt.KeyboardModifier.ShiftModifier
        self._shortcuts = {
            (Qt.Key.Key_Z, ctrl): self._try_undo,
            (Qt.Key.Key_Y, ctrl): self._try_redo,
            (Qt.Key.Key_Z, ctrl_shift): self._try_redo,
            (Qt.Key.Key_E, ctrl): lambda: self._try_create("action_create_event"),
            (Qt.Key.Key_I, ctrl): lambda: self._try_create("action_create_entity"),
            (Qt.Key.Key_M, ctrl): lambda: self._try_create("action_create_map"),
        }

    def _try_undo(self) -> bool:
        """Attempt to undo the last command.

        Returns:
            True if the undo was performed, False otherwise.

        """
        if hasattr(self.main_window, "coordinator"):
            if self.main_window.coordinator.can_undo():
                self.main_window.coordinator.undo()
                return True
        return False

    def _try_redo(self) -> bool:
        """Attempt to redo the last undone command.

        Returns:
            True if the redo was performed, False otherwise.

        """
        if hasattr(self.main_window, "coordinator"):
            if self.main_window.coordinator.can_redo():
                self.main_window.coordinator.redo()
                return True
        return False

    def _try_create(self, action_name: str) -> bool:
        """Trigger a creation action on the list widget.

        Args:
            action_name: The attribute name of the action on the list widget
                (e.g. ``"action_create_event"``).

        Returns:
            True if the action was triggered, False otherwise.

        """
        if hasattr(self.main_window, "list_widget"):
            getattr(self.main_window.list_widget, action_name).trigger()
            return True
        return False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter key events and intercept global shortcuts.

        Args:
            obj: The object receiving the event.
            event: The event to filter.

        Returns:
            True if the event was handled (consumed), False otherwise.

        """
        if event.type() != QEvent.Type.KeyPress:
            return False

        key_event = event  # type: QKeyEvent
        key = key_event.key()
        modifiers = key_event.modifiers()

        handler = self._shortcuts.get((key, modifiers))
        if handler is not None:
            return handler()

        return False


class MainWindow(QMainWindow, LayoutGuardMixin):
    """The main application window.

    Acts as the central controller for the UI, managing:
    - Dockable widgets (Lists, Editors, Timeline).
    - DatabaseWorker thread for async operations.
    - Signal/Slot connections between UI and persistent storage.

    Adheres to "Dumb UI" philosophy: logic delegates to Worker/Commands.

    Initialization follows a three-phase approach to avoid blocking the Qt
    event loop during startup:
    - Phase 1: Core services (data handler, worker thread, window properties).
    - Phase 2: UI skeleton (widgets, dock layout, menus) — no data loaded.
    - Phase 3: Deferred via QTimer (DB init, signal wiring, state restore).
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
            from src.core.theme_manager import ThemeManager
            from src.gui.utils.window_utils import apply_windows_title_bar_style

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
        self.current_world = None

        # Connect Theme Manager Signal
        try:
            from src.core.theme_manager import ThemeManager

            tm = ThemeManager()
            tm.theme_changed.connect(self._update_window_style)
            tm.theme_changed.connect(self._on_theme_changed_save_to_world)
        except Exception as e:
            logger.warning(f"Failed to connect theme signal: {e}")

        # Initialize Data Handler (signals-based, no window reference)
        self.data_handler = DataHandler()

        # Initialize backup service (will be properly connected after DB init)
        self.backup_service = None

        # Initialize coordinators via AppCoordinator facade
        self.app_coordinator = AppCoordinator(self)
        self.time_coordinator = self.app_coordinator.time
        self.data_coordinator = self.app_coordinator.data
        self.import_coordinator = self.app_coordinator.import_coord

        # Init Services (Worker Thread)
        self.worker_manager = WorkerManager(self)
        self.worker_manager.init_worker()

        # Initialize state variables
        self.cached_event_count: Optional[int] = None
        self.longform_filter_config: dict = {}
        self.calendar_converter = None
        self._pending_select_id = None
        self._pending_select_type = None

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

            # Determine if dark mode: dark backgrounds have lightness < 128.
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
        """Create a styled, permanent label and add it to the status bar.

        Args:
            text: Initial display text for the label.
            color: CSS color string (e.g. ``"#3498db"``) applied to the
                label's foreground via an inline stylesheet.

        Returns:
            The configured ``QLabel`` that has been added to the status bar.

        """
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
        # Propagate theme changes to the layer panel
        try:
            from src.core.theme_manager import ThemeManager

            def _refresh_layer_styles(_theme_data: dict) -> None:
                """Refresh map layer panel styles on theme change."""
                try:
                    import shiboken6

                    if shiboken6.isValid(self) and shiboken6.isValid(self.map_widget):
                        self.map_widget.layer_panel.refresh_styles()
                except (RuntimeError, ImportError):
                    pass

            ThemeManager().theme_changed.connect(_refresh_layer_styles)
        except Exception as e:
            logger.warning(f"Failed to connect theme->layer panel: {e}")

        self.ai_search_panel = AISearchPanelWidget()
        self.graph_widget = GraphWidget()
        self.longform_editor = LongformEditorWidget(db_path=self.db_path)

        # Create History Panel (Phase 3)
        from src.gui.widgets.history_panel import HistoryPanelWidget

        self.history_panel = HistoryPanelWidget()

        # Initialize Managers
        # MapHandler is initialized after coordinators (see below) because
        # it needs navigation_coordinator's set_global_selection callable.
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

        # Expose remaining coordinators from AppCoordinator facade
        self.fast_inject_coordinator = self.app_coordinator.fast_inject
        self.navigation_coordinator = self.app_coordinator.navigation
        self.backup_coordinator = self.app_coordinator.backup
        self.editor_coordinator = self.app_coordinator.editor

        # Initialize MapHandler with injected dependencies (no self reference)
        self.map_handler = MapHandler(
            map_widget=self.map_widget,
            worker=self.worker,
            db_path_accessor=lambda: self.db_path,
            navigation_set_selection=(self.navigation_coordinator.set_global_selection),
        )
        # Forward MapHandler's command_requested to MainWindow's
        self.map_handler.command_requested.connect(self.command_requested.emit)

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

        # Connect editor dirty signals via EditorCoordinator
        self.event_editor.dirty_changed.connect(
            lambda dirty: self.editor_coordinator.on_editor_dirty_changed(
                self.event_editor, dirty
            )
        )
        self.entity_editor.dirty_changed.connect(
            lambda dirty: self.editor_coordinator.on_editor_dirty_changed(
                self.entity_editor, dirty
            )
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

        # Connect to worker's command_finished to show toast for
        # drag-drop relations via EditorCoordinator
        self.worker.command_finished.connect(
            self.editor_coordinator.on_command_finished_check_toast,
            Qt.ConnectionType.QueuedConnection,
        )

        # Connect Coordinator Signals
        self.editor_coordinator.command_requested.connect(
            lambda cmd: self.command_requested.emit(cmd)
        )
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

        Always schedules ``guard_validate_dock_sizes`` after layout
        is established — whether from saved state or from reset_layout.
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
        elif state := settings.value("windowState"):
            # Restore window state (includes dock positions)
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

        # Always schedule dock size validation regardless of which code
        # path was taken above.  Qt's internal layout negotiation may
        # leave bottom docks (timeline, map, graph) collapsed.
        QTimer.singleShot(
            UI_DOCK_VALIDATE_DELAY_MS,
            self.guard_validate_dock_sizes,
        )

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

    def load_longform_sequence(self) -> None:
        """Loads the longform sequence. Delegates to LongformManager."""
        self.longform_manager.load_longform_sequence()

    # Removed: set_global_selection logic moved to NavigationCoordinator

    # Removed: _on_item_selected logic moved to NavigationCoordinator

    def check_unsaved_changes(self, editor: QWidget) -> bool:
        """Checks if the editor has unsaved changes and prompts the user.

        Delegates to EditorCoordinator.

        Args:
            editor: The editor widget to check.

        Returns:
            bool: True if safe to proceed, False if User Cancelled.

        """
        return self.editor_coordinator.check_unsaved_changes(editor)

    @Slot(list, list)
    def _update_history_panel(self, undo_snapshots: list, redo_snapshots: list) -> None:
        """Update the history panel with pre-built snapshot dicts.

        The snapshots are created inside ``CommandCoordinator`` at the
        moment the stacks are modified, so this method never touches
        live command objects and is therefore safe against worker-thread
        mutations.

        Args:
            undo_snapshots: List of ``{"description": str, "timestamp": float|None}``
                dicts for the undo stack.
            redo_snapshots: Same format for the redo stack.
        """
        try:
            if hasattr(self, "history_panel"):
                import shiboken6

                if not shiboken6.isValid(self.history_panel):
                    logger.debug(
                        "_update_history_panel: history_panel C++ object deleted"
                    )
                    return
                self.history_panel.update_history(undo_snapshots, redo_snapshots)
        except RuntimeError:
            # Underlying C++ object already deleted — nothing to update
            logger.debug("_update_history_panel: RuntimeError (widget deleted)")
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

    def _request_grouping_config(self) -> None:
        """Requests loading of the timeline grouping configuration."""
        self.grouping_manager.request_grouping_config()

    def on_grouping_config_loaded(self, config: dict) -> None:
        """Handler for grouping config loaded.

        Args:
            config: Dictionary with 'tag_order' and 'mode', or None.

        """
        self.grouping_manager.on_grouping_config_loaded(config)

    def _on_theme_changed_save_to_world(self, _theme_dict: dict) -> None:
        """Save the active theme to the current world's system_meta when it changes.

        Args:
            _theme_dict: The new theme dictionary from ThemeManager (unused).

        """
        try:
            if not hasattr(self, "gui_db_service") or self.gui_db_service is None:
                return
            from src.core.theme_manager import ThemeManager

            theme_name = ThemeManager().current_theme_name
            self.gui_db_service.set_world_theme(theme_name)
        except Exception as e:
            logger.warning(f"Failed to save world theme: {e}")

    def _on_theme_changed_for_titlebar(self, theme_dict: dict) -> None:
        """Update Windows title bar style when theme changes.

        Args:
            theme_dict: The new theme dictionary from ThemeManager.
        """
        try:
            from src.core.theme_manager import ThemeManager
            from src.gui.utils.window_utils import apply_windows_title_bar_style

            # Determine if new theme is dark
            theme_name = ThemeManager().current_theme_name
            dark_mode = "dark" in theme_name.lower()
            apply_windows_title_bar_style(self, dark_mode=dark_mode)
        except Exception as e:
            logger.warning(f"Failed to update title bar style on theme change: {e}")

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
        if hasattr(self, "data_coordinator"):
            self.data_coordinator.stop_graph_reload_timer()

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

    # DataHandler signal handlers (loose coupling via signals)

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

    def load_maps(self) -> None:
        """Requests loading of all maps."""
        self.map_handler.load_maps()

    # ----------------------------------------------------------------------
    # Timeline Grouping Methods
    # ----------------------------------------------------------------------

    @Slot(list, object)
    def on_grouping_dialog_data_loaded(
        self, tags_data: list, current_config: dict
    ) -> None:
        """Handler for grouping dialog data loaded from worker.

        Delegates to GroupingManager.
        """
        self.grouping_manager.on_grouping_dialog_data_loaded(tags_data, current_config)

    # Removed: _on_tag_color_change_requested, _on_remove_from_grouping_requested
    # rewired to GroupingManager in ConnectionManager

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
        self.data_coordinator.load_data()

    # Removed: show_longform_filter_dialog, clear_longform_filter
    # rewired to LongformManager in ConnectionManager

    # Removed: navigate_to_entity/prompt_create moved to NavigationCoordinator

    # Removed: promote/demote/move/export longform_entry
    # rewired to LongformManager in ConnectionManager

    # Removed: perform_semantic_search, rebuild_search_index,
    # _on_search_result_selected, refresh_search_index_status
    # rewired to AISearchManager in ConnectionManager
