"""Precision survives the real editor intent, command, database and undo paths."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import expression_from_attributes
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.event_editor import EventEditorWidget

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("text", ["961", "January 961", "c. 961", "961?"])
def test_editor_save_reload_export_and_undo(qtbot, db_service, text):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    event = Event(name="Execution", lore_date=12.5)
    db_service.insert_event(event)
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = EventEditorWidget(parent=parent)
    qtbot.addWidget(editor)
    editor.set_calendar_converter(converter)
    editor.load_event(event)
    date = editor.temporal_widget.date_start
    date.txt_date.setText(text)
    date._on_draft_edited(text)
    with qtbot.waitSignal(editor.save_requested) as signal:
        editor._on_save()
    command = UpdateEventCommand(event.id, signal.args[0])
    assert command.execute(db_service).success
    saved = db_service.get_event(event.id)
    assert saved.lore_duration == 0
    exported = Event.from_dict(saved.to_dict())
    reopened = EventEditorWidget(parent=parent)
    qtbot.addWidget(reopened)
    reopened.set_calendar_converter(converter)
    reopened.load_event(exported)
    assert reopened.temporal_widget.date_start.txt_date.text() == text
    assert reopened.temporal_widget.date_start.combo_day.currentIndex() == -1
    command.undo(db_service)
    original = db_service.get_event(event.id)
    assert original.lore_date == 12.5
    assert expression_from_attributes(original.attributes) is None


def test_structured_year_edit_keeps_unspecified_components(qtbot):
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    date = CompactDateWidget(text_first=True)
    qtbot.addWidget(date)
    date.set_calendar_converter(CalendarConverter(config))
    date.set_expression(DateParser(config).parse_expression("961"))
    date.spin_year.setValue(962)
    expression = date.get_expression()
    assert expression.year == 962
    assert expression.month is None and expression.day is None
    assert date.txt_date.text() == "962"


def test_drag_preserves_year_and_undo(db_service):
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    expression = DateParser(config).parse_expression("961")
    event = Event(
        name="Execution",
        lore_date=0,
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    db_service.insert_event(event)
    command = UpdateEventCommand(
        event.id, {"lore_date": converter.start_of_year(964) + 50}
    )
    assert command.execute(db_service).success
    moved = db_service.get_event(event.id)
    assertion = expression_from_attributes(moved.attributes)
    assert assertion.year == 964 and assertion.month is None and assertion.day is None
    assert moved.lore_date == assertion.representative_time(converter)
    command.undo(db_service)
    assert (
        expression_from_attributes(
            db_service.get_event(event.id).attributes
        ).original_text
        == "961"
    )


@pytest.mark.parametrize("duration", [False, True])
def test_range_meaning_survives_editor_save(qtbot, db_service, monkeypatch, duration):
    from PySide6.QtWidgets import QInputDialog

    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    event = Event(name="A reign", lore_date=0)
    db_service.insert_event(event)
    editor = EventEditorWidget(parent=parent)
    qtbot.addWidget(editor)
    editor.set_calendar_converter(CalendarConverter(config))
    editor.load_event(event)
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *args: (args[3][int(duration)], True)
    )
    date = editor.temporal_widget.date_start
    date.txt_date.setText("961-964")
    date._on_draft_edited("961-964")
    with qtbot.waitSignal(editor.save_requested) as signal:
        editor._on_save()
    command = UpdateEventCommand(event.id, signal.args[0])
    assert command.execute(db_service).success
    saved = db_service.get_event(event.id)
    metadata = saved.attributes["_temporal_v2"]
    assert (saved.lore_duration > 0) == duration
    assert ("end_expression" in metadata) == duration
    editor.load_event(saved)
    if duration:
        assert editor.temporal_widget.date_end.get_expression().year == 964
        move = UpdateEventCommand(
            event.id, {"lore_date": CalendarConverter(config).start_of_year(970)}
        )
        assert move.execute(db_service).success
        assert (
            db_service.get_event(event.id).attributes["_temporal_v2"]["end_expression"][
                "year"
            ]
            == 973
        )
    else:
        assert (
            expression_from_attributes(saved.attributes).explicit_outer_end is not None
        )
