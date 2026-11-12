"""GFM tables remain structured, editable and reversible in descriptions."""

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QTextCursor

from src.commands.entity_commands import UpdateEntityCommand
from src.core.entities import Entity
from src.core.markdown_content import RenderTarget, parse_content, render_content
from src.gui.widgets.wiki_tables import tables
from src.gui.widgets.wiki_text_edit import WikiTextEdit

pytestmark = pytest.mark.ci_fast

TABLE = (
    "| Character | Role | Location |\n"
    "| :--- | :--- | ---: |\n"
    "| [[id:aldric|Aldric]] | **King** | Northern Keep |\n"
    "| Mira | Scholar | Silver Library |\n"
    "| Thorne | ~~Captain~~ Exile | Unknown |"
)


@pytest.fixture
def writing(qtbot):
    widget = WikiTextEdit()
    qtbot.addWidget(widget)
    widget.set_adaptive_width(True)
    widget.resize(360, 600)
    widget.show()
    return widget


def at_cell(writing, row, column):
    table = tables(writing.editor)[0]
    writing.setTextCursor(table.cellAt(row, column).firstCursorPosition())
    return table


def test_paste_renders_real_cells_and_preserves_exact_source(writing):
    source = QMimeData()
    source.setText(TABLE)
    writing.editor.insertFromMimeData(source)
    assert writing.editor._view_mode == "rich"
    table = tables(writing.editor)[0]
    assert (table.rows(), table.columns()) == (4, 3)
    assert "Captain" in writing.toPlainText()
    assert "~~" not in writing.toPlainText()
    assert writing.get_wiki_text() == TABLE
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == TABLE
    writing.toggle_view_mode()
    assert writing.get_wiki_text() == TABLE
    writing.editor.undo()
    assert writing.get_wiki_text() == ""
    writing.editor.redo()
    assert writing.get_wiki_text() == TABLE


def test_cells_survive_edit_save_reopen_and_persistent_undo(writing, qtbot, db_service):
    source = "# Harbour\n\nBefore\n\n" + TABLE + "\n\nAfter"
    writing.set_wiki_text(source)
    at_cell(writing, 2, 1)
    cursor = writing.textCursor()
    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
    cursor.insertText("Lorekeeper")
    result = writing.get_wiki_text()
    assert "Before" in result and "After" in result
    assert "Lorekeeper" in result and "Scholar" not in result
    assert "[[id:aldric\\|Aldric]]" in result
    assert "**King**" in result and "~~Captain~~" in result
    assert "---:" in result
    entity = Entity(name="Harbour", type="Place", description=source)
    db_service.insert_entity(entity)
    command = UpdateEntityCommand(entity.id, {"description": result})
    assert command.execute(db_service).success
    reopened = WikiTextEdit()
    qtbot.addWidget(reopened)
    reopened.set_wiki_text(db_service.get_entity(entity.id).description)
    assert reopened.get_wiki_text() == result
    assert len(tables(reopened.editor)) == 1
    command.undo(db_service)
    assert db_service.get_entity(entity.id).description == source
    writing.editor.undo()
    assert writing.get_wiki_text() == source


@pytest.mark.parametrize(
    "operation,rows,columns",
    [
        ("Insert row above", 5, 3),
        ("Insert row below", 5, 3),
        ("Delete row", 3, 3),
        ("Insert column left", 4, 4),
        ("Insert column right", 4, 4),
        ("Delete column", 4, 2),
    ],
)
def test_structural_actions_are_one_undo_step(writing, operation, rows, columns):
    writing.set_wiki_text(TABLE)
    at_cell(writing, 2, 1)
    writing.editor._tables.actions[operation].trigger()
    table = tables(writing.editor)[0]
    assert (table.rows(), table.columns()) == (rows, columns)
    writing.editor.undo()
    assert writing.get_wiki_text() == TABLE
    writing.editor.redo()
    table = tables(writing.editor)[0]
    assert (table.rows(), table.columns()) == (rows, columns)


def test_insert_delete_table_preserves_prose_and_undo(writing):
    writing.set_wiki_text("Before\n\nAfter")
    writing.setTextCursor(writing.document().find("After"))
    cursor = writing.textCursor()
    cursor.clearSelection()
    writing.setTextCursor(cursor)
    writing.editor._tables.insert()
    assert len(tables(writing.editor)) == 1
    assert "Before" in writing.get_wiki_text() and "After" in writing.get_wiki_text()
    writing.editor._tables.delete()
    assert not tables(writing.editor)
    writing.editor.undo()
    assert len(tables(writing.editor)) == 1
    writing.editor.undo()
    assert writing.get_wiki_text() == "Before\n\nAfter"


def test_tab_backtab_enter_and_exit_do_not_mutate_table(writing, qtbot):
    writing.set_wiki_text(TABLE)
    table = at_cell(writing, 1, 0)
    writing.editor.setFocus()
    qtbot.keyClick(writing.editor, Qt.Key.Key_Tab)
    cell = table.cellAt(writing.textCursor())
    assert (cell.row(), cell.column()) == (1, 1)
    qtbot.keyClick(writing.editor, Qt.Key.Key_Backtab)
    assert table.cellAt(writing.textCursor()).column() == 0
    qtbot.keyClick(writing.editor, Qt.Key.Key_Return)
    assert table.cellAt(writing.textCursor()).row() == 2
    at_cell(writing, 3, 2)
    qtbot.keyClick(writing.editor, Qt.Key.Key_Tab)
    assert writing.textCursor().currentTable() is None
    assert writing.get_wiki_text() == TABLE


def test_alignment_and_inline_link_formatting_roundtrip(writing):
    writing.set_wiki_text(TABLE)
    at_cell(writing, 2, 1)
    writing.editor._tables.actions["Align column center"].trigger()
    table = tables(writing.editor)[0]
    assert (
        table.cellAt(0, 1).firstCursorPosition().blockFormat().alignment()
        & Qt.AlignmentFlag.AlignHCenter
    )
    cursor = writing.textCursor()
    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
    writing.setTextCursor(cursor)
    writing.editor._toggle_italic()
    result = writing.get_wiki_text()
    assert ":---:" in result and "*Scholar*" in result
    writing.editor.set_wiki_text(result, force=True)
    assert writing.get_wiki_text() == result
    assert tables(writing.editor)[0].columns() == 3


def test_typed_markdown_characters_remain_literal_cell_content(writing):
    writing.set_wiki_text("| A | B |\n| - | - |\n| one | two |")
    at_cell(writing, 1, 0)
    writing.editor.insertPlainText("| **literal** ")
    result = writing.get_wiki_text()
    rendered = render_content(parse_content(result), RenderTarget.EXPORT)
    assert rendered.count("<td") == 2
    assert "**literal**" in rendered and "<strong>literal" not in rendered


def test_unsupported_surrounding_content_keeps_source(writing):
    source = TABLE + "\n\n> Preserve this quotation"
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == source


def test_overfull_table_rows_preserve_unrepresented_cells_in_source(writing):
    source = "| A | B |\n| - | - |\n| one | two | Keep this too |"
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "source"
    assert writing.get_wiki_text() == source


def test_table_selection_survives_source_toggle_with_unicode(writing):
    source = TABLE.replace("Scholar", "þorn😀")
    writing.set_wiki_text(source)
    writing.setTextCursor(writing.document().find("þorn😀"))
    writing.toggle_view_mode()
    assert writing.textCursor().selectedText() == "þorn😀"
    writing.toggle_view_mode()
    assert writing.textCursor().selectedText() == "þorn😀"


@pytest.mark.parametrize("word", ["Aldric", "King", "Captain"])
def test_formatted_cell_selection_keeps_visible_text_across_views(writing, word):
    writing.set_wiki_text(TABLE)
    writing.setTextCursor(writing.document().find(word))
    writing.toggle_view_mode()
    assert writing.textCursor().selectedText() == word
    writing.toggle_view_mode()
    assert writing.textCursor().selectedText() == word


def test_readonly_table_commands_cannot_modify_content(writing):
    writing.set_wiki_text(TABLE)
    at_cell(writing, 1, 1)
    writing.editor.setReadOnly(True)
    writing.editor._tables.refresh()
    for action in writing.editor._tables.actions.values():
        assert not action.isEnabled()
        action.trigger()
    assert writing.get_wiki_text() == TABLE


def test_cell_inline_vocabulary_and_multiple_tables_survive_edits(writing):
    source = (
        "| **Head** | Plain |\n| - | - |\n| `a\\|b` | [site](https://example.org) |"
    )
    source += "\n\nBetween\n\n" + TABLE
    writing.set_wiki_text(source)
    assert writing.editor._view_mode == "rich"
    at_cell(writing, 1, 1)
    writing.editor.insertPlainText("Visit ")
    result = writing.get_wiki_text()
    rendered = render_content(parse_content(result), RenderTarget.EXPORT)
    assert rendered.count("<table>") == 2
    assert "<strong>Head</strong>" in rendered
    assert "<code>a|b</code>" in rendered
    assert "https://example.org" in rendered
    assert "Between" in result


def test_table_menu_remains_available_after_events(writing, qtbot):
    writing.set_wiki_text(TABLE)
    at_cell(writing, 1, 1)
    qtbot.wait(10)
    menu = writing.editor._tables.menu
    assert menu in [
        action.menu()
        for action in writing.toolbar_presentation._menus["Insert"].actions()
    ]
    menu.popup(writing.mapToGlobal(writing.rect().topLeft()))
    qtbot.wait(10)
    assert menu.isVisible()
    assert writing.editor._tables.actions["Insert row below"].isEnabled()
    assert not writing.editor.action_h1.isEnabled()
    menu.hide()


def test_strike_with_trailing_space_and_inserted_row_alignment(writing):
    writing.set_wiki_text(TABLE)
    table = at_cell(writing, 2, 1)
    cursor = writing.textCursor()
    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
    writing.setTextCursor(cursor)
    writing.editor._tables.strike.trigger()
    assert "~~Scholar~~" in writing.get_wiki_text()
    at_cell(writing, 1, 2)
    writing.editor._tables.row(True)
    assert (
        table.cellAt(2, 2).firstCursorPosition().blockFormat().alignment()
        & Qt.AlignmentFlag.AlignRight
    )


def test_theme_switch_retains_draft_selection_and_history(writing):
    from src.core.theme_manager import ThemeManager

    writing.set_wiki_text(TABLE)
    at_cell(writing, 2, 1)
    writing.editor.insertPlainText("New ")
    writing.setTextCursor(writing.document().find("Scholar"))
    before = writing.get_wiki_text()
    anchor, position = writing.textCursor().anchor(), writing.textCursor().position()
    manager = ThemeManager()
    previous = manager.current_theme_name
    try:
        manager.set_theme("light_mode", persist=False)
        assert writing.get_wiki_text() == before
        assert (writing.textCursor().anchor(), writing.textCursor().position()) == (
            anchor,
            position,
        )
        writing.editor.undo()
        assert writing.get_wiki_text() == TABLE
    finally:
        manager.set_theme(previous, persist=False)


def test_repeated_cell_labels_keep_the_selected_cell_identity(writing):
    source = "| Same | Same |\n| - | - |\n"
    source += "\n".join("| [[id:x|Same]] | **Same** |" for _ in range(40))
    writing.set_wiki_text(source)
    table = at_cell(writing, 35, 1)
    cursor = table.cellAt(35, 1).firstCursorPosition()
    cursor.movePosition(
        QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4
    )
    writing.setTextCursor(cursor)
    writing.toggle_view_mode()
    expected = source.splitlines(keepends=True)
    offset = len("".join(expected[:36])) + expected[36].rfind("Same")
    assert writing.textCursor().selectionStart() == offset
    assert writing.textCursor().selectedText() == "Same"
    writing.toggle_view_mode()
    table = tables(writing.editor)[0]
    assert table.cellAt(writing.textCursor()).row() == 35
    assert table.cellAt(writing.textCursor()).column() == 1
