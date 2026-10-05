"""Window-delivered scrolling must preserve unfocused authored choices."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.commands.relation_commands import UpdateRelationCommand
from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.entities import Entity
from src.core.events import Event
from src.gui.dialogs.relation_dialog import RelationEditDialog
from src.gui.widgets.choice_inputs import ScrollSafeComboBox
from src.gui.widgets.compact_date_widget import CompactDateWidget
from src.gui.widgets.lore_date_widget import LoreDateWidget

pytestmark = pytest.mark.ci_fast


def send_wheel(widget, delta=-120, pixel=False):
    window = widget.window()
    visible = widget.rect().translated(widget.mapTo(window, QPoint()))
    parent = widget.parentWidget()
    while parent is not None:
        visible = visible.intersected(
            parent.rect().translated(parent.mapTo(window, QPoint()))
        )
        if parent is window:
            break
        parent = parent.parentWidget()
    assert not visible.isEmpty(), "Wheel target must be visible inside the viewport"
    QTest.wheelEvent(
        window.windowHandle(),
        visible.center(),
        QPoint(0, delta),
        QPoint(0, delta) if pixel else QPoint(),
    )
    QApplication.processEvents()


@pytest.mark.parametrize("width", [400, 800])
@pytest.mark.parametrize("pixel", [False, True])
@pytest.mark.parametrize(
    "field", ["start", "end", "meaning", "type", "type_editor", "relative"]
)
def test_relation_unfocused_choices_preserve_draft(qtbot, width, pixel, field):
    dialog = RelationEditDialog(
        target_id="target-1",
        rel_type="custom relation",
        suggestion_items=[
            ("target-1", "Target", "entity"),
            ("event-1", "War", "event"),
        ],
        attributes={"notes": "Keep this note", "custom": {"source": "draft"}},
    )
    qtbot.addWidget(dialog)
    dialog.resize(width, 450)
    dialog.show()
    if field == "relative":
        boundary = dialog._boundary_choices["start"]
        boundary.setCurrentIndex(boundary.findData("event:event-1"))
    combo = {
        "start": dialog._boundary_choices["start"],
        "end": dialog._boundary_choices["end"],
        "meaning": dialog.temporal_behavior,
        "type": dialog.type_edit,
        "type_editor": dialog.type_edit,
        "relative": dialog._anchor_relations["start"],
    }[field]
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(dialog.notes_edit.hasFocus)
    dialog.form_scroll_area.ensureWidgetVisible(combo)
    QApplication.processEvents()
    scroll = dialog.form_scroll_area.verticalScrollBar()
    # Scroll away from the nearer edge so a delivered step has room to move.
    delta = 120 if scroll.value() > 0 else -120
    before_scroll = scroll.value()
    before = dialog.get_data()
    changed = QSignalSpy(combo.currentIndexChanged)
    text_changed = QSignalSpy(combo.currentTextChanged)
    activated = QSignalSpy(combo.activated)
    send_wheel(combo.lineEdit() if field == "type_editor" else combo, delta, pixel)
    assert dialog.get_data() == before
    assert changed.count() == text_changed.count() == activated.count() == 0
    assert dialog.notes_edit.hasFocus()
    assert scroll.value() != before_scroll


@pytest.mark.parametrize("editable", [False, True])
def test_deliberate_focus_keyboard_and_popup(qtbot, editable):
    surface = QWidget()
    layout = QVBoxLayout(surface)
    other = QLineEdit()
    combo = ScrollSafeComboBox()
    combo.setEditable(editable)
    combo.addItems([f"Choice {i}" for i in range(60)])
    combo.setMaxVisibleItems(5)
    combo.setCurrentIndex(2)
    layout.addWidget(other)
    layout.addWidget(combo)
    qtbot.addWidget(surface)
    surface.show()
    qtbot.wait(50)
    other.setFocus()
    qtbot.waitUntil(other.hasFocus)
    qtbot.keyClick(other, Qt.Key.Key_Tab)
    assert combo.hasFocus()
    send_wheel(combo)
    assert combo.currentIndex() == 3
    qtbot.keyClick(combo, Qt.Key.Key_Up)
    assert combo.currentIndex() == 2
    if editable:
        combo.lineEdit().selectAll()
        qtbot.keyClicks(combo.lineEdit(), "custom meaning")
        assert combo.currentText() == "custom meaning"
    # Deliberate click opens the popup; scrolling the view retains normal Qt behavior.
    qtbot.mouseClick(
        combo,
        Qt.MouseButton.LeftButton,
        pos=QPoint(combo.width() - 10, combo.height() // 2),
    )
    qtbot.waitUntil(lambda: combo.view().isVisible())
    view = combo.view()
    before = view.verticalScrollBar().value()
    send_wheel(view.viewport())
    assert view.verticalScrollBar().value() > before
    row = view.indexAt(QPoint(10, 10))
    assert row.isValid()
    qtbot.mouseMove(view.viewport(), pos=QPoint(10, 10))
    qtbot.wait(250)
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    assert combo.currentIndex() == row.row()
    assert not view.isVisible()


@pytest.mark.parametrize("width", [400, 800])
@pytest.mark.parametrize(
    "field",
    ["month", "day", "qualification", "lore_month", "lore_day", "hour", "minute"],
)
def test_date_choices_scroll_without_date_mutations(qtbot, width, field):
    surface = QWidget()
    layout = QVBoxLayout(surface)
    other = QLineEdit()
    layout.addWidget(other)
    area = QScrollArea()
    area.setWidgetResizable(True)
    layout.addWidget(area)
    content = QWidget()
    fields = QVBoxLayout(content)
    converter = CalendarConverter(CalendarConfig.create_default())
    date = CompactDateWidget(text_first=True)
    date.set_calendar_converter(converter)
    date.set_value(converter.to_float(CalendarDate(year=1218, month=3, day=15)))
    date.date_fields_button.setChecked(True)
    lore = LoreDateWidget()
    lore.set_calendar_converter(converter)
    lore.set_value(date.get_value())
    fields.addWidget(date)
    fields.addWidget(lore)
    filler = QWidget()
    filler.setMinimumHeight(900)
    fields.addWidget(filler)
    area.setWidget(content)
    qtbot.addWidget(surface)
    surface.resize(width, 450)
    surface.show()
    other.setFocus()
    qtbot.waitUntil(other.hasFocus)
    combo = {
        "month": date.combo_month,
        "day": date.combo_day,
        "qualification": date.qualifier_combo,
        "lore_month": lore._month_combo,
        "lore_day": lore._day_combo,
        "hour": lore._hour_combo,
        "minute": lore._minute_combo,
    }[field]
    area.ensureWidgetVisible(combo)
    QApplication.processEvents()
    before = (date.get_value(), date.get_expression(), lore.get_value())
    changed = QSignalSpy(date.value_changed)
    lore_changed = QSignalSpy(lore.value_changed)
    index_changed = QSignalSpy(combo.currentIndexChanged)
    scroll = area.verticalScrollBar()
    previous = scroll.value()
    send_wheel(combo, 120 if previous else -120)
    assert (date.get_value(), date.get_expression(), lore.get_value()) == before
    assert changed.count() == lore_changed.count() == index_changed.count() == 0
    assert other.hasFocus()
    assert scroll.value() != previous


@pytest.mark.parametrize("width", [400, 800])
def test_reported_empty_start_does_not_become_unknown(qtbot, width):
    dialog = RelationEditDialog(
        target_id="target-1",
        rel_type="connected",
        suggestion_items=[("target-1", "Target", "entity")],
    )
    qtbot.addWidget(dialog)
    dialog.resize(width, 450)
    dialog.show()
    combo = dialog._boundary_choices["start"]
    dialog.form_scroll_area.ensureWidgetVisible(combo)
    QApplication.processEvents()
    scroll = dialog.form_scroll_area.verticalScrollBar()
    # The reported +120 direction must have room above the current position.
    scroll.setValue(scroll.value() + 30)
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(dialog.notes_edit.hasFocus)
    before = dialog.get_data()
    assert before[3] == {}
    previous = scroll.value()
    changed = QSignalSpy(combo.currentIndexChanged)
    send_wheel(combo, 120)
    assert dialog.get_data() == before
    assert combo.currentData() == "open"
    assert changed.count() == 0
    assert dialog.notes_edit.hasFocus()
    assert scroll.value() < previous


def test_choices_preserve_event_binding_fixed_boundary_and_undo(qtbot, db_service):
    source = Event(name="Council", lore_date=100.0)
    target = Entity(name="Member", type="Character")
    db_service.insert_event(source)
    db_service.insert_entity(target)
    attributes = {
        "notes": "Original note",
        "custom": {"source": "manuscript"},
        "valid_from_event": True,
        "payload": {"attributes": {"rank": "member"}},
    }
    relation_id = db_service.insert_relation(
        source.id, target.id, "custom membership", attributes=attributes
    )
    dialog = RelationEditDialog(
        target_id=target.id,
        rel_type="custom membership",
        attributes=attributes,
        suggestion_items=[(target.id, target.name, "entity")],
        source_event_date=100.0,
        playhead_time=125.5,
        calendar_converter=CalendarConverter(CalendarConfig.create_default()),
    )
    qtbot.addWidget(dialog)
    dialog.resize(400, 450)
    dialog.show()
    dialog.ends_now_button.click()
    QApplication.processEvents()
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(dialog.notes_edit.hasFocus)
    before = dialog.get_data()
    for combo in [
        dialog.type_edit,
        dialog.temporal_behavior,
        *dialog._boundary_choices.values(),
    ]:
        dialog.form_scroll_area.ensureWidgetVisible(combo)
        QApplication.processEvents()
        send_wheel(combo)
        assert dialog.get_data() == before
        assert dialog.notes_edit.hasFocus()
    dialog.notes_edit.setPlainText("Revised note")
    target_id, rel_type, _, saved = dialog.get_data()
    assert saved["temporal"]["start"] == {"binding": "source_event"}
    assert saved["temporal"]["end"] == {"exact": 125.5}
    assert saved["custom"] == attributes["custom"]
    assert saved["payload"] == attributes["payload"]
    command = UpdateRelationCommand(relation_id, target_id, rel_type, attributes=saved)
    assert command.execute(db_service).success
    assert db_service.get_relation(relation_id)["attributes"] == saved
    command.undo(db_service)
    assert db_service.get_relation(relation_id)["attributes"] == attributes
    assert command.execute(db_service).success
    assert db_service.get_relation(relation_id)["attributes"] == saved


@pytest.mark.parametrize("width", [400, 800])
def test_expanded_manual_boundaries_remain_scroll_safe(qtbot, width):
    dialog = RelationEditDialog(
        playhead_time=125.5,
        calendar_converter=CalendarConverter(CalendarConfig.create_default()),
    )
    qtbot.addWidget(dialog)
    dialog.resize(width, 450)
    dialog.show()
    dialog.starts_now_button.click()
    qtbot.wait(50)
    assert dialog.valid_from.isVisible()
    assert dialog.get_data()[3]["temporal"]["start"] == {"exact": 125.5}
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(dialog.notes_edit.hasFocus)
    combo = dialog._boundary_choices["start"]
    dialog.form_scroll_area.ensureWidgetVisible(combo)
    QApplication.processEvents()
    before = dialog.get_data()
    scroll = dialog.form_scroll_area.verticalScrollBar()
    previous = scroll.value()
    send_wheel(combo, 120 if previous else -120)
    assert dialog.get_data() == before
    assert dialog.valid_from.isVisible()
    assert dialog.notes_edit.hasFocus()
    assert scroll.value() != previous
