"""Behavior and compact-layout acceptance checks for modern inspectors."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget


@pytest.fixture
def calendar():
    return CalendarConverter(
        CalendarConfig(
            id="test",
            name="Test",
            months=[MonthDefinition(name="Spring", abbreviation="Spr", days=30)],
            week=WeekDefinition(day_names=["Day"], day_abbreviations=["D"]),
            year_variants=[],
            epoch_name="Era",
        )
    )


@pytest.fixture
def event_editor(qtbot, calendar):
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = EventEditorWidget(parent)
    editor.temporal_widget.set_calendar_converter(calendar)
    editor.load_event(Event(id="event", name="Arrival", lore_date=0.0))
    qtbot.addWidget(editor)
    return editor


def test_invalid_date_draft_blocks_save_and_survives_reload(event_editor, qtbot):
    editor = event_editor
    field = editor.date_edit.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "not a date")
    saved = []
    editor.save_requested.connect(saved.append)
    assert editor.has_unsaved_changes()
    assert not editor.autosave_manager._autosave_timer.isActive()
    editor._on_save()
    assert saved == []
    assert "not recognized" in editor.date_edit.feedback.text()
    editor.load_event(Event(id="event", name="Arrival", lore_date=4.0))
    assert field.text() == "not a date"
    qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert not editor.temporal_widget.has_pending_draft()
    assert editor.temporal_widget.get_start() == 0.0
    assert not editor.has_unsaved_changes()


def test_editable_combo_inner_editor_uses_parent_styling(event_editor):
    """Avoid restyling the private line edit and shifting its text baseline."""
    inner_editor = event_editor.type_edit.lineEdit()

    assert inner_editor is not None
    assert inner_editor.styleSheet() == ""
    assert inner_editor.minimumHeight() < event_editor.type_edit.minimumHeight()


def test_cancel_date_preserves_other_edits(event_editor, qtbot):
    editor = event_editor
    field = editor.date_edit.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "invalid")
    editor.name_edit.setText("A new name")
    qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert editor.has_unsaved_changes()
    assert editor.name_edit.text() == "A new name"
    assert editor.autosave_manager._autosave_timer.isActive()


def test_formatted_date_round_trips(event_editor):
    field = event_editor.date_edit
    field._on_draft_edited(field.txt_date.text())
    assert field.commit_draft()
    assert field.get_value() == 0.0


def test_end_date_edit_is_saved(event_editor, qtbot):
    field = event_editor.end_date_edit.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "10 Spring 1")
    qtbot.keyClick(field, Qt.Key.Key_Return)
    assert event_editor.has_unsaved_changes()
    assert event_editor.temporal_widget.get_duration() == 9.0


def test_range_disclosure_survives_same_event_reload(event_editor):
    editor = event_editor
    event = Event(id="event", name="Arrival", lore_date=0.0, lore_duration=5.0)
    editor.load_event(event)
    editor.temporal_widget.range_button.setChecked(False)
    editor.load_event(event)
    assert not editor.temporal_widget.range_button.isChecked()
    assert editor.temporal_widget.get_duration() == 5.0


def test_navigation_save_rejects_invalid_draft(event_editor, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from src.app.coordinators.editor_coordinator import EditorCoordinator

    window = QWidget()
    qtbot.addWidget(window)
    window.event_editor = event_editor
    window.entity_editor = None
    coordinator = EditorCoordinator(window)
    field = event_editor.date_edit.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "invalid")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Save
    )
    assert not coordinator.check_unsaved_changes(event_editor)
    assert field.text() == "invalid"


def test_valid_date_uses_existing_parser(event_editor, qtbot):
    editor = event_editor
    field = editor.date_edit.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "5 Spring 1")
    qtbot.keyClick(field, Qt.Key.Key_Return)
    assert not editor.temporal_widget.has_pending_draft()
    assert editor.temporal_widget.get_start() == 4.0
    saved = []
    editor.save_requested.connect(saved.append)
    editor._on_save()
    assert saved[0]["lore_date"] == 4.0


def test_presentation_changes_do_not_dirty_event(event_editor):
    editor = event_editor
    editor.summary_checkbox.setChecked(True)
    editor.temporal_widget.range_button.setChecked(True)
    editor.temporal_widget.range_button.setChecked(False)
    editor.inspector.split_active_section()
    editor.inspector.reset_layout()
    assert not editor.has_unsaved_changes()
    assert editor.temporal_widget.get_duration() == 0
    assert editor.inspector.main_tabs.count() == 7


def test_no_calendar_uses_structured_entry(qtbot):
    from src.gui.widgets.compact_date_widget import CompactDateWidget

    field = CompactDateWidget(text_first=True)
    qtbot.addWidget(field)
    assert field.txt_date.isHidden()
    assert not field._date_chip.isHidden()
    assert "calendar" in field.feedback.text()


def test_hiding_time_preserves_value(event_editor):
    field = event_editor.date_edit
    field.set_value(0.5)
    field.btn_time_toggle.setChecked(True)
    field.btn_time_toggle.setChecked(False)
    assert field.get_value() == 0.5
    assert "12:00" in field.txt_date.text()


@pytest.mark.parametrize("keep_end", [False, True])
def test_typed_start_preserves_anchor_semantics(event_editor, qtbot, keep_end):
    temporal = event_editor.temporal_widget
    temporal.set_values(0.0, 10.0)
    if keep_end:
        temporal.btn_lock_end.click()
    field = temporal.date_start.txt_date
    field.selectAll()
    qtbot.keyClicks(field, "5 Spring 1")
    qtbot.keyClick(field, Qt.Key.Key_Return)
    assert temporal.get_start() == 4.0
    assert temporal.get_duration() == (6.0 if keep_end else 10.0)


def test_overflow_menu_reaches_every_section(event_editor):
    inspector = event_editor.inspector
    tabs = inspector.main_tabs
    tabs._populate_overflow()
    actions = tabs.overflow_menu.actions()
    assert len(actions) == 7
    for index, action in enumerate(actions):
        action.trigger()
        assert tabs.currentIndex() == index


@pytest.mark.parametrize("kind", ["event", "entity"])
@pytest.mark.parametrize("width", [360, 560, 800, 1200])
@pytest.mark.parametrize("height", [480, 900])
def test_editor_tabs_fit_compact_width(qtbot, kind, width, height, calendar):
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    font_file = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_file.exists():
        QFontDatabase.addApplicationFont(str(font_file))
    ThemeManager().apply_theme(
        QApplication.instance(),
        Path("src/resources/main.qss").read_text(encoding="utf-8"),
    )
    parent = QWidget()
    parent.worker = MagicMock()
    qtbot.addWidget(parent)
    editor = (
        EventEditorWidget(parent) if kind == "event" else EntityEditorWidget(parent)
    )
    qtbot.addWidget(editor)
    if kind == "event":
        editor.temporal_widget.set_calendar_converter(calendar)
        editor.load_event(Event(id="event", name="Arrival", lore_date=0.0))
    else:
        editor.load_entity(Entity(id="entity", name="Ada", type="Character"))
    editor.resize(width, height)
    editor.setWindowFlag(Qt.WindowType.Window, True)
    editor.show()
    assert not editor.has_unsaved_changes()
    for index in range(7):
        editor.inspector.main_tabs.setCurrentIndex(index)
        qtbot.wait(20)
        assert editor.width() == width
        assert not editor.has_unsaved_changes()
    editor.inspector.main_tabs.setCurrentIndex(0)
    qtbot.wait(20)
    assert not editor.has_unsaved_changes()
    assert editor.scroll_area.horizontalScrollBar().maximum() == 0, [
        (
            type(w).__name__,
            w.minimumWidth(),
            w.minimumSizeHint().width(),
            getattr(w, "text", lambda: "")(),
        )
        for w in editor.details_container.findChildren(QWidget)
        if w.isVisible() and w.minimumSizeHint().width() > 275
    ]
    editor.llm_checkbox.setChecked(True)
    if kind == "event":
        editor.temporal_widget.range_button.setChecked(True)
        editor.date_edit.date_fields_button.setChecked(True)
    qtbot.wait(20)
    assert editor.scroll_area.horizontalScrollBar().maximum() == 0, [
        (
            type(w).__name__,
            w.minimumWidth(),
            w.minimumSizeHint().width(),
            getattr(w, "text", lambda: "")(),
        )
        for w in editor.details_container.findChildren(QWidget)
        if w.isVisible() and w.minimumSizeHint().width() > 275
    ]
