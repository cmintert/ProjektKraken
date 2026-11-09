import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QAbstractItemView, QComboBox

from src.core.theme_manager import ThemeManager
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


def test_hidden_attributes_are_hidden_by_default_and_preserved(editor):
    editor.load_attributes({"visible": "shown", "_summary_data": {"text": "preserve"}})

    assert editor.table.rowCount() == 1
    assert editor.table.item(0, 0).text() == "visible"
    assert editor.get_attributes() == {
        "visible": "shown",
        "_summary_data": {"text": "preserve"},
    }


def test_hidden_attributes_can_be_shown_explicitly(editor):
    editor.load_attributes(
        {"visible": "shown", "_internal": "value"},
        show_hidden=True,
    )

    assert editor.table.rowCount() == 2
    assert editor.get_attributes()["_internal"] == "value"


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


def _has_focus_frame(table, row, column):
    rect = table.visualItemRect(table.item(row, column))
    image = table.viewport().grab().toImage()
    return image.pixelColor(rect.left() + 2, rect.center().y()) == QColor(
        ThemeManager().get_theme()["focus_ring"]
    )


@pytest.mark.parametrize("width", [360, 800])
def test_first_click_and_tab_paint_cell_focus_without_editing(editor, qtbot, width):
    """Exercise production QSS, all value variants and live palette changes."""
    from pathlib import Path

    manager = ThemeManager()
    template = Path("src/resources/main.qss").read_text(encoding="utf-8")
    editor._allow_null = True
    original = {"text": "unchanged", "number": 12.5, "boolean": True, "null": None}
    editor.load_attributes(original)
    editor.resize(width, 350)
    editor.show()
    editor.activateWindow()
    qtbot.waitUntil(editor.isActiveWindow)
    table = editor.table
    changed = QSignalSpy(editor.attributes_changed)

    for theme_name in manager.themes:
        manager.set_theme(theme_name, persist=False)
        editor.setStyleSheet(template.format(**manager.get_theme()))
        qtbot.waitUntil(editor.isVisible)
        for row in range(table.rowCount()):
            editor.btn_add.setFocus()
            qtbot.mouseClick(
                table.viewport(),
                Qt.MouseButton.LeftButton,
                pos=table.visualItemRect(table.item(row, 1)).center(),
            )
            assert table.hasFocus()
            assert table.currentRow() == row
            assert table.currentColumn() == 1
            assert table.state() == QAbstractItemView.State.NoState
            assert _has_focus_frame(table, row, 1)
            if row:
                assert not _has_focus_frame(table, row - 1, 1)

        # Tab enters the table and advances between name and value cells.
        table.setCurrentCell(0, 0)
        editor.btn_remove.setFocus()
        qtbot.keyClick(editor.btn_remove, Qt.Key.Key_Tab)
        assert table.hasFocus()
        assert _has_focus_frame(table, 0, 0)
        qtbot.keyClick(table, Qt.Key.Key_Tab)
        assert table.currentColumn() == 1
        assert _has_focus_frame(table, 0, 1)
        assert not _has_focus_frame(table, 0, 0)
        editor.btn_add.setFocus()
        assert not _has_focus_frame(table, 0, 1)
        table.setEnabled(False)
        assert not _has_focus_frame(table, 0, 1)
        table.setEnabled(True)
        assert editor.get_attributes() == original
        assert changed.count() == 0


@pytest.mark.parametrize(
    "column, value", [(0, "value"), (1, "value"), (1, 12.5), (1, True)]
)
def test_double_click_still_opens_type_aware_editor(editor, qtbot, column, value):
    from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLineEdit

    editor.load_attributes({"name": value})
    editor.resize(600, 300)
    editor.show()
    editor.activateWindow()
    qtbot.waitUntil(editor.isActiveWindow)
    table = editor.table
    point = table.visualItemRect(table.item(0, column)).center()
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert table.state() == QAbstractItemView.State.EditingState
    expected = (
        QLineEdit
        if column == 0 or isinstance(value, str)
        else QCheckBox
        if isinstance(value, bool)
        else QDoubleSpinBox
    )
    assert table.viewport().findChild(expected) is not None
    qtbot.keyClick(table.focusWidget(), Qt.Key.Key_Escape)
    assert editor.get_attributes() == {"name": value}
