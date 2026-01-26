from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication

from src.gui.utils.shortcut_manager import ShortcutManager, KeyboardShortcut
from src.gui.widgets.longform.content import LongformContentWidget
from src.gui.widgets.longform.editor import LongformEditorWidget


@pytest.fixture
def editor_widget(qtbot):
    # Ensure settings don't interfere with theme loading in tests
    settings = QSettings("ProjektKraken", "ThemeSettings")
    settings.setValue("current_theme", "dark_mode")

    widget = LongformEditorWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def test_shortcut_manager_has_find():
    """Test that ShortcutManager has FIND defined correctly."""
    assert hasattr(ShortcutManager, "FIND")
    assert ShortcutManager.FIND.sequence == "Ctrl+F"
    assert ShortcutManager.FIND.name == "Find"


def test_content_find_text(qtbot):
    """Test finding text in content widget."""
    widget = LongformContentWidget()
    qtbot.addWidget(widget)

    # Load content with "Hello World"
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Hello World. This is a test. Hello again.",
            "meta": {},
        },
    ]
    widget.load_content(sequence)

    # Find "Hello"
    assert widget.find_text("Hello") is True

    # Cursor should be after first Hello
    # Find next "Hello"
    assert widget.find_text("Hello") is True

    # Find "Zebra" (not there)
    assert widget.find_text("Zebra") is False

    # Find backwards "World"
    # Move cursor to end first or reset? API is stateful.
    # Reset cursor
    from PySide6.QtGui import QTextCursor

    widget.moveCursor(QTextCursor.Start)

    assert widget.find_text("World") is True
    # Ensure we are at "World"

    # Search backwards for "Hello" (should be the one before World)
    assert widget.find_text("Hello", backward=True) is True


def test_editor_search_bar_toggle(editor_widget, qtbot):
    """Test that search bar toggles with Ctrl+F."""

    # Initially hidden
    assert editor_widget.search_widget.isVisible() is False

    # Trigger toggle via method directly (simulating shortcut activation)
    editor_widget._toggle_search()

    assert editor_widget.search_widget.isVisible() is True
    assert editor_widget.search_input.hasFocus()

    # Toggle again (should stay visible but focus input, or hide if focused?)
    # Implementation: if focused, hide.
    editor_widget._toggle_search()
    assert editor_widget.search_widget.isVisible() is False


def test_editor_search_performance(editor_widget, qtbot):
    """Test performing search via UI buttons."""
    # Setup content
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "C1",
            "heading_level": 1,
            "content": "Apple Banana Apple",
            "meta": {},
        }
    ]
    editor_widget.load_sequence(sequence)
    editor_widget._toggle_search()

    # Type "Apple"
    editor_widget.search_input.setText("Apple")

    # Mock content.find_text to verify calls
    with patch.object(
        editor_widget.content, "find_text", return_value=True
    ) as mock_find:
        # Click Next
        editor_widget._perform_search_next()
        mock_find.assert_called_with("Apple", backward=False)

        # Click Prev
        editor_widget._perform_search_prev()
        mock_find.assert_called_with("Apple", backward=True)


def test_editor_escape_hides_search(editor_widget, qtbot):
    """Test that Escape key hides search."""
    editor_widget._toggle_search()
    assert editor_widget.search_widget.isVisible() is True

    # Simulate Escape
    # Note: QShortcut activation in test requires active window or manual trigger.
    # We'll trigger the handler manually.
    editor_widget._handle_escape()

    assert editor_widget.search_widget.isVisible() is False
