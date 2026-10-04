"""Delivered wheel events must distinguish navigation from numeric editing."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from src.commands.relation_commands import UpdateRelationCommand
from src.core.entities import Entity
from src.core.events import Event
from src.gui.dialogs.relation_dialog import RelationEditDialog
from src.gui.widgets.color_pickers.numeric_scrubber_spinbox import (
    NumericScrubberSpinBox,
)
from src.gui.widgets.numeric_inputs import ScrollSafeDoubleSpinBox, ScrollSafeSpinBox

pytestmark = pytest.mark.ci_fast


def send_wheel(widget, delta=-120, pixel=False):
    position = QPoint(5, widget.rect().center().y())
    # Deliver through QWindow so Qt performs hit testing and parent propagation.
    window = widget.window()
    QTest.wheelEvent(
        window.windowHandle(),
        widget.mapTo(window, position),
        QPoint(0, delta),
        QPoint(0, delta) if pixel else QPoint(),
    )
    QApplication.processEvents()


@pytest.mark.parametrize("width", [400, 800])
@pytest.mark.parametrize("pixel", [False, True])
@pytest.mark.parametrize("child", [False, True])
def test_relation_wheel_preserves_draft_and_scrolls(qtbot, width, pixel, child):
    dialog = RelationEditDialog(
        target_id="entity-1",
        rel_type="member_of",
        is_bidirectional=True,
        suggestion_items=[("entity-1", "Target", "entity")],
        source_event_date=100.0,
        attributes={
            "confidence": 0.7,
            "weight": 2.0,
            "notes": "An authored note",
            "custom": {"source": "manuscript"},
            "payload": {"attributes": {f"key_{i}": "value" for i in range(12)}},
        },
    )
    qtbot.addWidget(dialog)
    dialog.resize(width, 450)
    dialog.show()
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(lambda: dialog.notes_edit.hasFocus())
    scroll = dialog.form_scroll_area.verticalScrollBar()
    scroll.setValue(0)
    assert scroll.maximum() > 0
    before = dialog.get_data()
    changed = QSignalSpy(dialog.confidence_spin.valueChanged)
    target = dialog.confidence_spin.lineEdit() if child else dialog.confidence_spin
    send_wheel(target, pixel=pixel)
    assert dialog.confidence_spin.value() == 0.7
    assert changed.count() == 0
    assert dialog.get_data() == before
    assert dialog.notes_edit.hasFocus()
    assert scroll.value() > 0


@pytest.mark.parametrize(
    "spin_type", [ScrollSafeSpinBox, ScrollSafeDoubleSpinBox, NumericScrubberSpinBox]
)
def test_numeric_focus_owns_wheel_and_keyboard(qtbot, spin_type):
    surface = QWidget()
    layout = QVBoxLayout(surface)
    other = QLineEdit()
    spin = spin_type()
    spin.setRange(0, 100)
    spin.setValue(50)
    layout.addWidget(other)
    layout.addWidget(spin)
    qtbot.addWidget(surface)
    surface.show()
    other.setFocus()
    qtbot.waitUntil(other.hasFocus)
    changes = QSignalSpy(spin.valueChanged)
    send_wheel(spin)
    assert spin.value() == 50
    assert changes.count() == 0
    assert other.hasFocus()

    # Tab explicitly enters numeric editing, including its line-edit focus proxy.
    qtbot.keyClick(other, Qt.Key.Key_Tab)
    assert spin.hasFocus()
    send_wheel(spin)
    assert spin.value() == 49
    qtbot.keyClick(spin, Qt.Key.Key_Up)
    assert spin.value() == 50
    spin.selectAll()
    qtbot.keyClicks(spin, "42")
    qtbot.keyClick(spin, Qt.Key.Key_Return)
    assert spin.value() == 42

    other.setFocus()
    qtbot.mouseClick(spin.lineEdit(), Qt.MouseButton.LeftButton)
    assert spin.hasFocus()
    send_wheel(spin, delta=120)
    assert spin.value() == 43


@pytest.mark.parametrize("spin_type", [ScrollSafeSpinBox, ScrollSafeDoubleSpinBox])
def test_numeric_visible_arrows_still_step(qtbot, spin_type):
    spin = spin_type()
    qtbot.addWidget(spin)
    spin.setRange(0, 100)
    spin.setValue(50)
    spin.resize(150, 30)
    spin.show()
    from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox

    option = QStyleOptionSpinBox()
    spin.initStyleOption(option)
    arrow = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxUp,
        spin,
    )
    qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=arrow.center())
    assert spin.value() == 51


def test_relation_note_save_after_scrolling_preserves_metadata_and_undo(qtbot, db_service):
    source = Event(name="Council", lore_date=100.0)
    target = Entity(name="Member", type="Character")
    db_service.insert_event(source)
    db_service.insert_entity(target)
    attributes = {
        "confidence": 0.7,
        "weight": 2.0,
        "notes": "Original note",
        "custom": {"source": "manuscript"},
        "valid_from_event": True,
        "payload": {"attributes": {"rank": "member"}},
    }
    relation_id = db_service.insert_relation(
        source.id, target.id, "member_of", attributes=attributes
    )
    dialog = RelationEditDialog(
        target_id=target.id,
        rel_type="member_of",
        suggestion_items=[(target.id, target.name, "entity")],
        source_event_date=100.0,
        attributes=attributes,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.notes_edit.setFocus()
    qtbot.waitUntil(dialog.notes_edit.hasFocus)
    send_wheel(dialog.confidence_spin)
    dialog.notes_edit.setPlainText("Revised note")
    target_id, relation_type, _, saved_attributes = dialog.get_data()
    command = UpdateRelationCommand(
        relation_id, target_id, relation_type, attributes=saved_attributes
    )
    assert command.execute(db_service).success
    stored = db_service.get_relation(relation_id)["attributes"]
    assert stored["notes"] == "Revised note"
    for key in ("confidence", "weight", "custom", "valid_from_event", "payload"):
        assert stored[key] == attributes[key]
    command.undo(db_service)
    assert db_service.get_relation(relation_id)["attributes"] == attributes
    assert command.execute(db_service).success
    assert db_service.get_relation(relation_id)["attributes"] == saved_attributes
