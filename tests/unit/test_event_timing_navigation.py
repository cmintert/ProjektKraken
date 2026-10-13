"""KRT-78 menu selection and date persistence feedback regressions."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.app.coordinators.time_coordinator import TimeCoordinator
from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.events import Event
from src.core.temporal_expression import (
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
)
from src.gui.dialogs.relation_dialog import RelationEditDialog
from src.gui.widgets.event_editor import EventEditorWidget
from src.gui.widgets.timeline import TimelineWidget


@pytest.fixture
def timing_editor(qtbot, init_theme_manager):
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = EventEditorWidget(parent)
    qtbot.addWidget(editor)
    editor.autosave_manager.set_enabled(False)
    editor.load_event(Event(id="event", name="Event", lore_date=18.0))
    return editor


@pytest.mark.parametrize("date", [0.0, -42.25, 433177.5])
def test_selected_navigation_revalidates_global_target(qtbot, date):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    event = Event(id="event", name="Saved name", lore_date=date)
    window = QWidget()
    qtbot.addWidget(window)
    window.timeline = timeline
    window.calendar_converter = None
    window.navigation_coordinator = SimpleNamespace(
        selected_type="event", selected_id=event.id
    )
    window.data_coordinator = MagicMock()
    window.event_editor = MagicMock()
    window.data_coordinator.cached_events = [event]
    window.event_editor.current_event_id = "different inspector"
    coordinator = TimeCoordinator(window)
    coordinator.go_to_date = MagicMock()
    coordinator.refresh_selected_event_navigation()
    assert timeline.btn_go_to_date.isEnabled()
    assert not timeline.enter_date_action.isEnabled()
    assert "Saved name" in timeline.selected_event_date_action.toolTip()
    assert [action.text() for action in timeline.date_navigation_menu.actions()] == [
        "Go to selected event",
        "Enter a date…",
    ]
    timeline.selected_event_date_requested.connect(coordinator.go_to_selected_event)
    timeline.selected_event_date_action.trigger()
    assert coordinator.go_to_date.call_args.args[0] == date
    coordinator.go_to_date.reset_mock()
    window.navigation_coordinator.selected_type = "entity"
    timeline.selected_event_date_action.trigger()
    coordinator.go_to_date.assert_not_called()
    coordinator.refresh_selected_event_navigation()
    assert not timeline.selected_event_date_action.isEnabled()
    window.navigation_coordinator.selected_type = "event"
    window.data_coordinator.cached_events = []
    coordinator.go_to_selected_event(event.id)
    coordinator.go_to_date.assert_not_called()


def test_date_menu_survives_overflow(qtbot):
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.set_selected_event_navigation("event", "Saved event: 18 January 1187")
    timeline.resize(240, 300)
    timeline.show()
    qtbot.waitUntil(
        lambda: timeline.btn_go_to_date in timeline.action_toolbar.overflowed_buttons()
    )
    parent_action = next(
        action
        for action in timeline.action_toolbar.overflow_menu.actions()
        if action.text() == "Go to date"
    )
    assert parent_action.menu() is timeline.date_navigation_menu
    with qtbot.waitSignal(timeline.selected_event_date_requested) as signal:
        parent_action.menu().actions()[0].trigger()
    assert signal.args == ["event"]


def test_save_feedback_preserves_newer_text_and_caret(timing_editor):
    editor = timing_editor
    editor.name_edit.setText("First revision")
    assert editor.save_status.text() == "Unsaved changes"
    first = editor.begin_save()
    assert editor.save_status.text() == "Saving…"
    editor.name_edit.setText("Newer revision")
    editor.name_edit.setSelection(2, 4)
    cursor = editor.name_edit.cursorPosition()
    selection = editor.name_edit.selectedText()
    assert not editor.finish_save(first, True)
    assert editor.save_status.text() == "Unsaved changes"
    assert editor.name_edit.text() == "Newer revision"
    assert editor.name_edit.cursorPosition() == cursor
    assert editor.name_edit.selectedText() == selection
    second = editor.begin_save()
    assert not editor.finish_save(first, False)
    assert editor.save_status.text() == "Saving…"
    assert not editor.finish_save(second, False)
    assert editor.save_status.text() == "Save failed — changes retained"
    third = editor.begin_save()
    assert editor.finish_save(third, True)
    assert editor.save_status.text() == "Saved"


def test_fixed_relation_uses_saved_january_playhead(timing_editor, qtbot, db_service):
    """Saved-date navigation supplies the exact fixed relation boundary."""
    from src.commands.relation_commands import AddRelationCommand
    from src.core.entities import Entity

    converter = CalendarConverter(CalendarConfig.create_default())
    source = Entity(name="Magus", type="Character")
    target = Entity(name="Tribunal", type="Organisation")
    db_service.insert_entity(source)
    db_service.insert_entity(target)
    event = Event(id="session", name="Session", lore_date=433177.5)
    db_service.insert_event(event)
    window = timing_editor.parent()
    window.timeline = MagicMock()
    window.calendar_converter = converter
    window.data_coordinator = SimpleNamespace(cached_events=[event])
    window.navigation_coordinator = SimpleNamespace(
        selected_type="event", selected_id=event.id
    )
    coordinator = TimeCoordinator(window)
    coordinator.go_to_date = MagicMock()
    coordinator.go_to_selected_event(event.id)
    playhead = coordinator.go_to_date.call_args.args[0]
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.set_events([event])
    timeline.view.set_playhead_event_snapping(True)
    assert (
        timeline.view._manual_playhead_time(playhead * timeline.view.scale_factor + 2.0)
        == playhead
    )
    dialog = RelationEditDialog(calendar_converter=converter, playhead_time=playhead)
    qtbot.addWidget(dialog)
    dialog.starts_now_button.click()
    attrs = dialog.get_data()[3]
    assert attrs["temporal"]["start"] == {"exact": 433177.5}
    assert (
        AddRelationCommand(source.id, target.id, "member_of", attrs)
        .execute(db_service)
        .success
    )
    persisted = db_service.get_relations(source.id)[0]
    assert persisted["attributes"]["temporal"]["start"] == {"exact": playhead}


def test_invalid_date_never_requests_save(timing_editor, qtbot):
    editor = timing_editor
    editor.set_calendar_converter(CalendarConverter(CalendarConfig.create_default()))
    field = editor.temporal_widget.date_start.txt_date
    field.setText("half typed invalid date")
    field.textEdited.emit(field.text())
    requests = []
    editor.save_requested.connect(requests.append)
    editor._on_save()
    assert not requests
    assert editor.save_status.text() == "Unsaved changes"
    assert not editor.save_pending
    qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert editor.save_status.text() == "Saved"


def test_save_acknowledgement_retains_pending_date_caret(timing_editor):
    editor = timing_editor
    editor.set_calendar_converter(CalendarConverter(CalendarConfig.create_default()))
    editor.name_edit.setText("Revision being saved")
    revision = editor.begin_save()
    field = editor.temporal_widget.date_start.txt_date
    field.setText("1 January 11")
    field.textEdited.emit(field.text())
    field.setSelection(2, 7)
    cursor, selection = field.cursorPosition(), field.selectedText()
    assert not editor.finish_save(revision, True)
    assert field.text() == "1 January 11"
    assert field.cursorPosition() == cursor
    assert field.selectedText() == selection
    assert editor.temporal_widget.has_pending_draft()
    assert editor.save_status.text() == "Unsaved changes"


def test_hydration_rejects_old_save_feedback(timing_editor):
    editor = timing_editor
    editor.name_edit.setText("Pending")
    revision = editor.begin_save()
    editor.load_event(Event(id="other", name="Other", lore_date=0.0))
    assert not editor.finish_save(revision, False)
    assert editor.save_status.text() == "Saved"


@pytest.mark.parametrize("acceptance", ["enter", "blur", "autosave", "calendar"])
def test_january_entry_survives_command_and_reopening(
    timing_editor, qtbot, db_service, acceptance, monkeypatch
):
    """Reproduce the recorded suffix edit, then enter the requested full date."""
    editor = timing_editor
    config = CalendarConfig.create_default()
    db_service.insert_calendar_config(config)
    db_service.set_active_calendar_config(config.id)
    converter = CalendarConverter(config)
    editor.set_calendar_converter(converter)
    initial = converter.to_float(CalendarDate(year=1228, month=1, day=18))
    event = Event(id="event", name="Tribunal Session", lore_date=initial)
    db_service.insert_event(event)
    editor.load_event(event)
    field = editor.temporal_widget.date_start.txt_date
    field.setText("18 January 1187")
    field.textEdited.emit(field.text())
    assert editor.temporal_widget.commit_drafts()
    assert converter.from_float(editor.temporal_widget.get_start()).day == 18
    field.setText("1 January 1187")
    field.textEdited.emit(field.text())
    assert editor.save_status.text() == "Unsaved changes"
    if acceptance == "calendar":
        popup = MagicMock()
        popup.exec.return_value = True
        popup.get_selected_date.return_value = (1187, 1, 1)
        monkeypatch.setattr(
            "src.gui.widgets.compact_date_widget.CalendarPopup",
            lambda *_args, **_kwargs: popup,
        )
        editor.temporal_widget.date_start._open_calendar_popup()
    elif acceptance == "enter":
        qtbot.keyClick(field, Qt.Key.Key_Return)
    else:
        field.editingFinished.emit()
    requested = []
    editor.save_requested.connect(requested.append)
    if acceptance == "autosave":
        editor.autosave_manager._perform_autosave()
    else:
        editor._on_save()
    assert len(requested) == 1
    payload = requested[0]
    target = converter.from_float(payload["lore_date"])
    assert (target.year, target.month, target.day) == (1187, 1, 1)
    assert "1 January 1187" in field.text()
    assert editor.save_status.text() == "Saving…"
    changes = {k: v for k, v in payload.items() if not k.startswith("__")}
    assert UpdateEventCommand(event.id, changes).execute(db_service).success
    assert editor.finish_save(payload["__editor_revision"], True)
    persisted = db_service.get_event(event.id)
    assert persisted.lore_date == payload["lore_date"]
    editor.load_event(None)
    editor.load_event(persisted)
    assert "1 January 1187" in field.text()
    assert editor.save_status.text() == "Saved"


def test_structured_year_edit_preserves_day(timing_editor):
    """A year edit must not secretly reset other authored components."""
    converter = CalendarConverter(CalendarConfig.create_default())
    timing_editor.set_calendar_converter(converter)
    date = timing_editor.temporal_widget.date_start
    date.set_value(converter.to_float(CalendarDate(year=1228, month=1, day=18)))
    date.spin_year.setValue(1187)
    assert converter.from_float(date.get_value()).day == 18
    date.combo_day.setCurrentIndex(0)
    result = converter.from_float(date.get_value())
    assert (result.year, result.month, result.day) == (1187, 1, 1)


@pytest.mark.parametrize("initial_playhead", [0.0, 20.0])
def test_disputed_surrender_navigates_zero_anchor(
    timing_editor, qtbot, initial_playhead
):
    converter = CalendarConverter(CalendarConfig.create_default())
    expression = TemporalExpression(
        calendar_id=converter._config.id,
        year=1,
        month=1,
        precision=TemporalPrecision.MONTH,
        qualifier=TemporalQualifier.UNCERTAIN,
    )
    event = Event(
        id="disputed",
        name="03 - A disputed surrender report",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    assert event.lore_date == 0.0
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.set_calendar_converter(converter)
    timeline.set_events([event])
    timeline.set_current_time(100.0)
    window = timing_editor.parent()
    window.timeline = timeline
    window.calendar_converter = converter
    window.event_editor = timing_editor
    window.entity_editor = MagicMock()
    window.entity_editor.current_entity_id = None
    window.entity_editor.has_unsaved_changes.return_value = False
    window.data_coordinator = MagicMock()
    window.data_coordinator.cached_events = [event]
    window.navigation_coordinator = SimpleNamespace(
        selected_type="event", selected_id=event.id
    )
    coordinator = TimeCoordinator(window)
    timeline.playhead_time_changed.connect(coordinator.on_playhead_changed)
    timeline.selected_event_date_requested.connect(coordinator.go_to_selected_event)
    timeline.set_playhead_time(initial_playhead)
    coordinator.refresh_selected_event_navigation()
    timeline.selected_event_date_action.trigger()
    assert timeline.get_playhead_time() == 0.0
    assert timeline.get_current_time() == 100.0
    qtbot.waitUntil(lambda: "uncertain" in timeline.time_status.notice.text())
    assert timeline.view.time_indicators.context["event_id"] == event.id


@pytest.mark.parametrize("zoom", [0.5, 1.0, 2.0])
@pytest.mark.parametrize("precise", [False, True])
@pytest.mark.parametrize("duration", [0.0, 3.0])
def test_event_anchor_remains_selectable_under_playhead(qtbot, zoom, precise, duration):
    from src.gui.widgets.timeline.event_item import EventItem

    converter = CalendarConverter(CalendarConfig.create_default())
    expression = TemporalExpression(
        calendar_id=converter._config.id,
        year=1,
        month=1,
        day=1 if precise else None,
        hour=0 if precise else None,
        minute=0 if precise else None,
        precision=TemporalPrecision.MINUTE if precise else TemporalPrecision.MONTH,
        qualifier=TemporalQualifier.ASSERTED
        if precise
        else TemporalQualifier.UNCERTAIN,
    )
    event = Event(
        id="disputed",
        name="Disputed surrender",
        lore_date=0.0,
        lore_duration=duration,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    timeline = TimelineWidget()
    qtbot.addWidget(timeline)
    timeline.resize(700, 400)
    timeline.set_calendar_converter(converter)
    timeline.set_events([event])
    timeline.show()
    view = timeline.view
    qtbot.waitUntil(lambda: any(isinstance(i, EventItem) for i in view.items()))
    item = next(i for i in view.items() if isinstance(i, EventItem))
    view._apply_zoom(zoom)
    item.setY(200)
    view.centerOn(item.pos())
    pos = view.mapFromScene(item.pos())
    requests = []
    timeline.event_selected.connect(requests.append)
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert requests == [event.id]
    assert item.isSelected()
    assert not getattr(view, "_dragging_playhead", False)
    assert view._playhead.acceptedMouseButtons() != Qt.MouseButton.NoButton
    assert view.get_playhead_time() == 0.0
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert view.graphics_scene.mouseGrabberItem() is item
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    from PySide6.QtCore import QPoint

    line_pos = pos + QPoint(0, 50)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=line_pos)
    assert view._dragging_playhead
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=line_pos)
