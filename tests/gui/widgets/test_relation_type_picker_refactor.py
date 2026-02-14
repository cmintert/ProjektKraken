import pytest
from PySide6.QtCore import Qt

from src.gui.widgets.relation_type_picker import RelationTypePicker


@pytest.fixture
def picker(qtbot):
    widget = RelationTypePicker()
    qtbot.addWidget(widget)
    return widget


def test_initialization(picker):
    """Test default initialization."""
    assert picker.combo_box.count() == 1
    assert picker.combo_box.itemText(0) == "related"
    assert picker.combo_box.currentText() == "related"


def test_set_relation_types(picker):
    """Test updating relation types."""
    types = ["caused", "owns", "related"]
    picker.set_relation_types(types)

    assert picker.combo_box.count() == 3
    items = sorted([picker.combo_box.itemText(i) for i in range(3)])
    assert items == ["caused", "owns", "related"]


def test_selection_emits_signal(picker, qtbot):
    """Test that selecting an item emits the signal after confirmation."""
    picker.set_relation_types(["alpha", "beta"])

    with qtbot.waitSignal(picker.type_selected, timeout=1000) as blocker:
        picker.combo_box.setCurrentText("beta")
        # Click OK button
        qtbot.mouseClick(picker.ok_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["beta"]


def test_custom_text_emits_signal(picker, qtbot):
    """Test that entering custom text emits the signal after confirmation."""

    with qtbot.waitSignal(picker.type_selected, timeout=1000) as blocker:
        # User types "custom_type"
        picker.combo_box.setCurrentText("custom_type")
        # Simulate Enter key
        picker.combo_box.lineEdit().returnPressed.emit()

    assert blocker.args == ["custom_type"]
