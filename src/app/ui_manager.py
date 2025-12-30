"""
UIManager Module.
Handles the creation and layout of dock widgets and menus for the MainWindow.
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QInputDialog,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from src.app.constants import (
    DOCK_OBJ_AI_SEARCH,
    DOCK_OBJ_ENTITY_INSPECTOR,
    DOCK_OBJ_EVENT_INSPECTOR,
    DOCK_OBJ_LONGFORM,
    DOCK_OBJ_MAP,
    DOCK_OBJ_PROJECT,
    DOCK_OBJ_TIMELINE,
    DOCK_TITLE_AI_SEARCH,
    DOCK_TITLE_ENTITY_INSPECTOR,
    DOCK_TITLE_EVENT_INSPECTOR,
    DOCK_TITLE_LONGFORM,
    DOCK_TITLE_MAP,
    DOCK_TITLE_PROJECT,
    DOCK_TITLE_TIMELINE,
    SETTINGS_LAYOUTS_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.core.protocols import MainWindowProtocol


class UIManager:
    """
    Manages the UI components of the MainWindow, including Docks and Menus.

    This class uses the MainWindowProtocol to define its expectations of the
    main window, making the interface explicit and verifiable.
    """

    def __init__(self, main_window: MainWindowProtocol) -> None:
        """
        Initializes the UIManager.

        Args:
            main_window: A MainWindow instance implementing MainWindowProtocol.
        """
        self.main_window = main_window
        self.docks = {}

    def setup_docks(self, widgets: Dict[str, QWidget]) -> None:
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
                - 'ai_search_panel': AISearchPanelWidget (optional)
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

        # 7. AI Search Panel (Right, tabbed with inspectors)
        if "ai_search_panel" in widgets:
            self.docks["ai_search"] = self._create_dock(
                DOCK_TITLE_AI_SEARCH, DOCK_OBJ_AI_SEARCH, widgets["ai_search_panel"]
            )
            self.main_window.addDockWidget(
                Qt.RightDockWidgetArea, self.docks["ai_search"]
            )
            # Tabify with entity inspector
            self.main_window.tabifyDockWidget(
                self.docks["entity"], self.docks["ai_search"]
            )

    def _create_dock(self, title: str, obj_name: str, widget: QWidget) -> QDockWidget:
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

    def create_file_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the File menu."""
        file_menu = menu_bar.addMenu("File")

        # Open Database
        db_action = file_menu.addAction("Manage Databases...")
        db_action.triggered.connect(self.main_window.show_database_manager)

        file_menu.addSeparator()

        # Exit
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.main_window.close)

    def create_view_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the View menu for toggling docks."""
        view_menu = menu_bar.addMenu("View")
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())

        view_menu.addSeparator()

        # Theme Submenu (moved from Settings)
        from src.core.theme_manager import ThemeManager

        theme_menu = view_menu.addMenu("Theme")
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

        view_menu.addSeparator()
        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)

        # Layouts Menu
        self.create_layouts_menu(menu_bar)

    def create_layouts_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the Layouts menu for saving/restoring window layouts."""
        self.layouts_menu = menu_bar.addMenu("Layouts")
        self._refresh_layouts_menu()

    def _refresh_layouts_menu(self) -> None:
        """Refreshes the Layouts menu items."""
        if not hasattr(self, "layouts_menu"):
            return

        self.layouts_menu.clear()

        # Save Layout Action
        save_action = self.layouts_menu.addAction("Save Current Layout...")
        save_action.triggered.connect(self.prompt_save_layout)

        self.layouts_menu.addSeparator()

        # Existing Layouts
        layouts = self.get_saved_layouts()
        if not layouts:
            no_layouts = self.layouts_menu.addAction("No Saved Layouts")
            no_layouts.setEnabled(False)
        else:
            for name in layouts:
                # Add a submenu or just click to restore?
                # Let's do: Name -> Restore
                # And a separate "Manage Layouts" or Delete in submenu?
                # Simplest: Click to restore.
                # To delete, maybe a "Manage..." or "Delete..." submenu.

                # Let's try a submenu for each layout:
                # Layout Name >
                #   Restore
                #   Delete

                layout_menu = self.layouts_menu.addMenu(name)

                restore_action = layout_menu.addAction("Restore")
                restore_action.triggered.connect(
                    lambda checked=False, n=name: self.restore_layout(n)
                )

                delete_action = layout_menu.addAction("Delete")
                delete_action.triggered.connect(
                    lambda checked=False, n=name: self.delete_layout(n)
                )

    def prompt_save_layout(self) -> None:
        """Prompts user for a layout name and saves it."""
        name, ok = QInputDialog.getText(self.main_window, "Save Layout", "Layout Name:")
        if ok and name:
            if name in self.get_saved_layouts():
                reply = QMessageBox.question(
                    self.main_window,
                    "Overwrite Layout?",
                    f"Layout '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            self.save_layout(name)

    def save_layout(self, name: str) -> None:
        """
        Saves the current window layout (state and geometry).

        Args:
            name: The name of the layout.
        """
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = settings.value(SETTINGS_LAYOUTS_KEY, {})

        # We need to explicitly convert to dict if it's not
        # (first run might return something else or None)
        if not isinstance(layouts, dict):
            layouts = {}

        layouts[name] = {
            "state": self.main_window.saveState(),
            "geometry": self.main_window.saveGeometry(),
        }

        settings.setValue(SETTINGS_LAYOUTS_KEY, layouts)
        self._refresh_layouts_menu()

    def restore_layout(self, name: str) -> None:
        """
        Restores a saved window layout.

        Args:
            name: The name of the layout to restore.
        """
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = settings.value(SETTINGS_LAYOUTS_KEY, {})

        if not isinstance(layouts, dict) or name not in layouts:
            return

        layout_data = layouts[name]

        # Restore geometry first, then state
        if "geometry" in layout_data:
            self.main_window.restoreGeometry(layout_data["geometry"])
        if "state" in layout_data:
            self.main_window.restoreState(layout_data["state"])

    def delete_layout(self, name: str) -> None:
        """
        Deletes a saved layout.

        Args:
            name: The name of the layout to delete.
        """
        reply = QMessageBox.question(
            self.main_window,
            "Delete Layout",
            f"Are you sure you want to delete layout '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            layouts = settings.value(SETTINGS_LAYOUTS_KEY, {})

            if isinstance(layouts, dict) and name in layouts:
                del layouts[name]
                settings.setValue(SETTINGS_LAYOUTS_KEY, layouts)
                self._refresh_layouts_menu()

    def get_saved_layouts(self) -> list[str]:
        """
        Returns a list of saved layout names.

        Returns:
            List[str]: Sorted list of layout names.
        """
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = settings.value(SETTINGS_LAYOUTS_KEY, {})
        if isinstance(layouts, dict):
            return sorted(layouts.keys())
        return []

    def create_timeline_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the Timeline menu for grouping and calendar."""
        timeline_menu = menu_bar.addMenu("Timeline")

        # Grouping
        self.grouping_config_action = timeline_menu.addAction("Configure Grouping...")
        self.grouping_config_action.triggered.connect(
            self.main_window._on_configure_grouping_requested
        )

        self.grouping_clear_action = timeline_menu.addAction("Clear Grouping")
        self.grouping_clear_action.triggered.connect(
            self.main_window._on_clear_grouping_requested
        )

        timeline_menu.addSeparator()

        # Calendar Configuration
        calendar_action = timeline_menu.addAction("Calendar Configuration...")
        calendar_action.triggered.connect(self._open_calendar_config)

    def reset_layout(self) -> None:
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

    def create_settings_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the Settings menu (AI and other system settings)."""
        settings_menu = menu_bar.addMenu("Settings")

        # AI Search Index and Settings (moved from AI menu)
        search_settings_action = settings_menu.addAction(
            "AI Search Index and Settings..."
        )
        if hasattr(self.main_window, "show_ai_settings_dialog"):
            search_settings_action.triggered.connect(
                self.main_window.show_ai_settings_dialog
            )

        settings_menu.addSeparator()

        # Wiki Auto-Relation Setting
        from src.app.constants import SETTINGS_AUTO_RELATION_KEY

        self.auto_relation_action = settings_menu.addAction(
            "Auto-Create Relations from Wikilinks"
        )
        self.auto_relation_action.setCheckable(True)
        # Connect to MainWindow slot (to be created)
        if hasattr(self.main_window, "toggle_auto_relation_setting"):
            self.auto_relation_action.triggered.connect(
                self.main_window.toggle_auto_relation_setting
            )

            # Init state
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            is_checked = settings.value(SETTINGS_AUTO_RELATION_KEY, False, type=bool)
            self.auto_relation_action.setChecked(is_checked)

        # Track pending dialog state
        self._calendar_dialog_pending = False

    def _open_calendar_config(self) -> None:
        """Requests loading of calendar config to open dialog."""
        from PySide6.QtCore import QMetaObject
        from PySide6.QtCore import Qt as QtCore_Qt

        # Request config from worker (will be handled by on_calendar_config_loaded)
        self._calendar_dialog_pending = True
        QMetaObject.invokeMethod(
            self.main_window.worker, "load_calendar_config", QtCore_Qt.QueuedConnection
        )

    def show_calendar_dialog(self, current_config: Optional[Any]) -> None:
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

        def on_config_saved(config: Any) -> None:
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
