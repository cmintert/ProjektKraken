"""Interaction tests for the map search-and-create surface."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from src.gui.dialogs.map_object_picker_dialog import MapObjectPickerDialog


@pytest.fixture
def objects():
    """Return duplicate-name objects to verify identity-safe selection."""
    return (
        [
            SimpleNamespace(id="entity-grey", name="Grey Ford", type="Location"),
            SimpleNamespace(id="entity-edda", name="Edda Voss", type="Character"),
        ],
        [SimpleNamespace(id="event-grey", name="Grey Ford")],
    )


def test_existing_objects_visible_searchable_and_identity_safe(qtbot, objects):
    entities, events = objects
    dialog = MapObjectPickerDialog(entities, events)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(dialog.search_edit.hasFocus)
    assert dialog.results_list.count() == 3
    dialog.search_edit.setText("character")
    visible = [
        dialog.results_list.item(row)
        for row in range(dialog.results_list.count())
        if not dialog.results_list.item(row).isHidden()
    ]
    assert [item.text() for item in visible] == ["Edda Voss · Character"]

    dialog.search_edit.setText("Grey Ford")
    assert sum(
        not dialog.results_list.item(row).isHidden()
        for row in range(dialog.results_list.count())
    ) == 2
    event_row = next(
        row
        for row in range(dialog.results_list.count())
        if dialog.results_list.item(row)
        .data(Qt.ItemDataRole.UserRole)
        .object_id
        == "event-grey"
    )
    dialog.results_list.setCurrentRow(event_row)
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.choice() is not None
    assert dialog.choice().object_id == "event-grey"


def test_keyboard_arrows_move_existing_selection(qtbot, objects):
    dialog = MapObjectPickerDialog(*objects)
    qtbot.addWidget(dialog)
    dialog.show()
    first_id = dialog.results_list.currentItem().data(
        Qt.ItemDataRole.UserRole
    ).object_id

    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Down)

    second_id = dialog.results_list.currentItem().data(
        Qt.ItemDataRole.UserRole
    ).object_id
    assert second_id != first_id


def test_new_location_captures_name_directly(qtbot, objects):
    dialog = MapObjectPickerDialog(*objects)
    qtbot.addWidget(dialog)
    with patch(
        "src.gui.dialogs.map_object_picker_dialog.QInputDialog.getText",
        return_value=(" Grey Watch ", True),
    ):
        qtbot.mouseClick(dialog.new_location_button, Qt.MouseButton.LeftButton)

    assert dialog.choice().name == "Grey Watch"
    assert dialog.choice().entity_type == "Location"


def test_new_event_captures_name_directly(qtbot, objects):
    dialog = MapObjectPickerDialog(*objects)
    qtbot.addWidget(dialog)
    with patch(
        "src.gui.dialogs.map_object_picker_dialog.QInputDialog.getText",
        return_value=("Battle of Grey Ford", True),
    ):
        qtbot.mouseClick(dialog.new_event_button, Qt.MouseButton.LeftButton)

    assert dialog.choice().object_type == "event"
    assert dialog.choice().name == "Battle of Grey Ford"


def test_new_entity_preserves_custom_type(qtbot, objects):
    dialog = MapObjectPickerDialog(*objects)
    qtbot.addWidget(dialog)
    capture = MagicMock()
    capture.exec.return_value = QDialog.DialogCode.Accepted
    capture.name.return_value = "The Resolute"
    capture.entity_type.return_value = "Ship"
    with patch(
        "src.gui.dialogs.map_object_picker_dialog.EntityQuickCaptureDialog",
        return_value=capture,
    ):
        qtbot.mouseClick(dialog.new_entity_button, Qt.MouseButton.LeftButton)

    assert dialog.choice().name == "The Resolute"
    assert dialog.choice().entity_type == "Ship"


def test_escape_cancels_without_choice(qtbot, objects):
    dialog = MapObjectPickerDialog(*objects)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Escape)

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.choice() is None
