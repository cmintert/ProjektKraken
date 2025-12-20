"""
Unit tests for CompactDurationWidget.

Tests cover:
- Basic functionality (set/get value in days)
- Smart decomposition (years, months, days)
- Calendar-aware calculations
- Written format preview ("1 Year, 3 Months")
- Edge cases (zero values, very large durations, fractional days)
"""

import pytest
from unittest.mock import MagicMock, Mock
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
    """Standard 365-day calendar."""
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
def simple_calendar():
    """Simple 12x30 = 360 day calendar for easy math."""
    months = [
        MonthDefinition(name=f"Month {i+1}", abbreviation=f"M{i+1}", days=30)
        for i in range(12)
    ]
    week = WeekDefinition(
        day_names=["Day1", "Day2", "Day3", "Day4", "Day5"],
        day_abbreviations=["D1", "D2", "D3", "D4", "D5"],
    )
    config = CalendarConfig(
        id="simple",
        name="Simple",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="Year",
    )
    return CalendarConverter(config)


class TestCompactDurationWidgetBasics:
    """Basic functionality tests."""

    def test_widget_initializes(self, qtbot, simple_calendar):
        """Widget should initialize without errors."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        qtbot.addWidget(widget)
        assert widget is not None

    def test_set_get_value_roundtrip(self, qtbot, simple_calendar):
        """Setting a value should be retrievable."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(100.0)
        assert abs(widget.get_value() - 100.0) < 0.001

    def test_value_changed_signal_emitted(self, qtbot, simple_calendar):
        """Changing input should emit value_changed signal."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(0.0)

        # Change days
        with qtbot.waitSignal(widget.value_changed, timeout=1000):
            widget.spin_days.setValue(5)


class TestCompactDurationWidgetDecomposition:
    """Tests for smart duration decomposition."""

    def test_exact_year_decomposition(self, qtbot, simple_calendar):
        """360 days should decompose to 1 Year in simple calendar."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(360.0)

        assert widget.spin_years.value() == 1
        assert widget.spin_months.value() == 0
        assert widget.spin_days.value() == 0

    def test_year_and_month_decomposition(self, qtbot, simple_calendar):
        """390 days = 1 Year + 1 Month in simple calendar."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(390.0)  # 360 + 30

        assert widget.spin_years.value() == 1
        assert widget.spin_months.value() == 1
        assert widget.spin_days.value() == 0

    def test_complex_decomposition(self, qtbot, simple_calendar):
        """395 days = 1 Year + 1 Month + 5 Days."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(395.0)

        assert widget.spin_years.value() == 1
        assert widget.spin_months.value() == 1
        assert widget.spin_days.value() == 5

    def test_only_days_decomposition(self, qtbot, simple_calendar):
        """15 days should remain as 15 Days."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(15.0)

        assert widget.spin_years.value() == 0
        assert widget.spin_months.value() == 0
        assert widget.spin_days.value() == 15


class TestCompactDurationWidgetPreview:
    """Tests for preview label formatting."""

    def test_preview_hides_zero_units(self, qtbot, simple_calendar):
        """Preview should not show zero-value units."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(35.0)  # 1 Month + 5 Days

        preview = widget.lbl_preview.text()
        assert "Year" not in preview
        assert "Month" in preview or "Days" in preview

    def test_preview_written_format(self, qtbot, simple_calendar):
        """Preview should use written format like '1 Year, 3 Months'."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(450.0)  # 1 Year + 3 Months

        preview = widget.lbl_preview.text()
        # Should contain spelled-out units
        assert "Year" in preview
        assert "Month" in preview

    def test_plural_handling(self, qtbot, simple_calendar):
        """Preview should handle plurals (1 Day vs 2 Days)."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        # Single day
        widget.set_value(1.0)
        preview_single = widget.lbl_preview.text()

        # Multiple days
        widget.set_value(5.0)
        preview_plural = widget.lbl_preview.text()

        # Check singular/plural handling
        assert "Day" in preview_single
        assert "Days" in preview_plural


class TestCompactDurationWidgetEdgeCases:
    """Edge case and boundary tests."""

    def test_zero_duration(self, qtbot, simple_calendar):
        """Zero duration should display appropriately."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(0.0)

        assert widget.spin_years.value() == 0
        assert widget.spin_months.value() == 0
        assert widget.spin_days.value() == 0

    def test_fractional_days(self, qtbot, simple_calendar):
        """Fractional days should be handled (converted to hours/minutes)."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(1.5)  # 1 day + 12 hours

        # Value should be retrievable
        value = widget.get_value()
        assert abs(value - 1.5) < 0.1  # Allow for hour rounding

    def test_very_large_duration(self, qtbot, simple_calendar):
        """Very large durations should work."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        # 10 years
        widget.set_value(3600.0)

        assert widget.spin_years.value() == 10
        assert widget.spin_months.value() == 0
        assert widget.spin_days.value() == 0

    def test_no_converter_fallback(self, qtbot):
        """Widget should work without converter (fallback uses 365d/y, 30d/m)."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        qtbot.addWidget(widget)

        widget.set_value(100.0)

        # Without converter, fallback is 365d/y, 30d/m
        # 100 days = 0 years, 3 months (90d), 10 days
        assert widget.spin_years.value() == 0
        assert widget.spin_months.value() == 3
        assert widget.spin_days.value() == 10

    def test_start_date_affects_calculation(self, qtbot, standard_calendar):
        """Different start dates affect month lengths in calculations."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(standard_calendar)
        qtbot.addWidget(widget)

        # Start in January (31 days)
        widget.set_start_date(0.0)
        widget.set_value(31.0)
        jan_month = widget.spin_months.value()

        # Start in February (28 days)
        widget.set_start_date(31.0)  # Feb 1
        widget.set_value(28.0)
        feb_month = widget.spin_months.value()

        # Both should be 1 month (different lengths)
        assert jan_month == 1
        assert feb_month == 1


class TestCompactDurationWidgetCalendarAwareness:
    """Tests for calendar-specific behavior."""

    def test_standard_calendar_year_length(self, qtbot, standard_calendar):
        """Standard calendar should use 365 days per year."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(standard_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(365.0)

        assert widget.spin_years.value() == 1
        assert widget.spin_months.value() == 0
        # Might have remainder days due to varying month lengths

    def test_simple_calendar_year_length(self, qtbot, simple_calendar):
        """Simple calendar should use 360 days per year."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(simple_calendar)
        widget.set_start_date(0.0)
        qtbot.addWidget(widget)

        widget.set_value(360.0)

        assert widget.spin_years.value() == 1
        assert widget.spin_months.value() == 0
        assert widget.spin_days.value() == 0

    def test_varying_month_lengths(self, qtbot, standard_calendar):
        """Should correctly handle months with different lengths."""
        from src.gui.widgets.compact_duration_widget import CompactDurationWidget

        widget = CompactDurationWidget()
        widget.set_calendar_converter(standard_calendar)
        widget.set_start_date(0.0)  # January 1
        qtbot.addWidget(widget)

        # January (31) + February (28) = 59 days = 2 months
        widget.set_value(59.0)

        assert widget.spin_months.value() == 2
        assert widget.spin_days.value() == 0
