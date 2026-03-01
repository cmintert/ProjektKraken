import pytest
from PySide6.QtGui import QFont, QTextCursor

from src.gui.widgets.wiki_text_edit import WikiTextEdit


@pytest.fixture
def editor(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    return widget


def test_clear_formatting_source_mode(editor):
    """Test clearing markdown formatting in source mode."""
    view = editor.editor
    view.toggle_view_mode()  # Switch to source (MD)
    assert view._view_mode == "source"

    # Set some formatted text
    view.setPlainText("# Heading\n**Bold** and *Italic* text")

    # 1. Clear Heading
    cursor = view.textCursor()
    cursor.setPosition(2)  # Inside heading
    view.setTextCursor(cursor)
    view._clear_formatting()

    assert "Heading" in view.toPlainText()
    assert "#" not in view.toPlainText().split("\n")[0]

    # 2. Clear Inline Formatting (Select 'Bold' and 'Italic')
    view.setPlainText("**Bold** and *Italic*")
    cursor = view.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    view.setTextCursor(cursor)
    view._clear_formatting()

    # regex sub: **Bold** -> Bold, *Italic* -> Italic
    content = view.toPlainText()
    assert content == "Bold and Italic"


def test_clear_formatting_rich_mode(editor):
    """Test clearing formatting in rich mode."""
    view = editor.editor
    assert view._view_mode == "rich"

    # Set Heading
    view.set_wiki_text("# Heading")
    cursor = view.textCursor()
    cursor.setPosition(2)
    view.setTextCursor(cursor)

    assert cursor.blockFormat().headingLevel() == 1

    # Clear it
    view._clear_formatting()
    assert view.textCursor().blockFormat().headingLevel() == 0

    # Test Bold/Italic clearing
    view.set_wiki_text("**Bold Text**")
    cursor = view.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    view.setTextCursor(cursor)

    assert cursor.charFormat().fontWeight() > QFont.Weight.Normal

    view._clear_formatting()
    assert view.textCursor().charFormat().fontWeight() == QFont.Weight.Normal
    assert view.textCursor().charFormat().fontItalic() is False
