"""Unit tests for the Sheet Builder Widget.

Tests the SheetBuilderWidget and AttributePairWidget for:
- Attribute creation with Universal String default
- Layout serialization (2D list of key strings)
- Loading attributes with and without layout
- Value parsing by type (String, Number, Boolean)
- Add/remove attribute operations
"""

import pytest

from src.gui.widgets.sheet_builder import AttributePairWidget, SheetBuilderWidget

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

    def test_key_property(self, pair):
        """Test that the key property returns the attribute key."""
        assert pair.key == "Strength"

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
