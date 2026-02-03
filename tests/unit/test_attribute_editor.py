import pytest
from PySide6.QtWidgets import QComboBox

from src.gui.widgets.attribute_editor import AttributeEditorWidget


@pytest.fixture
def editor(qtbot):
    widget = AttributeEditorWidget()
    qtbot.addWidget(widget)
    return widget


def test_initial_state(editor):
    assert editor.table.rowCount() == 0


def test_add_attribute(editor, qtbot, monkeypatch):
    # Mock QInputDialog to return "New Key"
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("New Key", True))

    with qtbot.waitSignal(editor.attributes_changed):
        editor.btn_add.click()

    assert editor.table.rowCount() == 1
    assert editor.table.item(0, 0).text() == "New Key"
    assert editor.table.item(0, 1).text() == ""
    # Check default type is String
    combo = editor.table.cellWidget(0, 2)
    assert isinstance(combo, QComboBox)
    assert combo.currentText() == "String"


def test_get_attributes_parsing(editor):
    # Manually add rows
    editor._add_row("str_key", "value")
    editor._add_row("int_key", "123")

    # Change type of int_key to Number
    combo = editor.table.cellWidget(1, 2)
    combo.setCurrentText("Number")

    editor._add_row("bool_key", "True")
    combo_bool = editor.table.cellWidget(2, 2)
    combo_bool.setCurrentText("Boolean")

    attrs = editor.get_attributes()

    assert attrs["str_key"] == "value"
    assert attrs["int_key"] == 123
    assert attrs["bool_key"] is True


def test_parse_value_logic(editor):
    # Test internal parsing logic
    assert editor._parse_value("123", "Number") == 123
    assert editor._parse_value("12.34", "Number") == 12.34
    assert editor._parse_value("abc", "Number") == 0

    assert editor._parse_value("true", "Boolean") is True
    assert editor._parse_value("True", "Boolean") is True
    assert editor._parse_value("1", "Boolean") is True
    assert editor._parse_value("yes", "Boolean") is True
    assert editor._parse_value("on", "Boolean") is True
    assert editor._parse_value("false", "Boolean") is False

    assert editor._parse_value("anything", "String") == "anything"
