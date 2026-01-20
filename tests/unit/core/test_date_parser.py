import pytest

from src.core.calendar import CalendarConfig, MonthDefinition, WeekDefinition
from src.core.parsed_date import DatePrecision

# We expect this import to fail initially as the file doesn't exist yet
try:
    from src.core.date_parser import DateParser
except ImportError:
    DateParser = None


@pytest.fixture
def simple_calendar() -> CalendarConfig:
    """A simple test calendar with 12 months of 30 days each."""
    months = [
        MonthDefinition(name=f"Month{i + 1}", abbreviation=f"M{i + 1}", days=30)
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


class TestDateParserIntegration:
    """Tests for DateParser integrated with CalendarConfig."""

    def test_init(self, simple_calendar):
        """Test initialization with CalendarConfig."""
        if DateParser is None:
            pytest.fail("DateParser not implemented yet")

        parser = DateParser(simple_calendar)
        assert parser.calendar_config == simple_calendar

    def test_parse_simple_date(self, simple_calendar):
        """Test parsing a simple date using the config."""
        if DateParser is None:
            pytest.fail("DateParser not implemented yet")

        parser = DateParser(simple_calendar)
        # Using the month names from the fixture
        parsed = parser.parse_date("15 Month1 3019")

        assert parsed.year == 3019
        assert parsed.month == 1
        assert parsed.day == 15
        assert parsed.precision == DatePrecision.EXACT

    def test_calculate_timestamp_integration(self, simple_calendar):
        """Test timestamp calculation delegates to CalendarConverter correctly."""
        if DateParser is None:
            pytest.fail("DateParser not implemented yet")

        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("1.1.1 00:00:00")

        # Should match Epoch start = 0.0
        ts = parser.calculate_timestamp(parsed)
        assert ts == 0.0

    def test_negative_year_integration(self, simple_calendar):
        """Test negative year parsing and timestamp calculation."""
        if DateParser is None:
            pytest.fail("DateParser not implemented yet")

        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("-100.1.1")

        assert parsed.year == -100
        assert parsed.month == 1
        assert parsed.day == 1

        ts = parser.calculate_timestamp(parsed)
        # Verify it produces a negative float matching logic
        assert ts < 0.0

    def test_iso_parsing_integration(self, simple_calendar):
        """Test ISO format parsing (YYYY-MM-DD)."""
        if DateParser is None:
            pytest.fail("DateParser not implemented yet")

        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("2024-03-15")

        assert parsed.year == 2024
        assert parsed.month == 3
        assert parsed.day == 15
