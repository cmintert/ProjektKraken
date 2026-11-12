"""Clipboard ingestion and view changes preserve description structure and edits."""

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QTextCursor

from src.commands.entity_commands import UpdateEntityCommand
from src.core.entities import Entity
from src.gui.widgets.wiki_text_edit import WikiTextEdit

pytestmark = pytest.mark.ci_fast

VOCABULARY = (
    "# Northern Tongue\n\n"
    "| Word | Meaning | Notes |\n"
    "| :--- | ---: | --- |\n"
    "| þorn | **thorn** | [[id:entity-1|Aldric]] |\n"
    "| ð | | *voiced* |\n\n"
    "> A quotation\n\n- first\n- second\n"
)


@pytest.fixture
def writing(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    return widget


def paste(writing, text=None, html=None):
    mime = QMimeData()
    if text is not None:
        mime.setText(text)
    if html is not None:
        mime.setHtml(html)
    writing.editor.insertFromMimeData(mime)


@pytest.mark.parametrize("source_mode", [False, True])
@pytest.mark.parametrize("with_html", [False, True])
def test_markdown_paste_preserves_source_and_persistent_undo(
    writing, qtbot, db_service, source_mode, with_html
):
    writing.set_wiki_text("Before")
    if source_mode:
        writing.toggle_view_mode()
    cursor = writing.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    writing.setTextCursor(cursor)
    paste(writing, VOCABULARY, "<p>flattened</p>" if with_html else None)
    assert writing.get_wiki_text() == VOCABULARY
    assert writing.editor._view_mode == "source"
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == VOCABULARY

    entity = Entity(name="Draft", type="Concept", description="Before")
    db_service.insert_entity(entity)
    command = UpdateEntityCommand(entity.id, {"description": writing.get_wiki_text()})
    assert command.execute(db_service).success
    reopened = WikiTextEdit()
    qtbot.addWidget(reopened)
    reopened.set_wiki_text(db_service.get_entity(entity.id).description)
    assert reopened.get_wiki_text() == VOCABULARY
    command.undo(db_service)
    assert db_service.get_entity(entity.id).description == "Before"
    assert command.execute(db_service).success

    writing.editor.undo()
    assert writing.get_wiki_text() == "Before"
    writing.editor.redo()
    assert writing.get_wiki_text() == VOCABULARY


@pytest.mark.parametrize("source_mode", [False, True])
@pytest.mark.parametrize(
    "html",
    [
        "<table><tr><th>A</th><th>B</th></tr><tr><td>þ</td><td></td></tr></table>",
        "<table><tr><td colspan='2'>Wide</td></tr>"
        "<tr><td><p>first</p><p>second</p></td><td>ð</td></tr></table>",
        "<ul><li>first</li><li>second</li></ul>",
        "<blockquote>quoted <strong>words</strong></blockquote>",
        "<p><s>old words</s></p>",
        '<p><span style="text-decoration:line-through">old words</span></p>',
        "<style>.old {text-decoration:line-through}</style>"
        '<p class="old">old words</p>',
        "<pre><code>[[literal]]\nsecond line</code></pre>",
        '<p><img src="assets/image.png" alt="Map"></p>',
    ],
)
def test_unsupported_html_preserves_markup_in_source(
    writing, qtbot, db_service, source_mode, html
):
    if source_mode:
        writing.toggle_view_mode()
    paste(writing, "flattened clipboard rendition", html)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == html
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == html
    writing.editor.undo()
    assert writing.get_wiki_text() == ""
    writing.editor.redo()
    assert writing.get_wiki_text() == html
    entity = Entity(name="Pasted HTML", type="Concept", description="Before")
    db_service.insert_entity(entity)
    command = UpdateEntityCommand(entity.id, {"description": writing.get_wiki_text()})
    assert command.execute(db_service).success
    reopened = WikiTextEdit()
    qtbot.addWidget(reopened)
    reopened.set_wiki_text(db_service.get_entity(entity.id).description)
    assert reopened.get_wiki_text() == html


def test_view_switches_preserve_edit_history_across_both_modes(writing, qtbot):
    writing.set_wiki_text("Initial")
    cursor = writing.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    writing.setTextCursor(cursor)
    writing.editor.insertPlainText(" rich")
    writing.toggle_view_mode()
    writing.editor.insertPlainText(" source")
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == "Initial rich source"
    qtbot.keyClick(writing.editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert writing.get_wiki_text() == "Initial rich"
    writing.editor.undo()
    assert writing.get_wiki_text() == "Initial"
    writing.editor.redo()
    assert writing.get_wiki_text() == "Initial rich"
    writing.editor.redo()
    assert writing.get_wiki_text() == "Initial rich source"


def test_source_mode_plain_text_paste_keeps_linebreaks(writing):
    writing.toggle_view_mode()
    paste(writing, "first\nsecond\n")
    assert writing.get_wiki_text() == "first\nsecond\n"


def test_multiline_plain_text_paste_keeps_soft_linebreaks(writing):
    paste(writing, "first\nsecond")
    assert writing.get_wiki_text() == "first\nsecond"
    writing.toggle_view_mode()
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == "first\nsecond"


def test_read_only_paste_and_history_leave_content_unchanged(writing):
    writing.set_wiki_text("Before")
    writing.editor.insertPlainText(" edit")
    before = writing.get_wiki_text()
    writing.setReadOnly(True)
    paste(writing, VOCABULARY)
    writing.editor.undo()
    assert writing.get_wiki_text() == before


def test_reference_definition_remains_available_when_adding_a_link(writing):
    source = "[label]: https://example.org"
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == source


def test_external_link_serializes_as_standard_markdown(writing):
    paste(writing, html='<p><a href="https://example.org">Website</a></p>')
    assert writing.get_wiki_text() == "[Website](https://example.org)"


def test_paste_replaces_selected_words_after_non_bmp_character(writing):
    writing.set_wiki_text("😀 Before **Target** After")
    writing.setTextCursor(writing.document().find("Target"))
    paste(writing, "`code`")
    assert writing.get_wiki_text() == "😀 Before **`code`** After"
    writing.editor.undo()
    assert writing.get_wiki_text() == "😀 Before **Target** After"


def test_edit_menu_history_and_redo_branch(writing):
    writing.set_wiki_text("Before")
    writing.editor.insertPlainText("first ")
    writing.toggle_view_mode()
    menu = writing.editor.createStandardContextMenu()
    menu.actions()[0].trigger()
    assert writing.get_wiki_text() == "Before"
    writing.toggle_view_mode()
    writing.editor.insertPlainText("replacement ")
    writing.editor.redo()
    assert writing.get_wiki_text() == "replacement Before"
    writing.editor.undo()
    assert writing.get_wiki_text() == "Before"


def test_new_record_load_discards_previous_record_history(writing):
    writing.set_wiki_text("Before")
    writing.editor.insertPlainText("first ")
    writing.toggle_view_mode()
    writing.set_wiki_text("Another entry")
    writing.editor.undo()
    assert writing.get_wiki_text() == "Another entry"


def test_explicit_markdown_clipboard_format(writing):
    mime = QMimeData()
    mime.setData("text/markdown", VOCABULARY.encode("utf-8"))
    assert writing.editor.canInsertFromMimeData(mime)
    writing.editor.insertFromMimeData(mime)
    assert writing.get_wiki_text() == VOCABULARY


def test_projection_lifetime_survives_deferred_cleanup(writing, qtbot):
    writing.set_wiki_text("Before")
    timer = writing.editor._section_manager._analyze_timer
    assert timer.parent() is writing.editor
    for _ in range(4):
        writing.toggle_view_mode()
        qtbot.wait(1)
    paste(writing, VOCABULARY)
    writing.editor.undo()
    writing.editor.redo()
    assert writing.get_wiki_text() == VOCABULARY + "Before"
    qtbot.wait(350)
    assert writing.editor._section_manager.document is writing.document()


@pytest.mark.parametrize("source_mode", [False, True])
def test_native_paste_accepts_html_only_clipboard(writing, qapp, qtbot, source_mode):
    if source_mode:
        writing.toggle_view_mode()
    html = "<table><tr><td>Cell</td></tr></table>"
    mime = QMimeData()
    mime.setHtml(html)
    qapp.clipboard().setMimeData(mime)
    try:
        qtbot.keyClick(
            writing.editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier
        )
        assert writing.get_wiki_text() == html
    finally:
        qapp.clipboard().clear()
