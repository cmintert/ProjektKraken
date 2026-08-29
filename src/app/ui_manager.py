"""Menus and semantic workspace actions for the production main window."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Optional, cast

from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QInputDialog, QMenuBar, QMessageBox, QWidget

from src.app.constants import (
    SETTINGS_LAYOUTS_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.qt_invocation import invoke_queued
from src.core.protocols import MainWindowProtocol
from src.gui.workspace.panel_registry import ZoneName


class UIManager:
    """Build menus that operate on panels and application coordinators."""

    def __init__(self, main_window: MainWindowProtocol) -> None:
        """Bind menu actions to the production main window."""
        self.main_window = main_window
        self._window_widget = cast(QWidget, main_window)
        self._zone_actions: dict[ZoneName, QAction] = {}

    def create_file_menu(self, menu_bar: QMenuBar) -> None:
        """Create the File menu."""
        file_menu = menu_bar.addMenu("File")
        db_action = file_menu.addAction("Manage Databases...")
        db_action.triggered.connect(
            self.main_window.import_coordinator.show_database_manager
        )
        import_action = file_menu.addAction("Import Item...")
        import_action.triggered.connect(
            self.main_window.import_coordinator.import_item_requested
        )
        paste_action = file_menu.addAction("Import Pasted JSON...")
        paste_action.triggered.connect(
            self.main_window.import_coordinator.import_pasted_json_requested
        )

        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export")
        export_md_action = export_menu.addAction("Export Longform to Markdown...")
        export_md_action.triggered.connect(
            self.main_window.longform_manager.export_longform_document
        )
        export_vault_action = export_menu.addAction("Export as Obsidian Vault...")
        export_vault_action.triggered.connect(
            self.main_window.longform_manager.export_as_vault
        )

        file_menu.addSeparator()
        backup_menu = file_menu.addMenu("Backup && Restore")
        backup_action = backup_menu.addAction("Create Backup...")
        backup_action.triggered.connect(
            self.main_window.backup_coordinator.create_manual_backup
        )
        restore_action = backup_menu.addAction("Restore from Backup...")
        restore_action.triggered.connect(
            self.main_window.backup_coordinator.restore_from_backup
        )
        backup_menu.addSeparator()
        location_action = backup_menu.addAction("Show Backup Location")
        location_action.triggered.connect(
            self.main_window.backup_coordinator.show_backup_location
        )
        settings_action = backup_menu.addAction("Backup Settings...")
        settings_action.triggered.connect(
            self.main_window.backup_coordinator.show_backup_settings
        )

        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.main_window.close)

    def create_edit_menu(self, menu_bar: QMenuBar) -> None:
        """Create application-wide undo and redo actions."""
        from PySide6.QtGui import QKeySequence

        from src.gui.utils.shortcut_manager import ShortcutManager

        edit_menu = menu_bar.addMenu("Edit")
        self.undo_action = edit_menu.addAction("Undo")
        self.undo_action.setShortcut(ShortcutManager.UNDO.key_sequence)
        self.undo_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.undo_action.setEnabled(False)
        self.main_window.addAction(self.undo_action)

        self.redo_action = edit_menu.addAction("Redo")
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
        view_menu = menu_bar.addMenu("View")
        panels_menu = view_menu.addMenu("Panels")
        workspace = self.main_window.workspace
        for definition in workspace.registry.definitions():
            action = panels_menu.addAction(definition.title)
            action.setObjectName(f"ViewPanel_{definition.id}")
            action.triggered.connect(
                lambda _checked=False, panel_id=definition.id: workspace.show_panel(
                    panel_id
                )
            )

        zones_menu = view_menu.addMenu("Zones")
        for zone in ("left", "right", "bottom"):
            zone_name = cast(ZoneName, zone)
            action = zones_menu.addAction(zone.title())
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

        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        from src.core.theme_manager import ThemeManager

        theme_manager = ThemeManager()
        action_group = QActionGroup(self._window_widget)
        for theme_name in theme_manager.get_available_themes():
            action = theme_menu.addAction(theme_name.replace("_", " ").title())
            action.setCheckable(True)
            action.setChecked(theme_name == theme_manager.current_theme_name)
            action.triggered.connect(
                lambda _checked=False, name=theme_name: theme_manager.set_theme(name)
            )
            action_group.addAction(action)

        view_menu.addSeparator()
        reset_action = view_menu.addAction("Reset Layout")
        reset_action.triggered.connect(self.reset_layout)
        self.create_layouts_menu(menu_bar)

    def _sync_zone_action(self, zone: str, visible: bool) -> None:
        if zone in self._zone_actions:
            self._zone_actions[cast(ZoneName, zone)].setChecked(visible)

    def create_layouts_menu(self, menu_bar: QMenuBar) -> None:
        """Create named workspace layout actions."""
        self.layouts_menu = menu_bar.addMenu("Layouts")
        self._refresh_layouts_menu()

    def _refresh_layouts_menu(self) -> None:
        if not hasattr(self, "layouts_menu"):
            return
        self.layouts_menu.clear()
        save_action = self.layouts_menu.addAction("Save Current Layout...")
        save_action.triggered.connect(self.prompt_save_layout)
        self.layouts_menu.addSeparator()

        layouts = self.get_saved_layouts()
        if not layouts:
            no_layouts = self.layouts_menu.addAction("No Saved Layouts")
            no_layouts.setEnabled(False)
        for name in layouts:
            layout_menu = self.layouts_menu.addMenu(name)
            restore_action = layout_menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, layout_name=name: self.restore_layout(
                    layout_name
                )
            )
            delete_action = layout_menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, layout_name=name: self.delete_layout(layout_name)
            )

        self.layouts_menu.addSeparator()
        reset_action = self.layouts_menu.addAction("Reset Layout")
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
        """Create timeline grouping and calendar actions."""
        timeline_menu = menu_bar.addMenu("Timeline")
        self.grouping_config_action = timeline_menu.addAction(
            "Configure Grouping..."
        )
        self.grouping_config_action.triggered.connect(
            self.main_window.grouping_manager.on_configure_grouping_requested
        )
        self.grouping_clear_action = timeline_menu.addAction("Clear Grouping")
        self.grouping_clear_action.triggered.connect(
            self.main_window.grouping_manager.on_clear_grouping_requested
        )
        timeline_menu.addSeparator()
        calendar_action = timeline_menu.addAction("Calendar Configuration...")
        calendar_action.triggered.connect(self._open_calendar_config)

    def create_settings_menu(self, menu_bar: QMenuBar) -> None:
        """Create AI and editing preference actions."""
        settings_menu = menu_bar.addMenu("Settings")
        search_settings_action = settings_menu.addAction(
            "AI Search Index and Settings..."
        )
        search_settings_action.triggered.connect(
            self.main_window.ai_search_manager.show_ai_settings_dialog
        )
        settings_menu.addSeparator()

        from src.app.constants import SETTINGS_AUTO_RELATION_KEY

        self.auto_relation_action = settings_menu.addAction(
            "Auto-Create Relations from Wikilinks"
        )
        self.auto_relation_action.setCheckable(True)
        self.auto_relation_action.triggered.connect(
            self.main_window.toggle_auto_relation_setting
        )
        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
        self.auto_relation_action.setChecked(
            cast(
                bool,
                settings.value(SETTINGS_AUTO_RELATION_KEY, False, type=bool),
            )
        )

        self.longform_refresh_action = settings_menu.addAction(
            "Auto-Refresh Longform Editor"
        )
        self.longform_refresh_action.setCheckable(True)
        self.longform_refresh_action.triggered.connect(
            self.main_window.toggle_longform_auto_refresh
        )
        self.longform_refresh_action.setChecked(
            cast(bool, settings.value("longform_auto_refresh", True, type=bool))
        )
        self._calendar_dialog_pending = False

    def create_help_menu(self, menu_bar: QMenuBar) -> None:
        """Create shortcut and About actions."""
        help_menu = menu_bar.addMenu("Help")
        shortcuts_action = help_menu.addAction("Keyboard Shortcuts...")
        shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        help_menu.addSeparator()
        about_action = help_menu.addAction("About ProjektKraken")
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
        """Show calendar configuration after its worker snapshot arrives."""
        if not self._calendar_dialog_pending:
            return
        self._calendar_dialog_pending = False

        from src.commands.base_command import BaseCommand
        from src.commands.calendar_commands import (
            CreateCalendarConfigCommand,
            SetActiveCalendarCommand,
            UpdateCalendarConfigCommand,
        )
        from src.gui.dialogs.calendar_config_dialog import CalendarConfigDialog

        dialog = CalendarConfigDialog(self._window_widget, config=current_config)

        def on_config_saved(config: Any) -> None:
            command: BaseCommand
            if current_config and current_config.id == config.id:
                command = UpdateCalendarConfigCommand(config)
            else:
                command = CreateCalendarConfigCommand(config)
            self.main_window.command_requested.emit(command)
            self.main_window.command_requested.emit(
                SetActiveCalendarCommand(config.id)
            )
            self._request_calendar_config()

        dialog.config_saved.connect(on_config_saved)
        dialog.exec()
