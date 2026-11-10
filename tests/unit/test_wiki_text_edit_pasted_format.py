"""Pasted presentation cleanup preserves authored text, links and undo history."""

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QTextCursor, QTextFormat

from src.commands.entity_commands import UpdateEntityCommand
from src.core.entities import Entity
from src.core.theme_manager import ThemeManager
from src.gui.widgets.wiki_text_edit import WikiTextEdit

pytestmark = pytest.mark.ci_fast

HTML = (
    '<h2 style="background-color:#ffffaa;color:#eeeeee">'
    '<b>Pasted</b> <a href="id:entity-1">Alpha</a> '
    '<a href="https://example.com">Web</a></h2>'
    '<p style="background-color:#ffffaa;color:#eeeeee"><i>Second paragraph</i></p>'
)


@pytest.fixture
def editor(qtbot):
    wrapper = WikiTextEdit()
    qtbot.addWidget(wrapper)
    return wrapper.editor


def paste(view, html=HTML):
    mime = QMimeData()
    mime.setHtml(html)
    view.insertFromMimeData(mime)


def fragments(view):
    block = view.document().begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                yield fragment
            iterator += 1
        block = block.next()


def assert_clean(view):
    for fragment in fragments(view):
        fmt = fragment.charFormat()
        assert not fmt.hasProperty(QTextFormat.Property.ForegroundBrush)
        assert not fmt.hasProperty(QTextFormat.Property.BackgroundBrush)
    block = view.document().begin()
    while block.isValid():
        assert block.blockFormat().background().style() == Qt.BrushStyle.NoBrush
        assert block.blockFormat().headingLevel() == 0
        block = block.next()


@pytest.mark.parametrize("theme", ["dark_mode", "light_mode"])
def test_pasted_colors_clear_with_atomic_undo_links_and_theme(
    editor, qtbot, qapp, theme
):
    manager = ThemeManager()
    manager.set_theme(theme, qapp, persist=False)
    editor.set_completer(items=[("entity-1", "Alpha", "entity")])
    paste(editor)
    qtbot.wait(10)
    before = editor.document().toHtml()
    text = editor.toPlainText()
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    bounds = (cursor.anchor(), cursor.position())
    document = editor.document()
    editor.action_body.trigger()

    assert_clean(editor)
    assert editor.document() is document
    assert editor.toPlainText() == text
    assert (editor.textCursor().anchor(), editor.textCursor().position()) == bounds
    assert editor.get_wiki_text() == (
        "Pasted [[id:entity-1|Alpha]] [[https://example.com|Web]]\n\nSecond paragraph"
    )
    cleaned = editor.document().toHtml()
    editor.undo()
    assert editor.document().toHtml() == before
    editor.redo()
    assert editor.document().toHtml() == cleaned

    steps = document.availableUndoSteps()
    manager.set_theme(
        "light_mode" if theme == "dark_mode" else "dark_mode", qapp, persist=False
    )
    assert_clean(editor)
    assert document.availableUndoSteps() == steps
    qtbot.wait(10)
    formats = document.begin().layout().formats()
    colors = {item.format.foreground().color().name() for item in formats}
    current = manager.get_theme()
    assert current["text_main"].lower() in colors
    assert current["link_entity"].lower() in colors
    assert current["link_neutral"].lower() in colors


def test_caret_cleans_current_paragraph_and_future_typing(editor):
    paste(editor, '<p style="color:#eeeeee;background-color:#ffffaa">Pasted</p>')
    cursor = editor.textCursor()
    cursor.setPosition(3)
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    assert_clean(editor)
    assert editor.textCursor().position() == 3
    editor.insertPlainText("new")
    assert editor.toPlainText() == "Pasnewted"
    assert_clean(editor)


@pytest.mark.parametrize("reverse", [False, True])
def test_partial_selection_leaves_surrounding_characters_untouched(editor, reverse):
    paste(
        editor,
        '<p><span style="color:#eeeeee;background:#ffffaa">Before Target After</span></p>',
    )
    cursor = editor.textCursor()
    left, right = (13, 7) if reverse else (7, 13)
    cursor.setPosition(left)
    cursor.setPosition(right, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    assert (editor.textCursor().anchor(), editor.textCursor().position()) == (
        left,
        right,
    )
    for fragment in fragments(editor):
        fmt = fragment.charFormat()
        if fragment.text() == "Target":
            assert not fmt.hasProperty(QTextFormat.Property.BackgroundBrush)
            assert not fmt.hasProperty(QTextFormat.Property.ForegroundBrush)
        else:
            assert fmt.background().color().name() == "#ffffaa"
            assert fmt.foreground().color().name() == "#eeeeee"


def test_selection_ending_at_next_paragraph_does_not_clear_it(editor):
    paste(
        editor,
        '<p style="background:#ffffaa">First</p><p style="background:#ffffaa">Second</p>',
    )
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    first = editor.document().begin()
    assert first.blockFormat().background().style() == Qt.BrushStyle.NoBrush
    assert first.next().blockFormat().background().color().name() == "#ffffaa"


def test_empty_paragraph_insertion_format_is_clean(editor):
    paste(editor, '<p style="color:#eeeeee;background:#ffffaa">Text</p>')
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertBlock()
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    editor.insertPlainText("New paragraph")
    fmt = editor.textCursor().charFormat()
    assert not fmt.hasProperty(QTextFormat.Property.BackgroundBrush)
    assert not fmt.hasProperty(QTextFormat.Property.ForegroundBrush)


def test_partial_heading_becomes_body_without_retaining_heading_size(editor):
    paste(editor, '<h2 style="background:#ffffaa">Before Target After</h2>')
    cursor = editor.textCursor()
    cursor.setPosition(7)
    cursor.setPosition(13, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    assert editor.get_wiki_text() == "Before Target After"
    assert all(
        f.charFormat().fontPointSize() == editor._typography.body_size
        for f in fragments(editor)
    )


def test_read_only_clear_does_not_change_document(editor):
    paste(editor)
    before = editor.document().toHtml()
    steps = editor.document().availableUndoSteps()
    editor.setReadOnly(True)
    editor.action_body.trigger()
    assert editor.document().toHtml() == before
    assert editor.document().availableUndoSteps() == steps


def test_caret_cleanup_preserves_other_paragraphs_and_scroll(editor, qtbot):
    editor.window().resize(320, 240)
    editor.window().show()
    editor.window().activateWindow()
    paste(editor, '<p style="background:#ffffaa">Paragraph</p>' * 30)
    cursor = editor.textCursor()
    cursor.setPosition(editor.document().findBlockByNumber(15).position() + 3)
    editor.setTextCursor(cursor)
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)
    scroll = editor.verticalScrollBar().value()
    position = cursor.position()
    editor.action_body.trigger()
    assert editor.hasFocus()
    assert editor.textCursor().position() == position
    assert editor.verticalScrollBar().value() == scroll
    block = editor.document().begin()
    assert block.blockFormat().background().color().name() == "#ffffaa"
    assert (
        editor.textCursor().blockFormat().background().style() == Qt.BrushStyle.NoBrush
    )


def test_cleaned_text_saves_reloads_and_command_undo_preserves_links(
    editor, db_service
):
    entity = Entity(name="Draft", type="Concept", description="Original")
    db_service.insert_entity(entity)
    paste(editor)
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    editor.action_body.trigger()
    cleaned = editor.get_wiki_text()
    command = UpdateEntityCommand(entity.id, {"description": cleaned})
    assert command.execute(db_service).success
    saved = db_service.get_entity(entity.id)
    assert saved.description == cleaned
    editor.set_wiki_text(saved.description, force=True)
    assert editor.get_wiki_text() == cleaned
    assert all(
        fragment.charFormat().background().style() == Qt.BrushStyle.NoBrush
        for fragment in fragments(editor)
    )
    command.undo(db_service)
    assert db_service.get_entity(entity.id).description == "Original"
    assert command.execute(db_service).success
    assert db_service.get_entity(entity.id).description == cleaned
