"""
Integration tests for Undo/Redo Hotkey Configuration.

Verifies that the UIManager correctly assigns shortcuts from ShortcutManager
and sets the correct shortcut context.
"""

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from src.app.main_window import MainWindow
from src.gui.utils.shortcut_manager import ShortcutManager

# Similar patches to wiring test
MAIN_WINDOW_PATCHES = [
    patch("src.app.worker_manager.DatabaseWorker"),
    patch("src.app.worker_manager.QThread"),
    patch("src.app.ui_manager.UIManager.create_timeline_menu"),
    patch("src.app.ui_manager.UIManager.create_settings_menu"),
    patch("src.app.ui_manager.UIManager.create_file_menu"),
    patch("src.app.ui_manager.UIManager.create_view_menu"),
    patch("src.app.ui_manager.UIManager.create_layouts_menu"),
    patch("src.app.ui_manager.UIManager.create_help_menu"),
]


def _start_patches():
    for p in MAIN_WINDOW_PATCHES:
        p.start()


def _stop_patches():
    for p in MAIN_WINDOW_PATCHES:
        p.stop()


def test_undo_redo_hotkeys_configured(qtbot):
    """Verify Undo/Redo actions have correct shortcuts and context."""
    _start_patches()
    try:
        window = MainWindow()
        qtbot.addWidget(window)

        # Ensure UI Manager initialized
        window._complete_initialization()
        ui_manager = window.ui_manager

        # Verify Undo Action
        assert hasattr(ui_manager, "undo_action")
        undo_action = ui_manager.undo_action

        # Check Shortcut
        expected_undo = ShortcutManager.UNDO.key_sequence
        assert undo_action.shortcut() == expected_undo
        assert undo_action.shortcutContext() == Qt.ShortcutContext.ApplicationShortcut

        # Verify Redo Action
        assert hasattr(ui_manager, "redo_action")
        redo_action = ui_manager.redo_action

        # Check Primary Shortcut
        expected_redo = ShortcutManager.REDO.key_sequence
        assert redo_action.shortcut() == expected_redo
        assert redo_action.shortcutContext() == Qt.ShortcutContext.ApplicationShortcut

        # Check Secondary Shortcut (Ctrl+Shift+Z)
        shortcuts = redo_action.shortcuts()
        assert len(shortcuts) >= 2
        assert QKeySequence("Ctrl+Shift+Z") in shortcuts

    finally:
        _stop_patches()
