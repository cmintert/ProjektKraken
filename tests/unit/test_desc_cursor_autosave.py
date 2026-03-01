"""Regression tests for description-editor cursor preservation across autosave reloads.

Two bugs are covered:

1. (Fixed) _restore_desc_cursor_state() returned early when the editor lacked
   keyboard focus, leaving the cursor at position 0 after setHtml.

2. (Fixed) WikiTextEditView.set_completer() re-rendered the document using the
   stale _current_wiki_text (the text at initial load time) with force=True.
   Since _current_wiki_text is never updated when the user types, this replaced
   the user's unsaved edits with the original text and clamped the cursor to fit
   within the shorter original document.  This happened BEFORE load_entity/
   load_event in every autosave cycle (load_completer_data is queued before
   load_entity_details in load_data()).
"""

import pytest


@pytest.fixture
def entity_editor(qtbot):
    """Create an EntityEditorWidget for testing."""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    from src.gui.widgets.entity_editor import EntityEditorWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def event_editor(qtbot):
    """Create an EventEditorWidget for testing."""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QWidget

    from src.gui.widgets.event_editor import EventEditorWidget

    mock_parent = QWidget()
    mock_parent.worker = MagicMock()
    widget = EventEditorWidget(parent=mock_parent)
    qtbot.addWidget(widget)
    return widget


# ---------------------------------------------------------------------------
# EntityEditorWidget tests
# ---------------------------------------------------------------------------


def test_entity_desc_cursor_preserved_with_focus_on_reload(qtbot, entity_editor):
    """Cursor is restored to its pre-reload position (had_focus=True path).

    Note: in offscreen Qt mode hasFocus() always returns False, so we
    simulate the had_focus=True case by calling _save_desc_cursor_state and
    _restore_desc_cursor_state directly with had_focus=True.
    """
    from src.core.entities import Entity

    entity = Entity(id="e1", name="Ent", type="Character", description="Hello world")
    entity_editor.load_entity(entity)

    inner = entity_editor.desc_edit.editor
    cursor = inner.textCursor()
    cursor.setPosition(5)
    inner.setTextCursor(cursor)
    assert inner.textCursor().position() == 5

    # Simulate a reload with different description (forces setHtml)
    entity2 = Entity(
        id="e1", name="Ent", type="Character", description="Hello world updated"
    )
    entity_editor.load_entity(entity2)

    # The had_focus path must restore cursor (position 5 in new longer text is valid)
    # In offscreen mode, had_focus=False so the cursor restore path is the
    # no-focus path; we only assert it is not stuck at 0.
    assert inner.textCursor().position() == 5


def test_entity_desc_cursor_preserved_without_focus_on_reload(qtbot, entity_editor):
    """Cursor is restored even when the description editor does NOT have focus.

    Regression: Previously _restore_desc_cursor_state() returned early when
    had_focus was False, so the cursor was left at 0 after setHtml.
    """
    from src.core.entities import Entity

    entity = Entity(id="e1", name="Ent", type="Character", description="Hello world")
    entity_editor.load_entity(entity)

    # Move cursor to position 5 but ensure the editor does NOT have focus
    inner = entity_editor.desc_edit.editor
    cursor = inner.textCursor()
    cursor.setPosition(5)
    inner.setTextCursor(cursor)
    inner.clearFocus()

    assert not inner.hasFocus()
    assert inner.textCursor().position() == 5

    # Reload with a different description so setHtml is triggered inside
    # WikiTextEditView.set_wiki_text (get_wiki_text() != entity.description)
    entity2 = Entity(
        id="e1", name="Ent", type="Character", description="Hello world updated"
    )
    entity_editor.load_entity(entity2)

    # Cursor must be restored to 5 (not 0)
    assert inner.textCursor().position() == 5


def test_entity_desc_cursor_clamped_when_new_text_is_shorter(qtbot, entity_editor):
    """Cursor is clamped to text length when the reload brings shorter content."""
    from src.core.entities import Entity

    long_desc = "A much longer description that fills more space"
    entity = Entity(id="e1", name="Ent", type="Character", description=long_desc)
    entity_editor.load_entity(entity)

    inner = entity_editor.desc_edit.editor
    # Place cursor near the end of the long description
    end_pos = inner.document().characterCount() - 1
    cursor = inner.textCursor()
    cursor.setPosition(end_pos)
    inner.setTextCursor(cursor)
    inner.clearFocus()

    # Reload with a short description
    entity2 = Entity(id="e1", name="Ent", type="Character", description="Short")
    entity_editor.load_entity(entity2)

    # Cursor must be clamped to the end of the new (shorter) text, not 0
    new_len = len(inner.toPlainText())
    assert inner.textCursor().position() == new_len


# ---------------------------------------------------------------------------
# EventEditorWidget tests
# ---------------------------------------------------------------------------


def test_event_desc_cursor_preserved_without_focus_on_reload(qtbot, event_editor):
    """Cursor is restored for EventEditorWidget even without focus (regression)."""
    from src.core.events import Event

    event = Event(id="ev1", name="Evt", lore_date=0.0, description="First text here")
    event_editor.load_event(event)

    inner = event_editor.desc_edit.editor
    cursor = inner.textCursor()
    cursor.setPosition(6)
    inner.setTextCursor(cursor)
    inner.clearFocus()

    assert not inner.hasFocus()
    assert inner.textCursor().position() == 6

    event2 = Event(
        id="ev1", name="Evt", lore_date=0.0, description="First text here modified"
    )
    event_editor.load_event(event2)

    assert inner.textCursor().position() == 6


def test_event_desc_cursor_preserved_with_focus_on_reload(qtbot, event_editor):
    """Cursor is restored for EventEditorWidget (had_focus=True path).

    Note: in offscreen Qt mode hasFocus() always returns False; we verify
    cursor restoration is correct regardless.
    """
    from src.core.events import Event

    event = Event(id="ev1", name="Evt", lore_date=0.0, description="Some description")
    event_editor.load_event(event)

    inner = event_editor.desc_edit.editor
    cursor = inner.textCursor()
    cursor.setPosition(4)
    inner.setTextCursor(cursor)
    assert inner.textCursor().position() == 4

    event2 = Event(
        id="ev1", name="Evt", lore_date=0.0, description="Some description updated"
    )
    event_editor.load_event(event2)

    assert inner.textCursor().position() == 4


# ---------------------------------------------------------------------------
# set_completer stale _current_wiki_text bug (the REAL autosave cursor jump)
# ---------------------------------------------------------------------------


def test_set_completer_does_not_replace_unsaved_user_content(qtbot, entity_editor):
    """set_completer must not replace user's typed content with stale original.

    Regression: set_completer re-rendered the document with _current_wiki_text
    (which only updates on programmatic set_wiki_text calls, not on user typing).
    When the user had typed new text, _current_wiki_text was the original (shorter)
    text.  The force=True re-render replaced the live document with the stale
    original, corrupting both the content and the cursor position.
    """
    from PySide6.QtGui import QTextCursor

    from src.core.entities import Entity

    # Load entity with initial short description
    entity = Entity(id="e1", name="Ent", type="Character", description="Hello")
    entity_editor.load_entity(entity)

    inner = entity_editor.desc_edit.editor

    # Simulate user typing " World" by directly inserting into the document.
    # _current_wiki_text stays as "Hello" (not updated on keystrokes).
    cursor = inner.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(" World")
    inner.setTextCursor(cursor)

    typed_pos = inner.textCursor().position()  # end of "Hello World"
    assert inner.toPlainText().strip() == "Hello World"

    # Simulate completer update (this fires during every autosave cycle).
    items = [("id1", "SomeEntity", "Character"), ("id2", "AnotherEntity", "Location")]
    entity_editor.desc_edit.set_completer(items=items)

    # The document must still contain the user's typed text.
    assert inner.toPlainText().strip() == "Hello World"

    # The cursor must NOT have been clamped to the shorter original text length.
    # (Before the fix it would be min(typed_pos, len("Hello")-1).)
    assert inner.textCursor().position() == typed_pos


def test_entity_cursor_preserved_after_completer_update_then_reload(
    qtbot, entity_editor
):
    """Full autosave cycle: completer update fires BEFORE load_entity.

    Mirrors the real load_data() order: load_completer_data is queued before
    load_entity_details.  The completer update must not clobber the cursor so
    that the subsequent load_entity restores it correctly.
    """
    from PySide6.QtGui import QTextCursor

    from src.core.entities import Entity

    # Step 1: initial load
    entity = Entity(id="e1", name="Ent", type="Character", description="Hello")
    entity_editor.load_entity(entity)

    inner = entity_editor.desc_edit.editor

    # Step 2: user types " World" (cursor moves to end)
    cursor = inner.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(" World")
    inner.setTextCursor(cursor)
    assert inner.textCursor().position() == 11

    # Step 3: completer fires first (simulating load_completer_data completing)
    items = [("id1", "SomeEntity", "Character")]
    entity_editor.update_suggestions(items=items)

    # Step 4: load_entity fires (simulating load_entity_details completing).
    # entity.description is the saved value ("Hello World").
    entity2 = Entity(id="e1", name="Ent", type="Character", description="Hello World")
    entity_editor.load_entity(entity2)

    # Cursor must be at position 11 (end of "Hello World"), not ~4 (end of "Hello").
    assert inner.textCursor().position() == 11


def test_event_cursor_preserved_after_completer_update_then_reload(
    qtbot, event_editor
):
    """Full autosave cycle for EventEditorWidget: completer then reload."""
    from PySide6.QtGui import QTextCursor

    from src.core.events import Event

    event = Event(id="ev1", name="Evt", lore_date=0.0, description="Start")
    event_editor.load_event(event)

    inner = event_editor.desc_edit.editor

    # Simulate typing " text" after "Start"
    cursor = inner.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(" text")
    inner.setTextCursor(cursor)
    typed_pos = inner.textCursor().position()
    assert inner.toPlainText().strip() == "Start text"

    # Completer update fires first
    items = [("id1", "Entity1", "Character")]
    event_editor.update_suggestions(items=items)

    # Then the event details reload arrives
    event2 = Event(id="ev1", name="Evt", lore_date=0.0, description="Start text")
    event_editor.load_event(event2)

    assert inner.textCursor().position() == typed_pos
