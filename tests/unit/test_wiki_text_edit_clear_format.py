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


def test_body_action_preserves_wiki_link_identity(editor):
    view = editor.editor
    view.set_wiki_text("Before [[id:entity-1|**Alpha**]] after")
    cursor = view.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    view.setTextCursor(cursor)

    view._clear_rich_formatting()

    assert "[[id:entity-1|" in view.get_wiki_text()
    assert "Alpha" in view.get_wiki_text()


def test_manual_link_special_characters_round_trip(editor):
    view = editor.editor
    source = '[[A & <B> "C" \'D\' Ω]]'
    view.setPlainText(source)
    cursor = view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    view.setTextCursor(cursor)

    view._check_for_link_closure()

    assert view.get_wiki_text() == source
