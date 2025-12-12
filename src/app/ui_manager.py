"""
UIManager Module.
Handles the creation and layout of dock widgets and menus for the MainWindow.
"""

from PySide6.QtWidgets import QMainWindow, QDockWidget, QTabWidget, QMenu, QMenuBar
from PySide6.QtCore import Qt
from src.app.constants import (
    DOCK_TITLE_PROJECT,
    DOCK_TITLE_EVENT_INSPECTOR,
    DOCK_TITLE_ENTITY_INSPECTOR,
    DOCK_TITLE_TIMELINE,
    DOCK_OBJ_PROJECT,
    DOCK_OBJ_EVENT_INSPECTOR,
    DOCK_OBJ_ENTITY_INSPECTOR,
    DOCK_OBJ_TIMELINE,
    DOCK_TITLE_LONGFORM,
    DOCK_OBJ_LONGFORM,
)


class UIManager:
    """
    Manages the UI components of the MainWindow, including Docks and Menus.
    """

    def __init__(self, main_window: QMainWindow):
        """
        Initializes the UIManager.

        Args:
            main_window (QMainWindow): The main window instance to manage.
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
        """
        # Enable advanced docking
        self.main_window.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks
        )
        self.main_window.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

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

    def _create_dock(self, title: str, obj_name: str, widget) -> QDockWidget:
        """Helper to create a configured dock widget."""
        dock = QDockWidget(title, self.main_window)
        dock.setObjectName(obj_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        return dock

    def create_view_menu(self, menu_bar: QMenuBar):
        """Creates the View menu for toggling docks."""
        view_menu = menu_bar.addMenu("View")
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())

        view_menu.addSeparator()
        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)

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

            self.docks["timeline"].show()

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
