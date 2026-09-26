from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QCompleter

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
    model = editor._completer.model()
    assert [model.item(row).text() for row in range(model.rowCount())] == names


def test_completer_update(qapp):
    """Test that calling set_completer again updates the model."""
    editor = WikiTextEdit()
    names_v1 = ["Gandalf"]
    editor.set_completer(names_v1)

    names_v2 = ["Gandalf", "Bilbo"]
    editor.set_completer(names_v2)

    model = editor._completer.model()
    assert [model.item(row).text() for row in range(model.rowCount())] == names_v2


def test_incremental_completion_preserves_model_and_duplicate_identity(qapp):
    editor = WikiTextEdit()
    editor.set_completer(
        items=[
            ("entity-1", "Alpha", "entity"),
            ("event-1", "Alpha", "event"),
            ("entity-2", "Zulu", "entity"),
        ]
    )
    model = editor._completer.model()
    editor.apply_completion_effects(
        [
            {
                "object_type": "entity",
                "operation": "upsert",
                "object_id": "entity-2",
                "snapshot": {
                    "id": "entity-2",
                    "name": "Beta",
                    "type": "Person",
                },
                "relations_changed": False,
            }
        ]
    )
    assert editor._completer.model() is model
    assert [model.item(row).text() for row in range(model.rowCount())] == [
        "Alpha — Entity · entity-1",
        "Alpha — Event · event-1",
        "Beta",
    ]
    assert [model.item(row).data(Qt.ItemDataRole.UserRole) for row in range(2)] == [
        ["entity-1", "Alpha", "entity"],
        ["event-1", "Alpha", "event"],
    ]
    assert "Alpha" not in editor.editor._completion_map

    editor.apply_completion_effects(
        [
            {
                "object_type": "event",
                "operation": "delete",
                "object_id": "event-1",
                "snapshot": None,
                "relations_changed": True,
            }
        ]
    )
    assert [model.item(row).text() for row in range(model.rowCount())] == [
        "Alpha",
        "Beta",
    ]
    assert editor.editor._completion_map["Alpha"] == ("entity-1", "entity")


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
    refresh = Mock(wraps=editor.editor._refresh_document_layout)
    editor.editor._refresh_document_layout = refresh
    editor.insert_completion("Gandalf the Grey")

    # Expect "Seen [[Gandalf the Grey]]"
    # Note: Logic assumes cursor is at end of word.
    # New implementation uses HTML anchors and potentially adds a space.
    result = editor.get_wiki_text().strip()
    # Normalize result (WikiTextEdit might add non-breaking space)
    assert result == "Seen [[Gandalf the Grey]]"
    refresh.assert_called_once_with()


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
    assert result == "Go to [[Mordor]] and fight."
    assert "\u00a0" not in result


def test_duplicate_popup_rows_insert_their_own_ids(qapp):
    editor = WikiTextEdit()
    editor.set_completer(
        items=[
            ("entity-1", "Alpha", "entity"),
            ("entity-2", "Alpha", "entity"),
            ("event-1", "Alpha", "event"),
        ]
    )
    model = editor._completer.model()
    for row, item_id in enumerate(("entity-1", "entity-2", "event-1")):
        editor.setPlainText("See [[Alp")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor._completer.setCompletionPrefix("Alp")
        editor.editor.insert_completion_index(model.index(row, 0))
        assert editor.get_wiki_text() == f"See [[id:{item_id}|Alpha]]"
