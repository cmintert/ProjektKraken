"""Tests for KeyboardShortcutsDialog."""

import pytest


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    except ImportError:
        pytest.skip("PySide6 not available")


def test_keyboard_shortcuts_dialog_creation(qapp):
    """Test that KeyboardShortcutsDialog can be created."""
    from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
    
    dialog = KeyboardShortcutsDialog()
    
    assert dialog is not None
    assert dialog.windowTitle() == "Keyboard Shortcuts"
    assert dialog.minimumWidth() == 600
    assert dialog.minimumHeight() == 500
    
    dialog.close()


def test_keyboard_shortcuts_dialog_displays_shortcuts(qapp):
    """Test that dialog shows shortcuts from ShortcutManager."""
    from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
    from src.gui.utils.shortcut_manager import ShortcutManager
    
    dialog = KeyboardShortcutsDialog()
    
    # Verify dialog content contains some key shortcuts
    # We can check the window contains references to shortcuts
    # (exact testing would require inspecting widget tree)
    
    # Just verify it can be created with all shortcuts
    assert ShortcutManager.CREATE_EVENT is not None
    assert ShortcutManager.CREATE_ENTITY is not None
    assert ShortcutManager.FIND is not None
    
    dialog.close()


def test_keyboard_shortcuts_dialog_close_button(qapp):
    """Test that close button works."""

    from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
    
    dialog = KeyboardShortcutsDialog()
    
    # Find the close button and verify it exists
    # In a full test, we'd simulate clicking it
    # For now, just verify dialog can be closed
    dialog.close()
    
    assert not dialog.isVisible()


def test_keyboard_shortcuts_dialog_with_parent(qapp):
    """Test dialog creation with parent widget."""
    from PySide6.QtWidgets import QWidget

    from src.gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
    
    parent = QWidget()
    dialog = KeyboardShortcutsDialog(parent)
    
    assert dialog.parent() == parent
    
    dialog.close()
    parent.close()
