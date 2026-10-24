"""Menus and semantic workspace actions for the production main window."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Optional, cast

from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QMenuBar, QMessageBox, QWidget

from src.app.constants import (
    SETTINGS_LAYOUTS_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.qt_invocation import invoke_queued
from src.core.protocols import MainWindowProtocol
from src.gui.utils.help_context import declare_inspection
from src.gui.workspace.panel_registry import ZoneName


class UIManager:
    """Build menus that operate on panels and application coordinators."""

    def __init__(self, main_window: MainWindowProtocol) -> None:
        """Bind menu actions to the production main window."""
        self.main_window = main_window
        self._window_widget = cast(QWidget, main_window)
        self._zone_actions: dict[ZoneName, QAction] = {}
        self._panel_actions: dict[str, QAction] = {}
        self._calendar_dialog_pending = False

    def create_file_menu(self, menu_bar: QMenuBar) -> None:
        """Create the File menu."""
        file_menu = declare_inspection(
            menu_bar.addMenu("File"),
            "src-app-ui-manager-uimanager-create-file-menu-file-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-file-menu-file-menu",
        )
        self._file_menu = file_menu
        file_menu.setToolTipsVisible(True)
        icon_library_action = declare_inspection(
            file_menu.addAction("Icon Library..."),
            "src-app-ui-manager-uimanager-create-file-menu-icon-library-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-file-menu-icon-library-action",
        )
        icon_library_action.setToolTip(
            "Import and manage project icons without selecting a marker"
        )
        icon_library_action.triggered.connect(
            self.main_window.app_coordinator.show_icon_library
        )
        file_menu.addSeparator()
        transfer_action = declare_inspection(
            file_menu.addAction("Import / Export..."),
            "src-app-ui-manager-uimanager-create-file-menu-transfer-action|world.transfer|help-inspect-src-app-ui-manager-uimanager-create-file-menu-transfer-action",
        )
        transfer_action.triggered.connect(
            self.main_window.import_coordinator.show_transfer
        )
        db_action = declare_inspection(
            file_menu.addAction("Manage Databases..."),
            "src-app-ui-manager-uimanager-create-file-menu-db-action|world.manage|help-inspect-src-app-ui-manager-uimanager-create-file-menu-db-action",
        )
        db_action.triggered.connect(
            self.main_window.import_coordinator.show_database_manager
        )

        file_menu.addSeparator()
        backup_menu = declare_inspection(
            file_menu.addMenu("Backup && Restore"),
            "src-app-ui-manager-uimanager-create-file-menu-backup-menu|world.backups|help-inspect-src-app-ui-manager-uimanager-create-file-menu-backup-menu",
        )
        backup_action = declare_inspection(
            backup_menu.addAction("Create Backup..."),
            "src-app-ui-manager-uimanager-create-file-menu-backup-action|world.backups|help-inspect-src-app-ui-manager-uimanager-create-file-menu-backup-action",
        )
        backup_action.triggered.connect(
            self.main_window.backup_coordinator.create_manual_backup
        )
        restore_action = declare_inspection(
            backup_menu.addAction("Restore from Backup..."),
            "src-app-ui-manager-uimanager-create-file-menu-restore-action|world.backups|help-inspect-src-app-ui-manager-uimanager-create-file-menu-restore-action",
        )
        restore_action.triggered.connect(
            self.main_window.backup_coordinator.restore_from_backup
        )
        backup_menu.addSeparator()
        location_action = declare_inspection(
            backup_menu.addAction("Show Backup Location"),
            "src-app-ui-manager-uimanager-create-file-menu-location-action|world.backups|help-inspect-src-app-ui-manager-uimanager-create-file-menu-location-action",
        )
        location_action.triggered.connect(
            self.main_window.backup_coordinator.show_backup_location
        )
        file_menu.addSeparator()
        exit_action = declare_inspection(
            file_menu.addAction("Exit"),
            "src-app-ui-manager-uimanager-create-file-menu-exit-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-file-menu-exit-action",
        )
        exit_action.triggered.connect(self.main_window.close)

    def create_edit_menu(self, menu_bar: QMenuBar) -> None:
        """Create application-wide undo and redo actions."""
        from PySide6.QtGui import QKeySequence

        from src.gui.utils.shortcut_manager import ShortcutManager

        edit_menu = declare_inspection(
            menu_bar.addMenu("Edit"),
            "src-app-ui-manager-uimanager-create-edit-menu-edit-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-edit-menu-edit-menu",
        )
        self.undo_action = declare_inspection(
            edit_menu.addAction("Undo"),
            "src-app-ui-manager-uimanager-create-edit-menu-self-undo-action|history.undo|help-inspect-src-app-ui-manager-uimanager-create-edit-menu-self-undo-action",
        )
        self.undo_action.setShortcut(ShortcutManager.UNDO.key_sequence)
        self.undo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.undo_action.setEnabled(False)
        self.main_window.addAction(self.undo_action)

        self.redo_action = declare_inspection(
            edit_menu.addAction("Redo"),
            "src-app-ui-manager-uimanager-create-edit-menu-self-redo-action|history.undo|help-inspect-src-app-ui-manager-uimanager-create-edit-menu-self-redo-action",
        )
        self.redo_action.setShortcuts(
            [ShortcutManager.REDO.key_sequence, QKeySequence("Ctrl+Shift+Z")]
        )
        self.redo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.redo_action.setEnabled(False)
        self.main_window.addAction(self.redo_action)

    def connect_undo_redo_actions(self) -> None:
        """Connect undo and redo after the command coordinator exists."""
        self.undo_action.triggered.connect(self.main_window.coordinator.undo)
        self.redo_action.triggered.connect(self.main_window.coordinator.redo)

    def update_undo_redo_state(self, *_args: object) -> None:
        """Refresh undo and redo enabled state."""
        coordinator = self.main_window.coordinator
        self.undo_action.setEnabled(coordinator.can_undo())
        self.redo_action.setEnabled(coordinator.can_redo())

    def create_view_menu(self, menu_bar: QMenuBar) -> None:
        """Create semantic panel, zone, theme, and reset actions."""
        view_menu = declare_inspection(
            menu_bar.addMenu("View"),
            "src-app-ui-manager-uimanager-create-view-menu-view-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-view-menu-view-menu",
        )
        panels_menu = declare_inspection(
            view_menu.addMenu("Panels"),
            "src-app-ui-manager-uimanager-create-view-menu-panels-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-view-menu-panels-menu",
        )
        workspace = self.main_window.workspace
        for definition in workspace.registry.definitions():
            action = declare_inspection(
                panels_menu.addAction(definition.title),
                "workspace.show-panel|workspace.navigation|help-inspect-workspace-show-panel",
            )
            action.setObjectName(f"ViewPanel_{definition.id}")
            action.setCheckable(True)
            action.setChecked(workspace.is_panel_open(definition.id))
            action.triggered.connect(
                lambda checked=False, panel_id=definition.id: (
                    workspace.show_panel(panel_id)
                    if checked
                    else workspace.close_panel(panel_id)
                )
            )
            self._panel_actions[definition.id] = action
        workspace.layout_changed.connect(self._sync_panel_actions)

        zones_menu = declare_inspection(
            view_menu.addMenu("Zones"),
            "src-app-ui-manager-uimanager-create-view-menu-zones-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-view-menu-zones-menu",
        )
        for zone in ("left", "right", "bottom"):
            zone_name = cast(ZoneName, zone)
            action = declare_inspection(
                zones_menu.addAction(zone.title()),
                "workspace.show-zone|workspace.navigation|help-inspect-workspace-show-zone",
            )
            action.setCheckable(True)
            action.setChecked(workspace.zone_visible(zone_name))
            action.triggered.connect(
                lambda checked=False, target=zone_name: (
                    workspace.show_zone(target)
                    if checked
                    else workspace.hide_zone(target)
                )
            )
            self._zone_actions[zone_name] = action
        workspace.zone_visibility_changed.connect(self._sync_zone_action)

        from src.gui.widgets.focus_writing import FocusWritingController

        self.focus_writing = FocusWritingController(self.main_window, view_menu)

        view_menu.addSeparator()
        reset_action = declare_inspection(
            view_menu.addAction("Reset Layout"),
            "src-app-ui-manager-uimanager-create-view-menu-reset-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-view-menu-reset-action",
        )
        reset_action.triggered.connect(self.reset_layout)
        self.create_layouts_menu(menu_bar)

    def _sync_zone_action(self, zone: str, visible: bool) -> None:
        if zone in self._zone_actions:
            self._zone_actions[cast(ZoneName, zone)].setChecked(visible)

    def _sync_panel_actions(self) -> None:
        workspace = self.main_window.workspace
        for panel_id, action in self._panel_actions.items():
            action.setChecked(workspace.is_panel_open(panel_id))

    def create_layouts_menu(self, menu_bar: QMenuBar) -> None:
        """Create named workspace layout actions."""
        self.layouts_menu = declare_inspection(
            menu_bar.addMenu("Layouts"),
            "src-app-ui-manager-uimanager-create-layouts-menu-self-layouts-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-layouts-menu-self-layouts-menu",
        )
        self._refresh_layouts_menu()

    def _refresh_layouts_menu(self) -> None:
        if not hasattr(self, "layouts_menu"):
            return
        self.layouts_menu.clear()
        save_action = declare_inspection(
            self.layouts_menu.addAction("Save Current Layout..."),
            "src-app-ui-manager-uimanager-refresh-layouts-menu-save-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-save-action",
        )
        save_action.triggered.connect(self.prompt_save_layout)
        self.layouts_menu.addSeparator()

        layouts = self.get_saved_layouts()
        if not layouts:
            no_layouts = declare_inspection(
                self.layouts_menu.addAction("No Saved Layouts"),
                "src-app-ui-manager-uimanager-refresh-layouts-menu-no-layouts|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-no-layouts",
            )
            no_layouts.setEnabled(False)
        for name in layouts:
            layout_menu = declare_inspection(
                self.layouts_menu.addMenu(name),
                "workspace.saved-layout|workspace.navigation|help-inspect-workspace-saved-layout",
            )
            restore_action = declare_inspection(
                layout_menu.addAction("Restore"),
                "src-app-ui-manager-uimanager-refresh-layouts-menu-restore-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-restore-action",
            )
            restore_action.triggered.connect(
                lambda _checked=False, layout_name=name: self.restore_layout(
                    layout_name
                )
            )
            delete_action = declare_inspection(
                layout_menu.addAction("Delete"),
                "src-app-ui-manager-uimanager-refresh-layouts-menu-delete-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-delete-action",
            )
            delete_action.triggered.connect(
                lambda _checked=False, layout_name=name: self.delete_layout(layout_name)
            )

        self.layouts_menu.addSeparator()
        reset_action = declare_inspection(
            self.layouts_menu.addAction("Reset Layout"),
            "src-app-ui-manager-uimanager-refresh-layouts-menu-reset-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-refresh-layouts-menu-reset-action",
        )
        reset_action.triggered.connect(self.reset_layout)

    def prompt_save_layout(self) -> None:
        """Ask for a name and save the current explicit workspace layout."""
        name, accepted = QInputDialog.getText(
            self._window_widget, "Save Layout", "Layout Name:"
        )
        if not accepted or not name:
            return
        if name in self.get_saved_layouts():
            reply = QMessageBox.question(
                self._window_widget,
                "Overwrite Layout?",
                f"Layout '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.save_layout(name)

    def save_layout(self, name: str) -> None:
        """Save panel membership, order, active tabs, sizes, and visibility."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = self._load_saved_layouts(settings)
        layouts[name] = self.main_window.workspace.capture_layout()
        settings.setValue(SETTINGS_LAYOUTS_KEY, json.dumps(layouts, sort_keys=True))
        self._refresh_layouts_menu()

    def restore_layout(self, name: str) -> None:
        """Restore a named workspace layout without changing window geometry."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = self._load_saved_layouts(settings)
        layout = layouts.get(name)
        if layout is not None:
            self.main_window.workspace.apply_layout(layout)

    def delete_layout(self, name: str) -> None:
        """Delete a named workspace layout after confirmation."""
        reply = QMessageBox.question(
            self._window_widget,
            "Delete Layout",
            f"Are you sure you want to delete layout '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        layouts = self._load_saved_layouts(settings)
        if name in layouts:
            del layouts[name]
            settings.setValue(
                SETTINGS_LAYOUTS_KEY,
                json.dumps(layouts, sort_keys=True),
            )
            self._refresh_layouts_menu()

    def get_saved_layouts(self) -> list[str]:
        """Return named layouts in display order."""
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        return sorted(self._load_saved_layouts(settings))

    @staticmethod
    def _load_saved_layouts(settings: QSettings) -> dict[str, object]:
        """Load readable JSON layouts and tolerate the legacy mapping form."""
        raw_layouts = settings.value(SETTINGS_LAYOUTS_KEY, {})
        if isinstance(raw_layouts, str):
            try:
                raw_layouts = json.loads(raw_layouts)
            except (TypeError, ValueError):
                return {}
        if isinstance(raw_layouts, Mapping):
            return {str(name): layout for name, layout in raw_layouts.items()}
        return {}

    def reset_layout(self) -> None:
        """Restore the deterministic factory workspace only."""
        self.main_window.workspace.reset_layout()

    def create_timeline_menu(self, menu_bar: QMenuBar) -> None:
        """Keep deliberate timeline operations outside configuration."""
        timeline_menu = declare_inspection(
            menu_bar.addMenu("Timeline"),
            "src-app-ui-manager-uimanager-create-timeline-menu-timeline-menu|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-timeline-menu",
        )
        self.grouping_clear_action = declare_inspection(
            timeline_menu.addAction("Clear Grouping"),
            "src-app-ui-manager-uimanager-create-timeline-menu-self-grouping-clear-action|workspace.navigation|help-inspect-src-app-ui-manager-uimanager-create-timeline-menu-self-grouping-clear-action",
        )
        self.grouping_clear_action.triggered.connect(
            self.main_window.grouping_manager.on_clear_grouping_requested
        )

    def create_settings_menu(self, menu_bar: QMenuBar) -> None:
        """Expose one direct Settings action without a submenu."""
        action = declare_inspection(
            menu_bar.addAction("Settings"),
            "settings.center.open|settings.center|help-inspect-settings-center-open",
        )
        action.triggered.connect(
            lambda: self.main_window.app_coordinator.settings.open_settings()
        )

    def create_help_menu(self, menu_bar: QMenuBar) -> None:
        """Compose contextual Help and retain shortcut and About actions."""
        from src.app.help_composition import compose_help

        self.help_coordinator = compose_help(self._window_widget, self.main_window)
        help_menu = declare_inspection(
            menu_bar.addMenu("Help"),
            "src-app-ui-manager-uimanager-create-help-menu-help-menu|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-help-menu",
        )
        help_menu.aboutToShow.connect(self.help_coordinator.suspend_origin)
        current_action = declare_inspection(
            help_menu.addAction("Help for current task"),
            "src-app-ui-manager-uimanager-create-help-menu-current-action|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-current-action",
        )
        current_action.triggered.connect(self.help_coordinator.request)
        manual_action = declare_inspection(
            help_menu.addAction("User manual"),
            "src-app-ui-manager-uimanager-create-help-menu-manual-action|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-manual-action",
        )
        manual_action.triggered.connect(
            lambda: self.help_coordinator.open_topic("manual.home")
        )
        inspect_action = declare_inspection(
            help_menu.addAction("Inspect control"),
            "src-app-ui-manager-uimanager-create-help-menu-inspect-action|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-inspect-action",
        )
        inspect_action.triggered.connect(self.help_coordinator.inspection.enter)
        help_menu.addSeparator()
        shortcuts_action = declare_inspection(
            help_menu.addAction("Keyboard Shortcuts..."),
            "src-app-ui-manager-uimanager-create-help-menu-shortcuts-action|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-shortcuts-action",
        )
        shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        help_menu.addSeparator()
        about_action = declare_inspection(
            help_menu.addAction("About ProjektKraken"),
            "src-app-ui-manager-uimanager-create-help-menu-about-action|manual.inspect|help-inspect-src-app-ui-manager-uimanager-create-help-menu-about-action",
        )
        about_action.triggered.connect(self._show_about_dialog)

    def _show_keyboard_shortcuts(self) -> None:
        from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog

        KeyboardShortcutsDialog(self._window_widget).exec()

    def _show_about_dialog(self) -> None:
        from src.gui.dialogs.about_dialog import AboutDialog

        AboutDialog(self._window_widget).exec()

    def _open_calendar_config(self) -> None:
        self._calendar_dialog_pending = True
        self._request_calendar_config()

    def _request_calendar_config(self) -> None:
        invoke_queued(
            cast(QObject, self.main_window.worker),
            "load_calendar_config",
        )

    def show_calendar_dialog(self, current_config: Optional[Any]) -> None:
        """Reveal the shared calendar page after an explicit configuration request."""
        if not self._calendar_dialog_pending:
            return
        self._calendar_dialog_pending = False
        self.main_window.app_coordinator.settings.open_settings("world.calendar")
