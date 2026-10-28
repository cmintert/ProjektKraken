"""Authoring sources, stale context preservation and asynchronous review boundaries."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from src.app.coordinators.event_timing_coordinator import EventTimingCoordinator
from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.gui.widgets.event_editor import EventEditorWidget

pytestmark = pytest.mark.ci_fast


def editor_for(qtbot, event, sources):
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = EventEditorWidget(parent)
    qtbot.addWidget(editor)
    converter = CalendarConverter(CalendarConfig.create_default())
    editor.set_calendar_converter(converter)
    editor.set_temporal_context(
        TemporalResolutionContext.build([event, *sources], converter)
    )
    editor.load_event(event)
    return editor, converter


@pytest.mark.parametrize(
    "control",
    [
        "date",
        "time",
        "uncertainty",
        "source",
        "endpoint",
        "offset",
        "calendar_offset",
        "has_end",
        "duration",
        "end_date",
        "end_source",
        "end_endpoint",
        "end_offset",
    ],
)
def test_entire_date_frame_waits_for_explicit_save(qtbot, control):
    child = Event("Battle", 6, id="child")
    root = Event("March", 1, lore_duration=3, id="root")
    editor, _ = editor_for(qtbot, child, [root])
    timing = editor.temporal_widget
    requests = []
    editor.save_requested.connect(requests.append)
    editor.autosave_manager._autosave_timer.setInterval(20)
    if control in {"source", "endpoint", "offset", "calendar_offset"}:
        timing.source_start.mode.setCurrentIndex(1)
        timing.source_start.events.setCurrentIndex(
            timing.source_start.events.findData("event:root")
        )
        if control == "endpoint":
            timing.source_start.options.endpoint.setCurrentIndex(1)
        if control == "offset":
            timing.source_start.options.offset.setValue(2.5)
        if control == "calendar_offset":
            timing.source_start.options.unit.setCurrentIndex(1)
            timing.source_start.options.offset.setValue(2)
    elif control.startswith("end_") or control in {"has_end", "duration"}:
        timing.has_duration.setChecked(True)
        if control == "duration":
            timing.set_duration(4)
        if control.startswith("end_"):
            timing.btn_lock_end.setChecked(True)
            if control == "end_date":
                timing.date_end.set_value(10)
            else:
                timing.source_end.mode.setCurrentIndex(1)
                timing.source_end.events.setCurrentIndex(
                    timing.source_end.events.findData("event:root")
                )
                if control == "end_endpoint":
                    timing.source_end.options.endpoint.setCurrentIndex(1)
                if control == "end_offset":
                    timing.source_end.options.offset.setValue(12)
    elif control == "time":
        timing.date_start.spin_hour.setValue(12)
    elif control == "uncertainty":
        timing.date_start.qualifier_combo.setCurrentIndex(1)
    else:
        timing.date_start.set_value(8)
    editor.set_dirty(True)
    qtbot.wait(80)
    assert not requests
    assert not editor.save_pending
    assert editor.has_unsaved_temporal_changes()
    assert editor.has_unsaved_changes()
    assert "Save Changes" in editor.save_status.text()
    editor._on_save()
    assert len(requests) == 1
    assert not requests[0].get("__preserve_timing")


def test_content_autosave_keeps_incomplete_follow_draft_and_review_guard(
    qtbot, db_service, prepare_timing_command
):
    from src.app.coordinators.editor_coordinator import EditorCoordinator
    from src.commands.event_timing_intents import timing_intent

    root = Event("March", 1, id="root")
    child = Event("Battle", 6, id="child")
    for event in (root, child):
        db_service.insert_event(event)
    editor, _ = editor_for(qtbot, child, [root])
    parent = editor.parentWidget()
    parent.event_editor = editor
    parent.entity_editor = MagicMock()
    coordinator = EditorCoordinator(parent)
    coordinator.auto_create_relations = False
    commands = []
    editor.save_requested.connect(coordinator.update_event)
    coordinator.command_requested.connect(commands.append)
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(1)  # No source selected yet.
    editor.name_edit.setText("Renamed while choosing timing")
    editor.autosave_manager._autosave_timer.setInterval(20)
    editor.autosave_manager.start_timer()
    qtbot.waitUntil(lambda: bool(commands))
    command = commands[0]
    assert not timing_intent(command)
    assert "lore_date" not in command.update_data
    result = command.execute(db_service)
    assert result.success
    source.events.setCurrentIndex(source.events.findData("event:root"))
    source.options.offset.setValue(3)
    result.data["command_id"] = command.command_id
    coordinator.on_temporal_command_result(result)
    assert db_service.get_event(child.id).name == editor.name_edit.text()
    assert db_service.get_event(child.id).lore_date == 6
    assert editor.temporal_widget._loaded_definition.start.kind == "manual"
    assert source.options.offset.value() == 3
    assert not editor.save_pending
    assert editor.has_unsaved_changes()
    editor.autosave_manager._perform_autosave()
    assert len(commands) == 1  # No repeated saves of already accepted prose.
    editor._on_save()
    assert timing_intent(commands[-1])
    assert prepare_timing_command(commands[-1]).execute(db_service).success
    assert db_service.get_event(child.id).lore_date == 4


def test_content_autosave_does_not_commit_invalid_date_text(qtbot, db_service):
    from PySide6.QtCore import Qt

    child = Event("Battle", 6, id="child")
    db_service.insert_event(child)
    editor, _ = editor_for(qtbot, child, [])
    field = editor.temporal_widget.date_start.txt_date
    field.setText("unfinished date")
    field.textEdited.emit(field.text())
    field.setSelection(1, 5)
    selected, caret = field.selectedText(), field.cursorPosition()
    editor.name_edit.setText("Saved separately")
    requests = []
    editor.save_requested.connect(requests.append)
    editor.autosave_manager._autosave_timer.setInterval(20)
    editor.autosave_manager.start_timer()
    qtbot.waitUntil(lambda: bool(requests))
    payload = requests[0]
    assert UpdateEventCommand(child.id, payload).execute(db_service).success
    assert not editor.finish_save(payload["__editor_revision"], True)
    assert field.text() == "unfinished date"
    assert (field.selectedText(), field.cursorPosition()) == (selected, caret)
    assert db_service.get_event(child.id).lore_date == 6
    qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert not editor.has_unsaved_changes()
    assert editor.save_status.text() == "Saved"


def test_content_only_command_preserves_current_timing_and_undo(db_service):
    from copy import deepcopy

    from src.commands.event_timing_intents import request_for_command
    from src.services.event_timing.store import capture

    child = Event(
        "Battle",
        12,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:root")
        ).apply({}),
    )
    db_service.insert_event(child)
    before = deepcopy(child.attributes)
    command = UpdateEventCommand(
        child.id,
        {
            "name": "Renamed",
            "attributes": {"colour": "red", "_temporal_v2": {"schema": 99}},
            "__preserve_timing": True,
        },
    )
    prepared = request_for_command(command, capture(db_service))
    assert (
        prepared.updates[child.id]["attributes"]["_temporal_v2"]
        == before["_temporal_v2"]
    )
    assert command.execute(db_service).success
    result = db_service.get_event(child.id)
    assert result.attributes["_temporal_v2"] == before["_temporal_v2"]
    assert result.attributes["colour"] == "red"
    assert result.lore_date == 12
    command.undo(db_service)
    assert db_service.get_event(child.id).attributes == before
    assert (
        not UpdateEventCommand(
            child.id,
            {
                "lore_date": 0,
                "__preserve_timing": True,
            },
        )
        .execute(db_service)
        .success
    )


def test_content_ack_refreshes_clean_timing_after_concurrent_move(qtbot, db_service):
    from dataclasses import replace

    from src.app.coordinators.editor_coordinator import EditorCoordinator

    child = Event("Battle", 6, id="child")
    db_service.insert_event(child)
    editor, _ = editor_for(qtbot, child, [])
    parent = editor.parentWidget()
    parent.event_editor = editor
    parent.entity_editor = MagicMock()
    coordinator = EditorCoordinator(parent)
    coordinator.auto_create_relations = False
    commands = []
    editor.save_requested.connect(coordinator.update_event)
    coordinator.command_requested.connect(commands.append)
    editor.name_edit.setText("Renamed")
    editor._on_autosave()
    db_service.insert_event(replace(child, lore_date=9))
    result = commands[0].execute(db_service)
    assert result.success
    result.data["command_id"] = commands[0].command_id
    coordinator.on_temporal_command_result(result)
    assert editor.temporal_widget.get_start() == 9
    assert not editor.has_unsaved_temporal_changes()
    assert not editor.has_unsaved_changes()


def test_unsupported_timing_does_not_invent_a_draft_during_content_autosave(
    qtbot, db_service
):
    child = Event(
        "Future import",
        None,
        lore_duration=None,
        id="future",
        attributes={"_temporal_v2": {"schema": 99, "opaque": "preserved"}},
    )
    db_service.insert_event(child)
    editor, _ = editor_for(qtbot, child, [])
    editor.name_edit.setText("Still editable")
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_autosave()
    payload = requests[0]
    result = UpdateEventCommand(child.id, payload).execute(db_service)
    assert result.success
    editor.mark_temporal_saved(db_service.get_event(child.id).to_dict())
    assert editor.finish_save(payload["__editor_revision"], True)
    assert editor.save_status.text() == "Saved"
    assert db_service.get_event(child.id).attributes == child.attributes


def test_followed_start_and_duration_round_trip(
    qtbot, db_service, prepare_timing_command
):
    root = Event("Coronation", 10, id="root")
    child = Event("Journey", 2, id="child")
    db_service.insert_event(root)
    db_service.insert_event(child)
    editor, converter = editor_for(qtbot, child, [root])
    config = converter._config
    config.is_active = True
    db_service.insert_calendar_config(config)
    timing = editor.temporal_widget
    timing.source_start.mode.setCurrentIndex(1)
    timing.source_start.events.setCurrentIndex(
        timing.source_start.events.findData("event:root")
    )
    timing.source_start.options.offset.setValue(3)
    timing.has_duration.setChecked(True)
    timing.set_duration(5)
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    command = prepare_timing_command(UpdateEventCommand(child.id, saved.args[0]))
    assert command.execute(db_service).success
    result = db_service.get_event(child.id)
    assert result.lore_date == 13
    assert result.lore_duration == 5
    editor.load_event(result)
    assert editor.temporal_widget.source_start.definition().anchor_id == "event:root"
    assert editor.temporal_widget.date_start.isHidden()


def test_refresh_retains_offset_draft_and_new_source_name(qtbot):
    root = Event("Treaty", 10, id="root")
    child = Event(
        "War",
        2,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(instant=2),
            "independent",
            EndpointDefinition("event", anchor_id="event:root"),
        ).apply({}),
    )
    editor, converter = editor_for(qtbot, child, [root])
    source = editor.temporal_widget.source_end
    source.options.offset.setValue(-3)
    editor.autosave_manager.stop_timer()
    root.name = "Renamed treaty"
    root.lore_date = 20
    editor.set_temporal_context(
        TemporalResolutionContext.build([child, root], converter, 2)
    )
    assert source.definition().offset["value"] == -3
    assert "Renamed treaty" in source.options.summary.text()


def test_incomplete_follow_selection_reports_inline_instead_of_raising(qtbot):
    child = Event("Journey", 2, id="child")
    editor, _ = editor_for(qtbot, child, [])
    editor.temporal_widget.source_start.mode.setCurrentIndex(1)
    editor.autosave_manager.stop_timer()
    intents = []
    editor.save_requested.connect(intents.append)
    editor._on_save()
    assert not intents
    assert "source Event" in editor.temporal_widget.range_summary.text()


def test_async_review_cancellation_writes_nothing(qtbot, qapp, db_service, monkeypatch):
    root = Event("Treaty", 10, id="root")
    child = Event(
        "War",
        2,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(instant=2),
            "independent",
            EndpointDefinition("event", anchor_id="event:root"),
        ).apply({}),
    )
    db_service.insert_event(root)
    db_service.insert_event(child)
    parent = QWidget()
    qtbot.addWidget(parent)
    outgoing = []
    coordinator = EventTimingCoordinator(
        parent,
        qapp.thread(),
        lambda: db_service,
        lambda: db_service.db_path,
        outgoing.append,
    )
    monkeypatch.setattr(coordinator, "_review", lambda plan: False)
    failures = []
    coordinator.failed.connect(failures.append)
    assert coordinator.intercept(UpdateEventCommand(root.id, {"lore_date": 20}))
    qtbot.waitUntil(lambda: bool(failures), timeout=5000)
    assert not outgoing
    assert db_service.get_event(root.id).lore_date == 10
    coordinator.shutdown()


@pytest.mark.parametrize("apply", [False, True])
def test_completed_calculation_retires_progress_before_nested_review(
    qtbot, qapp, db_service, monkeypatch, apply
):
    from PySide6.QtWidgets import QProgressDialog

    root = Event("March", 10, id="root")
    child = Event(
        "Battle",
        12,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 2}
            )
        ).apply({}),
    )
    for event in (root, child):
        db_service.insert_event(event)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    outgoing, failures, progress_states = [], [], []
    coordinator = EventTimingCoordinator(
        parent,
        qapp.thread(),
        lambda: db_service,
        lambda: db_service.db_path,
        outgoing.append,
    )

    def review(plan):
        qtbot.wait(400)
        progress_states.append(
            (
                coordinator._progress is None,
                any(
                    isinstance(widget, QProgressDialog) and widget.isVisible()
                    for widget in qapp.topLevelWidgets()
                ),
            )
        )
        return apply

    monkeypatch.setattr(coordinator, "_review", review)
    coordinator.failed.connect(failures.append)
    try:
        assert coordinator.intercept(UpdateEventCommand(root.id, {"lore_date": 20}))
        coordinator._progress.setMinimumDuration(20)
        qtbot.waitUntil(lambda: bool(outgoing or failures), timeout=5000)
        assert progress_states == [(True, False)]
        assert db_service.get_event(root.id).lore_date == 10
        if apply:
            assert outgoing[0].execute(db_service).success
            assert db_service.get_event(child.id).lore_date == 22
        else:
            assert not outgoing
            assert failures[0].success is False
    finally:
        coordinator.shutdown()


def test_completed_joint_model_survives_json_context(qtbot):
    import json

    from src.core.event_timing.solver import resolve_world

    root = Event("Treaty", 10, id="root")
    child = Event(
        "Aftermath",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 2}
            )
        ).apply({}),
    )
    model = resolve_world([root, child])
    context = TemporalResolutionContext.build(
        [root, child], None, resolved_json=json.dumps(model.to_dict())
    )
    assert context.view_events()[1].lore_date == 12
    assert context.anchors()["event:child"].joint is not None


@pytest.mark.parametrize("prefer", [False, True])
def test_date_evidence_preserves_binding_until_explicit_replacement(
    qtbot, monkeypatch, prefer
):
    from PySide6.QtWidgets import QDialog

    from src.gui.dialogs.temporal_evidence_dialog import TemporalEvidenceDialog

    root = Event("Treaty", 10, id="root")
    child = Event(
        "Aftermath",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition("event", anchor_id="event:root"),
            "duration",
            duration_days=3,
        ).apply({}),
    )
    editor, _converter = editor_for(qtbot, child, [root])

    def accept_evidence(dialog):
        dialog._add_claim("Chronicle", "2 January 1")
        dialog.preferred.setCurrentIndex(1 if prefer else 0)
        dialog._accept_valid()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TemporalEvidenceDialog, "exec", accept_evidence)
    editor._edit_temporal_evidence()
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    metadata = saved.args[0]["attributes"]["_temporal_v2"]
    assert metadata["schema"] == 2
    assert "expression" not in metadata
    timing = EventTimingDefinition.from_dict(metadata["timing"])
    assert timing.start.kind == ("manual" if prefer else "event")
    assert timing.duration_days == 3
    assert metadata["claims"][0]["source"] == "Chronicle"


def test_future_expression_is_preserved_without_crashing_the_editor(qtbot):
    from copy import deepcopy

    expression = {"schema_version": 99, "future_date": {"opaque": True}}
    definition = EventTimingDefinition(EndpointDefinition(expression=expression))
    event = Event(
        "Future evidence",
        None,
        id="future",
        attributes=definition.apply({"notes": "keep"}),
    )
    original = deepcopy(event.attributes)
    editor, _converter = editor_for(qtbot, event, [])
    assert editor.temporal_widget._unsupported_timing
    assert not editor.temporal_evidence_button.isEnabled()
    editor.name_edit.setText("Rename preserves evidence")
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    assert saved.args[0]["attributes"]["_temporal_v2"] == original["_temporal_v2"]
    assert saved.args[0]["attributes"]["notes"] == "keep"


@pytest.mark.parametrize("undo", [False, True])
def test_accepted_timeline_change_then_follow_save_preserves_prose(
    qtbot, db_service, prepare_timing_command, undo
):
    from src.app.coordinators.map_temporal_coordinator import MapTemporalCoordinator

    root = Event("March", 0, id="root")
    child = Event("Battle", 6.822222222222221, id="child")
    for event in (root, child):
        db_service.insert_event(event)
    editor, converter = editor_for(qtbot, child, [root])
    editor.desc_edit.set_wiki_text("Keep this unsaved paragraph")
    cursor = editor.desc_edit.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(9, cursor.MoveMode.KeepAnchor)
    editor.desc_edit.setTextCursor(cursor)
    before_selection = editor.desc_edit.textCursor().selectedText()
    editor.temporal_widget.range_button.setChecked(True)
    publisher = MapTemporalCoordinator(
        db_service.get_all_events, [editor.set_temporal_context]
    )
    publisher.set_calendar(converter._config)
    move = prepare_timing_command(
        UpdateEventCommand(child.id, {"lore_date": 6.810985159629813})
    )
    assert move.execute(db_service).success
    publisher.refresh()
    if undo:
        move.undo(db_service)
        publisher.refresh()
    current = db_service.get_event(child.id)
    assert (
        editor.temporal_widget._loaded_definition
        == EventTimingDefinition.from_event(current)
    )
    assert editor.desc_edit.get_wiki_text() == "Keep this unsaved paragraph"
    assert editor.desc_edit.textCursor().selectedText() == before_selection
    assert editor.temporal_widget.range_button.isChecked()
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(source.mode.findData("event"))
    source.events.setCurrentIndex(source.events.findData("event:root"))
    source.options.offset.setValue(6)
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    command = prepare_timing_command(UpdateEventCommand(child.id, saved.args[0]))
    assert command.execute(db_service).success
    persisted = db_service.get_event(child.id)
    assert persisted.lore_date == 6
    assert persisted.start_follows_event
    assert persisted.description == "Keep this unsaved paragraph"


def test_context_refresh_preserves_timing_draft_and_real_conflict(qtbot, db_service):
    from dataclasses import replace

    from src.commands.event_timing_intents import request_for_command
    from src.services.event_timing.planning import prepare_change
    from src.services.event_timing.store import capture

    root = Event("March", 0, id="root")
    child = Event("Battle", 6, id="child")
    for event in (root, child):
        db_service.insert_event(event)
    editor, converter = editor_for(qtbot, child, [root])
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(source.mode.findData("event"))
    source.events.setCurrentIndex(source.events.findData("event:root"))
    source.options.offset.setValue(2)
    revised = replace(child, lore_date=9)
    db_service.insert_event(revised)
    editor.set_temporal_context(
        TemporalResolutionContext.build([revised, root], converter, 2)
    )
    assert source.definition().offset["value"] == 2
    assert (
        editor.temporal_widget._loaded_definition
        == EventTimingDefinition.from_event(child)
    )
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    snapshot = capture(db_service)
    request = request_for_command(UpdateEventCommand(child.id, saved.args[0]), snapshot)
    with pytest.raises(ValueError, match="timing changed since"):
        prepare_change(snapshot, request)


def test_prose_save_preserves_unedited_fractional_date(qtbot, db_service):
    from src.cli.event_timing import execute_timing

    child = Event("Fractional", 6.810985159629813, id="child")
    db_service.insert_event(child)
    editor, _converter = editor_for(qtbot, child, [])
    assert not editor.has_unsaved_temporal_changes()
    editor.name_edit.setText("Renamed")
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    assert execute_timing(
        UpdateEventCommand(child.id, saved.args[0]), db_service
    ).success
    assert db_service.get_event(child.id).lore_date == child.lore_date
    assert "_temporal_v2" not in db_service.get_event(child.id).attributes


@pytest.mark.parametrize("edit_during_save", [False, True])
def test_accepted_follow_save_advances_baseline_and_preserves_newer_edits(
    qtbot, db_service, prepare_timing_command, edit_during_save
):
    from src.app.coordinators.editor_coordinator import EditorCoordinator

    root = Event("March", 0, id="root")
    child = Event("Battle", 5, id="child")
    for event in (root, child):
        db_service.insert_event(event)
    editor, _converter = editor_for(qtbot, child, [root])
    parent = editor.parentWidget()
    parent.event_editor = editor
    parent.entity_editor = MagicMock()
    coordinator = EditorCoordinator(parent)
    coordinator.auto_create_relations = False
    editor.save_requested.connect(coordinator.update_event)
    outgoing = []
    coordinator.command_requested.connect(outgoing.append)
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(source.mode.findData("event"))
    source.events.setCurrentIndex(source.events.findData("event:root"))
    source.options.offset.setValue(3)
    editor.autosave_manager.stop_timer()
    editor._on_save()
    first = outgoing[-1]
    result = prepare_timing_command(first).execute(db_service)
    assert result.success
    if edit_during_save:
        source.options.offset.setValue(4)
    result.data["command_id"] = first.command_id
    coordinator.on_temporal_command_result(result)
    persisted = db_service.get_event(child.id)
    assert (
        editor.temporal_widget._loaded_definition
        == EventTimingDefinition.from_event(persisted)
    )
    assert source.options.offset.value() == (4 if edit_during_save else 3)
    assert editor.has_unsaved_changes() == edit_during_save
    editor.name_edit.setText("Next save")
    editor.autosave_manager.stop_timer()
    editor._on_save()
    second = outgoing[-1]
    assert second is not first
    result = prepare_timing_command(second).execute(db_service)
    assert result.success
    persisted = db_service.get_event(child.id)
    assert persisted.start_follows_event
    assert persisted.lore_date == (4 if edit_during_save else 3)


def test_prose_save_after_source_moves_keeps_binding_and_projection(
    qtbot, db_service, prepare_timing_command
):
    from src.cli.event_timing import execute_timing

    root = Event("March", 10, id="root")
    child = Event(
        "Battle",
        12,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 2}
            )
        ).apply({}),
    )
    for event in (root, child):
        db_service.insert_event(event)
    editor, converter = editor_for(qtbot, child, [root])
    move = prepare_timing_command(UpdateEventCommand(root.id, {"lore_date": 20}))
    assert move.execute(db_service).success
    editor.set_temporal_context(
        TemporalResolutionContext.build(db_service.get_all_events(), converter, 2)
    )
    assert not editor.has_unsaved_temporal_changes()
    editor.name_edit.setText("Renamed battle")
    editor.autosave_manager.stop_timer()
    with qtbot.waitSignal(editor.save_requested) as saved:
        editor._on_save()
    assert execute_timing(
        UpdateEventCommand(child.id, saved.args[0]), db_service
    ).success
    persisted = db_service.get_event(child.id)
    assert persisted.start_follows_event
    assert persisted.lore_date == 22


def test_unchanged_timing_refresh_preserves_date_selection(qtbot):
    from dataclasses import replace

    child = Event("Battle", 6.810985159629813, id="child")
    editor, converter = editor_for(qtbot, child, [])
    field = editor.temporal_widget.date_start.txt_date
    field.setSelection(1, 3)
    selected, caret = field.selectedText(), field.cursorPosition()
    editor.set_temporal_context(
        TemporalResolutionContext.build(
            [replace(child, name="New label")], converter, 2
        )
    )
    assert field.selectedText() == selected
    assert field.cursorPosition() == caret
    assert not editor.has_unsaved_temporal_changes()


def test_context_refresh_retains_uncommitted_date_text(qtbot):
    from dataclasses import replace

    child = Event("Battle", 6, id="child")
    editor, converter = editor_for(qtbot, child, [])
    field = editor.temporal_widget.date_start.txt_date
    field.setText("an unfinished date")
    field.textEdited.emit(field.text())
    editor.autosave_manager.stop_timer()
    editor.set_temporal_context(
        TemporalResolutionContext.build([replace(child, lore_date=9)], converter, 2)
    )
    assert field.text() == "an unfinished date"
    assert (
        editor.temporal_widget._loaded_definition
        == EventTimingDefinition.from_event(child)
    )


def test_discard_reloads_saved_timing_after_a_real_conflict(qtbot):
    from dataclasses import replace
    from types import SimpleNamespace

    from src.app.coordinators.data_coordinator import DataCoordinator

    root = Event("March", 0, id="root")
    child = Event("Battle", 6, id="child")
    editor, converter = editor_for(qtbot, child, [root])
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(source.mode.findData("event"))
    source.events.setCurrentIndex(source.events.findData("event:root"))
    source.options.offset.setValue(2)
    current = replace(child, lore_date=9)
    editor.set_temporal_context(
        TemporalResolutionContext.build([current, root], converter, 2)
    )
    parent = editor.parentWidget()
    parent.event_editor = editor
    parent.navigation_coordinator = SimpleNamespace(
        selected_type="event", selected_id=child.id
    )
    parent.map_widget = SimpleNamespace(maps_data=[])
    data = DataCoordinator(parent)
    editor.discard_requested.connect(
        lambda identity: data.on_event_details_ready(current, [], [])
    )
    editor.autosave_manager.stop_timer()
    editor._on_discard()
    assert not editor.has_unsaved_changes()
    assert editor.temporal_widget.source_start.mode.currentData() == "manual"
    assert (
        editor.temporal_widget._loaded_definition
        == EventTimingDefinition.from_event(current)
    )


@pytest.mark.parametrize("apply", [True, False])
def test_follow_save_with_real_review_finishes_editor_delivery(
    qtbot, qapp, db_service, monkeypatch, apply
):
    from PySide6.QtCore import QTimer

    from src.app.coordinators.editor_coordinator import EditorCoordinator
    from src.gui.dialogs.event_timing_review_dialog import EventTimingReviewDialog

    anchor = Event("Treaty", 20, id="anchor")
    root = Event("March", 10, id="root")
    child = Event(
        "Battle",
        12,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 2}
            )
        ).apply({}),
    )
    for event in (anchor, root, child):
        db_service.insert_event(event)
    editor, _converter = editor_for(qtbot, root, [anchor, child])
    parent = editor.parentWidget()
    parent.event_editor = editor
    parent.entity_editor = MagicMock()
    editing = EditorCoordinator(parent)
    editing.auto_create_relations = False
    completed = []

    def execute(command):
        result = command.execute(db_service)
        result.data["command_id"] = command.command_id
        completed.append(result)
        editing.on_temporal_command_result(result)

    timing = EventTimingCoordinator(
        parent, qapp.thread(), lambda: db_service, lambda: db_service.db_path, execute
    )
    timing.failed.connect(editing.on_temporal_command_result)
    editing.command_requested.connect(timing.intercept)
    editor.save_requested.connect(editing.update_event)
    native_exec = EventTimingReviewDialog.exec

    def review(dialog):
        QTimer.singleShot(
            350,
            dialog,
            dialog.apply_button.click if apply else dialog.cancel_button.click,
        )
        return native_exec(dialog)

    monkeypatch.setattr(EventTimingReviewDialog, "exec", review)
    source = editor.temporal_widget.source_start
    source.mode.setCurrentIndex(source.mode.findData("event"))
    source.events.setCurrentIndex(source.events.findData("event:anchor"))
    editor.autosave_manager.stop_timer()
    try:
        editor._on_save()
        assert editor.save_pending
        qtbot.waitUntil(lambda: not editor.save_pending, timeout=5000)
        assert timing._job == ""
        if apply:
            assert completed[0].success
            assert editor.save_status.text() == "Saved"
            assert db_service.get_event(root.id).start_follows_event
            assert db_service.get_event(child.id).lore_date == 22
        else:
            assert not completed
            assert editor.save_status.text() == "Unsaved changes"
            assert source.mode.currentData() == "event"
            assert editor.has_unsaved_changes()
            assert db_service.get_event(root.id).lore_date == 10
    finally:
        timing.shutdown()
