"""
Tests for Algorithmic Leap Years and Gregorian Logic.
"""

import pytest
from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    CalendarDate,
    LeapYearRule,
    MonthDefinition,
    WeekDefinition,
)


@pytest.fixture
def gregorian_config() -> CalendarConfig:
    """Returns a standard Gregorian calendar configuration."""
    return CalendarConfig.create_default()


class TestLeapYearRule:
    """Tests for the LeapYearRule logic."""

    def test_standard_leap_year(self):
        """Test simple every-4-years rule."""
        rule = LeapYearRule(interval=4, skip_interval=100, reset_interval=400)

        # Standard leap years
        assert rule.applies_to_year(2004) is True
        assert rule.applies_to_year(2008) is True

        # Non-leap years
        assert rule.applies_to_year(2005) is False
        assert rule.applies_to_year(2006) is False
        assert rule.applies_to_year(2007) is False

    def test_skip_interval(self):
        """Test skipping every 100 years."""
        rule = LeapYearRule(interval=4, skip_interval=100, reset_interval=400)

        # 1900 was NOT a leap year (divisible by 100 but not 400)
        assert rule.applies_to_year(1900) is False
        assert rule.applies_to_year(1800) is False
        assert rule.applies_to_year(1700) is False

    def test_reset_interval(self):
        """Test resetting rule every 400 years."""
        rule = LeapYearRule(interval=4, skip_interval=100, reset_interval=400)

        # 2000 WAS a leap year (divisible by 400)
        assert rule.applies_to_year(2000) is True
        assert rule.applies_to_year(1600) is True
        assert rule.applies_to_year(2400) is True


class TestGregorianCalendar:
    """Tests specifically for the default Gregorian calendar."""

    def test_feb_days_common_year(self, gregorian_config):
        """Test days in February for a common year (e.g. 2023)."""
        months = gregorian_config.get_months_for_year(2023)
        feb = months[1]
        assert feb.name == "February"
        assert feb.days == 28
        assert gregorian_config.get_year_length(2023) == 365

    def test_feb_days_leap_year(self, gregorian_config):
        """Test days in February for a leap year (e.g. 2024)."""
        months = gregorian_config.get_months_for_year(2024)
        feb = months[1]
        assert feb.name == "February"
        assert feb.days == 29
        assert gregorian_config.get_year_length(2024) == 366

    def test_feb_29_conversion(self, gregorian_config):
        """Test converting Feb 29th to float and back."""
        converter = CalendarConverter(gregorian_config)

        # Feb 29, 2024
        date = CalendarDate(year=2024, month=2, day=29, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29

    def test_mar_1_boundary(self, gregorian_config):
        """Test continuity from Feb 28 -> Mar 1 in common year."""
        converter = CalendarConverter(gregorian_config)

        # Feb 28, 2023
        feb28 = CalendarDate(year=2023, month=2, day=28, time_fraction=0.0)
        float_feb28 = converter.to_float(feb28)

        # Mar 1, 2023
        mar1 = CalendarDate(year=2023, month=3, day=1, time_fraction=0.0)
        float_mar1 = converter.to_float(mar1)

        assert float_mar1 - float_feb28 == 1.0

    def test_mar_1_boundary_leap(self, gregorian_config):
        """Test continuity from Feb 28 -> Feb 29 -> Mar 1 in leap year."""
        converter = CalendarConverter(gregorian_config)

        # Feb 28, 2024
        feb28 = CalendarDate(year=2024, month=2, day=28, time_fraction=0.0)
        float_feb28 = converter.to_float(feb28)

        # Feb 29, 2024
        feb29 = CalendarDate(year=2024, month=2, day=29, time_fraction=0.0)
        float_feb29 = converter.to_float(feb29)

        # Mar 1, 2024
        mar1 = CalendarDate(year=2024, month=3, day=1, time_fraction=0.0)
        float_mar1 = converter.to_float(mar1)

        assert float_feb29 - float_feb28 == 1.0
        assert float_mar1 - float_feb29 == 1.0
