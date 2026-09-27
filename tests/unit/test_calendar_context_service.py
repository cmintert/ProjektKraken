"""Calendar identity must survive the default-calendar startup and save path."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.app.coordinators.time_coordinator import TimeCoordinator
from src.commands.event_commands import UpdateEventCommand
from src.core.calendar import CalendarConfig
from src.core.events import Event
from src.gui.widgets.event_editor import EventEditorWidget
from src.services.calendar_context_service import ensure_active_calendar
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


def test_default_calendar_identity_is_persisted_and_reused(db_service):
    assert db_service.get_active_calendar_config() is None
    first = ensure_active_calendar(db_service)
    assert first.is_active
    assert db_service.get_calendar_config(first.id).to_dict() == first.to_dict()
    assert ensure_active_calendar(db_service).id == first.id
    assert len(db_service.get_all_calendar_configs()) == 1


def test_existing_custom_calendar_is_not_replaced(db_service):
    custom = CalendarConfig.create_default()
    custom.name = "Tytalus calendar"
    custom.months[0].days = 40
    custom.is_active = True
    db_service.insert_calendar_config(custom)
    loaded = ensure_active_calendar(db_service)
    assert loaded.id == custom.id
    assert loaded.months[0].days == 40
    assert len(db_service.get_all_calendar_configs()) == 1


def test_failed_calendar_write_does_not_publish_temporary_config(qtbot):
    worker = DatabaseWorker(":memory:")
    worker.db_service = MagicMock()
    worker.db_service.get_active_calendar_config.return_value = None
    worker.db_service.insert_calendar_config.side_effect = RuntimeError("Write failed")
    with qtbot.waitSignal(worker.calendar_config_loaded) as loaded:
        with qtbot.waitSignal(worker.error_occurred) as error:
            worker.load_calendar_config()
    assert loaded.args == [None]
    assert "Write failed" in error.args[0]


@pytest.mark.parametrize("text", ["961", "January 961", "c. 961"])
def test_startup_calendar_to_editor_to_serialized_save(qtbot, db_service, text):
    """Exercise the previously missing no-calendar world path with real widgets."""
    assert db_service.get_active_calendar_config() is None
    window = QWidget()
    qtbot.addWidget(window)
    worker = DatabaseWorker(":memory:", {"UpdateEventCommand": UpdateEventCommand})
    worker.db_service = db_service
    window.worker = worker
    window.calendar_converter = None
    for name in (
        "timeline",
        "map_widget",
        "unified_list",
        "longform_editor",
        "ui_manager",
        "lbl_world_time",
        "lbl_playhead_time",
    ):
        setattr(window, name, MagicMock())
    window.timeline.get_current_time.return_value = 0.0
    window.timeline.get_playhead_time.return_value = 0.0
    window.event_editor = EventEditorWidget(parent=window)
    window.time_coordinator = TimeCoordinator(window)
    worker.calendar_config_loaded.connect(
        window.time_coordinator.on_calendar_config_loaded,
        Qt.ConnectionType.QueuedConnection,
    )
    worker.load_calendar_config()
    qtbot.waitUntil(lambda: window.calendar_converter is not None)
    config = db_service.get_active_calendar_config()
    assert config.id == window.calendar_converter._config.id

    event = Event(name="Kalliste becomes Prima of House Tytalus", lore_date=12.5)
    db_service.insert_event(event)
    editor = window.event_editor
    editor.load_event(event)
    date = editor.temporal_widget.date_start
    date.txt_date.setText(text)
    date._on_draft_edited(text)
    with qtbot.waitSignal(editor.save_requested) as intent:
        editor._on_save()
    command = UpdateEventCommand(event.id, intent.args[0])
    with qtbot.waitSignal(worker.command_finished) as finished:
        worker.run_command(
            {
                "type": "UpdateEventCommand",
                "data": command.to_dict(),
                "base": command.base_state_dict(),
            }
        )
    assert finished.args[0].success, finished.args[0].message
    saved = db_service.get_event(event.id)
    assert saved.attributes["_temporal_v2"]["expression"]["calendar_id"] == config.id
    assert saved.attributes["_temporal_v2"]["expression"]["original_text"] == text
    with qtbot.waitSignal(worker.calendar_config_loaded) as reload:
        worker.load_calendar_config()
    assert reload.args[0].id == config.id
    reopened = EventEditorWidget(parent=window)
    reopened.set_calendar_converter(window.calendar_converter)
    reopened.load_event(saved)
    assert reopened.temporal_widget.date_start.txt_date.text() == text
