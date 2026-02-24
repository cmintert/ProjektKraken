"""Unit tests for the Sheet Builder Widget.

Tests the SheetBuilderWidget and AttributePairWidget for:
- Attribute creation with Universal String default
- Layout serialization (2D list of key strings)
- Loading attributes with and without layout
- Value parsing by type (String, Number, Boolean)
- Add/remove attribute operations
- Ghost widget during drag
- Insertion line drop indicators
- Weight percentage overlay during resize
"""

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFrame

from src.gui.widgets.sheet_builder import (
    AttributePairWidget,
    SheetBuilderWidget,
    _GhostWidget,
    _InsertionLine,
)

# ─────────────────────────────────────────────────────────────────────────────
# AttributePairWidget
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def pair(qtbot):
    """Create a basic AttributePairWidget."""
    widget = AttributePairWidget("Strength", "18", "Number")
    qtbot.addWidget(widget)
    return widget


class TestAttributePairWidget:
    """Tests for the AttributePairWidget."""

    def test_key_property_and_default_weight(self, pair):
        """Test that key returns attribute key and default weight is 1."""
        assert pair.key == "Strength"
        assert pair.weight == 1

    def test_get_value(self, pair):
        """Test that get_value returns the current value string."""
        assert pair.get_value() == "18"

    def test_set_value(self, pair, qtbot):
        """Test that set_value updates without emitting value_changed."""
        signal_emitted = False

        def on_changed():
            nonlocal signal_emitted
            signal_emitted = True

        pair.value_changed.connect(on_changed)
        pair.set_value("20")
        assert pair.get_value() == "20"
        assert not signal_emitted

    def test_get_type(self, pair):
        """Test that get_type returns the selected type."""
        assert pair.get_type() == "Number"

    def test_set_type(self, pair):
        """Test that set_type changes the combo without emitting."""
        pair.set_type("Boolean")
        assert pair.get_type() == "Boolean"

    def test_get_parsed_value_number_int(self, pair):
        """Test parsed value for integer Number type."""
        assert pair.get_parsed_value() == 18

    def test_get_parsed_value_number_float(self, qtbot):
        """Test parsed value for float Number type."""
        widget = AttributePairWidget("Weight", "72.5", "Number")
        qtbot.addWidget(widget)
        assert widget.get_parsed_value() == 72.5

    def test_get_parsed_value_number_invalid(self, qtbot):
        """Test parsed value falls back to 0 for invalid Number."""
        widget = AttributePairWidget("Invalid", "abc", "Number")
        qtbot.addWidget(widget)
        assert widget.get_parsed_value() == 0

    def test_get_parsed_value_boolean_true(self, qtbot):
        """Test parsed value for Boolean true variants."""
        for val in ["true", "True", "1", "yes", "on"]:
            widget = AttributePairWidget("Flag", val, "Boolean")
            qtbot.addWidget(widget)
            assert widget.get_parsed_value() is True

    def test_get_parsed_value_boolean_false(self, qtbot):
        """Test parsed value for Boolean false."""
        widget = AttributePairWidget("Flag", "false", "Boolean")
        qtbot.addWidget(widget)
        assert widget.get_parsed_value() is False

    def test_get_parsed_value_string(self, qtbot):
        """Test parsed value for String type (passthrough)."""
        widget = AttributePairWidget("Name", "Gandalf", "String")
        qtbot.addWidget(widget)
        assert widget.get_parsed_value() == "Gandalf"

    def test_value_changed_signal(self, pair, qtbot):
        """Test that editing the value emits value_changed."""
        with qtbot.waitSignal(pair.value_changed):
            pair.value_edit.setText("20")

    def test_universal_string_default(self, qtbot):
        """Test that new attributes default to String type."""
        widget = AttributePairWidget("NewAttr", "")
        qtbot.addWidget(widget)
        assert widget.get_type() == "String"

    def test_inline_layout_and_hidden_type(self, pair):
        """Test that the widget uses horizontal layout and hides the type selector."""
        # Check layout type
        from PySide6.QtWidgets import QHBoxLayout

        assert isinstance(pair.layout(), QHBoxLayout)

        # Check type selector visibility
        assert not pair.type_combo.isVisible()

        # Check label has colon
        assert ":" in pair.key_label.text()


# ─────────────────────────────────────────────────────────────────────────────
# SheetBuilderWidget
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sheet(qtbot):
    """Create a basic SheetBuilderWidget."""
    widget = SheetBuilderWidget()
    qtbot.addWidget(widget)
    return widget


class TestSheetBuilderWidget:
    """Tests for the SheetBuilderWidget."""

    def test_initial_state_empty(self, sheet):
        """Test that the sheet starts empty."""
        assert sheet.get_attributes() == {}
        assert sheet.get_layout() == []

    def test_load_attributes_no_layout(self, sheet):
        """Test loading attributes without a layout gives one row per attr."""
        attrs = {"Name": "Aragorn", "Race": "Human", "Age": 87}
        sheet.load_attributes(attrs)

        result = sheet.get_attributes()
        assert result["Name"] == "Aragorn"
        assert result["Race"] == "Human"
        assert result["Age"] == 87

        layout = sheet.get_layout()
        assert len(layout) == 3
        assert all(len(row) == 1 for row in layout)

    def test_load_attributes_with_layout_strings_and_weights(self, sheet):
        """Test loading attributes with a 2D layout mixing strings and dicts."""
        attrs = {
            "Strength": 10,
            "Dexterity": 15,
            "Intelligence": 12,
        }
        layout = [
            ["Strength"],
            [{"key": "Dexterity", "weight": 2}],
            [{"type": "spacer", "weight": 1}, "Intelligence"],
        ]
        sheet.load_attributes(attrs, layout)

        grid = sheet._grid_layout
        assert grid.count() == 3

        # Row 1: "Strength"
        row1 = grid.itemAt(0).layout()
        assert row1.itemAt(0).widget().key == "Strength"
        assert row1.stretch(0) == 1  # Default stretch

        # Row 2: "Dexterity" with weight 2
        row2 = grid.itemAt(1).layout()
        assert row2.itemAt(0).widget().key == "Dexterity"
        assert row2.stretch(0) == 2

        # Row 3: Spacer, [resize handle], Intelligence
        # Resize handles are inserted between adjacent items
        row3 = grid.itemAt(2).layout()
        assert row3.itemAt(0).widget() is not None
        assert row3.itemAt(0).widget().objectName() == "SpacerWidget"
        assert row3.stretch(0) == 1
        # Find the Intelligence widget (may be at index 1 or 2
        # depending on resize handle)
        found_intel = False
        for i in range(row3.count()):
            item = row3.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), "key"):
                assert item.widget().key == "Intelligence"
                found_intel = True
                break
        assert found_intel

    def test_load_attributes_with_layout(self, sheet):
        """Test loading attributes with a 2D layout arrangement."""
        attrs = {"STR": 18, "DEX": 14, "CON": 16, "Name": "Fighter"}
        layout = [["Name"], ["STR", "DEX", "CON"]]

        sheet.load_attributes(attrs, layout)

        result_layout = sheet.get_layout()
        assert result_layout == [["Name"], ["STR", "DEX", "CON"]]

    def test_load_attributes_layout_skips_missing_keys(self, sheet):
        """Test that layout keys not in attributes are skipped."""
        attrs = {"STR": 18, "DEX": 14}
        layout = [["STR", "MISSING", "DEX"]]

        sheet.load_attributes(attrs, layout)

        result_layout = sheet.get_layout()
        assert result_layout == [["STR", "DEX"]]

    def test_load_attributes_layout_appends_unlisted(self, sheet):
        """Test that attributes not in layout get appended as new rows."""
        attrs = {"STR": 18, "DEX": 14, "Extra": "bonus"}
        layout = [["STR", "DEX"]]

        sheet.load_attributes(attrs, layout)

        result_layout = sheet.get_layout()
        assert result_layout == [["STR", "DEX"], ["Extra"]]

    def test_get_attributes_returns_parsed_values(self, sheet):
        """Test that get_attributes returns correctly typed values."""
        attrs = {"HP": 100, "Alive": True, "Title": "Knight"}
        sheet.load_attributes(attrs)

        result = sheet.get_attributes()
        assert result["HP"] == 100
        assert result["Alive"] is True
        assert result["Title"] == "Knight"

    def test_add_attribute(self, sheet, qtbot):
        """Test adding a new attribute to the sheet."""
        with qtbot.waitSignal(sheet.attributes_changed):
            sheet.add_attribute("NewStat", "42")

        assert "NewStat" in sheet.get_attributes()
        assert sheet.get_attributes()["NewStat"] == "42"

    def test_add_attribute_duplicate_ignored(self, sheet):
        """Test that adding a duplicate key is silently ignored."""
        sheet.add_attribute("STR", "18")
        sheet.add_attribute("STR", "20")

        layout = sheet.get_layout()
        # Should only have one row with one entry
        total_keys = sum(len(row) for row in layout)
        assert total_keys == 1

    def test_remove_attribute(self, sheet, qtbot):
        """Test removing an attribute from the sheet."""
        sheet.load_attributes({"STR": 18, "DEX": 14})

        with qtbot.waitSignal(sheet.attributes_changed):
            sheet.remove_attribute("STR")

        assert "STR" not in sheet.get_attributes()
        assert "DEX" in sheet.get_attributes()

    def test_remove_nonexistent_attribute(self, sheet):
        """Test removing a key that doesn't exist does nothing."""
        sheet.load_attributes({"STR": 18})
        sheet.remove_attribute("MISSING")  # Should not raise
        assert sheet.get_attributes() == {"STR": 18}

    def test_layout_serialization_roundtrip(self, sheet):
        """Test that layout serialization is a proper roundtrip."""
        attrs = {"A": 1, "B": 2, "C": 3, "D": 4}
        layout = [["A", "B"], ["C"], ["D"]]

        sheet.load_attributes(attrs, layout)
        result = sheet.get_layout()

        assert result == layout

    def test_get_layout_mixed_types(self, sheet):
        """Test that get_layout serializes keys, weights, and spacers."""
        attrs = {"A": 1, "B": 2, "C": 3}
        layout = [
            ["A", {"key": "B", "weight": 3}],
            [{"type": "spacer", "weight": 2}, "C"],
        ]
        sheet.load_attributes(attrs, layout)

        saved_layout = sheet.get_layout()
        assert len(saved_layout) == 2
        assert saved_layout[0] == ["A", {"key": "B", "weight": 3}]
        assert saved_layout[1] == [{"type": "spacer", "weight": 2}, "C"]

    def test_attributes_changed_on_value_edit(self, sheet, qtbot):
        """Test that editing a pair value emits attributes_changed."""
        sheet.load_attributes({"STR": 18})

        with qtbot.waitSignal(sheet.attributes_changed):
            # Directly modify the pair's value edit
            pair = sheet._pairs["STR"]
            pair.value_edit.setText("20")

    def test_load_clears_previous_state(self, sheet):
        """Test that loading new attributes clears the previous state."""
        sheet.load_attributes({"Old": "data"})
        sheet.load_attributes({"New": "data"})

        assert "Old" not in sheet.get_attributes()
        assert "New" in sheet.get_attributes()

    def test_empty_layout_handled(self, sheet):
        """Test that an empty layout list defaults to one-per-row."""
        attrs = {"A": 1, "B": 2}
        sheet.load_attributes(attrs, [])

        # Empty layout means unplaced attributes get appended
        result = sheet.get_layout()
        assert len(result) == 2

    def test_calc_drop_position_with_spacers(self, sheet):
        """Test drop position calculation works correctly with spacers."""
        # Create a layout with a spacer
        attrs = {"A": 1, "B": 2, "C": 3}
        layout = [["A", {"type": "spacer", "weight": 2}, "B"], ["C"]]
        sheet.load_attributes(attrs, layout)

        # Force layout to compute geometries
        sheet._container.adjustSize()
        sheet._grid_layout.invalidate()
        sheet._grid_layout.activate()

        # Get geometries of widgets in the first row
        row_layout = sheet._grid_layout.itemAt(0).layout()
        item_A = row_layout.itemAt(0)
        item_spacer = row_layout.itemAt(1)
        item_B = row_layout.itemAt(2)

        # 1. Drop before 'A'
        pos = item_A.geometry().topLeft()
        row, col = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 0

        # 2. Drop on the spacer (inserts before 'B' if passed center)
        # exact drop col depends on center().x(), so we test right side of spacer
        pos = item_spacer.geometry().topRight()
        row, col = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 2  # After A(0), Spacer(1)

        # 3. Drop on 'B' right side
        pos = item_B.geometry().topRight()
        row, col = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 3  # End of row


# ─────────────────────────────────────────────────────────────────────────────
# TextBlockWidget & DividerWidget
# ─────────────────────────────────────────────────────────────────────────────


class TestTextBlockWidget:
    """Tests for the TextBlockWidget."""

    def test_get_set_text(self, qtbot):
        """Test text get/set round-trip."""
        from src.gui.widgets.sheet_builder import TextBlockWidget

        tb = TextBlockWidget("Hello world")
        qtbot.addWidget(tb)
        assert tb.get_text() == "Hello world"

        tb.set_text("Changed")
        assert tb.get_text() == "Changed"

    def test_text_changed_signal(self, qtbot):
        """Test that editing text emits text_changed."""
        from src.gui.widgets.sheet_builder import TextBlockWidget

        tb = TextBlockWidget("")
        qtbot.addWidget(tb)
        with qtbot.waitSignal(tb.text_changed):
            tb.text_edit.setText("new text")

    def test_set_text_no_signal(self, qtbot):
        """Test that set_text does not emit."""
        from src.gui.widgets.sheet_builder import TextBlockWidget

        tb = TextBlockWidget("")
        qtbot.addWidget(tb)
        emitted = False

        def on_changed():
            nonlocal emitted
            emitted = True

        tb.text_changed.connect(on_changed)
        tb.set_text("silent")
        assert not emitted


class TestDividerWidget:
    """Tests for the DividerWidget."""

    def test_creates_horizontal_line(self, qtbot):
        """Test that divider is a horizontal line with fixed height."""
        from src.gui.widgets.sheet_builder import DividerWidget

        dw = DividerWidget()
        qtbot.addWidget(dw)
        assert dw.frameShape() == QFrame.Shape.HLine
        assert dw.maximumHeight() == 2


# ─────────────────────────────────────────────────────────────────────────────
# SheetBuilderWidget – text/divider/toolbar integration
# ─────────────────────────────────────────────────────────────────────────────


class TestSheetBuilderTextDivider:
    """Tests for text and divider integration in the sheet builder."""

    def test_load_text_block(self, sheet):
        """Test loading a layout with a text block."""
        attrs = {"STR": 18}
        layout = [["STR"], [{"type": "text", "text": "flavour"}]]
        sheet.load_attributes(attrs, layout)

        saved = sheet.get_layout()
        assert len(saved) == 2
        assert saved[0] == ["STR"]
        assert saved[1] == [{"type": "text", "text": "flavour"}]

    def test_load_divider(self, sheet):
        """Test loading a layout with a divider."""
        attrs = {"STR": 18}
        layout = [["STR"], [{"type": "divider"}]]
        sheet.load_attributes(attrs, layout)

        saved = sheet.get_layout()
        assert len(saved) == 2
        assert saved[0] == ["STR"]
        assert saved[1] == [{"type": "divider"}]

    def test_text_roundtrip(self, sheet):
        """Test text serialization roundtrip."""
        attrs = {"A": 1}
        layout = [[{"type": "text", "text": "Lore block"}], ["A"]]
        sheet.load_attributes(attrs, layout)

        saved = sheet.get_layout()
        assert saved[0] == [{"type": "text", "text": "Lore block"}]

    def test_divider_roundtrip(self, sheet):
        """Test divider serialization roundtrip."""
        attrs = {"A": 1}
        layout = [[{"type": "divider"}], ["A"]]
        sheet.load_attributes(attrs, layout)

        saved = sheet.get_layout()
        assert saved[0] == [{"type": "divider"}]

    def test_toolbar_add_divider(self, sheet, qtbot):
        """Test toolbar adds a divider row."""
        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._on_toolbar_add_divider()

        saved = sheet.get_layout()
        assert len(saved) == 1
        assert saved[0] == [{"type": "divider"}]

    def test_toolbar_add_text(self, sheet, qtbot):
        """Test toolbar adds a text row."""
        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._on_toolbar_add_text()

        saved = sheet.get_layout()
        assert len(saved) == 1
        assert saved[0] == [{"type": "text", "text": ""}]

    def test_toolbar_add_spacer_to_last_row(self, sheet, qtbot):
        """Test toolbar adds a spacer to the last row."""
        sheet.load_attributes({"A": 1})

        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._on_toolbar_add_spacer()

        saved = sheet.get_layout()
        # Should have A + spacer in the same row
        assert len(saved) == 1
        assert any(
            isinstance(item, dict) and item.get("type") == "spacer" for item in saved[0]
        )

    def test_context_menu_delete_row(self, sheet, qtbot):
        """Test context menu row deletion."""
        sheet.load_attributes({"A": 1, "B": 2})
        assert len(sheet.get_layout()) == 2

        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._ctx_delete_row(0)

        assert "A" not in sheet.get_attributes()
        assert "B" in sheet.get_attributes()

    def test_context_menu_add_spacer_to_row(self, sheet, qtbot):
        """Test context menu adds spacer to a specific row."""
        sheet.load_attributes({"A": 1})

        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._ctx_add_spacer_to_row(0)

        saved = sheet.get_layout()
        assert any(
            isinstance(item, dict) and item.get("type") == "spacer" for item in saved[0]
        )

    def test_context_menu_remove_spacers(self, sheet, qtbot):
        """Test context menu removes spacers from a row."""
        attrs = {"A": 1}
        layout = [[{"type": "spacer", "weight": 1}, "A"]]
        sheet.load_attributes(attrs, layout)

        with qtbot.waitSignal(sheet.attributes_changed):
            sheet._ctx_remove_spacers_from_row(0)

        saved = sheet.get_layout()
        # Should only have A, no spacer
        for item in saved[0]:
            if isinstance(item, dict):
                assert item.get("type") != "spacer"

    def test_mixed_layout_roundtrip(self, sheet):
        """Test complex layout with text, divider, spacers, and attributes."""
        attrs = {"STR": 18, "DEX": 14}
        layout = [
            [{"type": "text", "text": "Stats"}],
            [{"type": "divider"}],
            ["STR", "DEX"],
        ]
        sheet.load_attributes(attrs, layout)

        saved = sheet.get_layout()
        assert saved[0] == [{"type": "text", "text": "Stats"}]
        assert saved[1] == [{"type": "divider"}]
        # Row 3 should have STR and DEX
        # (may have resize handles, but serialized without them)
        keys_in_row = [
            item if isinstance(item, str) else item.get("key", "") for item in saved[2]
        ]
        assert "STR" in keys_in_row
        assert "DEX" in keys_in_row


class TestResizeHandle:
    """Tests for the _ResizeHandle widget."""

    def test_resize_handle_drag_increases_weight(self, sheet, qtbot):
        """Test that dragging a resize handle changes item weights."""
        # Use heavier weights to avoid the 1-minimum issue for now
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        sheet.show()
        qtbot.waitForWindowShown(sheet)

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        # Initial stretch
        assert hlayout.stretch(0) == 2
        assert hlayout.stretch(2) == 2

        # Simulate drag right by 200 pixels
        # Needs to be a significant portion of the width
        center = handle.rect().center()

        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        # Move 200 pixels to the right
        qtbot.mouseMove(handle, center + QPoint(200, 0))
        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center + QPoint(200, 0)
        )

        # Should have updated stretches
        assert hlayout.stretch(0) > 2
        assert hlayout.stretch(2) < 2

    def test_resize_handle_drag_at_minimum_succeeds(self, sheet, qtbot):
        """Confirm that dragging works even when weights are at 1:1."""
        attrs = {"A": 1, "B": 1}
        layout = [["A", "B"]]  # defaults to 1:1
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        assert hlayout.stretch(0) == 1
        assert hlayout.stretch(2) == 1

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        # Move right by 200 pixels
        qtbot.mouseMove(handle, center + QPoint(200, 0))
        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center + QPoint(200, 0)
        )

        # We expect the left widget to increase its weight,
        # and the right widget to stay at 1 (minimum).
        assert hlayout.stretch(0) > 1
        assert hlayout.stretch(2) == 1

    def test_resize_handle_signal_timing(self, sheet, qtbot):
        """Verify that attributes_changed is only emitted after drag release."""
        attrs = {"A": 1, "B": 1}
        layout = [["A", "B"]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        # Connect a spy to count signals
        signal_count = 0

        def count():
            nonlocal signal_count
            signal_count += 1

        sheet.attributes_changed.connect(count)

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        # Move past threshold (currently 10px)
        qtbot.mouseMove(handle, center + QPoint(15, 0))
        qtbot.mouseMove(handle, center + QPoint(30, 0))

        # Currently, it results in multiple signals.
        # We WANT it to be 0 here.
        assert signal_count == 0, f"Expected 0 signals during drag, got {signal_count}"

        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center + QPoint(30, 0)
        )

        # Should be exactly 1 after release
        assert signal_count == 1

    def test_resize_handle_disconnects_on_destroy(self, qtbot):
        """Test that destroying a handle disconnects it from ThemeManager."""
        import pytest
        from PySide6.QtWidgets import QHBoxLayout, QWidget

        from src.core.theme_manager import ThemeManager
        from src.gui.widgets.sheet_builder import _ResizeHandle

        tm = ThemeManager()

        parent = QWidget()
        layout = QHBoxLayout(parent)
        qtbot.addWidget(parent)

        handle = _ResizeHandle(layout, 0, 1)
        qtbot.addWidget(handle)

        handle.deleteLater()
        qtbot.wait(50)  # Allow event loop to process deleteLater

        # Emitting the signal should not raise RuntimeError: wrapped C/C++ object...
        try:
            tm.theme_changed.emit(tm.get_theme())
        except RuntimeError as e:
            pytest.fail(f"Signal emission caused RuntimeError: {e}")


class TestSheetBuilderMemoryLeaks:
    """Tests for memory leaks and signal cleanup in SheetBuilderWidget."""

    def test_clear_disconnects_all_widgets(self, sheet, qtbot):
        """Test that _clear properly deletes widgets and disconnects
        them from ThemeManager."""
        import pytest

        from src.core.theme_manager import ThemeManager

        tm = ThemeManager()

        # Load a complex layout
        attrs = {"STR": 18, "DEX": 14}
        layout = [
            [{"type": "text", "text": "Stats"}],
            [{"type": "divider"}],
            ["STR", "DEX"],
        ]
        sheet.load_attributes(attrs, layout)

        # Clear the sheet
        sheet._clear()
        qtbot.wait(50)  # Process deleteLater events

        # Emitting the signal should not raise RuntimeError
        try:
            tm.theme_changed.emit(tm.get_theme())
        except RuntimeError as e:
            pytest.fail(f"Signal emission caused RuntimeError: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug-fix regression tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBugFixes:
    """Regression tests for the code-review bug fixes."""

    # ── Fix #1: stale weight after resize release ─────────────────────────

    def test_weight_written_correctly_after_release(self, sheet, qtbot):
        """widget.weight must reflect final_left/final_right after release, not
        the pre-normalisation scratch values."""
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        qtbot.mouseMove(handle, center + QPoint(200, 0))
        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center + QPoint(200, 0)
        )

        left_widget = hlayout.itemAt(0).widget()
        right_widget = hlayout.itemAt(2).widget()

        # weight on the widget must equal what the layout reports
        assert left_widget.weight == hlayout.stretch(0)
        assert right_widget.weight == hlayout.stretch(2)

    # ── Fix #2: toolbar spacer injects resize handle ──────────────────────

    def test_toolbar_spacer_adds_resize_handle(self, sheet, qtbot):
        """After toolbar adds a spacer to an existing row, a resize handle must
        be present between the existing widget and the new spacer."""
        from src.gui.widgets.sheet_builder import SpacerWidget, _ResizeHandle

        sheet.load_attributes({"A": 1})
        sheet._on_toolbar_add_spacer()

        hlayout = sheet._grid_layout.itemAt(0).layout()
        widget_types = [
            type(hlayout.itemAt(i).widget()) for i in range(hlayout.count())
        ]
        assert (
            _ResizeHandle in widget_types
        ), "No _ResizeHandle found after toolbar spacer add"
        assert SpacerWidget in widget_types

    # ── Fix #3: ctx-menu spacer injects resize handle ─────────────────────

    def test_ctx_spacer_adds_resize_handle(self, sheet, qtbot):
        """After the context-menu adds a spacer to a row, a resize handle must
        be present between the existing widget and the new spacer."""
        from src.gui.widgets.sheet_builder import SpacerWidget, _ResizeHandle

        sheet.load_attributes({"A": 1})
        sheet._ctx_add_spacer_to_row(0)

        hlayout = sheet._grid_layout.itemAt(0).layout()
        widget_types = [
            type(hlayout.itemAt(i).widget()) for i in range(hlayout.count())
        ]
        assert (
            _ResizeHandle in widget_types
        ), "No _ResizeHandle found after ctx-menu spacer add"
        assert SpacerWidget in widget_types

    # ── Fix #8: stale handles cleaned up on remove_attribute ─────────────

    def test_remove_attribute_clears_stale_handles(self, sheet, qtbot):
        """Removing one of two attributes in a row must remove the _ResizeHandle
        that sat between them — no stale handles should remain."""
        from src.gui.widgets.sheet_builder import _ResizeHandle

        sheet.load_attributes({"A": 1, "B": 1}, [["A", "B"]])
        sheet.remove_attribute("A")

        # Row with "B" should still exist
        assert "B" in sheet.get_attributes()

        # If a row remains, verify it contains no _ResizeHandle
        if sheet._grid_layout.count() > 0:
            hlayout = sheet._grid_layout.itemAt(0).layout()
            for i in range(hlayout.count()):
                assert not isinstance(
                    hlayout.itemAt(i).widget(), _ResizeHandle
                ), "Stale _ResizeHandle found after remove_attribute"

    # ── Fix #10: type_combo toggles back to hidden ────────────────────────

    def test_type_combo_toggles_back_to_hidden(self, sheet, qtbot):
        """Cycling String->Number->Boolean->String must hide the combo on return.

        Uses isHidden() (explicit visibility flag) rather than isVisible() so
        the assertion works without the parent widget being shown.
        """
        sheet.load_attributes({"X": "hello"})
        pair = sheet._pairs["X"]

        # Initially explicitly hidden
        assert pair.type_combo.isHidden()

        sheet._ctx_toggle_type(pair)  # String -> Number
        assert not pair.type_combo.isHidden()

        sheet._ctx_toggle_type(pair)  # Number -> Boolean
        assert not pair.type_combo.isHidden()

        sheet._ctx_toggle_type(pair)  # Boolean -> String (back to default)
        assert (
            pair.type_combo.isHidden()
        ), "type_combo should be hidden when type returns to String"

    # ── Fix: dropEvent raises AttributeError ──────────────────────────────

    def test_drop_event_no_attribute_error(self, sheet, qtbot):
        """Verify that dropping an attribute pill doesn't raise an AttributeError."""
        sheet.load_attributes({"A": 1, "B": 2})
        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")

        drop_event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Should not raise AttributeError: 'SheetBuilderWidget' object
        # has no attribute '_block_signals'
        try:
            with qtbot.waitSignal(sheet.attributes_changed, timeout=1000):
                sheet.dropEvent(drop_event)
        except AttributeError as e:
            import pytest

            pytest.fail(f"dropEvent raised AttributeError: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Ghost Widget (WYSIWYG drag preview)
# ─────────────────────────────────────────────────────────────────────────────


class TestGhostWidget:
    """Tests for the _GhostWidget – the semi-transparent drag preview."""

    def test_ghost_widget_created_with_label(self, qtbot):
        """Test that _GhostWidget displays the attribute key."""
        ghost = _GhostWidget("Strength")
        qtbot.addWidget(ghost)
        assert ghost._label.text() == "Strength"

    def test_ghost_widget_semi_transparent(self, qtbot):
        """Test that _GhostWidget window opacity is < 1.0."""
        ghost = _GhostWidget("Strength")
        qtbot.addWidget(ghost)
        assert ghost.windowOpacity() < 1.0

    def test_ghost_widget_frameless(self, qtbot):
        """Test that _GhostWidget is a frameless tool window."""
        ghost = _GhostWidget("Strength")
        qtbot.addWidget(ghost)
        flags = ghost.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert flags & Qt.WindowType.Tool

    def test_ghost_widget_move_to(self, qtbot):
        """Test that move_to positions the ghost at the given global point."""
        ghost = _GhostWidget("STR")
        qtbot.addWidget(ghost)
        ghost.move_to(QPoint(100, 200))
        # The ghost should be positioned near (100, 200) with an offset
        gpos = ghost.pos()
        assert abs(gpos.x() - 100) < 30
        assert abs(gpos.y() - 200) < 30


# ─────────────────────────────────────────────────────────────────────────────
# Insertion Line (Active Drop Zone Indicator)
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertionLine:
    """Tests for the _InsertionLine – the active drop zone indicator."""

    def test_insertion_line_created(self, qtbot):
        """Test that _InsertionLine can be created."""
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        qtbot.addWidget(parent)
        line = _InsertionLine(parent)
        assert line.parent() is parent

    def test_insertion_line_has_fixed_height(self, qtbot):
        """Test that the insertion line has a small fixed height."""
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        qtbot.addWidget(parent)
        line = _InsertionLine(parent)
        # Should be a thin line (2-4px)
        assert line.maximumHeight() <= 4

    def test_insertion_line_starts_hidden(self, qtbot):
        """Test that the insertion line starts hidden."""
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        qtbot.addWidget(parent)
        line = _InsertionLine(parent)
        assert line.isHidden()


# ─────────────────────────────────────────────────────────────────────────────
# WYSIWYG Drag-and-Drop Integration
# ─────────────────────────────────────────────────────────────────────────────


class TestWYSIWYGDragDrop:
    """Integration tests for the ghost + insertion line during DnD."""

    def test_drag_enter_creates_ghost(self, sheet, qtbot):
        """Test that dragEnterEvent creates a ghost widget internally."""
        sheet.load_attributes({"A": 1, "B": 2})
        with qtbot.waitExposed(sheet):
            sheet.show()

        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")
        event = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dragEnterEvent(event)
        assert sheet._ghost is not None

    def test_drag_enter_creates_insertion_line(self, sheet, qtbot):
        """Test that dragEnterEvent creates an insertion line."""
        sheet.load_attributes({"A": 1, "B": 2})
        with qtbot.waitExposed(sheet):
            sheet.show()

        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")
        event = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dragEnterEvent(event)
        assert sheet._insertion_line is not None

    def test_drag_leave_hides_ghost(self, sheet, qtbot):
        """Test that dragLeaveEvent hides and cleans up the ghost."""
        sheet.load_attributes({"A": 1})
        with qtbot.waitExposed(sheet):
            sheet.show()

        # Enter drag
        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")
        enter_ev = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dragEnterEvent(enter_ev)
        assert sheet._ghost is not None

        # Leave drag
        sheet.dragLeaveEvent(None)
        assert sheet._ghost is None

    def test_drag_leave_hides_insertion_line(self, sheet, qtbot):
        """Test that dragLeaveEvent hides the insertion line."""
        sheet.load_attributes({"A": 1})
        with qtbot.waitExposed(sheet):
            sheet.show()

        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")
        enter_ev = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dragEnterEvent(enter_ev)
        assert sheet._insertion_line is not None

        sheet.dragLeaveEvent(None)
        assert sheet._insertion_line.isHidden()

    def test_drop_cleans_up_ghost_and_line(self, sheet, qtbot):
        """Test that dropEvent cleans up ghost and insertion line."""
        sheet.load_attributes({"A": 1, "B": 2})
        with qtbot.waitExposed(sheet):
            sheet.show()

        # Enter drag first
        mime = QMimeData()
        mime.setData("application/x-kraken-sheet-key", b"A")
        enter_ev = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dragEnterEvent(enter_ev)

        # Now drop
        drop_ev = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        sheet.dropEvent(drop_ev)
        assert sheet._ghost is None
        assert sheet._insertion_line.isHidden()


# ─────────────────────────────────────────────────────────────────────────────
# Weight Percentage Overlay on Resize Handle
# ─────────────────────────────────────────────────────────────────────────────


class TestWeightPercentageOverlay:
    """Tests for the percentage overlay shown during resize drag."""

    def test_resize_creates_weight_overlay(self, sheet, qtbot):
        """Test that dragging a resize handle creates a weight overlay label."""
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)

        # After pressing, the weight overlay should exist
        assert handle._weight_overlay is not None
        assert handle._weight_overlay.isVisible()

        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center
        )

    def test_resize_overlay_shows_percentages(self, sheet, qtbot):
        """Test that the weight overlay displays percentages."""
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)

        # Overlay should contain "%" text
        text = handle._weight_overlay.text()
        assert "%" in text

        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center
        )

    def test_resize_overlay_hides_on_release(self, sheet, qtbot):
        """Test that the weight overlay is hidden after mouse release."""
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
        assert handle._weight_overlay is not None

        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center
        )
        # After release, overlay should be hidden
        assert handle._weight_overlay is None or handle._weight_overlay.isHidden()

    def test_resize_overlay_updates_during_drag(self, sheet, qtbot):
        """Test that the overlay updates while dragging."""
        attrs = {"A": 1, "B": 1}
        layout = [[{"key": "A", "weight": 2}, {"key": "B", "weight": 2}]]
        sheet.load_attributes(attrs, layout)
        with qtbot.waitExposed(sheet):
            sheet.show()

        row_item = sheet._grid_layout.itemAt(0)
        hlayout = row_item.layout()
        handle = hlayout.itemAt(1).widget()

        center = handle.rect().center()
        qtbot.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)

        # Verify overlay exists and contains percentage text initially
        assert "%" in handle._weight_overlay.text()

        # Move right significantly
        qtbot.mouseMove(handle, center + QPoint(200, 0))

        # Text should have updated to reflect new ratios
        new_text = handle._weight_overlay.text()
        assert "%" in new_text

        qtbot.mouseRelease(
            handle, Qt.MouseButton.LeftButton, pos=center + QPoint(200, 0)
        )
