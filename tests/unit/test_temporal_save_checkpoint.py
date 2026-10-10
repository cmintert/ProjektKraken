"""A save acknowledgement supplies the next draft's authoritative comparisons."""

import json
import logging
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QTextCursor

from src.commands.composite_command import CompositeCommand
from src.commands.registry import get_command_types
from src.commands.temporal_entity_edit_command import TemporalEntityEditCommand
from src.commands.wiki_commands import ProcessWikiLinksCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.events import Event
from src.core.operation_trace import finish, new_trace
from src.core.temporal_entity_checkpoint import parse_temporal_entity_checkpoint
from src.core.temporal_manager import TemporalManager
from src.services.history_service import HistoryService
from src.services.temporal_entity_snapshot_service import TemporalEntitySnapshotService
from src.services.worker import DatabaseWorker
from tests.unit.test_editor_coordinator import coordinator as _coordinator_fixture
from tests.unit.test_editor_coordinator import fake_window as _window_fixture
from tests.unit.test_entity_editor import editor as _editor_fixture

pytestmark = pytest.mark.ci_fast
editor = _editor_fixture
coordinator = _coordinator_fixture
fake_window = _window_fixture


def _command(request):
    return TemporalEntityEditCommand(
        request["entity_id"],
        request["lore_time"],
        request["expected"],
        request["patches"],
        request["metadata"],
        request["expected_metadata"],
        request.get("__save_origin", "unknown"),
    )


def _setup(editor, db_service, time=12.0, event_owned=False):
    entity = Entity(
        name="Harbor",
        type="Location",
        description="Old harbor",
        attributes={"owner": "Guild"},
    )
    db_service.insert_entity(entity)
    if event_owned:
        event = Event(name="Rebuilding", lore_date=time)
        db_service.insert_event(event)
        db_service.insert_relation(
            event.id,
            entity.id,
            "involved",
            {
                "valid_from_event": True,
                "payload": {
                    "description": "Old harbor",
                    "attributes": {"owner": "Guild"},
                },
            },
        )
    editor.load_entity(entity)
    state = TemporalManager(db_service).get_entity_state_at(entity.id, time).to_dict()
    editor.display_temporal_state(entity.id, state, playhead_time=time)
    return entity, state


@pytest.mark.parametrize("time", [-12.0, 0.0, 12.0])
@pytest.mark.parametrize("event_owned", [False, True])
@pytest.mark.parametrize("manual", [False, True])
def test_consecutive_saves_without_background_refresh(
    editor, db_service, qtbot, time, event_owned, manual
):
    entity, state = _setup(editor, db_service, time, event_owned)
    inner = editor.desc_edit.editor
    inner.moveCursor(QTextCursor.MoveOperation.End)
    inner.insertPlainText(" rebuilt")
    with qtbot.waitSignal(editor.temporal_save_requested) as first_request:
        editor._on_autosave()
    first = deepcopy(first_request.args[0])
    inner.insertPlainText(" again")
    cursor = inner.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
    inner.setTextCursor(cursor)
    selection = (cursor.anchor(), cursor.position())
    scroll = inner.verticalScrollBar().value()
    first_result = _command(first).execute(db_service)
    assert first_result.success, first_result.message
    checkpoint = first_result.data["temporal_entity_checkpoint"]
    assert editor.finish_temporal_save(True, checkpoint)
    assert editor._temporal_state["description"] == "Old harbor rebuilt"
    checkpoint["state"]["description"] = "Mutated transport"
    assert editor._temporal_state["description"] == "Old harbor rebuilt"
    assert editor.has_unsaved_changes()
    assert editor.edit_revision > first["__editor_revision"]
    assert editor._persisted_revision == first["__editor_revision"]
    assert inner.document().isUndoAvailable()
    assert (inner.textCursor().anchor(), inner.textCursor().position()) == selection
    assert inner.verticalScrollBar().value() == scroll
    # A stale background snapshot must not rebase a newer draft.
    editor.display_temporal_state(entity.id, state, playhead_time=time)
    assert editor._temporal_state["description"] == "Old harbor rebuilt"
    with qtbot.waitSignal(editor.temporal_save_requested) as second_request:
        (editor._on_save if manual else editor._on_autosave)()
    editor.display_temporal_state(entity.id, state, playhead_time=time)
    second_result = _command(deepcopy(second_request.args[0])).execute(db_service)
    assert second_result.success, second_result.message
    assert editor.finish_temporal_save(
        True, second_result.data["temporal_entity_checkpoint"]
    )
    assert not editor.has_unsaved_changes()
    saved = TemporalManager(db_service).get_entity_state_at(entity.id, time)
    assert saved.description == "Old harbor rebuilt again"
    assert saved.description_source == state["description_source"]
    assert inner.toPlainText() == saved.description
    assert (inner.textCursor().anchor(), inner.textCursor().position()) == selection


def test_acknowledged_metadata_does_not_replace_newer_metadata(
    editor, db_service, qtbot
):
    entity, _ = _setup(editor, db_service)
    editor.name_edit.setText("First harbor")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_autosave()
    first = deepcopy(request.args[0])
    editor.name_edit.setText("Newer harbor")
    result = _command(first).execute(db_service)
    assert result.success
    assert editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])
    assert editor.name_edit.text() == "Newer harbor"
    assert editor._baseline_name == "First harbor"
    with qtbot.waitSignal(editor.temporal_save_requested) as next_request:
        editor._on_save()
    result = _command(deepcopy(next_request.args[0])).execute(db_service)
    assert result.success, result.message
    assert db_service.get_entity(entity.id).name == "Newer harbor"
    editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])


@pytest.mark.parametrize(
    "malformed", [None, {}, "wrong", "wrong_time", "missing_source"]
)
def test_invalid_acknowledgement_keeps_draft_and_stops_retries(
    editor, db_service, qtbot, malformed
):
    entity, state = _setup(editor, db_service)
    editor.desc_edit.editor.insertPlainText("Draft ")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_autosave()
    result = _command(deepcopy(request.args[0])).execute(db_service)
    assert result.success
    checkpoint = deepcopy(result.data["temporal_entity_checkpoint"])
    if malformed == "wrong":
        checkpoint["entity_id"] = "another-entity"
    elif malformed == "wrong_time":
        checkpoint["lore_time"] = 99.0
    elif malformed == "missing_source":
        checkpoint["state"].pop("description_source")
    else:
        checkpoint = malformed
    editor.desc_edit.editor.insertPlainText("Newer ")
    draft = editor.desc_edit.get_wiki_text()
    assert not editor.finish_temporal_save(True, checkpoint)
    assert editor.has_unsaved_changes()
    assert not editor.save_pending
    assert not editor.autosave_manager._autosave_timer.isActive()
    assert "Changes were saved" in editor.temporal_snapshot_label.text()
    with qtbot.assertNotEmitted(editor.temporal_save_requested):
        editor._on_autosave()
        editor._on_save()
    editor.display_temporal_state(entity.id, state, playhead_time=12.0)
    assert editor.desc_edit.get_wiki_text() == draft
    editor.load_entity(db_service.get_entity(entity.id))
    assert not editor._temporal_checkpoint_invalid


def test_genuine_conflict_does_not_rebase_dirty_draft(editor, db_service, qtbot):
    entity, state = _setup(editor, db_service)
    editor.desc_edit.editor.insertPlainText("Local ")
    entity.description = "External edit"
    db_service.insert_entity(entity)
    external = (
        TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    )
    editor.display_temporal_state(entity.id, external, playhead_time=12.0)
    assert editor._temporal_state == state
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_save()
    result = _command(deepcopy(request.args[0])).execute(db_service)
    assert not result.success
    assert "visible value or its source changed" in result.message
    editor.finish_temporal_save(False)
    assert editor.has_unsaved_changes()
    assert db_service.get_entity(entity.id).description == "External edit"


def test_conflict_log_identifies_field_source_and_operation_without_values(
    editor, db_service, qtbot, caplog
):
    entity, state = _setup(editor, db_service, event_owned=True)
    editor.desc_edit.editor.insertPlainText("PRIVATE_DRAFT ")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_autosave()
    saved_request = deepcopy(request.args[0])
    assert saved_request["__save_origin"] == "autosave"
    event = Event(name="PRIVATE_EVENT", lore_date=12.0)
    db_service.insert_event(event)
    replacement_id = db_service.insert_relation(
        event.id,
        entity.id,
        "involved",
        {
            "valid_from_event": True,
            "priority": "manual",
            "modified_at": 99.0,
            "payload": {"description": "PRIVATE_EXTERNAL"},
        },
    )
    command = _command(saved_request)
    with caplog.at_level(logging.INFO, logger="src.operations"):
        result = finish(
            new_trace(command, "save", "world-1", 0), command.execute(db_service)
        )
    assert not result.success
    diagnostic = result.data["diagnostic"]
    assert diagnostic["field"] == "description"
    assert (
        diagnostic["expected_relation_id"] == state["description_source"]["relation_id"]
    )
    assert diagnostic["actual_relation_id"] == replacement_id
    assert diagnostic["value_changed"] is True
    record = next(
        r.message for r in caplog.records if "stage=temporal_rejection" in r.message
    )
    assert f"operation_id={result.data['operation_trace']['operation_id']}" in record
    assert "save_origin=autosave" in record
    assert "lore_time=12.0" in record
    assert "PRIVATE_" not in caplog.text


def test_success_and_composite_conflict_keep_diagnostics_separate(db_service, caplog):
    entity = Entity(name="Harbor", type="Location", description="PRIVATE_OLD")
    db_service.insert_entity(entity)
    state = TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    edit = TemporalEntityEditCommand(
        entity.id,
        12.0,
        state,
        [{"field": "description", "action": "set", "value": "PRIVATE_NEW"}],
        save_origin="manual",
    )
    composite = CompositeCommand(
        [edit, ProcessWikiLinksCommand(entity.id, "PRIVATE_NEW", "entity")]
    )
    with caplog.at_level(logging.INFO, logger="src.operations"):
        success = finish(
            new_trace(composite, "save", "world-1", 0), composite.execute(db_service)
        )
    assert success.success
    assert "diagnostic" not in success.data
    assert "stage=temporal_rejection" not in caplog.text
    assert "save_origin=manual" in caplog.text
    assert f"target_id={entity.id}" in caplog.text
    caplog.clear()
    stale = CompositeCommand(
        [
            TemporalEntityEditCommand(
                entity.id,
                12.0,
                state,
                [{"field": "description", "action": "set", "value": "PRIVATE_OTHER"}],
                save_origin="manual",
            )
        ]
    )
    with caplog.at_level(logging.INFO, logger="src.operations"):
        failure = finish(
            new_trace(stale, "save", "world-1", 0), stale.execute(db_service)
        )
    assert not failure.success
    assert failure.data["diagnostic"]["reason"] == "visible_value_or_source_changed"
    assert "stage=temporal_rejection" in caplog.text
    assert "PRIVATE_" not in caplog.text


def test_source_only_conflict_records_provenance_without_description(db_service):
    entity = Entity(name="Harbor", type="Location", description="PRIVATE_BODY")
    db_service.insert_entity(entity)
    expected = (
        TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    )
    event = Event(name="PRIVATE_EVENT", lore_date=12.0)
    db_service.insert_event(event)
    relation_id = db_service.insert_relation(
        event.id,
        entity.id,
        "involved",
        {"valid_from_event": True, "payload": {"description": "PRIVATE_BODY"}},
    )
    result = TemporalEntityEditCommand(
        entity.id,
        12.0,
        expected,
        [{"field": "description", "action": "set", "value": "PRIVATE_DRAFT"}],
        save_origin="manual",
    ).execute(db_service)
    assert not result.success
    diagnostic = result.data["diagnostic"]
    assert diagnostic["value_changed"] is False
    assert diagnostic["expected_source_kind"] == "baseline"
    assert diagnostic["actual_source_kind"] == "relation"
    assert diagnostic["actual_relation_id"] == relation_id
    assert "PRIVATE_" not in json.dumps(diagnostic)


def test_checkpoint_failure_rolls_back_edit(editor, db_service, qtbot):
    entity, _ = _setup(editor, db_service)
    editor.desc_edit.editor.insertPlainText("Changed ")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_save()
    command = _command(deepcopy(request.args[0]))
    build = TemporalEntitySnapshotService.build
    calls = 0

    def fail_after_write(service, entity_id, time):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("Checkpoint resolution failed")
        return build(service, entity_id, time)

    with patch.object(TemporalEntitySnapshotService, "build", fail_after_write):
        result = command.execute(db_service)
    assert not result.success
    assert "temporal_entity_checkpoint" not in result.data
    assert result.data["diagnostic"]["reason"] == "unexpected_failure"
    assert db_service.get_entity(entity.id).description == "Old harbor"
    editor.finish_temporal_save(False)


def test_checkpoint_round_trip_and_composite_undo_redo(db_service):
    entity = Entity(name="Harbor", type="Location", description="Old harbor")
    db_service.insert_entity(entity)
    state = TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    edit = TemporalEntityEditCommand(
        entity.id,
        12.0,
        state,
        [{"field": "description", "action": "set", "value": "New harbor"}],
    )
    composite = CompositeCommand(
        [edit, ProcessWikiLinksCommand(entity.id, "New harbor", "entity")]
    )
    result = composite.execute(db_service)
    assert result.success, result.message
    checkpoint = json.loads(json.dumps(result.data["temporal_entity_checkpoint"]))
    assert parse_temporal_entity_checkpoint(checkpoint, entity.id, 12.0)
    assert checkpoint == TemporalEntitySnapshotService(db_service).build(
        entity.id, 12.0
    )
    restored = CompositeCommand.from_dict(json.loads(json.dumps(composite.to_dict())))
    restored.undo(db_service)
    assert db_service.get_entity(entity.id).description == "Old harbor"
    result = restored.execute(db_service)
    assert result.success, result.message
    assert (
        result.data["temporal_entity_checkpoint"]["state"]["description"]
        == "New harbor"
    )


def test_composite_checkpoint_failure_rolls_back_children(db_service):
    entity = Entity(name="Harbor", type="Location", description="Old harbor")
    db_service.insert_entity(entity)
    state = TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    edit = TemporalEntityEditCommand(
        entity.id,
        12.0,
        state,
        [{"field": "description", "action": "set", "value": "New harbor"}],
    )
    composite = CompositeCommand(
        [edit, ProcessWikiLinksCommand(entity.id, "New harbor", "entity")]
    )
    build = TemporalEntitySnapshotService.build
    calls = 0

    def fail_final_snapshot(service, entity_id, time):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError("Final checkpoint failed")
        return build(service, entity_id, time)

    with patch.object(TemporalEntitySnapshotService, "build", fail_final_snapshot):
        with pytest.raises(ValueError, match="Final checkpoint failed"):
            composite.execute(db_service)
    assert db_service.get_entity(entity.id).description == "Old harbor"


@pytest.mark.parametrize("event_owned", [False, True])
def test_acknowledgement_keeps_newer_attribute_edits(
    editor, db_service, qtbot, event_owned
):
    entity, state = _setup(editor, db_service, event_owned=event_owned)
    value = editor.sheet_builder._pairs["owner"].value_edit
    value.setPlainText("Navy")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_autosave()
    first = deepcopy(request.args[0])
    value.setPlainText("Crown")
    result = _command(first).execute(db_service)
    assert result.success
    editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])
    assert value.toPlainText() == "Crown"
    assert editor._temporal_state["attributes"]["owner"] == "Navy"
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_save()
    result = _command(deepcopy(request.args[0])).execute(db_service)
    assert result.success, result.message
    editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])
    saved = TemporalManager(db_service).get_entity_state_at(entity.id, 12.0)
    assert saved.attributes["owner"] == "Crown"
    assert saved.attribute_sources["owner"] == state["attribute_sources"]["owner"]


def test_dated_creation_acknowledges_new_source_without_refresh(
    editor, db_service, qtbot
):
    entity, _ = _setup(editor, db_service)
    editor._pending_new_description_event = {"event_name": "Rebuilding"}
    editor.desc_edit.editor.insertPlainText("New chapter: ")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_save()
    result = _command(deepcopy(request.args[0])).execute(db_service)
    assert result.success, result.message
    editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])
    assert "Rebuilding" in editor.description_source_label.text()
    editor.desc_edit.editor.insertPlainText("Corrected ")
    with qtbot.waitSignal(editor.temporal_save_requested) as request:
        editor._on_save()
    result = _command(deepcopy(request.args[0])).execute(db_service)
    assert result.success, result.message
    editor.finish_temporal_save(True, result.data["temporal_entity_checkpoint"])
    assert len(db_service.get_all_events()) == 1
    assert db_service.get_entity(entity.id).description == "Old harbor"


def _pending_coordinator_save(editor, coordinator, fake_window, qtbot):
    fake_window.entity_editor = editor
    fake_window.time_coordinator = MagicMock()
    editor.temporal_save_requested.connect(coordinator.update_temporal_entity)
    editor.desc_edit.editor.insertPlainText("Changed ")
    with qtbot.waitSignal(coordinator.command_requested) as request:
        editor._on_autosave()
    return request.args[0]


def test_coordinator_installs_checkpoint_before_completion_signal(
    editor, db_service, qtbot, coordinator, fake_window, caplog
):
    _setup(editor, db_service)
    command = _pending_coordinator_save(editor, coordinator, fake_window, qtbot)
    result = command.execute(db_service)
    assert result.success
    result.data["command_id"] = command.command_id
    result.data["operation_trace"] = new_trace(command, "save", "world-1", 0)
    observed = []

    def on_completion(*args):
        observed.append(editor._temporal_state["description"])
        assert not editor.save_pending
        assert not editor._temporal_save_pending

    coordinator.editor_save_finished.connect(on_completion)
    with caplog.at_level(logging.INFO, logger="src.operations"):
        coordinator.on_temporal_command_result(result)
    assert observed == ["Changed Old harbor"]
    fake_window.time_coordinator.on_temporal_save_completed.assert_called_once()
    assert "stage=temporal_ack save_origin=autosave lore_time=12.0" in caplog.text
    assert "outcome=accepted" in caplog.text


@pytest.mark.parametrize("change", ["discard", "entity", "world", "time", "command"])
def test_coordinator_ignores_stale_acknowledgements(
    editor, db_service, qtbot, coordinator, fake_window, change, caplog
):
    entity, _ = _setup(editor, db_service)
    command = _pending_coordinator_save(editor, coordinator, fake_window, qtbot)
    result = command.execute(db_service)
    assert result.success
    result.data["command_id"] = command.command_id
    result.data["operation_trace"] = new_trace(command, "save", "world-1", 0)
    if change == "discard":
        editor._on_discard()
    elif change == "entity":
        editor.load_entity(Entity(name="Another entity", type="Location"))
    elif change == "world":
        editor.clear()
        editor.load_entity(entity)
    elif change == "time":
        editor._temporal_time = 99.0
    else:
        result.data["command_id"] = "old-command-id"
    before = deepcopy(editor._temporal_state)
    with caplog.at_level(logging.INFO, logger="src.operations"):
        with patch.object(editor, "finish_temporal_save") as acknowledge:
            coordinator.on_temporal_command_result(result)
    acknowledge.assert_not_called()
    assert "stage=temporal_ack save_origin=autosave lore_time=12.0" in caplog.text
    assert "outcome=stale" in caplog.text
    assert editor._temporal_state == before
    fake_window.time_coordinator.on_temporal_save_completed.assert_not_called()
    editor.autosave_manager.stop_timer()


def test_coordinator_handles_missing_checkpoint_as_saved_but_unacknowledged(
    editor, db_service, qtbot, coordinator, fake_window, caplog
):
    _setup(editor, db_service)
    command = _pending_coordinator_save(editor, coordinator, fake_window, qtbot)
    result = command.execute(db_service)
    result.data["command_id"] = command.command_id
    result.data["operation_trace"] = new_trace(command, "save", "world-1", 0)
    result.data.pop("temporal_entity_checkpoint")
    with caplog.at_level(logging.INFO, logger="src.operations"):
        with qtbot.waitSignal(coordinator.editor_save_finished) as completion:
            coordinator.on_temporal_command_result(result)
    assert completion.args[-1] is False
    assert editor._temporal_checkpoint_invalid
    assert "stage=temporal_ack save_origin=autosave lore_time=12.0" in caplog.text
    assert "outcome=invalid" in caplog.text
    assert "reason=missing_or_invalid_checkpoint" in caplog.text
    fake_window.time_coordinator.on_temporal_save_completed.assert_not_called()


def test_worker_delivers_checkpoint_after_commit_and_history_round_trip(
    db_service, qtbot
):
    entity = Entity(name="Harbor", type="Location", description="Old harbor")
    db_service.insert_entity(entity)
    state = TemporalManager(db_service).get_entity_state_at(entity.id, 12.0).to_dict()
    edit = TemporalEntityEditCommand(
        entity.id,
        12.0,
        state,
        [{"field": "description", "action": "set", "value": "Saved harbor"}],
    )
    registry = get_command_types()
    worker = DatabaseWorker(":memory:", registry)
    worker.db_service = db_service
    worker.history_service = HistoryService(db_service, "checkpoint-world")
    for name, command_class in registry.items():
        worker.history_service.register_command_type(name, command_class)
    observed = []

    def delivered(result):
        assert not db_service._connection.in_transaction
        observed.append(result)

    worker.command_finished.connect(delivered)
    worker.run_command(
        {
            "type": "TemporalEntityEditCommand",
            "data": edit.to_dict(),
            "base": edit.base_state_dict(),
        }
    )
    assert len(observed) == 1 and observed[0].success
    assert observed[0].data["command_id"] == edit.command_id
    assert observed[0].data["temporal_entity_checkpoint"]["state"]["description"] == (
        "Saved harbor"
    )
    history = worker.history_service.load_recent_history()
    assert len(history) == 1
    history[0].undo(db_service)
    assert db_service.get_entity(entity.id).description == "Old harbor"
    result = history[0].execute(db_service)
    assert result.success
    assert (
        result.data["temporal_entity_checkpoint"]["state"]["description"]
        == "Saved harbor"
    )
    worker.history_service.end_session()


def test_snapshot_uses_calendar_aware_resolution_for_verification(db_service):
    config = CalendarConfig.create_default()
    db_service.insert_calendar_config(config)
    db_service.set_active_calendar_config(config.id)
    calendar = CalendarConverter(config)
    expression = DateParser(config).parse_expression("961")
    time = calendar.start_of_year(962)
    entity = Entity(name="Harbor", type="Location", description="Old harbor")
    db_service.insert_entity(entity)
    event = Event(
        name="Rebuilding",
        lore_date=0.0,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    db_service.insert_event(event)
    db_service.insert_relation(
        event.id,
        entity.id,
        "involved",
        {"valid_from_event": True, "payload": {"description": "Dated harbor"}},
    )
    expected = (
        TemporalManager(db_service).get_entity_state_at(entity.id, time).to_dict()
    )
    assert expected["description"] == "Dated harbor"
    assert TemporalEntitySnapshotService(db_service).build(entity.id, time)[
        "state"
    ] == (expected)
    edit = TemporalEntityEditCommand(
        entity.id,
        time,
        expected,
        [{"field": "description", "action": "set", "value": "Corrected harbor"}],
    )
    result = edit.execute(db_service)
    assert result.success, result.message
    assert result.data["temporal_entity_checkpoint"]["state"]["description"] == (
        "Corrected harbor"
    )
    assert db_service.get_entity(entity.id).description == "Old harbor"


def test_rapid_typing_uses_acknowledgement_before_real_autosave_timer(
    editor, db_service, qtbot, coordinator, fake_window
):
    """Exercise keyboard input and the actual debounce timer without a refresh."""
    entity, _ = _setup(editor, db_service)
    fake_window.entity_editor = editor
    fake_window.time_coordinator = MagicMock()
    editor.temporal_save_requested.connect(coordinator.update_temporal_entity)
    editor.resize(680, 820)
    qtbot.addWidget(editor.window())
    editor.window().show()
    editor.window().activateWindow()
    editor.show()
    inner = editor.desc_edit.editor
    inner.setFocus()
    qtbot.waitUntil(inner.hasFocus)
    inner.moveCursor(QTextCursor.MoveOperation.End)
    editor.autosave_manager._autosave_timer.setInterval(30)
    with qtbot.waitSignal(coordinator.command_requested) as first:
        qtbot.keyClicks(inner, " rebuilt")
    qtbot.keyClicks(inner, " again")
    position = inner.textCursor().position()
    result = first.args[0].execute(db_service)
    result.data["command_id"] = first.args[0].command_id
    with qtbot.waitSignal(coordinator.command_requested) as second:
        coordinator.on_temporal_command_result(result)
    assert inner.toPlainText() == "Old harbor rebuilt again"
    assert inner.textCursor().position() == position
    assert inner.hasFocus()
    assert inner.document().isUndoAvailable()
    result = second.args[0].execute(db_service)
    assert result.success, result.message
    result.data["command_id"] = second.args[0].command_id
    coordinator.on_temporal_command_result(result)
    assert db_service.get_entity(entity.id).description == "Old harbor rebuilt again"
    assert not editor.has_unsaved_changes()
    assert inner.textCursor().position() == position
