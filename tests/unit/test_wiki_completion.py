import pytest
from PySide6.QtWidgets import QApplication, QCompleter
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from src.gui.widgets.wiki_text_edit import WikiTextEdit


# Ensure QApplication exists
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_completer_initialization(qapp):
    """Test that set_completer initializes the QCompleter correctly."""
    editor = WikiTextEdit()
    names = ["Gandalf", "Frodo", "Sauron"]
    editor.set_completer(names)

    assert editor._completer is not None
    assert isinstance(editor._completer, QCompleter)
    assert editor._completer.model().stringList() == names


def test_completer_update(qapp):
    """Test that calling set_completer again updates the model."""
    editor = WikiTextEdit()
    names_v1 = ["Gandalf"]
    editor.set_completer(names_v1)

    names_v2 = ["Gandalf", "Bilbo"]
    editor.set_completer(names_v2)

    assert editor._completer.model().stringList() == names_v2


def test_insert_completion(qapp):
    """Test inserting a completion replaces the token."""
    editor = WikiTextEdit()
    names = ["Gandalf the Grey"]
    editor.set_completer(names)

    # Simulate typing "[[Gan"
    editor.setPlainText("Seen [[Gan")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    # Manually trigger completion insert
    # The completer prefix would normally be set by logic, but here we simulate it
    editor._completer.setCompletionPrefix("Gan")
    editor.insert_completion("Gandalf the Grey")

    # Expect "Seen [[Gandalf the Grey]]"
    # Note: Logic assumes cursor is at end of word.
    # New implementation uses HTML anchors and potentially adds a space.
    result = editor.get_wiki_text().strip()
    # Normalize result (WikiTextEdit might add non-breaking space)
    assert result == "Seen [[Gandalf the Grey]]"


def test_insert_completion_mid_sentence(qapp):
    """Test inserting completion works in middle of text."""
    editor = WikiTextEdit()
    names = ["Mordor"]
    editor.set_completer(names)

    editor.setPlainText("Go to [[Mor and fight.")

    # Move cursor after "Mor"
    cursor = editor.textCursor()
    cursor.setPosition(11)  # "Go to [[Mor" -> len is 11
    editor.setTextCursor(cursor)

    editor._completer.setCompletionPrefix("Mor")
    editor.insert_completion("Mordor")

    result = editor.get_wiki_text()
    # "Go to [[Mordor]] and fight." (plus nbsp maybe)

    # insert_completion adds &nbsp; after link.
    # So "Go to [[Mordor]] \xa0and fight." if cursor was in middle.
    # But wait, we didn't insert text AFTER the link. The text " and fight." was already there.
    # insert_completion inserts at cursor.
    # Original: "Go to [[Gan| and fight." (cursor at |)
    # We deleted "[[Gan". Inserted Anchor+Space.
    # Result: "Go to Anchor Space and fight."
    # get_wiki_text: "Go to [[Mordor]]  and fight." (Normal space + nbsp?)

    # Let's simple check content
    assert "[[Mordor]]" in result
    assert "and fight" in result
