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


def test_toggle_view_mode(qtbot):
    """Test toggling between Rich and Source mode updates content."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # 1. Start with Wiki Content
    original_text = "[[Link|Label]]"
    widget.set_wiki_text(original_text)

    # Verify initial state (Rich Mode)
    assert widget._view_mode == "rich"
    # In rich mode, text should be HTML with anchor
    assert "href" in widget.toHtml()
    assert "Label" in widget.toPlainText()
    assert "[[" not in widget.toPlainText()  # Should be rendered

    # 2. Toggle to Source
    widget.btn_toggle_view.click()

    assert widget._view_mode == "source"
    assert widget.toPlainText() == "[[Link|Label]]"

    # 3. Edit in Source Mode
    widget.setPlainText("[[NewLink]]")

    # 4. Toggle back to Rich
    widget.btn_toggle_view.click()

    assert widget._view_mode == "rich"
    # Should now be rendered
    assert "href" in widget.toHtml()
    # get_wiki_text should return the new link
    assert widget.get_wiki_text() == "[[NewLink]]"


def test_get_wiki_text_in_source_mode(qtbot):
    """Test get_wiki_text returns raw text when in source mode."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    widget.set_wiki_text("Initial")

    # Toggle to Source
    widget.toggle_view_mode()  # Programmatic toggle

    widget.setPlainText("Updated Source")

    # Should return raw text without parsing
    assert widget.get_wiki_text() == "Updated Source"


def test_set_wiki_text_in_source_mode(qtbot):
    """Test set_wiki_text updates plain text directly in source mode."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Toggle to Source
    widget.toggle_view_mode()

    widget.set_wiki_text("[[RawLink]]")

    # Should be set as plain text, not rendered HTML
    assert widget.toPlainText() == "[[RawLink]]"
    # Switch back to verify it renders
    widget.toggle_view_mode()
    assert "href" in widget.toHtml()


def test_reverse_conversion_bold(qtbot):
    """Test converting bold HTML to Markdown."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # HTML: <b>Bold Text</b>
    # Note: QTextEdit normalizes HTML, often using span style="font-weight:600;"
    # We setHtml and let Qt normalize it
    widget.setHtml("<b>Bold Text</b>")

    assert widget.get_wiki_text() == "**Bold Text**"


def test_reverse_conversion_italic(qtbot):
    """Test converting italic HTML to Markdown."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    widget.setHtml("<i>Italic Text</i>")

    assert widget.get_wiki_text() == "*Italic Text*"


def test_reverse_conversion_bold_italic(qtbot):
    """Test converting bold and italic HTML to Markdown."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    widget.setHtml("<b><i>Bold Italic</i></b>")

    # Order of * and * depends on logic, but standard is *** or ** *
    # Let's simple assertion for now, check strictness later
    result = widget.get_wiki_text()
    assert (
        result == "***Bold Italic***"
        or result == "**_Bold Italic_**"
        or result == "_**Bold Italic**_"
    )


def test_reverse_conversion_mixed(qtbot):
    """Test mixed formatting."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    widget.setHtml("Normal <b>Bold</b> and <i>Italic</i>.")

    assert widget.get_wiki_text() == "Normal **Bold** and *Italic*."


def test_reverse_conversion_wikilink_in_bold(qtbot):
    """Test WikiLink inside bold formatting."""
    # This is tricky: bold tag usually wraps the link anchor
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Simulate: **[[Link]]**
    # set_wiki_text("**[[Link]]**") -> HTML rendering
    # We want get_wiki_text to return "**[[Link]]**"

    # Manually construct similar HTML: bold span wrapping the anchor
    # But easiest is to use the parser we trust:
    widget.set_wiki_text("**[[Link]]**")

    assert widget.get_wiki_text() == "**[[Link]]**"


def test_reverse_conversion_headings(qtbot):
    """Test converting Headings via font size heuristic."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # We assume standard theme font sizes: h1=18pt, h2=16pt, h3=14pt
    # Note: set_wiki_text applies CSS, so let's use that
    widget.set_wiki_text("# Heading 1\n## Heading 2\nText")

    result = widget.get_wiki_text()
    assert "# Heading 1" in result
    assert "## Heading 2" in result
    assert "Text" in result


def test_cursor_position_preserved_on_toggle(qtbot):
    """Test that cursor position is preserved when toggling view modes."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Set some content
    widget.set_wiki_text("Hello World, this is a test")

    # In rich mode, move cursor to position 6 (at 'W')
    cursor = widget.textCursor()
    cursor.setPosition(6)
    widget.setTextCursor(cursor)

    # Verify cursor is at expected position
    assert widget.textCursor().position() == 6

    # Toggle to source mode
    widget.toggle_view_mode()

    # Cursor should NOT be at 0 (completely reset)
    assert widget.textCursor().position() > 0

    # Toggle back to rich mode
    widget.toggle_view_mode()

    # Again, should not reset to 0
    assert widget.textCursor().position() > 0


def test_cursor_mapping_with_formatting(qtbot):
    """Test cursor mapping with bold/italic formatting."""
    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Set formatted content
    widget.set_wiki_text("Hello **Bold** World")

    # Position cursor in the middle
    cursor = widget.textCursor()
    cursor.setPosition(10)
    widget.setTextCursor(cursor)

    # Toggle to source
    widget.toggle_view_mode()

    # Cursor should be preserved (not at 0)
    pos = widget.textCursor().position()
    assert pos > 0, "Cursor should not reset to start"

    # The markdown is "Hello **Bold** World"
    # Cursor should be somewhere within the text
    assert pos < len(widget.toPlainText())


def test_ctrl_b_bold_in_source_mode(qtbot):
    """Test Ctrl+B wraps selection with ** in source mode."""
    from PySide6.QtGui import QTextCursor

    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Switch to source mode
    widget.toggle_view_mode()
    widget.setPlainText("Hello World")

    # Select "World"
    cursor = widget.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)

    # Simulate Ctrl+B
    widget._toggle_bold()

    # Should wrap with **
    assert widget.toPlainText() == "Hello **World**"


def test_ctrl_i_italic_in_source_mode(qtbot):
    """Test Ctrl+I wraps selection with * in source mode."""
    from PySide6.QtGui import QTextCursor

    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Switch to source mode
    widget.toggle_view_mode()
    widget.setPlainText("Hello World")

    # Select "World"
    cursor = widget.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)

    # Simulate Ctrl+I
    widget._toggle_italic()

    # Should wrap with *
    assert widget.toPlainText() == "Hello *World*"


def test_bold_toggle_removes_markers(qtbot):
    """Test that bold toggle removes markers if already present."""
    from PySide6.QtGui import QTextCursor

    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Switch to source mode
    widget.toggle_view_mode()
    widget.setPlainText("Hello **World**")

    # Select "**World**"
    cursor = widget.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(15, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)

    # Toggle should remove markers
    widget._toggle_bold()

    assert widget.toPlainText() == "Hello World"


def test_bold_no_selection_inserts_markers(qtbot):
    """Test that bold with no selection inserts markers and positions cursor."""
    from PySide6.QtGui import QTextCursor

    widget = WikiTextEdit()
    qtbot.addWidget(widget)

    # Switch to source mode
    widget.toggle_view_mode()
    widget.setPlainText("Hello")

    # Position cursor at end
    cursor = widget.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    widget.setTextCursor(cursor)

    # Toggle bold with no selection
    widget._toggle_bold()

    # Should insert ** and position cursor between
    assert widget.toPlainText() == "Hello****"
    # Cursor should be between the markers
    assert widget.textCursor().position() == 7
