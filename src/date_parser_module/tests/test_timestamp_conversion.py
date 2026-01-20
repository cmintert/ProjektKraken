import pytest
from src.date_parser_module.dateparser import DateParser, ParsedDate, DatePrecision


@pytest.fixture
def parser():
    calendar_data = {
        "month_names": ["Month1", "Month2", "Month3"],
        "month_days": [30, 30, 30],
        "year_length": 90,
        "current_year": 1,
    }
    return DateParser(calendar_data)


class TestTimestampConversion:
    def test_epoch_start(self, parser):
        """1.1.1 00:00:00 -> 0.0"""
        date = ParsedDate(year=1, month=1, day=1, hour=0, minute=0, second=0)
        ts = parser.calculate_timestamp(date)
        assert ts == 0.0

    def test_end_of_first_month(self, parser):
        """1.1.30 24:00:00 (effectively start of next month)"""
        # Day 30 at end of day (24:00 is invalid in ParsedDate validation)
        # Use 1.2.1 00:00:00 instead to represent the exact same moment
        date = ParsedDate(year=1, month=2, day=1, hour=0, minute=0, second=0)
        ts = parser.calculate_timestamp(date)
        # (1-1)*90 + (2-1)*30 + (1-1) = 30.0
        assert ts == 30.0
        date = ParsedDate(year=1, month=1, day=30, hour=12, minute=0, second=0)
        # 29.5
        ts = parser.calculate_timestamp(date)
        assert ts == 29.5

    def test_start_of_second_year(self, parser):
        """2.1.1 00:00:00 -> 90.0"""
        date = ParsedDate(year=2, month=1, day=1)
        ts = parser.calculate_timestamp(date)
        assert ts == 90.0

    def test_mid_year(self, parser):
        """1.2.16 00:00:00 -> 30 + 15 = 45.0"""
        date = ParsedDate(year=1, month=2, day=16)
        ts = parser.calculate_timestamp(date)
        assert ts == 45.0

    def test_negative_year_start(self, parser):
        """0.1.1 00:00:00 -> -90.0 (one year before epoch)"""
        date = ParsedDate(year=0, month=1, day=1)
        ts = parser.calculate_timestamp(date)
        assert ts == -90.0

    def test_negative_year_end(self, parser):
        """0.3.30 24:00:00 (end of year 0) -> 0.0 (start of year 1)"""
        # 24:00 is invalid. Use 1.1.1 00:00:00 which is effectively the same moment
        # But we want to test correct calculation from Year 0 perspective.
        # Use 0.3.30 12:00:00 -> -0.5
        date = ParsedDate(year=0, month=3, day=30, hour=12)
        ts = parser.calculate_timestamp(date)
        # Total days in year 0 is 90.
        # Days in year 0 up to 3.30 12:00 is 89.5.
        # Remaining to start of Year 1 is 0.5.
        # Result should be -0.5.
        assert ts == -0.5

    def test_precision_checks(self, parser):
        """Test that missing components raise error"""
        with pytest.raises(ValueError, match="without year"):
            parser.calculate_timestamp(ParsedDate(year=None, month=1))

        with pytest.raises(ValueError, match="without month"):
            parser.calculate_timestamp(ParsedDate(year=1, month=None))

    def test_time_precision_defaults(self, parser):
        """Test DatePrecision.TIME defaults to 1.1 if missing month/day"""
        # "14:30" parsed as TIME precision
        date = ParsedDate(year=1, precision=DatePrecision.TIME, hour=14, minute=30)
        # Should behave like 1.1.1 14:30 -> 0.0 + 14.5/24
        ts = parser.calculate_timestamp(date)
        expected = 14.5 / 24.0
        assert abs(ts - expected) < 0.000001
