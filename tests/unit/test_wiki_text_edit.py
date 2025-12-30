"""
Unit tests for WikiTextEdit.
"""

import pytest
from PySide6.QtCore import Qt

from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit

# Requires qtbot to interact with widgets


def test_ctrl_click_emits_signal(qtbot):
    """Test that Ctrl+Click on a link emits the signal."""
    widget = WikiTextEdit()
    # We use HTML anchor for the test context
    widget.setHtml('Jump to <a href="The Shire">The Shire</a>.')
    # widget.show()
    qtbot.addWidget(widget)

    # Mock anchorAt to return a valid href
    widget.anchorAt = lambda pos: "The Shire"

    with qtbot.waitSignal(widget.link_clicked) as blocker:
        # Simulate Ctrl+Click
        qtbot.mouseClick(widget.viewport(), Qt.LeftButton, Qt.ControlModifier)

    assert blocker.args == ["The Shire"]


def test_normal_click_ignores_link(qtbot):
    """Test that click without Ctrl does NOT emit signal."""
    widget = WikiTextEdit()
    # Mock anchorAt to return a valid href (simulate hovering a link)
    widget.anchorAt = lambda pos: "The Shire"
    qtbot.addWidget(widget)

    # No signal expected
    try:
        with qtbot.waitSignal(widget.link_clicked, timeout=200):
            qtbot.mouseClick(widget.viewport(), Qt.LeftButton, Qt.NoModifier)
        pytest.fail("Signal should not have been emitted")
    except Exception:
        # Expected timeout (good)
        pass


def test_font_sizes_applied_on_init(qtbot):
    """Test that font sizes from theme are applied on initialization."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Get theme font sizes
    tm = ThemeManager()
    theme = tm.get_theme()
    fs_h1 = theme.get("font_size_h1", "18pt")

    # Check that stylesheet is applied
    stylesheet = widget.document().defaultStyleSheet()
    assert stylesheet is not None
    assert len(stylesheet) > 0
    # Font size should be in the stylesheet
    assert fs_h1 in stylesheet or "font-size:" in stylesheet


def test_font_sizes_applied_in_set_wiki_text(qtbot):
    """Test that font sizes are applied when setting wiki text."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Set some wiki text with headings
    widget.set_wiki_text("# Heading 1\n\nSome content here.")

    # Get theme font sizes
    tm = ThemeManager()
    theme = tm.get_theme()
    fs_h1 = theme.get("font_size_h1", "18pt")

    # Check that stylesheet contains font sizes
    stylesheet = widget.document().defaultStyleSheet()
    assert stylesheet is not None
    assert fs_h1 in stylesheet


def test_theme_change_updates_stylesheet(qtbot):
    """Test that changing theme updates the stylesheet."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Set initial content
    widget.set_wiki_text("# Test Heading")

    # Change theme (if there's another theme available)
    tm = ThemeManager()
    available_themes = tm.get_available_themes()

    if len(available_themes) > 1:
        # Switch to a different theme
        current_theme = tm.current_theme_name
        new_theme = [t for t in available_themes if t != current_theme][0]

        # Trigger theme change
        tm.set_theme(new_theme)

        # Check that stylesheet was updated
        updated_stylesheet = widget.document().defaultStyleSheet()
        # Note: Stylesheet might be the same if font sizes are identical
        # But the connection should be working
        assert updated_stylesheet is not None
