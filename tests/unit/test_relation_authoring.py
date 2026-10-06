"""Capture, refinement and replay acceptance for KRT-22."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.commands.relation_commands import AddRelationCommand, UpdateRelationCommand
from src.core.entities import Entity
from src.core.events import Event
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.relation_item_widget import RelationItemWidget

pytestmark = pytest.mark.ci_fast


@pytest.fixture(params=["entity", "event"])
def editor(request, qtbot, init_theme_manager):
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    widget = (
        EntityEditorWidget(parent)
        if request.param == "entity"
        else EventEditorWidget(parent)
    )
    qtbot.addWidget(widget)
    owner = (
        Entity(id="source", name="Tasgillia", type="Character")
        if request.param == "entity"
        else Event(id="source", name="Winter Council", lore_date=100.0)
    )
    getattr(widget, f"load_{request.param}")(owner)
    widget._suggestion_items = [("target", "House Bjornaer", "entity")]
    return widget


def relation(attributes=None):
    return {
        "id": "relation",
        "source_id": "source",
        "target_id": "target",
        "source_name": "Tasgillia",
        "target_name": "House Bjornaer",
        "target_kind": "entity",
        "rel_type": "related",
        "attributes": attributes or {},
    }


def test_capture_requires_only_existing_target_and_no_semantics(editor):
    assert not editor.btn_edit_rel.isEnabled()
    requests = []
    editor.relation_authoring_requested.connect(requests.append)
    editor._on_add_relation()
    panel = editor.relation_authoring
    assert panel.form is None
    panel.target.setText("not an existing object")
    panel.apply()
    assert not requests
    panel.target.setText("House Bjornaer")
    panel.apply()
    assert len(requests) == 1
    assert requests[0]["target_id"] == "target"
    assert requests[0]["rel_type"] == "related"
    assert requests[0]["attributes"] == {}
    assert panel.pending_id
    panel.on_finished({"request_id": "unrelated", "success": True})
    assert panel.pending_id
    panel.on_finished(
        {
            "request_id": panel.pending_id,
            "success": False,
            "message": "Database failure",
        }
    )
    assert panel.target.text() == "House Bjornaer"
    assert panel.body.isEnabled()
    assert panel.status.text() == "Database failure"


def test_refine_only_notes_and_meaning_preserves_advanced_snapshot(editor):
    attrs = {
        "confidence": 0.6000000000000001,
        "weight": 1.234567,
        "notes": "old",
        "custom": {"unknown": [1, 2]},
        "temporal": {
            "schema": 1,
            "behavior": "historical",
            "start": {"status": "unknown", "extra": "retained"},
            "end": {"status": "open"},
        },
    }
    original = deepcopy(attrs)
    panel = editor.relation_authoring
    panel.refine(relation(attrs))
    assert not panel.is_dirty()
    assert not panel.timing_disclosure.isChecked()
    assert not panel.advanced_disclosure.isChecked()
    panel.timing_disclosure.setChecked(True)
    panel.timing_disclosure.setChecked(False)
    panel.advanced_disclosure.setChecked(True)
    panel.advanced_disclosure.setChecked(False)
    assert not panel.is_dirty()
    requests = []
    editor.relation_authoring_requested.connect(requests.append)
    panel.meaning.setCurrentIndex(panel.meaning.findData("member_of"))
    panel.form.notes_edit.setPlainText("Learned from the charter")
    panel.apply()
    assert requests[0]["id"] == "relation"
    assert requests[0]["source_id"] == "source"
    assert requests[0]["rel_type"] == "member_of"
    expected = {**original, "notes": "Learned from the charter"}
    assert requests[0]["attributes"] == expected
    assert attrs == original


def test_refresh_preserves_relation_draft_and_disclosure_then_blocks_deleted_row(
    editor,
):
    panel = editor.relation_authoring
    row = relation()
    panel.refine(row)
    panel.form.notes_edit.setPlainText("unfinished")
    panel.timing_disclosure.setChecked(True)
    form = panel.form
    load = (
        getattr(editor, "_load_entity_relations", None) or editor._load_event_relations
    )
    load([row], [])
    assert panel.form is form
    assert form.notes_edit.toPlainText() == "unfinished"
    assert panel.timing_disclosure.isChecked()
    assert panel.apply_button.isEnabled()
    load([], [])
    assert not panel.apply_button.isEnabled()
    assert "no longer exists" in panel.status.text()


def test_notes_enter_and_escape_do_not_change_description(editor, qtbot):
    panel = editor.relation_authoring
    editor.desc_edit.set_wiki_text("Unfinished prose")
    panel.refine(relation())
    panel.form.notes_edit.setFocus()
    qtbot.keyClicks(panel.form.notes_edit, "First")
    qtbot.keyClick(panel.form.notes_edit, Qt.Key.Key_Return)
    qtbot.keyClicks(panel.form.notes_edit, "Second")
    assert panel.form.notes_edit.toPlainText() == "First\nSecond"
    assert not panel.pending_id
    qtbot.keyClick(panel.form.notes_edit, Qt.Key.Key_Escape)
    assert panel.form is None
    assert editor.desc_edit.get_wiki_text() == "Unfinished prose"


def test_inline_timing_keeps_fixed_start_and_dynamic_end(editor):
    from src.core.calendar import CalendarConfig, CalendarConverter

    converter = CalendarConverter(CalendarConfig.create_default())
    editor.set_relation_time_context(125.512345, converter)
    row = relation(
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {"status": "unknown"},
                "end": {"binding": "source_event"},
            }
        }
    )
    row["source_event_date"] = 100.0
    panel = editor.relation_authoring
    panel.refine(row)
    assert not panel.is_dirty()
    panel.form.starts_now_button.click()
    assert "Timing changed" in panel.timing_caption.text()
    attributes = panel.form.get_data()[3]
    assert attributes["temporal"]["start"] == {"exact": 125.512345}
    assert attributes["temporal"]["end"] == {"binding": "source_event"}
    panel.cancel()
    changed = relation(attributes)
    changed["source_event_date"] = 200.0
    panel.refine(changed)
    assert panel.form.get_data()[3] == attributes


def test_coordinator_capture_feedback_and_relation_refresh_preserve_prose(
    editor, db_service, qtbot
):
    from src.app.coordinators.data_coordinator import DataCoordinator
    from src.app.coordinators.editor_coordinator import EditorCoordinator

    kind = "entity" if hasattr(editor, "_current_entity_id") else "event"
    source = (
        Entity(id="source", name="Tasgillia", type="Character")
        if kind == "entity"
        else Event(id="source", name="Council", lore_date=100)
    )
    target = Entity(id="target", name="House Bjornaer", type="Faction")
    db_service.insert_entity(target)
    getattr(db_service, f"insert_{kind}")(source)
    window = editor.parentWidget()
    window.event_editor = editor if kind == "event" else MagicMock()
    window.entity_editor = editor if kind == "entity" else MagicMock()
    window.navigation_coordinator = MagicMock(selected_type=kind, selected_id="source")
    window.map_widget = MagicMock(maps_data=[])
    window.time_coordinator = None
    commands = []
    coordinator = EditorCoordinator(window)
    coordinator.command_requested.connect(commands.append)
    editor.relation_authoring_requested.connect(coordinator.author_relation)
    coordinator.relation_authoring_finished.connect(
        editor.relation_authoring.on_finished
    )
    data = DataCoordinator(window)
    editor.desc_edit.set_wiki_text("Unfinished prose")
    before = editor.desc_edit.textCursor().position()
    editor._on_add_relation()
    editor.relation_authoring.target.setText("House Bjornaer")
    editor.relation_authoring.apply()
    command = commands[0]
    result = command.execute(db_service)
    result.data["command_id"] = command.command_id
    coordinator.on_command_finished_check_toast(result)
    getattr(data, f"load_{kind}_details")("source", relations_only=True)
    rows = db_service.get_relations("source")
    getattr(data, f"on_{kind}_details_ready")(source, rows, [])
    assert editor.desc_edit.get_wiki_text() == "Unfinished prose"
    assert editor.desc_edit.textCursor().position() == before
    assert (
        editor.rel_list.currentItem().data(Qt.ItemDataRole.UserRole)["id"]
        == rows[0]["id"]
    )
    assert not editor.relation_authoring.pending_id


def test_capture_refinement_full_undo_redo_retains_identity_and_creation(db_service):
    source = Entity(name="Tasgillia", type="Character")
    target = Entity(name="House", type="Faction")
    for item in (source, target):
        db_service.insert_entity(item)
    capture = AddRelationCommand(source.id, target.id, "related")
    assert capture.execute(db_service).success
    saved = db_service.get_relations(source.id)[0]
    refine = UpdateRelationCommand(
        saved["id"],
        target.id,
        "member_of",
        {"notes": "charter"},
        source_id=source.id,
        expected=saved,
    )
    assert refine.execute(db_service).success
    refine.undo(db_service)
    capture.undo(db_service)
    assert db_service.get_relation(saved["id"]) is None
    # Replay from the same serialized shape used by history persistence.
    capture = AddRelationCommand.from_dict(capture.to_dict())
    refine = UpdateRelationCommand.from_dict(refine.to_dict())
    assert capture.execute(db_service).success
    assert refine.execute(db_service).success
    result = db_service.get_relation(saved["id"])
    assert result["created_at"] == saved["created_at"]
    assert result["rel_type"] == "member_of"
    assert result["attributes"] == {"notes": "charter"}
    assert len(db_service.get_relations(source.id)) == 1


def test_reversal_is_one_undoable_update_and_stale_snapshot_is_rejected(db_service):
    source, target = (
        Event(name="Source", lore_date=1),
        Event(name="Target", lore_date=2),
    )
    for item in (source, target):
        db_service.insert_event(item)
    rel_id = db_service.insert_relation(source.id, target.id, "related", {"keep": True})
    original = db_service.get_relation(rel_id)
    reverse = UpdateRelationCommand(
        rel_id,
        source.id,
        "caused",
        {"keep": True},
        source_id=target.id,
        expected=original,
    )
    assert reverse.execute(db_service).success
    changed = db_service.get_relation(rel_id)
    assert (changed["source_id"], changed["target_id"]) == (target.id, source.id)
    stale = UpdateRelationCommand(rel_id, target.id, "member_of", {}, expected=original)
    assert not stale.execute(db_service).success
    assert db_service.get_relation(rel_id) == changed
    reverse.undo(db_service)
    assert db_service.get_relation(rel_id) == original
    assert reverse.execute(db_service).success


def test_bidirectional_replay_collision_rolls_back_first_insert(db_service):
    source, target = (
        Event(name="Source", lore_date=1),
        Event(name="Target", lore_date=2),
    )
    for item in (source, target):
        db_service.insert_event(item)
    capture = AddRelationCommand(source.id, target.id, "related", bidirectional=True)
    assert capture.execute(db_service).success
    ids = capture.to_dict()["created_rel_ids"]
    capture.undo(db_service)
    from src.services.repositories.relation_repository import RelationRepository

    repo = RelationRepository()
    repo.set_connection(db_service.require_connection())
    repo.insert(ids[1], source.id, target.id, "owns", {"unrelated": True}, 42)
    assert not capture.execute(db_service).success
    assert db_service.get_relation(ids[0]) is None
    assert db_service.get_relation(ids[1])["attributes"] == {"unrelated": True}


def test_confidence_display_does_not_change_stored_precision(qtbot):
    attrs = {"confidence": 0.6000000000000001}
    widget = RelationItemWidget("Connection", "target", "Target", attrs)
    qtbot.addWidget(widget)
    assert widget._format_attributes() == "confidence=0.6"
    assert attrs["confidence"] == 0.6000000000000001
