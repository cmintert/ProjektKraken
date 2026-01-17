"""
UIManager Module.
Handles the creation and layout of dock widgets and menus for the MainWindow.
"""

from typing import Any, Dict, Optional

# NOTE: PySide6 Fully Qualified Enum Paths
# =========================================
# Uses fully qualified enum paths (e.g., Qt.DockWidgetArea.LeftDockWidgetArea)
# per PySide6 6.4+ best practices. See src/app/main.py for full explanation.
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
    DOCK_OBJ_GRAPH,
    DOCK_OBJ_LONGFORM,
    DOCK_OBJ_MAP,
    DOCK_OBJ_PROJECT,
    DOCK_OBJ_TIMELINE,
    DOCK_TITLE_AI_SEARCH,
    DOCK_TITLE_ENTITY_INSPECTOR,
    DOCK_TITLE_EVENT_INSPECTOR,
    DOCK_TITLE_GRAPH,
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
        from src.core.logging_config import get_logger

        logger = get_logger(__name__)

        # Track dock creation results
        failed_docks = []

        # Enable advanced docking
        self.main_window.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self.main_window.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

        # Configure Corners to prioritize Side Panels (Full Height)
        self.main_window.setCorner(
            Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.main_window.setCorner(
            Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.main_window.setCorner(
            Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.main_window.setCorner(
            Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea
        )

        # 1. Project Explorer (Left)
        dock = self._create_dock(
            DOCK_TITLE_PROJECT, DOCK_OBJ_PROJECT, widgets.get("unified_list")
        )
        if dock:
            self.docks["list"] = dock
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.LeftDockWidgetArea, self.docks["list"]
            )
        else:
            failed_docks.append("list")

        # 2. Event Inspector (Right)
        dock = self._create_dock(
            DOCK_TITLE_EVENT_INSPECTOR,
            DOCK_OBJ_EVENT_INSPECTOR,
            widgets.get("event_editor"),
        )
        if dock:
            self.docks["event"] = dock
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.docks["event"]
            )
        else:
            failed_docks.append("event")

        # 3. Entity Inspector (Right)
        dock = self._create_dock(
            DOCK_TITLE_ENTITY_INSPECTOR,
            DOCK_OBJ_ENTITY_INSPECTOR,
            widgets.get("entity_editor"),
        )
        if dock:
            self.docks["entity"] = dock
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.docks["entity"]
            )
        else:
            failed_docks.append("entity")

        # Tabify Inspectors (only if both exist)
        if "event" in self.docks and "entity" in self.docks:
            self.main_window.tabifyDockWidget(self.docks["event"], self.docks["entity"])

        # 4. Timeline (Bottom)
        dock = self._create_dock(
            DOCK_TITLE_TIMELINE, DOCK_OBJ_TIMELINE, widgets.get("timeline")
        )
        if dock:
            self.docks["timeline"] = dock
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea, self.docks["timeline"]
            )
        else:
            failed_docks.append("timeline")

        # 5. Longform Editor (Right)
        if "longform_editor" in widgets:
            dock = self._create_dock(
                DOCK_TITLE_LONGFORM, DOCK_OBJ_LONGFORM, widgets["longform_editor"]
            )
            if dock:
                self.docks["longform"] = dock
                self.main_window.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self.docks["longform"]
                )
            else:
                failed_docks.append("longform")

        # 6. Map Widget (Bottom, tabbed with Timeline by default)
        if "map_widget" in widgets:
            dock = self._create_dock(
                DOCK_TITLE_MAP, DOCK_OBJ_MAP, widgets["map_widget"]
            )
            if dock:
                self.docks["map"] = dock
                self.main_window.addDockWidget(
                    Qt.DockWidgetArea.BottomDockWidgetArea, self.docks["map"]
                )
                if "timeline" in self.docks:
                    self.main_window.tabifyDockWidget(
                        self.docks["timeline"], self.docks["map"]
                    )
            else:
                failed_docks.append("map")

        # 7. AI Search Panel (Right, tabbed with inspectors)
        if "ai_search_panel" in widgets:
            dock = self._create_dock(
                DOCK_TITLE_AI_SEARCH, DOCK_OBJ_AI_SEARCH, widgets["ai_search_panel"]
            )
            if dock:
                self.docks["ai_search"] = dock
                self.main_window.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self.docks["ai_search"]
                )
                # Tabify with entity inspector if it exists
                if "entity" in self.docks:
                    self.main_window.tabifyDockWidget(
                        self.docks["entity"], self.docks["ai_search"]
                    )
            else:
                failed_docks.append("ai_search")

        # 8. Graph Widget (Bottom, tabbed with Map)
        if "graph_widget" in widgets:
            dock = self._create_dock(
                DOCK_TITLE_GRAPH, DOCK_OBJ_GRAPH, widgets["graph_widget"]
            )
            if dock:
                self.docks["graph"] = dock
                self.main_window.addDockWidget(
                    Qt.DockWidgetArea.BottomDockWidgetArea, self.docks["graph"]
                )
                # Tabify with map if it exists, otherwise with timeline
                if "map" in self.docks:
                    self.main_window.tabifyDockWidget(
                        self.docks["map"], self.docks["graph"]
                    )
                elif "timeline" in self.docks:
                    self.main_window.tabifyDockWidget(
                        self.docks["timeline"], self.docks["graph"]
                    )
            else:
                failed_docks.append("graph")

        # Report results
        if failed_docks:
            logger.warning(f"Failed to create docks: {failed_docks}")

        # Validate critical docks are present
        critical_docks = ["list", "event", "entity", "timeline"]
        missing_critical = [d for d in critical_docks if d not in self.docks]

        if missing_critical:
            error_msg = f"Critical docks missing: {missing_critical}"
            logger.error(error_msg)
            raise RuntimeError(
                f"UI initialization failed - {error_msg}. Cannot continue."
            )

        logger.info(
            f"Successfully created {len(self.docks)} docks: {list(self.docks.keys())}"
        )

    def _create_dock(
        self, title: str, obj_name: str, widget: QWidget
    ) -> Optional[QDockWidget]:
        """
        Helper to create a configured dock widget with size constraints.

        Sets minimum sizes to prevent dock collapse during resize/rearrangement.
        Includes validation and error handling to ensure robust dock creation.

        Args:
            title: Display title for the dock widget.
            obj_name: Object name for state persistence.
            widget: The widget to contain in the dock.

        Returns:
            Configured QDockWidget with size constraints, or None if creation fails.
        """
        from PySide6.QtWidgets import QSizePolicy

        from src.core.logging_config import get_logger

        logger = get_logger(__name__)

        try:
            # Validate widget parameter
            if widget is None:
                logger.error(f"Cannot create dock '{title}': widget is None")
                return None

            if not isinstance(widget, QWidget):
                logger.error(
                    f"Invalid widget type for dock '{title}': {type(widget).__name__}"
                )
                return None

            # Create dock widget
            dock = QDockWidget(title, self.main_window)
            dock.setObjectName(obj_name)
            dock.setWidget(widget)

            # Validate widget was set correctly
            if dock.widget() is not widget:
                logger.error(f"Widget assignment failed for dock '{title}'")
                return None

            # Configure dock properties
            dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                | QDockWidget.DockWidgetFeature.DockWidgetClosable
            )

            # Set minimum sizes to prevent collapse
            # Base minimum that shows title bar + some content
            dock.setMinimumWidth(250)  # Enough for form labels
            dock.setMinimumHeight(150)  # Enough for controls

            # Set size policy to allow shrinking but with limits
            policy = QSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
            )
            policy.setHorizontalStretch(1)
            policy.setVerticalStretch(1)
            dock.setSizePolicy(policy)

            logger.debug(f"Successfully created dock: {title} ({obj_name})")
            return dock

        except Exception as e:
            logger.exception(f"Failed to create dock '{title}': {e}")
            return None

    def create_file_menu(self, menu_bar: QMenuBar) -> None:
        """Creates the File menu."""
        file_menu = menu_bar.addMenu("File")

        # Open Database
        db_action = file_menu.addAction("Manage Databases...")
        db_action.triggered.connect(self.main_window.show_database_manager)

        file_menu.addSeparator()

        # Backup submenu
        backup_menu = file_menu.addMenu("Backup && Restore")

        # Create Backup
        backup_action = backup_menu.addAction("Create Backup...")
        backup_action.triggered.connect(self.main_window.create_manual_backup)

        # Restore from Backup
        restore_action = backup_menu.addAction("Restore from Backup...")
        restore_action.triggered.connect(self.main_window.restore_from_backup)

        backup_menu.addSeparator()

        # Show Backup Location
        location_action = backup_menu.addAction("Show Backup Location")
        location_action.triggered.connect(self.main_window.show_backup_location)

        # Backup Settings
        settings_action = backup_menu.addAction("Backup Settings...")
        settings_action.triggered.connect(self.main_window.show_backup_settings)

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
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
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
        # 1. Try to load from default_layout.json
        from src.core.paths import get_default_layout_path

        default_path = get_default_layout_path()
        import json
        from pathlib import Path

        if Path(default_path).exists():
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    layout_data = json.load(f)

                if "geometry" in layout_data:
                    self.main_window.restoreGeometry(
                        bytes.fromhex(layout_data["geometry"])
                    )
                if "state" in layout_data:
                    self.main_window.restoreState(bytes.fromhex(layout_data["state"]))
                return
            except Exception:
                # Fallback if load fails
                pass

        # 2. Hardcoded fallback
        if "list" in self.docks:
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.LeftDockWidgetArea, self.docks["list"]
            )
            self.docks["list"].show()

        if "event" in self.docks and "entity" in self.docks:
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.docks["event"]
            )
            self.main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.docks["entity"]
            )
            self.main_window.tabifyDockWidget(self.docks["event"], self.docks["entity"])
            self.docks["event"].show()
            self.docks["entity"].show()

            self.docks["timeline"].show()
            if "map" in self.docks:
                self.main_window.tabifyDockWidget(
                    self.docks["timeline"], self.docks["map"]
                )
                self.docks["map"].show()

    def save_as_default_layout(self) -> None:
        """
        Saves the current layout as the default factory layout.
        Writes to src/assets/default_layout.json.
        """
        from src.core.paths import get_default_layout_path

        default_path = get_default_layout_path()
        import json
        from pathlib import Path

        # Ensure directory exists
        Path(default_path).parent.mkdir(parents=True, exist_ok=True)

        layout_data = {
            "state": self.main_window.saveState().toHex().data().decode("utf-8"),
            "geometry": self.main_window.saveGeometry().toHex().data().decode("utf-8"),
        }

        with open(default_path, "w", encoding="utf-8") as f:
            json.dump(layout_data, f, indent=2)

        print(f"Default layout saved to: {default_path}")

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

        # Longform Auto-Refresh Setting
        self.longform_refresh_action = settings_menu.addAction(
            "Auto-Refresh Longform Editor"
        )
        self.longform_refresh_action.setCheckable(True)

        if hasattr(self.main_window, "toggle_longform_auto_refresh"):
            self.longform_refresh_action.triggered.connect(
                self.main_window.toggle_longform_auto_refresh
            )
            # Init state (default True)
            settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
            is_checked = settings.value("longform_auto_refresh", True, type=bool)
            self.longform_refresh_action.setChecked(is_checked)

        # Track pending dialog state
        self._calendar_dialog_pending = False

    def _open_calendar_config(self) -> None:
        """Requests loading of calendar config to open dialog."""
        from PySide6.QtCore import QMetaObject

        # Request config from worker (will be handled by on_calendar_config_loaded)
        self._calendar_dialog_pending = True
        QMetaObject.invokeMethod(
            self.main_window.worker,
            "load_calendar_config",
            Qt.ConnectionType.QueuedConnection,
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
