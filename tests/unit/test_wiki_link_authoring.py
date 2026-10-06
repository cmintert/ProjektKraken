"""User-visible link operations preserve identity, text and local undo."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QTextCursor

from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.text_parser import WikiLinkParser

pytestmark = pytest.mark.ci_fast
TARGET = "550e8400-e29b-41d4-a716-446655440000"
OTHER = "550e8400-e29b-41d4-a716-446655440001"


@pytest.fixture
def writing(qtbot):
    widget = WikiTextEdit()
    widget.set_adaptive_width(True)
    widget.set_completer(items=[(TARGET, "House Bjornaer", "entity")])
    widget.resize(360, 340)
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.link_authoring.cancel()


def select(widget, start, end):
    cursor = widget.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    widget.setTextCursor(cursor)


def accept(widget):
    widget.action_link_entry.trigger()
    picker = widget.link_authoring.picker
    assert picker is not None
    picker.results.setCurrentRow(0)
    picker.link_button.click()


@pytest.mark.parametrize("mode", ["rich", "source"])
def test_selected_prose_label_identity_undo_and_following_typing(writing, mode, qtbot):
    writing.set_wiki_text("See their house today.")
    if mode == "source":
        writing.toggle_view_mode()
    select(writing, 4, 15)
    writing.action_link_entry.trigger()
    picker = writing.link_authoring.picker
    picker.search.setText("House")
    picker.results.setCurrentRow(0)
    picker.link_button.click()
    linked = writing.get_wiki_text()
    assert linked == f"See [[id:{TARGET}|their house]] today."
    writing.editor.undo()
    assert writing.get_wiki_text() == "See their house today."
    writing.editor.redo()
    assert writing.get_wiki_text() == linked
    qtbot.keyClicks(writing.editor, "!")
    assert writing.get_wiki_text() == f"See [[id:{TARGET}|their house]]! today."


@pytest.mark.parametrize("mode", ["rich", "source"])
def test_caret_insertion_and_source_completion(writing, mode):
    if mode == "source":
        writing.toggle_view_mode()
    writing.set_wiki_text("See ")
    select(writing, 4, 4)
    accept(writing)
    assert writing.get_wiki_text() == f"See [[id:{TARGET}|House Bjornaer]]"
    if mode == "source":
        writing.set_wiki_text("See [[Hou")
        select(writing, 9, 9)
        writing.editor._completer.setCompletionPrefix("Hou")
        writing.editor.insert_completion("House Bjornaer")
        assert writing.get_wiki_text() == f"See [[id:{TARGET}|House Bjornaer]]"
        writing.editor.undo()
        assert writing.get_wiki_text() == "See [[Hou"


@pytest.mark.parametrize("dismiss", ["escape", "hide", "cancel"])
def test_cancellation_preserves_reversed_selection_and_draft(writing, qtbot, dismiss):
    writing.set_wiki_text("See House Bjornaer today.")
    select(writing, 18, 4)
    before = writing.get_wiki_text()
    writing.action_link_entry.trigger()
    picker = writing.link_authoring.picker
    picker.search.setText("Other search")
    if dismiss == "escape":
        qtbot.keyClick(picker.search, Qt.Key.Key_Escape)
    elif dismiss == "hide":
        picker.hide()
    else:
        picker.close()
    assert writing.link_authoring.picker is None
    assert writing.get_wiki_text() == before
    assert writing.textCursor().anchor() == 18
    assert writing.textCursor().position() == 4


def test_duplicate_choices_keep_exact_id_and_renamed_label(writing):
    writing.set_completer(
        items=[(TARGET, "Alpha", "entity"), (OTHER, "Alpha", "event")]
    )
    writing.set_wiki_text("Alias")
    select(writing, 0, 5)
    writing.action_link_entry.trigger()
    picker = writing.link_authoring.picker
    picker.search.clear()
    assert picker.results.count() == 2
    assert "Event" in picker.results.item(1).text()
    picker.results.setCurrentRow(1)
    picker.link_button.click()
    assert writing.get_wiki_text() == f"[[id:{OTHER}|Alias]]"
    writing.set_completer(items=[(OTHER, "Renamed", "event")])
    assert writing.get_wiki_text() == f"[[id:{OTHER}|Alias]]"
    select(writing, 0, 5)
    assert writing.editor.link_target_at_cursor() == f"id:{OTHER}"


@pytest.mark.parametrize("change", ["text", "mode", "readonly", "deleted"])
def test_stale_picker_does_not_mutate_current_text(writing, change):
    writing.set_wiki_text("House Bjornaer")
    select(writing, 0, 14)
    writing.action_link_entry.trigger()
    picker = writing.link_authoring.picker
    if change == "text":
        writing.set_wiki_text("New document")
    elif change == "mode":
        writing.toggle_view_mode()
    elif change == "readonly":
        writing.setReadOnly(True)
    else:
        writing.set_completer(items=[])
    current = writing.get_wiki_text()
    if writing.link_authoring.picker is not None:
        picker.results.setCurrentRow(0)
        picker.link_button.click()
    assert writing.get_wiki_text() == current
    assert not WikiLinkParser.extract_links(current)


def test_mixed_formatting_whitespace_and_supported_roundtrip(writing):
    writing.set_wiki_text("See House **Bjornaer** and *friends*.")
    select(writing, 4, 18)
    accept(writing)
    linked = writing.get_wiki_text()
    assert f"[[id:{TARGET}|House ]]" in linked
    writing.toggle_view_mode()
    writing.toggle_view_mode()
    assert writing.toPlainText() == "See House Bjornaer and friends."
    assert writing.get_wiki_text() == linked
    links = WikiLinkParser.extract_links(linked)
    assert [link.modifier for link in links] == ["House ", "Bjornaer"]


@pytest.mark.parametrize("source", [False, True])
def test_visible_open_and_peek_resolve_same_id(writing, source, qtbot):
    writing.set_wiki_text(f"😀 See [[id:{TARGET}|Éowyn & friends]].")
    if source:
        writing.toggle_view_mode()
    select(writing, 9, 9)
    with qtbot.waitSignal(writing.link_clicked) as opened:
        writing.action_open_link.trigger()
    assert opened.args == [f"id:{TARGET}"]
    with qtbot.waitSignal(writing.peek_requested) as peeked:
        writing.action_peek_link.trigger()
    assert peeked.args == opened.args


def test_source_selection_preserves_unrelated_unsupported_markdown(writing):
    original = "- unsupported list\n\nSee House Bjornaer."
    writing.set_wiki_text(original)
    start = original.index("House")
    select(writing, start, start + 14)
    accept(writing)
    assert writing.get_wiki_text() == original.replace(
        "House Bjornaer", f"[[id:{TARGET}|House Bjornaer]]"
    )


@pytest.mark.parametrize("source", [False, True])
def test_completion_separates_adjacent_word_as_one_edit(writing, source):
    if source:
        writing.toggle_view_mode()
    writing.set_wiki_text("See [[Houfriend")
    select(writing, 9, 9)
    writing.editor._completer.setCompletionPrefix("Hou")
    writing.editor.insert_completion("House Bjornaer")
    assert writing.get_wiki_text() == f"See [[id:{TARGET}|House Bjornaer]] friend"
    writing.editor.undo()
    assert writing.get_wiki_text() == "See [[Houfriend"


@pytest.mark.parametrize(
    "modifier,signal",
    [
        (Qt.KeyboardModifier.ControlModifier, "link_clicked"),
        (Qt.KeyboardModifier.AltModifier, "peek_requested"),
    ],
)
def test_source_modifier_clicks_keep_navigation_accelerators(
    writing, qtbot, modifier, signal
):
    writing.set_wiki_text(f"See [[id:{TARGET}|House Bjornaer]]")
    writing.toggle_view_mode()
    select(writing, 10, 10)
    point = writing.editor.cursorRect().center()
    with qtbot.waitSignal(getattr(writing, signal)) as requested:
        qtbot.mouseClick(
            writing.editor.viewport(), Qt.MouseButton.LeftButton, modifier, point
        )
    assert requested.args[0].removeprefix("id:") == TARGET


@pytest.mark.parametrize(
    "text, mode, start, end",
    [
        ("One\n\nTwo", "rich", 0, 7),
        (f"[[id:{TARGET}|House]]", "rich", 0, 5),
        ("**House**", "source", 0, 9),
    ],
)
def test_invalid_selection_is_explained_without_mutation(
    writing, text, mode, start, end
):
    writing.set_wiki_text(text)
    if mode == "source":
        writing.toggle_view_mode()
    before = writing.get_wiki_text()
    select(writing, start, end)
    writing.action_link_entry.trigger()
    assert writing.link_authoring.picker is None
    assert not writing.link_notice.isHidden()
    assert writing.get_wiki_text() == before


@pytest.mark.parametrize("spell_hit", [False, True])
def test_both_context_menus_offer_link_creation(writing, monkeypatch, spell_hit):
    writing.set_wiki_text("House Bjornaer")
    select(writing, 0, 14)
    if spell_hit:
        writing.editor._lt_matches = [
            SimpleNamespace(offset=0, length=14, replacements=["House"], rule_id="TEST")
        ]
    menus = []
    monkeypatch.setattr(
        writing.editor, "_show_context_menu", lambda menu, _pos: menus.append(menu)
    )
    writing.editor.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
    )
    assert any(action.text() == "Link to entry…" for action in menus[0].actions())


def test_enter_in_results_accepts_selected_entry(writing, qtbot):
    writing.set_wiki_text("See ")
    select(writing, 4, 4)
    writing.action_link_entry.trigger()
    picker = writing.link_authoring.picker
    picker.results.setCurrentRow(0)
    picker.results.setFocus()
    assert writing.get_wiki_text() == "See "
    qtbot.keyClick(picker.results, Qt.Key.Key_Return)
    assert writing.get_wiki_text() == f"See [[id:{TARGET}|House Bjornaer]]"
