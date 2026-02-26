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

    def test_hover_styling(self, pair):
        """Test that the widget has hover styling applied with the primary color."""
        # We want the entire AttributePairWidget to lightly border or highlight on hover
        # Or just checking that :hover is in the stylesheet
        theme = pair._theme_mgr.get_theme()
        primary = theme.get("primary", "#FF9900")

        stylesheet = pair.styleSheet()
        assert "AttributePairWidget:hover" in stylesheet
        assert primary in stylesheet

    def test_label_is_transparent_to_mouse_events(self, pair):
        """Test that the key label ignores mouse events to allow dragging."""
        assert pair.key_label.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )


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
        pos = item_A.geometry().center()
        pos.setX(item_A.geometry().left() + 2)
        pos = sheet.mapFrom(sheet._container, pos)
        row, col, new_row = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 0
        assert not new_row

        # 2. Drop on the spacer (inserts before 'B' if passed center)
        # exact drop col depends on center().x(), so we test right side of spacer
        pos = item_spacer.geometry().center()
        pos.setX(item_spacer.geometry().right() - 2)
        pos = sheet.mapFrom(sheet._container, pos)
        row, col, new_row = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 2  # After A(0), Spacer(1)
        assert not new_row

        # 3. Drop on 'B' right side
        pos = item_B.geometry().center()
        pos.setX(item_B.geometry().right() - 2)
        pos = sheet.mapFrom(sheet._container, pos)
        row, col, new_row = sheet._calc_drop_position(pos)
        assert row == 0
        assert col == 3
        assert not new_row  # End of row

    def test_row_accepts_columns(self, sheet, qtbot):
        """Test that Text and Divider rows reject new columns."""
        sheet.load_attributes(
            {"A": 1},
            [
                ["A"],
                [{"type": "text", "text": "Test"}],
                [{"type": "divider"}],
            ],
        )
        with qtbot.waitExposed(sheet):
            sheet.show()

        layout_a = sheet._grid_layout.itemAt(0).layout()
        layout_text = sheet._grid_layout.itemAt(1).layout()
        layout_divider = sheet._grid_layout.itemAt(2).layout()

        assert sheet._row_accepts_columns(layout_a) is True
        assert sheet._row_accepts_columns(layout_text) is False
        assert sheet._row_accepts_columns(layout_divider) is False

    def test_calc_drop_position_forces_new_row_on_special_rows(self, sheet, qtbot):
        """Test that dropping on a Text or Divider row forces insert_as_new_row=True."""
        sheet.load_attributes(
            {"A": 1},
            [
                ["A"],
                [{"type": "text", "text": "Test"}],
            ],
        )
        with qtbot.waitExposed(sheet):
            sheet.show()

        # Force layout update to ensure geometry is valid
        sheet._grid_layout.invalidate()
        sheet._grid_layout.activate()

        text_item = sheet._grid_layout.itemAt(1).layout().itemAt(0).widget()

        # Dropping on the top half of the text block targets row 1 (above text)
        # Use mapToGlobal/mapFromGlobal for correct mapping between
        # _container (inside scroll area) and the sheet widget.
        top_pos = text_item.geometry().center()
        top_pos.setY(text_item.geometry().top() + 2)
        top_pos = sheet.mapFromGlobal(sheet._container.mapToGlobal(top_pos))
        row, col, new_row = sheet._calc_drop_position(top_pos)
        assert row == 1
        assert new_row is True

        # Dropping on the bottom half of the text block targets row 2 (below text)
        bot_pos = text_item.geometry().center()
        bot_pos.setY(text_item.geometry().bottom() - 2)
        bot_pos = sheet.mapFromGlobal(sheet._container.mapToGlobal(bot_pos))
        row, col, new_row = sheet._calc_drop_position(bot_pos)
        assert row == 2
        assert new_row is True


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

    def test_hover_styling(self, qtbot):
        """Test that the text block widget has hover styling applied."""
        from src.gui.widgets.sheet_builder import TextBlockWidget

        tb = TextBlockWidget("")
        qtbot.addWidget(tb)

        theme = tb._theme_mgr.get_theme()
        primary = theme.get("primary", "#FF9900")

        stylesheet = tb.styleSheet()
        # Needs StyledPanel for border, and hover state
        assert tb.frameShape() == QFrame.Shape.StyledPanel
        assert "TextBlockWidget:hover" in stylesheet
        assert primary in stylesheet


class TestDividerWidget:
    """Tests for the DividerWidget."""

    def test_creates_horizontal_line(self, qtbot):
        """Test that divider is a horizontal line with fixed height."""
        from src.gui.widgets.sheet_builder import DividerWidget

        dw = DividerWidget()
        qtbot.addWidget(dw)
        assert dw.frameShape() == QFrame.Shape.HLine
        assert dw.maximumHeight() == 2

    def test_hover_styling(self, qtbot):
        """Test that the divider widget has hover styling applied."""
        from src.gui.widgets.sheet_builder import DividerWidget

        dw = DividerWidget()
        qtbot.addWidget(dw)

        theme = dw._theme_mgr.get_theme()
        primary = theme.get("primary", "#FF9900")

        stylesheet = dw.styleSheet()
        assert "DividerWidget:hover" in stylesheet
        assert primary in stylesheet


class TestSpacerWidget:
    """Tests for the SpacerWidget."""

    def test_hover_styling(self, qtbot):
        """Test that the spacer widget has hover styling applied."""
        from src.gui.widgets.sheet_builder import SpacerWidget

        sw = SpacerWidget()
        qtbot.addWidget(sw)

        theme = sw._theme_mgr.get_theme()
        primary = theme.get("primary", "#FF9900")

        stylesheet = sw.styleSheet()
        assert "SpacerWidget:hover" in stylesheet
        assert primary in stylesheet


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

        # A should have gained weight, B should have lost weight
        assert hlayout.stretch(0) > hlayout.stretch(2), (
            f"Expected A > B after dragging right, got "
            f"A={hlayout.stretch(0)}, B={hlayout.stretch(2)}"
        )

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

        # A should have gained weight relative to B
        assert hlayout.stretch(0) > hlayout.stretch(2), (
            f"Expected A > B after dragging right, got "
            f"A={hlayout.stretch(0)}, B={hlayout.stretch(2)}"
        )

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

    def test_hover_styling(self, qtbot):
        """Test that the resize handle has hover styling with primary color."""
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from src.gui.widgets.sheet_builder import _ResizeHandle

        parent = QWidget()
        layout = QHBoxLayout(parent)
        qtbot.addWidget(parent)

        handle = _ResizeHandle(layout, 0, 1)
        qtbot.addWidget(handle)

        theme = handle._theme_mgr.get_theme()
        primary = theme.get("primary", "#FF9900")

        stylesheet = handle.styleSheet()
        assert "_ResizeHandle:hover" in stylesheet
        assert primary in stylesheet
        # Ensure it doesn't just use border color on hover anymore
        border = theme.get("border", "#333333")
        assert f"background-color: {border};" not in stylesheet

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
# Focus Preservation During Reload
# ─────────────────────────────────────────────────────────────────────────────


class TestFocusPreservation:
    """Tests for focus and scroll preservation during load_attributes reload."""

    def test_load_preserves_focused_key(self, sheet, qtbot):
        """After reload, if user was editing key 'B', focus should return to 'B'."""
        from PySide6.QtWidgets import QApplication

        attrs = {"A": "1", "B": "2", "C": "3"}
        layout = [["A", "B", "C"]]
        sheet.load_attributes(attrs, layout)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        # Focus the value edit of key 'B'
        pair_b = sheet._pairs["B"]
        pair_b.value_edit.setFocus()
        pair_b.value_edit.setCursorPosition(1)
        QApplication.processEvents()

        # Reload with same data (simulates autosave reload)
        sheet.load_attributes(attrs, layout)
        QApplication.processEvents()

        # After reload, the new 'B' widget's value_edit should have focus
        new_pair_b = sheet._pairs["B"]
        assert new_pair_b.value_edit.hasFocus()

    def test_load_preserves_cursor_position(self, sheet, qtbot):
        """Cursor position within the value edit is preserved after reload."""
        from PySide6.QtWidgets import QApplication

        attrs = {"Name": "Hello World"}
        sheet.load_attributes(attrs)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        pair = sheet._pairs["Name"]
        pair.value_edit.setFocus()
        pair.value_edit.setCursorPosition(5)  # After "Hello"
        QApplication.processEvents()

        sheet.load_attributes(attrs)
        QApplication.processEvents()

        new_pair = sheet._pairs["Name"]
        assert new_pair.value_edit.hasFocus()
        assert new_pair.value_edit.cursorPosition() == 5

    def test_load_preserves_scroll_position(self, sheet, qtbot):
        """Scroll position of the sheet is preserved after reload."""
        # Create many rows to enable scrolling
        attrs = {f"Attr{i}": str(i) for i in range(20)}
        sheet.load_attributes(attrs)
        sheet.resize(300, 200)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        # Scroll down
        scrollbar = sheet._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() // 2)
        saved_scroll = scrollbar.value()

        # Reload
        sheet.load_attributes(attrs)

        # Scroll position should be restored
        assert sheet._scroll.verticalScrollBar().value() == saved_scroll

    def test_load_handles_missing_key_gracefully(self, sheet, qtbot):
        """If focused key no longer exists after reload, no crash occurs."""
        from PySide6.QtWidgets import QApplication

        attrs = {"A": "1", "B": "2"}
        sheet.load_attributes(attrs)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        pair_b = sheet._pairs["B"]
        pair_b.value_edit.setFocus()
        QApplication.processEvents()

        # Reload without 'B'
        sheet.load_attributes({"A": "1"})

        # Should not crash; focus goes somewhere reasonable (or nowhere)
        assert "B" not in sheet._pairs

    def test_load_no_focus_when_sheet_unfocused(self, sheet, qtbot):
        """If no widget in the sheet had focus, no focus is forced after reload."""
        attrs = {"A": "1", "B": "2"}
        sheet.load_attributes(attrs)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        # Don't focus anything in the sheet
        # Reload
        sheet.load_attributes(attrs)

        # No pair should have forced focus
        for pair in sheet._pairs.values():
            assert not pair.value_edit.hasFocus()

    def test_load_preserves_text_block_focus(self, sheet, qtbot):
        """Focus in a TextBlockWidget is preserved across reload."""
        from PySide6.QtWidgets import QApplication

        attrs = {"A": "1"}
        layout = [["A"], [{"type": "text", "text": "some lore"}]]
        sheet.load_attributes(attrs, layout)
        sheet.show()
        sheet.activateWindow()
        qtbot.waitExposed(sheet)

        # Find the text block and focus it
        from src.gui.widgets.sheet_builder import TextBlockWidget

        text_block = None
        for row_idx in range(sheet._grid_layout.count()):
            row_item = sheet._grid_layout.itemAt(row_idx)
            if row_item and row_item.layout():
                hlayout = row_item.layout()
                for col_idx in range(hlayout.count()):
                    item = hlayout.itemAt(col_idx)
                    if item and isinstance(item.widget(), TextBlockWidget):
                        text_block = item.widget()
                        break
        assert text_block is not None
        text_block.text_edit.setFocus()
        text_block.text_edit.setCursorPosition(4)
        QApplication.processEvents()

        # Reload
        sheet.load_attributes(attrs, layout)
        QApplication.processEvents()

        # Find new text block and verify focus
        new_text_block = None
        for row_idx in range(sheet._grid_layout.count()):
            row_item = sheet._grid_layout.itemAt(row_idx)
            if row_item and row_item.layout():
                hlayout = row_item.layout()
                for col_idx in range(hlayout.count()):
                    item = hlayout.itemAt(col_idx)
                    if item and isinstance(item.widget(), TextBlockWidget):
                        new_text_block = item.widget()
                        break
        assert new_text_block is not None
        assert new_text_block.text_edit.hasFocus()
        assert new_text_block.text_edit.cursorPosition() == 4
