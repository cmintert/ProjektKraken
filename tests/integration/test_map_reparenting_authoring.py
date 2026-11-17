"""A2 parent-picker intent and context preservation through real map widgets."""

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from src.commands.map_reparent_commands import PreserveMapPlacementCommand
from src.gui.dialogs.register_detail_map_dialog import RegisterDetailMapDialog
from src.services.map_reparenting import preservation_options
from tests.integration.test_map_hierarchy_authoring import authoring as _authoring
from tests.integration.test_map_hierarchy_authoring import registration

pytestmark = pytest.mark.ci_fast
authoring = _authoring


def connect_maps(handler, db):
    target = db.get_map("parent")
    db.insert_map(
        replace(
            target,
            attributes={
                **target.attributes,
                "parent_map_id": "source",
                "registration": registration(),
            },
        )
    )
    handler.on_maps_ready(db.get_all_maps())


def parent_dialog(widget, map_id, qtbot):
    maps = widget.maps_data
    record = next(m for m in maps if m.id == map_id)
    candidates = RegisterDetailMapDialog.filter_candidate_parents(maps, map_id)
    dialog = RegisterDetailMapDialog(
        record,
        candidates,
        parent=widget,
        preservation_options=preservation_options(maps, map_id, candidates),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_parent_picker_availability_and_explicit_manual_choice(authoring, qtbot):
    widget, handler, commands, db, _ = authoring
    # Initially parent is an unrelated root, so the option explains manual alignment.
    dialog = parent_dialog(widget, "child", qtbot)
    dialog._parent_combo.setCurrentIndex(dialog._parent_combo.findData("parent"))
    assert not dialog._keep_position.isEnabled()
    assert not dialog.preserves_position()
    assert "no shared registered ancestor" in dialog._placement_explanation.text()
    dialog.reject()
    assert not commands
    connect_maps(handler, db)
    dialog = parent_dialog(widget, "child", qtbot)
    dialog._parent_combo.setCurrentIndex(dialog._parent_combo.findData("parent"))
    assert dialog.preserves_position()
    assert dialog._apply_button.text() == "Change parent"
    dialog._keep_position.setFocus()
    QTest.keyClick(dialog._keep_position, Qt.Key.Key_Space)
    assert not dialog.preserves_position()
    assert dialog._apply_button.text() == "Place on parent map"
    dialog._apply_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.registration()["confidence"] == "suggested"
    assert not commands


def test_same_parent_requires_manual_edit_and_escape_saves_nothing(authoring, qtbot):
    widget, _, commands, db, _ = authoring
    before = db.get_map("child").to_dict()
    dialog = parent_dialog(widget, "child", qtbot)
    dialog._parent_combo.setCurrentIndex(dialog._parent_combo.findData("source"))
    assert dialog.preserves_position()
    assert not dialog._apply_button.isEnabled()
    dialog._keep_position.setChecked(False)
    assert dialog._apply_button.isEnabled()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert not commands
    assert db.get_map("child").to_dict() == before


def test_picker_emits_one_worker_command_without_changing_canvas(
    authoring, qtbot, monkeypatch
):
    widget, handler, commands, db, _ = authoring
    connect_maps(handler, db)
    widget.view.scale(1.4, 1.4)
    selected = widget.get_selected_map_id()
    transform = widget.view.transform()
    center = widget.view.mapToScene(widget.view.viewport().rect().center())
    before = db.get_map("child").to_dict()

    def accept_parent(dialog):
        dialog._parent_combo.setCurrentIndex(dialog._parent_combo.findData("parent"))
        assert dialog.preserves_position()
        dialog._apply_button.click()
        return dialog.result()

    monkeypatch.setattr(RegisterDetailMapDialog, "exec", accept_parent)
    widget._choose_parent_for("child")
    assert len(commands) == 1
    assert isinstance(commands[0], PreserveMapPlacementCommand)
    assert db.get_map("child").to_dict() == before  # UI never writes the database.
    assert commands[0].execute(db).success
    handler.on_maps_ready(db.get_all_maps())
    assert widget.get_selected_map_id() == selected
    assert widget.view.transform() == transform
    assert widget.view.mapToScene(widget.view.viewport().rect().center()) == center
    assert not widget.view.is_editing_footprint
    assert db.get_map("child").attributes["parent_map_id"] == "parent"


def test_unavailable_preservation_never_silently_starts_manual_preview(authoring):
    widget, handler, commands, _, _ = authoring
    feedback = []
    owner = handler.hierarchy_coordinator
    owner.ports = replace(
        owner.ports, feedback=lambda title, message: feedback.append((title, message))
    )
    owner.preserve_position("child", "parent")
    assert "no shared registered ancestor" in feedback[0][1]
    assert not commands
    assert not widget.view.is_editing_footprint


def test_preservation_waits_for_edit_transition_before_calculating(authoring):
    _, handler, commands, db, _ = authoring
    connect_maps(handler, db)
    owner = handler.hierarchy_coordinator
    continuations = []
    owner.ports = replace(
        owner.ports,
        request_transition=lambda reason, continuation: continuations.append(
            continuation
        ),
    )
    owner.preserve_position("child", "parent")
    assert not commands
    assert len(continuations) == 1
    continuations[0]()
    assert len(commands) == 1
