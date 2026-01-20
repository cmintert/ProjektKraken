import pytest
from src.date_parser_module.dateparser import DateParser, ParsedDate, DatePrecision


@pytest.fixture
def parser():
    calendar_data = {
        "month_names": ["Wintermarch", "Springbloom", "Summerday", "Harvestmoon"],
        "month_days": [30, 30, 30, 30],
        "year_length": 120,
        "current_year": 3019,
    }
    return DateParser(calendar_data)


class TestTimeParsing:
    def test_standalone_time_basic(self, parser):
        """Test HH:MM format"""
        date = parser.parse_date("14:30")
        assert date.hour == 14
        assert date.minute == 30
        assert date.second is None
        assert date.precision == DatePrecision.TIME
        assert date.year == 3019  # From current_year

    def test_standalone_time_seconds(self, parser):
        """Test HH:MM:SS format"""
        date = parser.parse_date("14:30:45")
        assert date.hour == 14
        assert date.minute == 30
        assert date.second == 45
        assert date.precision == DatePrecision.TIME

    def test_standalone_time_single_digit(self, parser):
        """Test H:MM format"""
        date = parser.parse_date("9:05")
        assert date.hour == 9
        assert date.minute == 5

    def test_date_time_exact_names(self, parser):
        """Test Date + Time with month names"""
        # "15th day of Wintermarch, 3019 14:30"
        date = parser.parse_date("15th day of Wintermarch, 3019 14:30")
        assert date.year == 3019
        assert date.month == 1
        assert date.day == 15
        assert date.hour == 14
        assert date.minute == 30
        assert date.precision == DatePrecision.EXACT

    def test_date_time_numeric_dot(self, parser):
        """Test DD.MM.YYYY HH:MM"""
        date = parser.parse_date("15.1.3019 14:30")
        assert date.year == 3019
        assert date.month == 1
        assert date.day == 15
        assert date.hour == 14
        assert date.minute == 30

    def test_date_time_numeric_slash(self, parser):
        """Test MM/DD/YYYY HH:MM:SS"""
        date = parser.parse_date("1/15/3019 14:30:15")
        assert date.year == 3019
        assert date.month == 1
        assert date.day == 15
        assert date.hour == 14
        assert date.minute == 30
        assert date.second == 15

    def test_invalid_hour(self, parser):
        with pytest.raises(ValueError, match="Hour must be between 0 and 23"):
            parser.parse_date("25:00")

    def test_invalid_minute(self, parser):
        with pytest.raises(ValueError, match="Minute must be between 0 and 59"):
            parser.parse_date("14:60")

    def test_invalid_second(self, parser):
        with pytest.raises(ValueError, match="Second must be between 0 and 59"):
            parser.parse_date("14:30:60")

    def test_boundary_time(self, parser):
        """Test 00:00:00 and 23:59:59"""
        d1 = parser.parse_date("00:00:00")
        assert d1.hour == 0
        assert d1.minute == 0
        assert d1.second == 0

        d2 = parser.parse_date("23:59:59")
        assert d2.hour == 23
        assert d2.minute == 59
        assert d2.second == 59

    def test_json_serialization(self, parser):
        """Test JSON roundtrip with time"""
        date = parser.parse_date("15.3.3019 14:30:45")
        json_data = parser.to_json(date)

        assert json_data["hour"] == 14
        assert json_data["minute"] == 30
        assert json_data["second"] == 45

        restored = parser.from_json(json_data)
        assert restored.hour == 14
        assert restored.minute == 30
        assert restored.second == 45
        assert restored.year == 3019
