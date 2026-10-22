"""KRT-93 semantic, pointer, draft and refresh regressions."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QWheelEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from src.core.entities import Entity
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.gui.widgets.connection_presentation import project_connections
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget

pytestmark = [
    pytest.mark.ci_fast,
    pytest.mark.usefixtures("isolated_theme_manager"),
]


def saved(index, predicate="related", **extra):
    return {
        "id": f"relation-{index}",
        "source_id": "source",
        "target_id": f"target-{index}",
        "source_name": "Tasgillia",
        "target_name": f"House {index}",
        "rel_type": predicate,
        "attributes": {},
        **extra,
    }


@pytest.fixture(params=["entity", "event"])
def inspector(request, qtbot):
    kind = request.param
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = (
        EntityEditorWidget(parent) if kind == "entity" else EventEditorWidget(parent)
    )
    qtbot.addWidget(editor)
    owner = (
        Entity(id="source", name="Tasgillia", type="Character")
        if kind == "entity"
        else Event(id="source", name="Tasgillia", lore_date=10.0)
    )
    getattr(editor, f"load_{kind}")(owner)
    editor.resize(650, 900)
    parent.resize(650, 900)
    parent.show()
    editor.show()
    editor.inspector.activate_section_id("connections")
    editor._suggestion_items = [("target-0", "House 0", "entity")]
    return editor


def refresh(editor, outgoing, incoming=None):
    kind = "event" if isinstance(editor, EventEditorWidget) else "entity"
    getattr(editor, f"_load_{kind}_relations")(outgoing, incoming or [])


@pytest.mark.parametrize("predicate", ["member_of", "guards Ælf's gate"])
def test_both_overview_perspectives_preserve_canonical_assertion(predicate):
    snapshot = saved(0, predicate, attributes={"notes": "Keep", "confidence": 0.75})
    before = deepcopy(snapshot)
    outgoing = project_connections([snapshot], [], "entity", "source", "Tasgillia")[0]
    incoming = project_connections([], [snapshot], "entity", "target-0", "House 0")[0]
    caption = "Member of" if predicate == "member_of" else predicate
    assert outgoing.meaning == incoming.meaning == caption
    assert (
        outgoing.assertion == incoming.assertion == f"Tasgillia → {caption} → House 0"
    )
    expected = f"Tasgillia → {caption} → House 0 · Timing: not specified"
    assert outgoing.text == incoming.text == expected
    assert outgoing.snapshot["id"] == incoming.snapshot["id"] == "relation-0"
    assert snapshot == before


def test_semantic_projection_does_not_guess_or_duplicate():
    rows = [
        saved(0, "member_of"),
        saved(1, "located_at"),
        saved(2, "involved"),
        saved(3, "caused"),
        saved(4, "unknown", target_kind="location"),
        saved(5, "mentions"),
    ]
    before = deepcopy(rows)
    result = project_connections(rows, rows, "event", "source", "Tasgillia")
    assert len(result) == 6
    assert [r.group for r in result] == [
        "Other connections",
        "Locations",
        "Participants",
        "Causes & consequences",
        "Other connections",
        "References",
    ]
    assert rows == before
    incoming = project_connections([], rows, "event", "target", "House")
    assert [r.group for r in incoming] == [r.group for r in result]
    assert all(r.direction == "incoming" and r.other_id == "source" for r in incoming)
    explicit = project_connections(
        rows, [], "entity", "source", "Tasgillia", categories={"member_of": "unknown"}
    )
    assert explicit[0].group == "Other connections"


def test_connections_stay_one_line_at_narrow_and_wide_widths(inspector, qapp):
    view = inspector.connections
    target = "Ashford Army with a deliberately long connection name " * 4
    refresh(inspector, [saved(0, "departs_from", target_name=target)])
    index = view._indices["relation-0"]
    assert "\n" not in index.data()
    assert "departs_from" in index.data()
    assert target in index.data(Qt.ItemDataRole.ToolTipRole)
    assert not view.tree.wordWrap()
    for width in (360, 1000):
        inspector.resize(width, 900)
        qapp.processEvents()
        assert view.tree.visualRect(index).height() == (
            QFontMetrics(view.tree.font()).height() + 16
        )


@pytest.mark.parametrize("count", [0, 5, 20, 100])
def test_counts_filters_and_uuid_refresh(inspector, count):
    view = inspector.connections
    rows = [saved(i, "member_of" if i % 2 else "caused") for i in range(count)]
    refresh(inspector, rows)
    assert len(view.rows) == count
    if not count:
        assert view.connect_button.isEnabled()
        return
    view.select_relation(rows[-1]["id"])
    view.search.setText("no match")
    assert view.selected_id == rows[-1]["id"]
    assert "hidden" in view.summary.text()
    assert not view.edit_button.isEnabled()
    refresh(inspector, list(reversed(rows)))
    assert view.selected_id == rows[-1]["id"]
    assert view.search.text() == "no match"
    view.search.clear()
    assert view.edit_button.isEnabled()
    index = view._indices[view.selected_id]
    group = index.parent()
    name = group.data(Qt.ItemDataRole.UserRole + 1)
    view.tree.collapse(group)
    refresh(inspector, rows)
    assert not view.tree.isExpanded(view._indices[view.selected_id].parent())
    assert view._expanded[name] is False


def test_ten_pointer_selections_never_open_or_mutate(inspector, qtbot):
    view = inspector.connections
    rows = [saved(i) for i in range(10)]
    refresh(inspector, rows)
    requests = []
    inspector.relation_authoring_requested.connect(requests.append)
    for row in rows:
        index = view._indices[row["id"]]
        view.tree.scrollTo(index)
        qtbot.wait(5)
        qtbot.mouseClick(
            view.tree.viewport(),
            Qt.MouseButton.LeftButton,
            pos=view.tree.visualRect(index).center(),
        )
        assert view.selected_id == row["id"]
        assert inspector.relation_authoring.form is None
    assert requests == []
    qtbot.keyClick(view.tree, Qt.Key.Key_Return)
    assert inspector.relation_authoring.relation["id"] == rows[-1]["id"]


@pytest.mark.parametrize("decision", ["Keep editing", "Discard", "Apply"])
def test_dirty_selection_guard_and_draft_refresh(inspector, monkeypatch, decision):
    rows = [saved(0), saved(1)]
    refresh(inspector, rows)
    view = inspector.connections
    view.select_relation(rows[0]["id"])
    view.edit_selected()
    panel = inspector.relation_authoring
    panel.form.notes_edit.setPlainText("Unfinished lore")
    draft = panel.form
    assert "Unsaved" in panel.heading.text()
    assert panel.form is draft
    refresh(inspector, list(reversed(rows)))
    assert panel.form is draft
    assert panel.heading.isVisible()
    monkeypatch.setattr(QMessageBox, "exec", lambda box: None)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda box: next(b for b in box.buttons() if b.text() == decision),
    )
    accepted = view.select_relation(rows[1]["id"])
    assert accepted is (decision == "Discard")
    assert view.selected_id == rows[1 if accepted else 0]["id"]
    if decision == "Keep editing":
        assert panel.form is draft
        assert panel.form.notes_edit.toPlainText() == "Unfinished lore"
    if decision == "Apply":
        assert panel.pending_id
        assert not view.select_relation(rows[1]["id"])


def test_references_navigation_and_readonly_survive_refresh(inspector):
    view = inspector.connections
    refresh(inspector, [saved(0, "mentions"), saved(1)])
    view.select_relation("relation-0")
    assert not view.edit_button.isEnabled()
    assert not view.remove_button.isEnabled()
    assert not view.tree.isExpanded(view._indices["relation-0"].parent())
    view.tree.expand(view._indices["relation-0"].parent())
    assert view.go_button.isEnabled()
    view.set_editable(False)
    refresh(inspector, [saved(1)])
    view.select_relation("relation-1")
    assert not view.edit_button.isEnabled()
    assert not view.remove_button.isEnabled()
    assert not view.connect_button.isEnabled()
    assert view.go_button.isEnabled()


def test_double_click_and_notes_refresh_preserve_caret(inspector, qtbot):
    refresh(inspector, [saved(0)])
    view = inspector.connections
    index = view._indices["relation-0"]
    view.tree.scrollTo(index)
    qtbot.wait(10)
    qtbot.mouseClick(
        view.tree.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.tree.visualRect(index).center(),
    )
    qtbot.mouseDClick(
        view.tree.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.tree.visualRect(index).center(),
    )
    panel = inspector.relation_authoring
    assert panel.relation["id"] == "relation-0"
    notes = panel.form.notes_edit
    notes.setPlainText("Lore remains at the caret")
    notes.setFocus()
    cursor = notes.textCursor()
    cursor.setPosition(7)
    notes.setTextCursor(cursor)
    refresh(inspector, [saved(0, "parent_of")])
    assert panel.form.notes_edit is notes
    assert notes.hasFocus()
    assert notes.textCursor().position() == 7
    refresh(inspector, [])
    assert not panel.apply_button.isEnabled()
    assert notes.toPlainText() == "Lore remains at the caret"


def test_group_keyboard_never_removes_a_previously_selected_relation(inspector, qtbot):
    refresh(inspector, [saved(0)])
    view = inspector.connections
    view.select_relation("relation-0")
    removals = []
    view.remove_requested.connect(removals.append)
    group = view._indices["relation-0"].parent()
    view.tree.setCurrentIndex(group)
    qtbot.keyClick(view.tree, Qt.Key.Key_Delete)
    assert removals == []
    assert view.selected_id == "relation-0"
    before = view.tree.isExpanded(group)
    qtbot.keyClick(view.tree, Qt.Key.Key_Return)
    assert view.tree.isExpanded(group) is not before
    assert inspector.relation_authoring.form is None


def test_minimum_height_uses_wrapped_content_without_overlap(
    inspector, qtbot, qapp, monkeypatch
):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    inspector.setFont(QFont("Segoe UI", 10))
    inspector.resize(360, 720)
    long_row = saved(
        0, target_name="House Bjornaer of the Northern Forest and Forgotten Marshes"
    )
    refresh(inspector, [long_row])
    view = inspector.connections
    view.select_relation("relation-0")
    view.edit_selected()
    panel = inspector.relation_authoring
    panel.timing_disclosure.setChecked(True)
    manager = ThemeManager()
    previous_style = qapp.styleSheet()
    monkeypatch.setattr(qapp, "setStyleSheet", inspector.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", inspector.setPalette)
    template = Path("src/resources/main.qss").read_text(encoding="utf-8")
    monkeypatch.setattr(manager, "_qss_template", template)
    try:
        for theme in manager.themes:
            manager.set_theme(theme)
            qtbot.wait(5)
            palette = manager.get_theme()
            assert palette["scrollbar_handle"] in panel.body_scroll.styleSheet(), theme
            assert palette["scrollbar_bg"] in panel.body_scroll.styleSheet(), theme
            assert palette["border"] in panel.styleSheet(), theme
            assert inspector.height() == 720, theme
            assert view.tree.geometry().bottom() < view.summary.geometry().top(), theme
            assert view.geometry().bottom() < panel.geometry().top(), theme
            assert panel.body_scroll.viewport().height() >= 32, theme
            assert (
                panel.body_scroll.geometry().bottom() < panel.footer.geometry().top()
            ), theme
    finally:
        qapp.setStyleSheet(previous_style)


def test_wheel_scrolls_overview_without_changing_meaning(inspector, qtbot):
    refresh(inspector, [saved(i) for i in range(100)])
    view = inspector.connections
    qtbot.wait(10)
    viewport = view.tree.viewport()
    before = view.tree.verticalScrollBar().value()
    event = QWheelEvent(
        QPointF(30, 30),
        QPointF(viewport.mapToGlobal(QPoint(30, 30))),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(viewport, event)
    assert view.tree.verticalScrollBar().value() > before
    assert not inspector.relation_authoring.is_dirty()
    assert inspector.relation_authoring.form is None


def test_meaning_is_editable_and_reuses_known_keys_without_custom_mode(inspector):
    inspector._suggestion_types = ["swore an ancient oath", "Member of"]
    row = saved(
        0, "member_of", attributes={"payload": {"attributes": {"rank": "Lord"}}}
    )
    refresh(inspector, [row])
    inspector.connections.select_relation("relation-0")
    inspector.connections.edit_selected()
    panel = inspector.relation_authoring
    assert panel.meaning.isEditable()
    assert panel.meaning.currentText() == "Member of"
    assert panel.form.type_edit.currentText() == "member_of"
    assert panel.form.type_edit.isHidden()
    assert panel.meaning.findText("Custom type…") == -1
    assert not panel.is_dirty()
    panel.meaning.setCurrentIndex(panel.meaning.findData("Member of"))
    assert panel.form.type_edit.currentText() == "Member of"
    panel.meaning.setCurrentIndex(panel.meaning.findData("swore an ancient oath"))
    assert panel.form.type_edit.currentText() == "swore an ancient oath"
    panel.meaning.setEditText("guards the forgotten gate beyond the winter sea")
    requests = []
    inspector.relation_authoring_requested.connect(requests.append)
    panel.apply()
    assert requests[0]["rel_type"] == "guards the forgotten gate beyond the winter sea"
    assert requests[0]["id"] == row["id"]
    assert requests[0]["attributes"] == row["attributes"]


def test_editable_display_caption_does_not_rewrite_stable_type_on_notes_edit(inspector):
    refresh(inspector, [saved(0, "member_of")])
    inspector.connections.select_relation("relation-0")
    inspector.connections.edit_selected()
    panel = inspector.relation_authoring
    panel.form.notes_edit.setPlainText("Only the notes change")
    requests = []
    inspector.relation_authoring_requested.connect(requests.append)
    panel.apply()
    assert requests[0]["rel_type"] == "member_of"


def test_editor_heading_is_plain_and_empty_meaning_stays_local(inspector):
    refresh(inspector, [saved(0)])
    inspector.connections.select_relation("relation-0")
    inspector.connections.edit_selected()
    panel = inspector.relation_authoring
    assert not hasattr(panel.heading, "setChecked")
    assert "Edit relationship" in panel.heading.text()
    panel.meaning.setEditText("  ")
    requests = []
    inspector.relation_authoring_requested.connect(requests.append)
    panel.apply()
    assert not requests
    assert panel.status.isVisible()
    assert "type a relationship phrase" in panel.status.text()
