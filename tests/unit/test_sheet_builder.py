"""Unit tests for the Sheet Builder Widget.

Tests the SheetBuilderWidget and AttributePairWidget for:
- Attribute creation with Universal String default
- Layout serialization (2D list of key strings)
- Loading attributes with and without layout
- Value parsing by type (String, Number, Boolean)
- Add/remove attribute operations
"""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame

from src.gui.widgets.sheet_builder import (
    AttributePairWidget,
    SheetBuilderWidget,
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
        assert row3.itemAt(0).spacerItem() is not None
        assert row3.stretch(0) == 1
        # Find the Intelligence widget (may be at index 1 or 2 depending on resize handle)
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
        # Row 3 should have STR and DEX (may have resize handles, but serialized without them)
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
        sheet.show()
        qtbot.waitForWindowShown(sheet)

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
        sheet.show()
        qtbot.waitForWindowShown(sheet)

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
