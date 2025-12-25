"""
UIManager Module.
Handles the creation and layout of dock widgets and menus for the MainWindow.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QMenuBar, QTabWidget

from src.app.constants import (
    DOCK_OBJ_ENTITY_INSPECTOR,
    DOCK_OBJ_EVENT_INSPECTOR,
    DOCK_OBJ_LONGFORM,
    DOCK_OBJ_MAP,
    DOCK_OBJ_PROJECT,
    DOCK_OBJ_TIMELINE,
    DOCK_TITLE_ENTITY_INSPECTOR,
    DOCK_TITLE_EVENT_INSPECTOR,
    DOCK_TITLE_LONGFORM,
    DOCK_TITLE_MAP,
    DOCK_TITLE_PROJECT,
    DOCK_TITLE_TIMELINE,
)
from src.core.protocols import MainWindowProtocol


class UIManager:
    """
    Manages the UI components of the MainWindow, including Docks and Menus.
    
    This class uses the MainWindowProtocol to define its expectations of the
    main window, making the interface explicit and verifiable.
    """

    def __init__(self, main_window: MainWindowProtocol):
        """
        Initializes the UIManager.

        Args:
            main_window: A MainWindow instance implementing MainWindowProtocol.
        """
        self.main_window = main_window
        self.docks = {}

    def setup_docks(self, widgets: dict):
        """
        Creates and arranges all dock widgets.

        Args:
            widgets (dict): Dictionary containing the widget instances:
                - 'unified_list': UnifiedListWidget
                - 'event_editor': EventEditorWidget
                - 'entity_editor': EntityEditorWidget
                - 'timeline': TimelineWidget
                - 'longform_editor': LongformEditorWidget
                - 'map_widget': MapWidget
        """
        # Enable advanced docking
        self.main_window.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks
        )
        self.main_window.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # Configure Corners to prioritize Side Panels (Full Height)
        self.main_window.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.main_window.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.main_window.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.main_window.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        # 1. Project Explorer (Left)
        self.docks["list"] = self._create_dock(
            DOCK_TITLE_PROJECT, DOCK_OBJ_PROJECT, widgets["unified_list"]
        )
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.docks["list"])

        # 2. Event Inspector (Right)
        self.docks["event"] = self._create_dock(
            DOCK_TITLE_EVENT_INSPECTOR,
            DOCK_OBJ_EVENT_INSPECTOR,
            widgets["event_editor"],
        )
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.docks["event"])

        # 3. Entity Inspector (Right)
        self.docks["entity"] = self._create_dock(
            DOCK_TITLE_ENTITY_INSPECTOR,
            DOCK_OBJ_ENTITY_INSPECTOR,
            widgets["entity_editor"],
        )
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.docks["entity"])

        # Tabify Inspectors
        self.main_window.tabifyDockWidget(self.docks["event"], self.docks["entity"])

        # 4. Timeline (Bottom)
        self.docks["timeline"] = self._create_dock(
            DOCK_TITLE_TIMELINE, DOCK_OBJ_TIMELINE, widgets["timeline"]
        )
        self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.docks["timeline"])

        # 5. Longform Editor (Right)
        if "longform_editor" in widgets:
            self.docks["longform"] = self._create_dock(
                DOCK_TITLE_LONGFORM, DOCK_OBJ_LONGFORM, widgets["longform_editor"]
            )
            self.main_window.addDockWidget(
                Qt.RightDockWidgetArea, self.docks["longform"]
            )
            # Tabify with inspectors if desired, or keep separate.
            # Instructions say: addDockWidget(Qt.RightDockWidgetArea, ...)

        # 6. Map Widget (Bottom, tabbed with Timeline by default)
        if "map_widget" in widgets:
            self.docks["map"] = self._create_dock(
                DOCK_TITLE_MAP, DOCK_OBJ_MAP, widgets["map_widget"]
            )
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.docks["map"])
            self.main_window.tabifyDockWidget(self.docks["timeline"], self.docks["map"])

    def _create_dock(self, title: str, obj_name: str, widget) -> QDockWidget:
        """
        Helper to create a configured dock widget with size constraints.

        Sets minimum sizes to prevent dock collapse during resize/rearrangement.

        Args:
            title: Display title for the dock widget.
            obj_name: Object name for state persistence.
            widget: The widget to contain in the dock.

        Returns:
            Configured QDockWidget with size constraints.
        """
        from PySide6.QtWidgets import QSizePolicy

        dock = QDockWidget(title, self.main_window)
        dock.setObjectName(obj_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )

        # Set minimum sizes to prevent collapse
        # Base minimum that shows title bar + some content
        dock.setMinimumWidth(250)  # Enough for form labels
        dock.setMinimumHeight(150)  # Enough for controls

        # Set size policy to allow shrinking but with limits
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHorizontalStretch(1)
        policy.setVerticalStretch(1)
        dock.setSizePolicy(policy)

        return dock

    def create_view_menu(self, menu_bar: QMenuBar):
        """Creates the View menu for toggling docks."""
        view_menu = menu_bar.addMenu("View")
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())

        view_menu.addSeparator()
        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)

        # Timeline Grouping
        view_menu.addSeparator()
        self.grouping_config_action = view_menu.addAction(
            "Configure Timeline Grouping..."
        )
        self.grouping_config_action.triggered.connect(
            self.main_window._on_configure_grouping_requested
        )

        self.grouping_clear_action = view_menu.addAction("Clear Timeline Grouping")
        self.grouping_clear_action.triggered.connect(
            self.main_window._on_clear_grouping_requested
        )

    def reset_layout(self):
        """Restores the default docking layout."""
        if "list" in self.docks:
            self.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.docks["list"])
            self.docks["list"].show()

        if "event" in self.docks and "entity" in self.docks:
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.docks["event"])
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.docks["entity"])
            self.main_window.tabifyDockWidget(self.docks["event"], self.docks["entity"])
            self.docks["event"].show()
            self.docks["entity"].show()

            self.docks["entity"].show()

            self.docks["timeline"].show()
            if "map" in self.docks:
                self.main_window.tabifyDockWidget(
                    self.docks["timeline"], self.docks["map"]
                )
                self.docks["map"].show()

    def create_settings_menu(self, menu_bar: QMenuBar):
        """Creates the Settings menu."""
        from src.core.theme_manager import ThemeManager

        settings_menu = menu_bar.addMenu("Settings")

        # Theme Submenu
        theme_menu = settings_menu.addMenu("Theme")
        tm = ThemeManager()
        available_themes = tm.get_available_themes()

        # Create action group for exclusivity
        from PySide6.QtGui import QActionGroup

        action_group = QActionGroup(self.main_window)

        for theme_name in available_themes:
            action = theme_menu.addAction(theme_name.replace("_", " ").title())
            action.setCheckable(True)
            if theme_name == tm.current_theme_name:
                action.setChecked(True)

            action.triggered.connect(
                lambda checked=False, name=theme_name: tm.set_theme(name)
            )
            action_group.addAction(action)

        # Calendar Configuration
        settings_menu.addSeparator()
        calendar_action = settings_menu.addAction("Calendar Configuration...")
        calendar_action.triggered.connect(self._open_calendar_config)

        # Track pending dialog state
        self._calendar_dialog_pending = False

    def _open_calendar_config(self):
        """Requests loading of calendar config to open dialog."""
        from PySide6.QtCore import QMetaObject
        from PySide6.QtCore import Qt as QtCore_Qt

        # Request config from worker (will be handled by on_calendar_config_loaded)
        self._calendar_dialog_pending = True
        QMetaObject.invokeMethod(
            self.main_window.worker, "load_calendar_config", QtCore_Qt.QueuedConnection
        )

    def show_calendar_dialog(self, current_config):
        """
        Shows the calendar configuration dialog.

        Args:
            current_config: CalendarConfig or None.
        """
        if not self._calendar_dialog_pending:
            return
        self._calendar_dialog_pending = False

        from src.commands.calendar_commands import (
            CreateCalendarConfigCommand,
            SetActiveCalendarCommand,
            UpdateCalendarConfigCommand,
        )
        from src.gui.dialogs.calendar_config_dialog import CalendarConfigDialog

        dialog = CalendarConfigDialog(self.main_window, config=current_config)

        def on_config_saved(config):
            """
            Handles calendar config save by creating appropriate commands.

            Args:
                config: The calendar configuration to save.
            """
            # Save the config
            if current_config and current_config.id == config.id:
                cmd = UpdateCalendarConfigCommand(config)
            else:
                cmd = CreateCalendarConfigCommand(config)
            self.main_window.command_requested.emit(cmd)

            # Set as active
            active_cmd = SetActiveCalendarCommand(config.id)
            self.main_window.command_requested.emit(active_cmd)

            # Refresh the calendar converter
            self.main_window._request_calendar_config()

        dialog.config_saved.connect(on_config_saved)
        dialog.exec()
