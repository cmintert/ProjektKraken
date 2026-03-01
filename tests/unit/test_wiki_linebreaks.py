"""TDD regression tests for linebreak round-trip in WikiTextEditView.

The Qt HTML renderer converts ``<br>`` (produced by the ``nl2br`` markdown
extension from a single ``\\n``) to ``\\u2028`` (Qt's in-block line-separator
character) inside the QTextDocument.  Before the fix, ``get_wiki_text()``
returned ``\\u2028`` verbatim, which:

1.  Meant ``_current_wiki_text`` contained ``\\u2028`` rather than ``\\n``.
2.  When passed back to ``markdown.markdown()``, ``\\u2028`` was rendered as a
    space, silently discarding the linebreak.
3.  When switching from rich → source mode, the source view showed the raw
    ``\\u2028`` character (invisible or as a replacement box) instead of a
    real newline.

Fix: in ``_process_fragment``, replace ``\\u2028`` with ``\\n`` immediately
after reading the fragment text, so all callers always receive clean newlines.
"""

import pytest

LINE_SEP = "\u2028"  # Qt's in-block line-separator character


@pytest.fixture
def rich_editor(qtbot):
    """Create a WikiTextEditView in the default rich mode."""
    from src.gui.widgets.wiki_text_edit import WikiTextEditView

    widget = WikiTextEditView()
    qtbot.addWidget(widget)
    assert widget._view_mode == "rich"
    return widget


@pytest.fixture
def wiki_edit(qtbot):
    """Create a WikiTextEdit wrapper (includes mode-toggle action)."""
    from src.gui.widgets.wiki_text_edit import WikiTextEdit

    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    return widget


# ---------------------------------------------------------------------------
# RED group 1: get_wiki_text must not return \u2028
# ---------------------------------------------------------------------------


def test_get_wiki_text_no_line_separator_single_newline(rich_editor):
    """get_wiki_text must convert Qt line-separator (\\u2028) to \\n.

    A single \\n fed to set_wiki_text produces a <br> in HTML, which Qt stores
    as \\u2028 in the block.  get_wiki_text must normalise this back to \\n.
    """
    rich_editor.set_wiki_text("Line1\nLine2")
    result = rich_editor.get_wiki_text()
    assert LINE_SEP not in result, (
        f"get_wiki_text() returned \\u2028 character: {repr(result)}"
    )


def test_single_newline_roundtrip_rich_mode(rich_editor):
    """set_wiki_text('A\\nB') → get_wiki_text() must return 'A\\nB'."""
    rich_editor.set_wiki_text("A\nB")
    result = rich_editor.get_wiki_text()
    assert result == "A\nB", f"Expected 'A\\nB', got {repr(result)}"


def test_mixed_newline_roundtrip_rich_mode(rich_editor):
    """'A\\nB\\n\\nC' must survive a set/get round-trip in rich mode."""
    rich_editor.set_wiki_text("A\nB\n\nC")
    result = rich_editor.get_wiki_text()
    assert result == "A\nB\n\nC", f"Expected 'A\\nB\\n\\nC', got {repr(result)}"


def test_paragraph_break_unchanged(rich_editor):
    """Paragraph breaks (\\n\\n) must still round-trip as \\n\\n."""
    rich_editor.set_wiki_text("Para1\n\nPara2")
    result = rich_editor.get_wiki_text()
    assert result == "Para1\n\nPara2", f"Got {repr(result)}"


def test_current_wiki_text_no_line_separator(rich_editor):
    """_current_wiki_text must not contain \\u2028 after set_wiki_text."""
    rich_editor.set_wiki_text("Hello\nWorld")
    assert LINE_SEP not in rich_editor._current_wiki_text, (
        f"_current_wiki_text contains \\u2028: {repr(rich_editor._current_wiki_text)}"
    )


# ---------------------------------------------------------------------------
# RED group 2: mode-switch must preserve linebreaks
# ---------------------------------------------------------------------------


def test_mode_switch_rich_to_source_preserves_single_newline(wiki_edit):
    """Rich mode content with \\n → source mode must show \\n not \\u2028."""
    wiki_edit.set_wiki_text("Line1\nLine2")
    assert wiki_edit.editor._view_mode == "rich"

    # Switch rich → source
    wiki_edit.action_toggle_mode.trigger()
    assert wiki_edit.editor._view_mode == "source"

    source_text = wiki_edit.toPlainText()
    assert LINE_SEP not in source_text, (
        f"Source mode contains \\u2028: {repr(source_text)}"
    )
    assert source_text == "Line1\nLine2", (
        f"Source mode shows {repr(source_text)} instead of 'Line1\\nLine2'"
    )


def test_mode_switch_source_to_rich_to_source_preserves_newline(wiki_edit):
    """Source mode \\n must survive rich-mode and back without corruption."""
    # Start in source mode
    wiki_edit.action_toggle_mode.trigger()  # rich → source
    assert wiki_edit.editor._view_mode == "source"
    wiki_edit.setPlainText("Hello\nWorld")

    # Switch source → rich
    wiki_edit.action_toggle_mode.trigger()
    assert wiki_edit.editor._view_mode == "rich"

    # Switch rich → source again
    wiki_edit.action_toggle_mode.trigger()
    assert wiki_edit.editor._view_mode == "source"

    source_text = wiki_edit.toPlainText()
    assert LINE_SEP not in source_text, (
        f"After round-trip, source contains \\u2028: {repr(source_text)}"
    )
    assert source_text == "Hello\nWorld", (
        f"After round-trip, source shows {repr(source_text)}"
    )


def test_linebreak_not_lost_when_stale_text_re_rendered(rich_editor):
    """Feeding _current_wiki_text back into set_wiki_text must not lose the break.

    Before fix: _current_wiki_text = 'A\\u2028B'; markdown treats \\u2028 as a
    space, so the linebreak is silently dropped.
    """
    rich_editor.set_wiki_text("A\nB")
    # Simulate what set_completer/_on_theme_changed does: re-render with stored text
    stored = rich_editor._current_wiki_text
    rich_editor.set_wiki_text(stored, force=True)
    result = rich_editor.get_wiki_text()
    # Linebreak must still be present (as \n, not as \u2028 or space)
    assert "\n" in result, f"Linebreak lost after re-render: {repr(result)}"
    assert LINE_SEP not in result


# ---------------------------------------------------------------------------
# RED group 3: empty blocks must survive set_completer (autosave cycle)
# ---------------------------------------------------------------------------


def test_empty_block_preserved_after_completer_update(rich_editor):
    """Empty block between paragraphs must survive a set_completer() call.

    The root cause: set_completer() called set_wiki_text(get_wiki_text(), force=True)
    which round-trips through markdown.  'Hello\\n\\nWorld' from a 3-block document
    maps to the same string as a 2-block document, so the round-trip silently
    collapses the empty block.
    Fix: set_completer should not call set_wiki_text at all — use _update_link_colors.
    """
    from PySide6.QtGui import QTextCursor

    # Start with "Hello" rendered
    rich_editor.set_wiki_text("Hello")
    # Simulate user pressing Enter twice then typing "World"
    cursor = rich_editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertBlock()  # empty block
    cursor.insertBlock()  # "World" block
    cursor.insertText("World")
    rich_editor.setTextCursor(cursor)

    block_count_before = rich_editor.document().blockCount()
    assert block_count_before == 3, f"Setup error: expected 3 blocks, got {block_count_before}"

    # Simulate an autosave completer update
    items = [("id1", "Alice", "Character"), ("id2", "Bob", "Location")]
    rich_editor.set_completer(items=items)

    block_count_after = rich_editor.document().blockCount()
    assert block_count_after == block_count_before, (
        f"set_completer() collapsed {block_count_before} blocks to "
        f"{block_count_after}"
    )


def test_cursor_position_preserved_after_completer_update_with_empty_block(rich_editor):
    """Cursor in 'World' must not jump to after 'Hello' when completer fires.

    When an empty block exists between 'Hello' and 'World', the cursor absolute
    position is higher than the end of 'Hello'.  Before the fix, set_completer's
    re-render collapsed the doc so the cursor was clamped to end-of-'Hello'.
    """
    from PySide6.QtGui import QTextCursor

    rich_editor.set_wiki_text("Hello")
    cursor = rich_editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertBlock()
    cursor.insertBlock()
    cursor.insertText("World")
    rich_editor.setTextCursor(cursor)

    pos_before = rich_editor.textCursor().position()
    assert pos_before > 0

    items = [("id1", "Alice", "Character")]
    rich_editor.set_completer(items=items)

    after_pos = rich_editor.textCursor().position()
    assert after_pos == pos_before, (
        f"Cursor jumped from {pos_before} to {after_pos} after set_completer()"
    )


def test_empty_block_preserved_via_update_suggestions(qtbot):
    """Empty block must survive update_suggestions() on EntityEditorWidget.

    update_suggestions() calls set_completer() AND has a redundant re-render block.
    Both paths must be inert to document structure.
    """
    from unittest.mock import MagicMock

    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QWidget

    from src.core.entities import Entity
    from src.gui.widgets.entity_editor import EntityEditorWidget

    mock_parent = QWidget()
    qtbot.addWidget(mock_parent)
    mock_parent.worker = MagicMock()
    editor = EntityEditorWidget(parent=mock_parent)
    qtbot.addWidget(editor)

    entity = Entity(id="e1", name="E", type="Character", description="Hello")
    editor.load_entity(entity)

    inner = editor.desc_edit.editor
    cursor = inner.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertBlock()
    cursor.insertBlock()
    cursor.insertText("World")
    inner.setTextCursor(cursor)

    block_count_before = inner.document().blockCount()
    assert block_count_before == 3

    items = [("id1", "Alice", "Character")]
    editor.update_suggestions(items=items)

    block_count_after = inner.document().blockCount()
    assert block_count_after == block_count_before, (
        f"update_suggestions() collapsed {block_count_before} blocks to "
        f"{block_count_after}"
    )
