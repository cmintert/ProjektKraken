"""Readable chronology projection and detached edit intents."""

import pytest
from PySide6.QtWidgets import QDialog, QScrollArea

from src.core.events import Event
from src.gui.dialogs.event_chronology_dialog import EventChronologyDialog

pytestmark = pytest.mark.ci_fast


def test_incoming_rule_is_shown_from_current_event_view(qtbot) -> None:
    a = Event(name="Discovery", lore_date=1)
    b = Event(name="Execution", lore_date=2)
    rule = {
        "anchor_a": f"event:{a.id}",
        "relation": "before",
        "anchor_b": f"event:{b.id}",
        "min_offset_days": 0,
    }
    a.attributes = {"_temporal_v2": {"schema": 1, "constraints": [rule]}}
    dialog = EventChronologyDialog(b.id, [a, b])
    qtbot.addWidget(dialog)
    dialog.resize(630, 400)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.findChild(QScrollArea).horizontalScrollBar().maximum() == 0
    row = dialog._rows[0]
    assert row["relation"].currentText() == "After"
    assert row["target"].currentData() == f"event:{a.id}"
    dialog._accept_valid()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.operations == []


def test_unavailable_target_can_be_removed(qtbot) -> None:
    event = Event(name="A", lore_date=1)
    rule = {
        "anchor_a": f"event:{event.id}",
        "relation": "before",
        "anchor_b": "event:deleted",
        "min_offset_days": 0,
    }
    event.attributes = {"_temporal_v2": {"schema": 1, "constraints": [rule]}}
    dialog = EventChronologyDialog(event.id, [event])
    qtbot.addWidget(dialog)
    dialog._rows[0]["remove_button"].click()
    dialog._accept_valid()
    assert dialog.operations[0]["kind"] == "delete"
