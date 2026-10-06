"""Deliberate classification and keyboard acceptance for KRT-14."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from src.gui.dialogs.entity_creation_dialog import EntityCreationDialog
from src.gui.dialogs.map_object_picker_dialog import EntityQuickCaptureDialog

pytestmark = pytest.mark.ci_fast


def test_name_alone_cannot_create_even_with_enter(qtbot):
    dialog = EntityCreationDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name_edit.setText("Tasgillia")
    assert dialog.type_combo.currentIndex() == -1
    assert dialog.entity_type() == ""
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    with qtbot.assertNotEmitted(dialog.accepted):
        qtbot.keyClick(dialog.name_edit, Qt.Key.Key_Return)
        dialog.accept()
    assert dialog.isVisible()


@pytest.mark.parametrize("entity_type", EntityCreationDialog.DEFAULT_TYPES)
def test_common_type_accepts_named_entity(qtbot, entity_type):
    dialog = EntityCreationDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name_edit.setText("  New lore  ")
    dialog.type_combo.setCurrentIndex(dialog.type_combo.findText(entity_type))
    with qtbot.waitSignal(dialog.accepted):
        qtbot.keyClick(dialog.name_edit, Qt.Key.Key_Return)
    assert dialog.name() == "New lore"
    assert dialog.entity_type() == entity_type


def test_keyboard_custom_type_and_clearing(qtbot):
    dialog = EntityCreationDialog(entity_types=["Ship", "Character", " Ship "])
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.type_combo.count() == len(dialog.DEFAULT_TYPES) + 1
    dialog.name_edit.setText("Grey Gull")
    dialog.activateWindow()
    dialog.name_edit.setFocus()
    qtbot.waitUntil(dialog.name_edit.hasFocus)
    qtbot.keyClick(dialog.name_edit, Qt.Key.Key_Tab)
    assert dialog.type_combo.hasFocus()
    qtbot.keyClicks(dialog.type_combo, "  Airship  ")
    assert dialog.entity_type() == "Airship"
    button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert button.isEnabled()
    dialog.type_combo.setEditText("  ")
    assert not button.isEnabled()
    dialog.type_combo.setCurrentText("Ship")
    dialog.name_edit.clear()
    assert not button.isEnabled()


def test_escape_cancels_without_reusing_last_type(qtbot):
    dialog = EntityCreationDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name_edit.setText("House Bjornaer")
    dialog.type_combo.setCurrentText("Faction")
    with qtbot.waitSignal(dialog.rejected):
        qtbot.keyClick(dialog.name_edit, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected
    next_dialog = EntityCreationDialog()
    qtbot.addWidget(next_dialog)
    assert next_dialog.entity_type() == ""


def test_quick_capture_keeps_intentional_concept_default(qtbot):
    dialog = EntityQuickCaptureDialog(entity_types=["Ship"])
    qtbot.addWidget(dialog)
    assert dialog.entity_type() == "Concept"
    dialog.name_edit.setText("Unclassified idea")
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
