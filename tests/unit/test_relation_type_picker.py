"""Tests for RelationTypePicker widget (TDD approach)."""

import pytest
from PySide6.QtCore import QPoint, Qt

from src.gui.widgets.relation_type_picker import RelationTypePicker


@pytest.fixture
def type_picker(qtbot):
    """Create a RelationTypePicker widget for testing."""
    relation_types = ["related", "caused", "participated_in", "located_at", "owns"]
    widget = RelationTypePicker(relation_types=relation_types)
    qtbot.addWidget(widget)
    return widget


def test_type_picker_initialization(type_picker):
    """Test that type picker initializes with correct properties."""
    assert type_picker.relation_types == sorted(
        [
            "related",
            "caused",
            "participated_in",
            "located_at",
            "owns",
        ]
    )
    assert not type_picker.isVisible()  # Hidden by default
    assert type_picker.combo_box.currentText() == "related"  # Default selection


def test_type_picker_shows_at_position(type_picker, qtbot):
    """Test that type picker can be shown at a specific position."""
    position = QPoint(100, 100)
    type_picker.show_at_position(position)

    assert type_picker.isVisible()
    # Position should be near the specified point
    actual_pos = type_picker.pos()
    assert abs(actual_pos.x() - position.x()) < 50  # Within reasonable range
    assert abs(actual_pos.y() - position.y()) < 50


def test_type_picker_displays_all_types(type_picker):
    """Test that type picker displays all provided relation types."""
    type_picker.show()

    # Check that combo box contains all types
    combo = type_picker.combo_box
    assert combo.count() == 5

    # Check that items match the relation types
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "related" in items
    assert "caused" in items
    assert "participated_in" in items


def test_type_picker_selects_type_on_click(type_picker, qtbot):
    """Test that selecting a type emits signal."""
    type_picker.show()

    # Track signal emissions
    with qtbot.waitSignal(type_picker.type_selected, timeout=1000) as blocker:
        # Select the second item (index 1) which is "caused" (sorted)
        # Note: types are sorted in __init__
        # ["caused", "located_at", "owns", "participated_in", "related"]
        combo = type_picker.combo_box
        combo.setCurrentIndex(0)  # "caused"
        qtbot.mouseClick(type_picker.ok_button, Qt.MouseButton.LeftButton)

    # Check that signal was emitted with correct type
    assert blocker.args[0] == "caused"


def test_type_picker_hides_after_selection(type_picker, qtbot):
    """Test that type picker hides after a type is selected."""
    type_picker.show()
    assert type_picker.isVisible()

    # Select a type
    combo = type_picker.combo_box
    combo.setCurrentIndex(1)
    qtbot.mouseClick(type_picker.ok_button, Qt.MouseButton.LeftButton)

    # Should be hidden after selection
    qtbot.wait(100)  # Give time for hide to process
    assert not type_picker.isVisible()


def test_type_picker_uses_theme_colors(type_picker):
    """Test that type picker applies theme colors."""
    stylesheet = type_picker.styleSheet()
    assert len(stylesheet) > 0  # Has styling applied


def test_type_picker_highlights_default_type(type_picker):
    """Test that the default type ('related') is selected."""
    type_picker.show()

    # "related" should be selected by default
    combo = type_picker.combo_box
    assert combo.currentText() == "related"


def test_type_picker_escape_key_closes(type_picker, qtbot):
    """Test that pressing Escape key closes the picker without selection."""
    type_picker.show()
    assert type_picker.isVisible()

    # Focus the combo box (since it has the focus proxy or similar)
    type_picker.combo_box.setFocus()

    # Press Escape on the combo box
    qtbot.keyPress(type_picker.combo_box, Qt.Key.Key_Escape)

    # Should be hidden
    assert not type_picker.isVisible()


def test_type_picker_empty_list_default():
    """Test that type picker with empty list defaults to 'related'."""
    picker = RelationTypePicker(relation_types=[])
    assert picker.combo_box.currentText() == "related"
    assert picker.combo_box.count() == 1  # Should have at least "related"


def test_type_picker_signal_emission(type_picker, qtbot):
    """Test that type_selected signal is emitted correctly."""
    selections = []
    type_picker.type_selected.connect(lambda t: selections.append(t))

    type_picker.show()
    combo = type_picker.combo_box

    # Select different types
    # sorted: caused, located_at, owns, participated_in, related
    for i in range(3):
        combo.setCurrentIndex(i)
        qtbot.mouseClick(type_picker.ok_button, Qt.MouseButton.LeftButton)

    # Should have received 3 signals
    assert len(selections) == 3


def test_type_picker_stays_on_top():
    """Test that type picker stays on top of other windows."""
    picker = RelationTypePicker(relation_types=["related"])
    from PySide6.QtCore import Qt

    assert picker.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_type_picker_has_border():
    """Test that type picker has visible border."""
    picker = RelationTypePicker(relation_types=["related"])
    stylesheet = picker.styleSheet()
    assert "border" in stylesheet.lower()
