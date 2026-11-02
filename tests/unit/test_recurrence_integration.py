"""Verify ordinary Event persistence, date drafts and compact marker projection."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.commands.event_commands import CreateEventCommand, UpdateEventCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.recurrence import RECURRENCE_ATTRIBUTE, RecurrenceRule
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.timeline import TimelineWidget
from src.services.event_recurrence_service import validate_recurrence_change
from src.services.recurrence_presentation_service import project_recurrence

pytestmark = pytest.mark.ci_fast


def series(frequency="days", **settings):
    return Event(
        "Festival",
        0.0,
        description="A three-day celebration.",
        attributes={
            RECURRENCE_ATTRIBUTE: RecurrenceRule(
                frequency=frequency, **settings
            ).to_dict()
        },
    )


@pytest.fixture
def editor(qtbot, monkeypatch):
    from src.gui.widgets.gallery_widget import GalleryWidget

    monkeypatch.setattr(GalleryWidget, "set_owner", lambda *_args: None)
    widget = EventEditorWidget()
    qtbot.addWidget(widget)
    return widget


def test_command_roundtrip_undo_and_content_preservation(db_service):
    event = series(interval=40, direction="both")
    command = CreateEventCommand(event.to_dict())
    assert command.execute(db_service).success
    assert len(db_service.get_all_events()) == 1
    update = UpdateEventCommand(
        event.id,
        {
            "description": "Updated prose",
            "attributes": {"new": 2},
            "__preserve_timing": True,
        },
    )
    assert update.execute(db_service).success
    saved = db_service.get_event(event.id)
    assert (
        saved.attributes[RECURRENCE_ATTRIBUTE] == event.attributes[RECURRENCE_ATTRIBUTE]
    )
    replay = UpdateEventCommand.from_dict(update.to_dict())
    assert replay.update_data == update.update_data
    update.undo(db_service)
    assert db_service.get_event(event.id).description == event.description
    assert update.execute(db_service).success
    assert len(db_service.get_all_events()) == 1


def test_invalid_schedule_is_atomic_and_unknown_version_survives_prose(db_service):
    event = series()
    db_service.insert_event(event)
    invalid = deepcopy(event.attributes)
    invalid[RECURRENCE_ATTRIBUTE]["interval"] = 0
    result = UpdateEventCommand(
        event.id, {"name": "Changed", "attributes": invalid}
    ).execute(db_service)
    assert not result.success
    assert db_service.get_event(event.id).to_dict() == event.to_dict()
    event.attributes[RECURRENCE_ATTRIBUTE] = {"schema": 500, "future": {"rule": 4}}
    db_service.insert_event(event)
    assert (
        UpdateEventCommand(event.id, {"description": "Still editable"})
        .execute(db_service)
        .success
    )
    assert db_service.get_event(event.id).attributes == event.attributes


def test_unresolved_calendar_does_not_block_unrelated_content():
    event = series("years", calendar_id="missing")
    validate_recurrence_change(event, replace(event, description="changed"), None)
    with pytest.raises(ValueError, match="calendar"):
        validate_recurrence_change(None, event, None)


def test_editor_autosave_does_not_apply_schedule(editor):
    editor.load_event(series(interval=40))
    editor.recurrence_widget.interval.setValue(80)
    assert editor.has_unsaved_temporal_changes()
    assert editor.btn_save.isEnabled()
    editor.desc_edit.set_wiki_text("New description")
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_autosave()
    assert requests[-1]["__preserve_timing"]
    assert RECURRENCE_ATTRIBUTE not in requests[-1].get("attributes", {})
    editor.finish_save(requests[-1]["__editor_revision"], True)
    assert editor.recurrence_widget.interval.value() == 80
    assert editor.has_unsaved_temporal_changes()
    assert editor.has_unsaved_changes()
    editor._on_save()
    assert requests[-1]["attributes"][RECURRENCE_ATTRIBUTE]["interval"] == 80


def test_recurrence_ack_keeps_newer_draft(editor):
    event = series(interval=40)
    editor.load_event(event)
    editor.recurrence_widget.interval.setValue(80)
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_save()
    editor.recurrence_widget.interval.setValue(120)
    snapshot = {**event.to_dict(), **requests[-1]}
    editor.mark_temporal_saved(snapshot)
    editor.finish_save(requests[-1]["__editor_revision"], True)
    assert editor.recurrence_widget.interval.value() == 120
    assert editor.has_unsaved_temporal_changes()


def test_disable_keeps_authored_date(editor):
    editor.load_event(series())
    editor.recurrence_widget.enabled.setChecked(False)
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_save()
    assert RECURRENCE_ATTRIBUTE not in requests[-1]["attributes"]
    assert requests[-1]["lore_date"] == 0


def test_same_event_hydration_keeps_recurrence_draft_and_discard_restores(editor):
    event = series(interval=40)
    editor.load_event(event)
    editor.recurrence_widget.interval.setValue(80)
    editor.load_event(event)
    assert editor.recurrence_widget.interval.value() == 80
    editor.discard_requested.connect(lambda _identity: editor.load_event(event))
    editor._on_discard()
    assert editor.recurrence_widget.interval.value() == 40
    assert not editor.has_unsaved_temporal_changes()


def test_annual_semantic_zoom_and_unresolved_projection():
    converter = CalendarConverter(CalendarConfig.create_default())
    event = series("years", calendar_id=converter._config.id)
    assert project_recurrence(event, converter, 0, 1000, 365).occurrences
    assert not project_recurrence(event, converter, 0, 1000, 3650).occurrences
    assert project_recurrence(event, None, 0, 1000, 365).error


def test_strip_only_and_incremental_toggle(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 400)
    widget.show()
    recurring, riot = series(interval=40, direction="both"), Event("Riot", 4)
    widget.set_events([recurring, riot])
    assert [e.id for e in widget.view.events] == [riot.id]
    assert recurring.id not in widget.view._event_items
    widget.view.recurrence_strip.refresh()
    assert widget.view.recurrence_strip.projections[0].occurrences
    ordinary = replace(recurring, attributes={})
    widget.apply_event_effects(
        [
            {
                "object_type": "event",
                "operation": "upsert",
                "object_id": ordinary.id,
                "snapshot": ordinary.to_dict(),
                "relations_changed": False,
            }
        ]
    )
    assert ordinary.id in widget.view._event_items
    assert not widget.view._recurring_events


def test_strip_clusters_select_source_without_mutating_time(qtbot):
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(800, 400)
    widget.show()
    event = series(interval=1)
    widget.set_events([event])
    widget.view._apply_zoom(4)
    widget.view.center_on_date(0)
    strip = widget.view.recurrence_strip
    strip.refresh()
    assert strip._buttons
    strip.set_selected_event(None)
    assert not any(button.isChecked() for button in strip._buttons)
    before = widget.view.get_playhead_time()
    selected = []
    widget.event_selected.connect(selected.append)
    strip._select(event.id, strip._generation)
    assert selected == [event.id]
    selected.clear()
    strip._buttons[0].click()
    menu = strip._menus[-1]
    from PySide6.QtCore import Qt

    qtbot.keyClick(menu, Qt.Key.Key_Down)
    qtbot.keyClick(menu, Qt.Key.Key_Return)
    assert selected == [event.id]
    assert widget.view.get_playhead_time() == before
    assert event.to_dict() == series(interval=1).to_dict() | {
        "id": event.id,
        "created_at": event.created_at,
        "modified_at": event.modified_at,
    }


def test_custom_week_and_variant_skip():
    from src.core.calendar import MonthDefinition, WeekDefinition, YearVariant
    from src.core.recurrence import occurrences_in_window

    config = CalendarConfig.create_default()
    config.week = WeekDefinition(["A", "B", "C"], ["A", "B", "C"])
    config.year_variants = [
        YearVariant(year=2, months=[MonthDefinition("Only", "O", 10)])
    ]
    converter = CalendarConverter(config)
    anchor = converter.start_of_day(1, 2, 12)
    event = replace(series("years", calendar_id=config.id), lore_date=anchor)
    page = occurrences_in_window(event, converter, anchor, converter.start_of_year(4))
    assert [converter.from_float(o.start).year for o in page.occurrences] == [1, 3]
    weekly = series("weeks", calendar_id=config.id, weekdays=(0, 2), direction="both")
    starts = [
        o.start for o in occurrences_in_window(weekly, converter, -4, 4).occurrences
    ]
    assert starts == [-4, -3, -1, 0, 2, 3]


def test_recurrence_calendar_context_export_and_explicit_import_mapping(db_service):
    from src.services.transfer_context import export_context, prepare_calendars

    target = CalendarConfig.create_default()
    target.is_active = True
    db_service.insert_calendar_config(target)
    event = series("years", calendar_id=target.id)
    context, warnings = export_context(db_service, {"events": [event.to_dict()]})
    assert [config["id"] for config in context["calendars"]] == [target.id]
    assert not warnings
    foreign = {**target.to_dict(), "id": "source-world-calendar"}
    incoming = event.to_dict()
    incoming["attributes"] = deepcopy(event.attributes)
    incoming["attributes"][RECURRENCE_ATTRIBUTE]["calendar_id"] = foreign["id"]
    payload = {"events": [incoming]}
    errors, warnings, _decisions = prepare_calendars(
        db_service,
        payload,
        {"calendars": [foreign]},
        {"calendar_mappings": {foreign["id"]: target.id}},
    )
    assert not errors and not warnings
    assert (
        payload["events"][0]["attributes"][RECURRENCE_ATTRIBUTE]["calendar_id"]
        == target.id
    )


def test_import_rejects_invalid_supported_rule_and_retains_future_schema():
    from unittest.mock import MagicMock

    from src.services.transfer_context import native_calendar_ids
    from src.services.transfer_validation import validate_record

    event = series().to_dict()
    event["attributes"][RECURRENCE_ATTRIBUTE]["interval"] = 0
    assert validate_record("events", event, MagicMock())
    event["attributes"][RECURRENCE_ATTRIBUTE] = {"schema": 500, "calendar_id": "opaque"}
    assert not validate_record("events", event, MagicMock())
    assert not native_calendar_ids(event["attributes"])


def test_stale_schedule_save_rejected_but_prose_can_preserve_current_rule(db_service):
    event = series(interval=40)
    db_service.insert_event(event)
    old = deepcopy(event.attributes[RECURRENCE_ATTRIBUTE])
    newer = replace(
        event,
        attributes={
            RECURRENCE_ATTRIBUTE: RecurrenceRule(
                frequency="days", interval=80
            ).to_dict()
        },
    )
    db_service.insert_event(newer)
    rejected = UpdateEventCommand(
        event.id,
        {
            "attributes": event.attributes,
            "__expected_recurrence": old,
        },
    ).execute(db_service)
    assert not rejected.success and "changed" in rejected.message
    prose = UpdateEventCommand(
        event.id,
        {
            "description": "Independent writing",
            "attributes": event.attributes,
            "__preserve_timing": True,
        },
    ).execute(db_service)
    assert prose.success
    assert (
        db_service.get_event(event.id).attributes[RECURRENCE_ATTRIBUTE]["interval"]
        == 80
    )


def test_typed_bounds_include_the_whole_authored_day_and_survive_other_edits(editor):
    from src.core.temporal_expression import TemporalExpression

    converter = CalendarConverter(CalendarConfig.create_default())
    editor.set_calendar_converter(converter)
    event = replace(series(interval=1), lore_date=0.75)
    editor.load_event(event)
    widget = editor.recurrence_widget
    for key in ("earliest", "latest"):
        check, date = widget.bounds[key]
        check.setChecked(True)
        date.set_expression(
            TemporalExpression(calendar_id=converter._config.id, year=1, month=1, day=1)
        )
    data = widget.metadata()
    assert data["earliest"] == 0
    assert 0.99 < data["latest"] < 1
    saved = replace(event, attributes={RECURRENCE_ATTRIBUTE: data})
    widget.load_event(saved)
    widget.interval.setValue(2)
    assert widget.metadata()["latest"] == data["latest"]


def test_correcting_invalid_bound_keeps_save_available(editor):
    from src.core.temporal_expression import TemporalExpression, TemporalPrecision

    converter = CalendarConverter(CalendarConfig.create_default())
    editor.set_calendar_converter(converter)
    editor.load_event(series())
    check, date = editor.recurrence_widget.bounds["earliest"]
    check.setChecked(True)
    date.set_expression(
        TemporalExpression(
            calendar_id=converter._config.id, year=1, precision=TemporalPrecision.YEAR
        )
    )
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_save()
    assert not requests and editor.btn_save.isEnabled()
    date.set_expression(
        TemporalExpression(calendar_id=converter._config.id, year=1, month=1, day=1)
    )
    date.value_changed.emit(date.get_value())
    editor._on_save()
    assert len(requests) == 1
