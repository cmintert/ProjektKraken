"""
Unit tests for CompactDateWidget.

Tests cover:
- Basic functionality (set/get value)
- Calendar-aware month dropdown population
- Day dropdown adjustment based on month
- Time handling
- Edge cases (negative years, month boundaries, year variants)
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from PySide6.QtWidgets import QApplication

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    CalendarDate,
    MonthDefinition,
    WeekDefinition,
)


@pytest.fixture
def app(qtbot):
    """Ensure QApplication exists."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def standard_calendar():
    """Standard 12-month calendar with varying days."""
    months = [
        MonthDefinition(name="January", abbreviation="Jan", days=31),
        MonthDefinition(name="February", abbreviation="Feb", days=28),
        MonthDefinition(name="March", abbreviation="Mar", days=31),
        MonthDefinition(name="April", abbreviation="Apr", days=30),
        MonthDefinition(name="May", abbreviation="May", days=31),
        MonthDefinition(name="June", abbreviation="Jun", days=30),
        MonthDefinition(name="July", abbreviation="Jul", days=31),
        MonthDefinition(name="August", abbreviation="Aug", days=31),
        MonthDefinition(name="September", abbreviation="Sep", days=30),
        MonthDefinition(name="October", abbreviation="Oct", days=31),
        MonthDefinition(name="November", abbreviation="Nov", days=30),
        MonthDefinition(name="December", abbreviation="Dec", days=31),
    ]
    week = WeekDefinition(
        day_names=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        day_abbreviations=["M", "T", "W", "Th", "F", "Sa", "Su"],
    )
    config = CalendarConfig(
        id="std",
        name="Standard",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="AD",
    )
    return CalendarConverter(config)


@pytest.fixture
def fantasy_calendar():
    """Fantasy calendar with 10 months of varying lengths."""
    months = [
        MonthDefinition(name="Hammer", abbreviation="Ham", days=30),
        MonthDefinition(name="Alturiak", abbreviation="Alt", days=30),
        MonthDefinition(name="Ches", abbreviation="Che", days=30),
        MonthDefinition(name="Tarsakh", abbreviation="Tar", days=30),
        MonthDefinition(name="Mirtul", abbreviation="Mir", days=30),
        MonthDefinition(name="Kythorn", abbreviation="Kyt", days=30),
        MonthDefinition(name="Flamerule", abbreviation="Fla", days=30),
        MonthDefinition(name="Eleasis", abbreviation="Ele", days=30),
        MonthDefinition(name="Eleint", abbreviation="Eli", days=30),
        MonthDefinition(name="Nightal", abbreviation="Nig", days=30),
    ]
    week = WeekDefinition(
        day_names=["First", "Second", "Third", "Fourth", "Fifth"],
        day_abbreviations=["1", "2", "3", "4", "5"],
    )
    config = CalendarConfig(
        id="fantasy",
        name="Forgotten Realms",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="DR",
    )
    return CalendarConverter(config)


class TestCompactDateWidgetBasics:
    """Basic functionality tests."""

    def test_widget_initializes(self, qtbot, standard_calendar):
        """Widget should initialize without errors."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        qtbot.addWidget(widget)
        assert widget is not None

    def test_set_get_value_roundtrip(self, qtbot, standard_calendar):
        """Setting a value should be retrievable."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Set to Year 1, Month 1, Day 1 (float = 0.0)
        widget.set_value(0.0)
        assert abs(widget.get_value() - 0.0) < 0.001

    def test_set_value_updates_display(self, qtbot, standard_calendar):
        """Setting value should update spinboxes/dropdowns."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # 31 days (January) = float 31.0 -> Feb 1
        widget.set_value(31.0)

        assert widget.spin_year.value() == 1
        assert widget.combo_month.currentIndex() == 1  # February (0-indexed)
        assert widget.combo_day.currentIndex() == 0  # Day 1 (0-indexed)

    def test_value_changed_signal_emitted(self, qtbot, standard_calendar):
        """Changing input should emit value_changed signal."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        widget.set_value(0.0)

        # Change year
        with qtbot.waitSignal(widget.value_changed, timeout=1000):
            widget.spin_year.setValue(2)


class TestCompactDateWidgetCalendarAwareness:
    """Tests for calendar-aware behavior."""

    def test_month_dropdown_populated_from_calendar(self, qtbot, fantasy_calendar):
        """Month dropdown should show calendar-specific month names."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(fantasy_calendar)
        qtbot.addWidget(widget)

        # Check month names
        month_names = [
            widget.combo_month.itemText(i) for i in range(widget.combo_month.count())
        ]
        assert "Hammer" in month_names
        assert "Nightal" in month_names
        assert len(month_names) == 10

    def test_day_dropdown_adjusts_to_month(self, qtbot, standard_calendar):
        """Day dropdown count should change based on selected month."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Select January (31 days)
        widget.combo_month.setCurrentIndex(0)
        assert widget.combo_day.count() == 31

        # Select February (28 days)
        widget.combo_month.setCurrentIndex(1)
        assert widget.combo_day.count() == 28

        # Select April (30 days)
        widget.combo_month.setCurrentIndex(3)
        assert widget.combo_day.count() == 30

    def test_fantasy_calendar_months(self, qtbot, fantasy_calendar):
        """Fantasy calendar should work with non-standard months."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(fantasy_calendar)
        qtbot.addWidget(widget)

        # All months have 30 days in fantasy calendar
        for i in range(10):
            widget.combo_month.setCurrentIndex(i)
            assert widget.combo_day.count() == 30


class TestCompactDateWidgetEdgeCases:
    """Edge case and boundary tests."""

    def test_negative_year(self, qtbot, standard_calendar):
        """Widget should handle negative years (pre-Epoch)."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # -365 = approximately Year 0
        widget.set_value(-365.0)
        assert widget.spin_year.value() == 0

    def test_large_year(self, qtbot, standard_calendar):
        """Widget should handle large year values."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Set to year 9999
        widget.spin_year.setValue(9999)
        # Year spinbox should preserve the value
        assert widget.spin_year.value() == 9999

    def test_month_boundary_transition(self, qtbot, standard_calendar):
        """Changing month should preserve valid day or adjust if out of range."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Set to Jan 31
        widget.spin_year.setValue(1)
        widget.combo_month.setCurrentIndex(0)  # January
        widget.combo_day.setCurrentIndex(30)  # Day 31 (0-indexed)

        # Switch to February (28 days) - day should clamp to 28
        widget.combo_month.setCurrentIndex(1)  # February
        assert widget.combo_day.currentIndex() <= 27  # Day 28 or less

    def test_no_converter_fallback(self, qtbot):
        """Widget should have fallback behavior without converter."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        qtbot.addWidget(widget)

        # Should not crash
        widget.set_value(100.0)
        value = widget.get_value()
        assert value >= 0  # Some sensible default

    def test_time_fraction_preserved(self, qtbot, standard_calendar):
        """Time fraction should be preserved when set."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Set to noon on day 1 (0.5 fraction)
        widget.set_value(0.5)

        # Get value and check fraction is preserved (approximately)
        value = widget.get_value()
        fraction = value - int(value)
        assert abs(fraction - 0.5) < 0.01 or widget.spin_hour.value() == 12

    def test_year_zero(self, qtbot, standard_calendar):
        """Year 0 should be handled correctly."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        widget.spin_year.setValue(0)
        assert widget.spin_year.value() == 0


class TestCompactDateWidgetCalendarPopup:
    """Tests for calendar popup functionality."""

    def test_calendar_button_exists(self, qtbot, standard_calendar):
        """Widget should have a calendar popup button."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)
        widget.show()

        assert hasattr(widget, "btn_calendar")
        # Button exists and is part of widget
        assert widget.btn_calendar is not None

    def test_calendar_popup_opens(self, qtbot, standard_calendar):
        """Clicking calendar button should open popup."""
        from src.gui.widgets.compact_date_widget import CompactDateWidget

        widget = CompactDateWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Click button (test that it doesn't crash)
        widget.btn_calendar.click()
        # If popup is modal, it would block, so we test non-modal or mock
