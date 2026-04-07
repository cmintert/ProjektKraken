import pytest

from src.core.calendar import CalendarConfig, MonthDefinition, WeekDefinition
from src.core.date_parser import DateParser
from src.core.parsed_date import DatePrecision


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


@pytest.fixture
def gregorian_calendar() -> CalendarConfig:
    """Standard Gregorian calendar for testing real-world date formats."""
    return CalendarConfig.create_default()


class TestDateParserIntegration:
    """Tests for DateParser integrated with CalendarConfig."""

    def test_init(self, simple_calendar):
        """Test initialization with CalendarConfig."""
        parser = DateParser(simple_calendar)
        assert parser.calendar_config == simple_calendar

    def test_parse_simple_date(self, simple_calendar):
        """Test parsing a simple date using the config."""
        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("15 Month1 3019")

        assert parsed.year == 3019
        assert parsed.month == 1
        assert parsed.day == 15
        assert parsed.precision == DatePrecision.EXACT

    def test_calculate_timestamp_integration(self, simple_calendar):
        """Test timestamp calculation delegates to CalendarConverter correctly."""
        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("1.1.1 00:00:00")

        ts = parser.calculate_timestamp(parsed)
        assert ts == 0.0

    def test_negative_year_integration(self, simple_calendar):
        """Test negative year parsing and timestamp calculation."""
        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("-100.1.1")

        assert parsed.year == -100
        assert parsed.month == 1
        assert parsed.day == 1

        ts = parser.calculate_timestamp(parsed)
        assert ts < 0.0

    def test_iso_parsing_integration(self, simple_calendar):
        """Test ISO format parsing (YYYY-MM-DD)."""
        parser = DateParser(simple_calendar)
        parsed = parser.parse_date("2024-03-15")

        assert parsed.year == 2024
        assert parsed.month == 3
        assert parsed.day == 15


class TestAbbreviatedMonthParsing:
    """Tests for parsing dates with 3-letter month abbreviations."""

    def test_day_abbrev_month_year(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("12 JUL 1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 12
        assert parsed.month == 7
        assert parsed.year == 1895

    def test_day_abbrev_month_year_lowercase(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("12 jul 1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 12
        assert parsed.month == 7
        assert parsed.year == 1895

    def test_single_digit_day_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("3 AUG 1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 3
        assert parsed.month == 8
        assert parsed.year == 1895

    def test_abbrev_sep(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("1 SEP 1955")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 1
        assert parsed.month == 9
        assert parsed.year == 1955

    def test_abbrev_feb(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("22 FEB 1951")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 22
        assert parsed.month == 2
        assert parsed.year == 1951

    def test_full_month_still_works(self, gregorian_calendar):
        """Regression: full month names must still work after abbreviation support."""
        parsed = DateParser(gregorian_calendar).parse_date("12 July 1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 12
        assert parsed.month == 7
        assert parsed.year == 1895

    def test_fuzzy_with_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("circa 3 Aug 1895")
        assert parsed.precision == DatePrecision.FUZZY
        assert parsed.day == 3
        assert parsed.month == 8
        assert parsed.year == 1895

    def test_month_first_abbrev(self, gregorian_calendar):
        """Month-first format: 'Aug 23, 1895'."""
        parsed = DateParser(gregorian_calendar).parse_date("Aug 23, 1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 23
        assert parsed.month == 8
        assert parsed.year == 1895


class TestRangeParsingSameMonth:
    """Tests for day ranges within the same month using dash notation."""

    def test_endash_day_range_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23\u201330 AUG 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_start.month == 8
        assert parsed.range_start.year == 1895
        assert parsed.range_end.day == 30
        assert parsed.range_end.month == 8
        assert parsed.range_end.year == 1895

    def test_emdash_day_range_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23\u201430 AUG 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30
        assert parsed.range_start.month == 8

    def test_hyphen_day_range_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23-30 AUG 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30
        assert parsed.range_start.month == 8

    def test_endash_day_range_full_month(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23\u201330 August 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30
        assert parsed.range_start.month == 8

    def test_hyphen_day_range_full_month(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23-30 August 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30

    def test_single_digit_day_range(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("1\u20133 March 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 1
        assert parsed.range_end.day == 3
        assert parsed.range_start.month == 3

    def test_range_with_spaces_around_dash(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23 \u2013 30 AUG 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30


class TestRangeParsingCrossMonth:
    """Tests for day ranges spanning two months using dash notation."""

    def test_cross_month_endash(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("23 AUG\u20136 SEP 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_start.month == 8
        assert parsed.range_end.day == 6
        assert parsed.range_end.month == 9
        assert parsed.range_end.year == 1895

    def test_cross_month_with_spaces(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "23 AUG \u2013 6 SEP 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_start.month == 8
        assert parsed.range_end.day == 6
        assert parsed.range_end.month == 9

    def test_cross_month_full_names(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "23 August\u20136 September 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9

    def test_cross_month_hyphen(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "23 Aug - 6 Sep 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_start.month == 8
        assert parsed.range_end.day == 6
        assert parsed.range_end.month == 9


class TestRangeParsingMonthToMonth:
    """Tests for month-to-month ranges using dash notation."""

    def test_month_range_endash(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("AUG\u2013SEP 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_start.precision == DatePrecision.MONTH
        assert parsed.range_end.month == 9
        assert parsed.range_end.precision == DatePrecision.MONTH

    def test_month_range_hyphen(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("AUG-SEP 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9

    def test_month_range_full_names(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "August\u2013September 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9

    def test_month_range_with_spaces(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "August \u2013 September 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9


class TestRangeParsingFromTo:
    """Tests for existing from/to and between/and range formats with abbreviations."""

    def test_from_day_to_day_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "from 23 to 30 Aug 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.day == 23
        assert parsed.range_end.day == 30
        assert parsed.range_start.month == 8

    def test_from_month_to_month_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date("from Aug to Sep 1895")
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9

    def test_between_months_abbrev(self, gregorian_calendar):
        parsed = DateParser(gregorian_calendar).parse_date(
            "between Aug and Sep 1895"
        )
        assert parsed.precision == DatePrecision.RANGE
        assert parsed.range_start.month == 8
        assert parsed.range_end.month == 9


class TestRangeEdgeCases:
    """Edge cases to ensure ranges don't conflict with other formats."""

    def test_iso_date_not_mismatched_as_range(self, gregorian_calendar):
        """ISO date 1895-08-23 must parse as EXACT, not range."""
        parsed = DateParser(gregorian_calendar).parse_date("1895-08-23")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.year == 1895
        assert parsed.month == 8
        assert parsed.day == 23

    def test_eu_date_not_mismatched(self, gregorian_calendar):
        """EU format 23.08.1895 must parse as EXACT, not range."""
        parsed = DateParser(gregorian_calendar).parse_date("23.08.1895")
        assert parsed.precision == DatePrecision.EXACT
        assert parsed.day == 23
        assert parsed.month == 8

    def test_range_timestamp_start_before_end(self, gregorian_calendar):
        """Range start timestamp must be less than end timestamp."""
        parser = DateParser(gregorian_calendar)
        parsed = parser.parse_date("23\u201330 AUG 1895")
        start_ts = parser.calculate_timestamp(parsed.range_start)
        end_ts = parser.calculate_timestamp(parsed.range_end)
        assert start_ts < end_ts
        assert end_ts - start_ts == 7.0

    def test_range_cross_month_timestamp(self, gregorian_calendar):
        """Cross-month range duration accounts for month boundary."""
        parser = DateParser(gregorian_calendar)
        parsed = parser.parse_date("23 Aug\u20136 Sep 1895")
        start_ts = parser.calculate_timestamp(parsed.range_start)
        end_ts = parser.calculate_timestamp(parsed.range_end)
        # Aug has 31 days: 31-23=8 remaining days in Aug + 6 days in Sep = 14
        assert end_ts - start_ts == 14.0
