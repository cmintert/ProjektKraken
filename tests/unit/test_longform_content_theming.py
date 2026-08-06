from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.widgets.longform.content import LongformContentWidget


@pytest.fixture
def content_widget(qtbot):
    widget = LongformContentWidget()
    qtbot.addWidget(widget)
    return widget


def test_theme_change_reloads_content_with_new_colors(content_widget):
    """Test that changing the theme updates the HTML content with new CSS colors."""
    sequence = [
        {
            "table": "events",
            "id": "1",
            "name": "Chapter 1",
            "heading_level": 1,
            "content": "Content 1",
            "meta": {},
        }
    ]
    content_widget.load_content(sequence)

    # Assert initial state doesn't have our unique test color
    assert "#123456" not in content_widget.toHtml()

    # Mock theme data with unique colors
    new_theme = {
        "text_main": "#123456",  # Unique text color
        "accent_secondary": "#222222",
        "surface": "#333333",
        "border": "#444444",
        "primary": "#555555",
        "app_bg": "#666666",
        "font_size_h1": "20pt",
        "font_size_h2": "18pt",
        "font_size_h3": "16pt",
        "font_size_body": "12pt",
    }

    # Patch ThemeManager inside content.py to return our new theme
    with patch("src.gui.widgets.longform.content.ThemeManager") as MockThemeManager:
        mock_tm = MockThemeManager.return_value
        mock_tm.get_theme.return_value = new_theme

        # Trigger theme update
        content_widget._apply_theme()

        # Verify HTML now contains the new text color
        # The CSS is embedded in <style> block in <head>
        html = content_widget.toHtml()
        assert "#123456" in html
        assert "#333333" in html  # Surface color (card bg)


def test_content_uses_compact_reading_line_height(content_widget):
    """The in-app longform stylesheet keeps paragraph leading compact."""
    assert "line-height: 1.35" in content_widget._get_theme_css()


def test_scroll_position_preserved_on_theme_change(content_widget):
    """Test that scroll position is preserved when content is reloaded for theme change."""
    # Create enough content to scroll
    content_widget.resize(400, 300)
    content_widget.show()

    sequence = [
        {
            "table": "events",
            "id": f"{i}",
            "name": f"Chapter {i}",
            "heading_level": 1,
            "content": "Content line\n" * 20,
            "meta": {},
        }
        for i in range(20)
    ]
    content_widget.load_content(sequence)

    # Allow layout to calculate
    QApplication.processEvents()

    # Scroll down
    scrollbar = content_widget.verticalScrollBar()

    # Verify we can scroll
    assert scrollbar.maximum() > 0

    target_scroll = scrollbar.maximum() // 2
    scrollbar.setValue(target_scroll)

    # Ensure value was set
    assert scrollbar.value() == target_scroll

    # Mock ThemeManager but keep same scroll
    with patch("src.gui.widgets.longform.content.ThemeManager") as MockThemeManager:
        mock_tm = MockThemeManager.return_value
        # Use a minimal theme to avoid KeyError
        mock_tm.get_theme.return_value = {
            "text_main": "#000000",
            "accent_secondary": "#000000",
            "surface": "#000000",
            "border": "#000000",
            "primary": "#000000",
            "app_bg": "#000000",
            "font_size_h1": "10pt",
            "font_size_h2": "10pt",
            "font_size_h3": "10pt",
            "font_size_body": "10pt",
        }

        content_widget._apply_theme()

        # Process events again just in case reload triggers layout
        QApplication.processEvents()

        # Verify scroll position is preserved
        # Allow small margin of error (e.g. 1-2 pixels) if floats are involved but int should be exact for same content
        assert abs(scrollbar.value() - target_scroll) <= 2
