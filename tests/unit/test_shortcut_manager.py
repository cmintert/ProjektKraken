from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from src.gui.utils.shortcut_manager import KeyboardShortcut, ShortcutManager


def test_shortcut_definition():
    """Test that shortcuts are defined correctly."""
    assert isinstance(ShortcutManager.CREATE_EVENT, KeyboardShortcut)
    assert ShortcutManager.CREATE_EVENT.name == "Create Event"
    assert ShortcutManager.CREATE_EVENT.sequence == "Ctrl+E"


def test_check_event_match():
    """Test matching logic."""
    # Create a mock event for Ctrl+E
    # QKeyEvent(type, key, modifiers)
    # Qt.Key_E is likely 69 (ASCII 'E') or found in Qt.Key

    event = QKeyEvent(
        QEvent.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier
    )

    assert ShortcutManager.check_event(event, ShortcutManager.CREATE_EVENT)


def test_check_event_mismatch():
    """Test matching logic failure."""
    # Control+F (should not match Ctrl+E)
    event = QKeyEvent(
        QEvent.KeyPress, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
    )
    assert not ShortcutManager.check_event(event, ShortcutManager.CREATE_EVENT)

    # Shift+E (should not match Ctrl+E)
    event = QKeyEvent(QEvent.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.ShiftModifier)
    assert not ShortcutManager.check_event(event, ShortcutManager.CREATE_EVENT)


def test_formatting_shortcuts():
    """Test formatting shortcuts match."""
    # Ctrl+B
    event_bold = QKeyEvent(
        QEvent.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier
    )
    assert ShortcutManager.check_event(event_bold, ShortcutManager.FORMAT_BOLD)


def test_outline_shortcuts():
    """Test promote/demote shortcuts match."""
    # Ctrl+[
    event_promote = QKeyEvent(
        QEvent.KeyPress, Qt.Key.Key_BracketLeft, Qt.KeyboardModifier.ControlModifier
    )
    assert ShortcutManager.check_event(event_promote, ShortcutManager.OUTLINE_PROMOTE)
