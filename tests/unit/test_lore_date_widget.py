"""
Unit tests for LoreDateWidget.

Tests the structured date input widget that provides Year/Month/Day dropdowns
with fallback to raw float input.
"""

import pytest

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)


@pytest.fixture
def simple_calendar() -> CalendarConfig:
    """A simple test calendar with 12 months of 30 days each."""
    months = [
        MonthDefinition(name=f"Month{i+1}", abbreviation=f"M{i+1}", days=30)
        for i in range(12)
    ]
    week = WeekDefinition(
        day_names=["Day1", "Day2", "Day3", "Day4", "Day5", "Day6", "Day7"],
        day_abbreviations=["D1", "D2", "D3", "D4", "D5", "D6", "D7"],
    )
    return CalendarConfig(
        id="test-simple",
        name="Simple Calendar",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="SE",
    )


@pytest.fixture
def variable_month_calendar() -> CalendarConfig:
    """A calendar with variable month lengths (28, 30, 31 days)."""
    months = [
        MonthDefinition(name="January", abbreviation="Jan", days=31),
        MonthDefinition(name="February", abbreviation="Feb", days=28),
        MonthDefinition(name="March", abbreviation="Mar", days=31),
        MonthDefinition(name="April", abbreviation="Apr", days=30),
    ]
    week = WeekDefinition(
        day_names=["Sunday", "Monday", "Tuesday", "Wednesday"],
        day_abbreviations=["Su", "Mo", "Tu", "We"],
    )
    return CalendarConfig(
        id="test-variable",
        name="Variable Calendar",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="AD",
    )


@pytest.fixture
def converter(simple_calendar) -> CalendarConverter:
    """CalendarConverter for the simple calendar."""
    return CalendarConverter(simple_calendar)


@pytest.fixture
def variable_converter(variable_month_calendar) -> CalendarConverter:
    """CalendarConverter for the variable month calendar."""
    return CalendarConverter(variable_month_calendar)


class TestLoreDateWidgetBasic:
    """Basic functionality tests."""

    def test_widget_initializes_without_calendar(self, qtbot):
        """Test widget can be created without a calendar (raw mode only)."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)

        # Should be in raw mode by default when no calendar
        assert widget.get_value() == 0.0

    def test_set_calendar_enables_structured_mode(self, qtbot, converter):
        """Test that setting a calendar enables structured input."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Year combo should have items
        assert widget._year_spin.isEnabled()
        # Month combo should have 12 items
        assert widget._month_combo.count() == 12

    def test_month_combo_shows_month_names(self, qtbot, converter):
        """Test that month dropdown shows correct month names."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Check first and last month names
        assert widget._month_combo.itemText(0) == "Month1"
        assert widget._month_combo.itemText(11) == "Month12"


class TestLoreDateWidgetValueRoundTrip:
    """Round-trip conversion tests."""

    def test_set_value_updates_structured_fields(self, qtbot, converter):
        """Test that set_value correctly updates Year/Month/Day fields."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Set to Year 2, Month 3, Day 15 (float = 360 + 60 + 14 = 434)
        widget.set_value(434.0)

        assert widget._year_spin.value() == 2
        assert widget._month_combo.currentIndex() == 2  # 0-indexed, so Month3
        assert widget._day_combo.currentIndex() == 14  # 0-indexed, so Day 15

    def test_get_value_returns_correct_float(self, qtbot, converter):
        """Test that structured fields produce correct float."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Set Year 1, Month 1, Day 1 directly
        widget._year_spin.setValue(1)
        widget._month_combo.setCurrentIndex(0)
        widget._day_combo.setCurrentIndex(0)

        assert widget.get_value() == pytest.approx(0.0)

    def test_round_trip_consistency(self, qtbot, converter):
        """Test set_value -> get_value returns same float (including time)."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Test values including some with time fractions (on 5-minute boundaries)
        # 0.5 = 12:00 (noon), 0.25 = 06:00, 0.75 = 18:00
        test_values = [0.0, 1.0, 30.0, 360.0, 720.5, 1000.25]
        for val in test_values:
            widget.set_value(val)
            result = widget.get_value()
            # Allow some tolerance due to 5-minute interval rounding
            assert result == pytest.approx(val, abs=0.02), f"Failed for {val}"


class TestLoreDateWidgetDayRange:
    """Tests for day dropdown range updates."""

    def test_day_combo_has_correct_count(self, qtbot, converter):
        """Test day combo has correct number of days for month."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # All months have 30 days in simple calendar
        assert widget._day_combo.count() == 30

    def test_day_combo_updates_on_month_change(self, qtbot, variable_converter):
        """Test day combo count updates when month changes."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(variable_converter)

        # January has 31 days
        widget._month_combo.setCurrentIndex(0)
        assert widget._day_combo.count() == 31

        # February has 28 days
        widget._month_combo.setCurrentIndex(1)
        assert widget._day_combo.count() == 28

        # April has 30 days
        widget._month_combo.setCurrentIndex(3)
        assert widget._day_combo.count() == 30

    def test_day_selection_preserved_when_valid(self, qtbot, variable_converter):
        """Test that day selection is preserved when changing to month with enough days."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(variable_converter)

        # Set to January 15
        widget._month_combo.setCurrentIndex(0)
        widget._day_combo.setCurrentIndex(14)  # Day 15

        # Switch to March (31 days) - should keep Day 15
        widget._month_combo.setCurrentIndex(2)
        assert widget._day_combo.currentIndex() == 14

    def test_day_clamped_when_exceeds_month(self, qtbot, variable_converter):
        """Test that day is clamped when changing to shorter month."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(variable_converter)

        # Set to January 31
        widget._month_combo.setCurrentIndex(0)
        widget._day_combo.setCurrentIndex(30)  # Day 31

        # Switch to February (28 days) - should clamp to Day 28
        widget._month_combo.setCurrentIndex(1)
        assert widget._day_combo.currentIndex() == 27  # Day 28


class TestLoreDateWidgetRawMode:
    """Tests for raw float mode toggle."""

    def test_raw_mode_toggle_shows_spinbox(self, qtbot, converter):
        """Test that enabling raw mode shows the float spinbox."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        # Initially structured mode should be visible (use isHidden to check widget's
        # own visibility flag, as isVisible() also checks parent visibility)
        assert not widget._year_spin.isHidden()
        assert not widget._month_combo.isHidden()
        assert not widget._day_combo.isHidden()
        assert not widget._hour_combo.isHidden()
        assert not widget._minute_combo.isHidden()
        assert widget._raw_spin.isHidden()

        # Toggle to raw mode
        widget._raw_toggle.setChecked(True)

        assert widget._year_spin.isHidden()
        assert widget._month_combo.isHidden()
        assert widget._day_combo.isHidden()
        assert widget._hour_combo.isHidden()
        assert widget._minute_combo.isHidden()
        assert not widget._raw_spin.isHidden()

    def test_raw_mode_preserves_value(self, qtbot, converter):
        """Test that toggling to raw mode preserves the current value."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        widget.set_value(100.0)
        widget._raw_toggle.setChecked(True)

        assert widget._raw_spin.value() == pytest.approx(100.0)

    def test_structured_mode_from_raw_preserves_value(self, qtbot, converter):
        """Test that toggling back to structured mode preserves value."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        widget._raw_toggle.setChecked(True)
        widget._raw_spin.setValue(50.0)
        widget._raw_toggle.setChecked(False)

        assert widget.get_value() == pytest.approx(50.0, abs=0.5)


class TestLoreDateWidgetSignals:
    """Tests for signal emission."""

    def test_value_changed_emitted_on_year_change(self, qtbot, converter):
        """Test value_changed signal emitted when year changes."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        signal_received = []
        widget.value_changed.connect(lambda v: signal_received.append(v))

        widget._year_spin.setValue(2)

        assert len(signal_received) > 0

    def test_value_changed_emitted_on_month_change(self, qtbot, converter):
        """Test value_changed signal emitted when month changes."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        signal_received = []
        widget.value_changed.connect(lambda v: signal_received.append(v))

        widget._month_combo.setCurrentIndex(5)

        assert len(signal_received) > 0

    def test_value_changed_emitted_on_day_change(self, qtbot, converter):
        """Test value_changed signal emitted when day changes."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        signal_received = []
        widget.value_changed.connect(lambda v: signal_received.append(v))

        widget._day_combo.setCurrentIndex(10)

        assert len(signal_received) > 0


class TestLoreDateWidgetPreview:
    """Tests for formatted date preview."""

    def test_preview_shows_formatted_date(self, qtbot, converter):
        """Test that preview label shows formatted date."""
        from src.gui.widgets.lore_date_widget import LoreDateWidget

        widget = LoreDateWidget()
        qtbot.addWidget(widget)
        widget.set_calendar_converter(converter)

        widget.set_value(0.0)  # Year 1, Month1, Day 1

        # Preview should contain year and month info
        preview_text = widget._preview_label.text()
        assert "1" in preview_text  # Year 1
        assert "Month1" in preview_text or "M1" in preview_text
