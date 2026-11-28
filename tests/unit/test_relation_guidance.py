"""KRT-72 exact-key choice, nonblocking advice and perspective regressions."""

import json

import pytest
from PySide6.QtCore import Qt

from src.core.relation_guidance import relation_hint, type_suggestions
from src.core.relation_vocabulary import parse_vocabulary
from src.gui.dialogs.graph_connection_dialog import GraphConnectionDialog
from src.gui.widgets.relation_form import RelationForm
from src.gui.widgets.relation_guidance import RelationTypeField

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def vocabulary():
    return parse_vocabulary(
        json.dumps(
            {
                "version": 1,
                "definitions": [
                    {
                        "key": "member_of",
                        "forward_label": "Member of",
                        "reverse_label": "Members",
                        "description": "Membership",
                        "preferred_source_kind": "entity",
                        "preferred_target_kind": "entity",
                        "forward_template": "{source} is a member of {target}.",
                        "reverse_template": "{target} has {source} as a member.",
                    },
                    {
                        "key": "involved",
                        "forward_label": "Participation",
                        "reverse_label": "Participants",
                        "description": "Event participation",
                        "preferred_target_kind": "event",
                    },
                    {
                        "key": "participated_in",
                        "forward_label": "Participation",
                        "reverse_label": "Participants",
                        "description": "Event role",
                        "preferred_target_kind": "unknown",
                    },
                ],
            }
        )
    )


def test_preferences_rank_without_restricting_or_inventing_kinds(vocabulary):
    assert type_suggestions(["z", "mentions"], vocabulary, "entity", "entity") == [
        ("member_of", "Member of"),
        ("participated_in", "Participation (participated_in)"),
        ("z", "z"),
        ("involved", "Participation (involved)"),
    ]
    assert not relation_hint("involved", vocabulary, "entity", "")
    assert "points to an Event" in relation_hint(
        "involved", vocabulary, "entity", "entity"
    )
    assert "lifecycle" in relation_hint(" Death ", vocabulary, "entity", "event")
    assert not relation_hint("Born at", vocabulary, "entity", "event")


def test_caption_completion_saves_key_but_literal_text_survives_refresh(
    qtbot, vocabulary
):
    field = RelationTypeField()
    qtbot.addWidget(field)
    field.set_suggestions([], vocabulary)
    field.show()
    line = field.lineEdit()
    line.setFocus()
    qtbot.keyClicks(line, "Participation")
    assert field.currentText() == "Participation"

    completion = field.completer()
    popup = completion.popup()
    qtbot.waitUntil(popup.isVisible)
    qtbot.keyClick(line, Qt.Key.Key_Return)
    assert field.currentText() == "Participation"
    assert not popup.isVisible()

    completion.complete()
    qtbot.waitUntil(popup.isVisible)
    qtbot.keyClick(line, Qt.Key.Key_Escape)
    assert not popup.isVisible()
    assert field.currentText() == "Participation"

    completion.complete()
    qtbot.waitUntil(popup.isVisible)
    qtbot.keyClick(line, Qt.Key.Key_Down)
    qtbot.keyClick(line, Qt.Key.Key_Return)
    assert field.currentText() == "involved"

    field.setEditText("Participation")
    line.setSelection(2, 3)
    with qtbot.assertNotEmitted(field.currentTextChanged):
        field.set_suggestions([], vocabulary, "entity", "event")
    assert field.currentText() == "Participation"
    assert line.selectedText() == "rti"

    completion.setCompletionPrefix("Participation")
    completion.complete()
    qtbot.waitUntil(popup.isVisible)
    row = popup.model().index(1, 0)
    qtbot.mouseClick(
        popup.viewport(), Qt.MouseButton.LeftButton, pos=popup.visualRect(row).center()
    )
    assert field.currentText() == "participated_in"


def test_form_perspectives_keep_the_draft_and_warn_without_blocking(qtbot, vocabulary):
    form = RelationForm(
        target_id="guild",
        rel_type="member_of",
        suggestion_items=[("guild", "Harbor Guild", "entity")],
        source_name="Alrik",
        source_kind="event",
        relation_vocabulary=vocabulary,
    )
    qtbot.addWidget(form)
    form.show()
    original = form.get_data()
    assert form.preview_label.text() == "Alrik is a member of Harbor Guild."
    assert form.relation_guide.hint.isVisible()
    assert form.validate()
    button = form.relation_guide.other
    button.setFocus()
    qtbot.keyClick(button, Qt.Key.Key_Space)
    assert form.preview_label.text() == "Harbor Guild has Alrik as a member."
    assert form.get_data() == original


def test_graph_reversal_updates_advice_but_preview_switch_does_not(
    qtbot, vocabulary, qapp
):
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = GraphConnectionDialog("Ada", [], parent, source_kind="entity")
    qtbot.addWidget(dialog)
    dialog.set_target("Parade", kind="event", identity="parade")
    dialog.set_relation_vocabulary(vocabulary)
    dialog.type_field.setEditText("involved")
    assert not dialog.relation_guide.hint.text()
    assert dialog.relation_guide.preview.text() == "Ada → Participation → Parade"
    dialog.relation_guide.other.click()
    assert dialog.direction.currentData() == "forward"
    dialog.direction.setCurrentIndex(1)
    assert "points to an Event" in dialog.relation_guide.hint.text()
    assert dialog.save.isEnabled()
    with qtbot.waitSignal(dialog.save_requested) as submitted:
        dialog.save.click()
    assert submitted.args == ["involved", "reverse", False]
