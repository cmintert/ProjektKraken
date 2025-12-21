from unittest.mock import MagicMock, Mock

import pytest

from src.core.calendar import CalendarConverter, CalendarDate
from src.gui.widgets.lore_duration_widget import LoreDurationWidget


@pytest.fixture
def mock_converter():
    """Returns a mock CalendarConverter with standard 12-month 30-day config."""
    converter = MagicMock(spec=CalendarConverter)
    config = MagicMock()
    converter._config = config

    # Mock month structure
    month_mock = Mock()
    month_mock.days = 30
    month_mock.name = "Month"

    # Return 12 months of 30 days
    months_list = [month_mock] * 12
    config.get_months_for_year.return_value = months_list

    # Mock conversion logic
    # Simplified: Float = (Year-1)*360 + (Month-1)*30 + (Day-1) + Time
    def from_float(val):
        # 1.0 = Year 1, Month 1, Day 1
        total_days = val - 1.0  # 0-indexed total days

        year = int(total_days // 360) + 1
        rem_days = total_days % 360

        month = int(rem_days // 30) + 1
        rem_days = rem_days % 30

        day = int(rem_days) + 1
        time = rem_days - int(rem_days)

        return CalendarDate(year, month, day, time_fraction=time)

    def to_float(date):
        total_days = (date.year - 1) * 360
        total_days += (date.month - 1) * 30
        total_days += date.day - 1
        total_days += date.time_fraction
        return total_days + 1.0

    converter.from_float.side_effect = from_float
    converter.to_float.side_effect = to_float

    return converter


def test_duration_decomposition_exact_year(qtbot, mock_converter):
    """Test that 360 days decomposes to 1 Year."""
    widget = LoreDurationWidget()
    widget.set_calendar_converter(mock_converter)

    # Set start date
    widget.set_start_date(1.0)  # Year 1

    # Set duration of 360 days (1 Year in our mock)
    widget.set_value(360.0)

    assert widget.spin_years.value() == 1
    assert widget.spin_months.value() == 0
    assert widget.spin_days.value() == 0


def test_duration_decomposition_year_and_month(qtbot, mock_converter):
    """Test 1 Year and 1 Month (390 days)."""
    widget = LoreDurationWidget()
    widget.set_calendar_converter(mock_converter)
    widget.set_start_date(1.0)

    widget.set_value(390.0)

    assert widget.spin_years.value() == 1
    assert widget.spin_months.value() == 1
    assert widget.spin_days.value() == 0


def test_duration_decomposition_complex(qtbot, mock_converter):
    """Test 1 Year, 1 Month, 5 Days (395 days)."""
    widget = LoreDurationWidget()
    widget.set_calendar_converter(mock_converter)
    widget.set_start_date(1.0)

    widget.set_value(395.0)

    assert widget.spin_years.value() == 1
    assert widget.spin_months.value() == 1
    assert widget.spin_days.value() == 5


def test_decomposition_without_converter(qtbot):
    """Test fallback when no converter is present."""
    widget = LoreDurationWidget()
    # No converter set

    # 400 days -> 400 Days (no years/months logic without calendar)
    widget.set_value(400.0)

    assert widget.spin_years.value() == 0
    assert widget.spin_months.value() == 0
    assert widget.spin_days.value() == 400
