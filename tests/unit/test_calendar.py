"""
Calendar System Unit Tests.

Tests for the CalendarConfig domain model and CalendarConverter logic.
Follows TDD approach - tests written before implementation.
"""

import pytest

# These imports will work once the module is implemented
from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    CalendarDate,
    MonthDefinition,
    WeekDefinition,
    YearVariant,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_calendar() -> CalendarConfig:
    """
    A simple test calendar with 12 months of 30 days each (360-day year).
    """
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
def variable_month_calendar() -> CalendarConfig:
    """
    A calendar with variable month lengths (like Gregorian: 28, 30, 31 days).
    """
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
        day_names=[
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ],
        day_abbreviations=["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"],
    )
    return CalendarConfig(
        id="test-variable",
        name="Variable Month Calendar",
        months=months,
        week=week,
        year_variants=[],
        epoch_name="AD",
    )


@pytest.fixture
def year_variant_calendar() -> CalendarConfig:
    """
    A calendar with a special year that has different month structure.
    Year 5 has only 6 months instead of 12.
    """
    default_months = [
        MonthDefinition(name=f"Month{i + 1}", abbreviation=f"M{i + 1}", days=30)
        for i in range(12)
    ]
    # Year 5 is special - only 6 months
    year5_months = [
        MonthDefinition(name=f"SpecialMonth{i + 1}", abbreviation=f"S{i + 1}", days=30)
        for i in range(6)
    ]
    week = WeekDefinition(
        day_names=["Day1", "Day2", "Day3", "Day4", "Day5"],
        day_abbreviations=["D1", "D2", "D3", "D4", "D5"],
    )
    return CalendarConfig(
        id="test-variant",
        name="Year Variant Calendar",
        months=default_months,
        week=week,
        year_variants=[YearVariant(year=5, months=year5_months)],
        epoch_name="YV",
    )


# ---------------------------------------------------------------------------
# CalendarConfig Validation Tests
# ---------------------------------------------------------------------------


class TestCalendarConfigValidation:
    """Tests for CalendarConfig validation logic."""

    def test_valid_config_passes_validation(self, simple_calendar: CalendarConfig):
        """Test that a valid config has no validation errors."""
        errors = simple_calendar.validate()
        assert errors == []

    def test_duplicate_month_names_rejected(self):
        """Test that duplicate month names trigger validation error."""
        months = [
            MonthDefinition(name="January", abbreviation="Jan", days=31),
            MonthDefinition(name="January", abbreviation="Feb", days=28),  # Duplicate!
        ]
        week = WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"])
        config = CalendarConfig(
            id="test",
            name="Test",
            months=months,
            week=week,
            year_variants=[],
            epoch_name="T",
        )

        errors = config.validate()
        assert len(errors) > 0
        assert any("duplicate" in e.lower() and "name" in e.lower() for e in errors)

    def test_duplicate_abbreviations_rejected(self):
        """Test that duplicate abbreviations trigger validation error."""
        months = [
            MonthDefinition(name="January", abbreviation="Jan", days=31),
            MonthDefinition(name="February", abbreviation="Jan", days=28),  # Duplicate!
        ]
        week = WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"])
        config = CalendarConfig(
            id="test",
            name="Test",
            months=months,
            week=week,
            year_variants=[],
            epoch_name="T",
        )

        errors = config.validate()
        assert len(errors) > 0
        assert any(
            "duplicate" in e.lower() and "abbreviation" in e.lower() for e in errors
        )

    def test_empty_month_list_rejected(self):
        """Test that empty month list is invalid."""
        week = WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"])
        config = CalendarConfig(
            id="test",
            name="Test",
            months=[],
            week=week,
            year_variants=[],
            epoch_name="T",
        )

        errors = config.validate()
        assert len(errors) > 0
        assert any("month" in e.lower() and "empty" in e.lower() for e in errors)

    def test_zero_day_month_rejected(self):
        """Test that a month with 0 days is invalid."""
        months = [
            MonthDefinition(name="January", abbreviation="Jan", days=0),  # Invalid!
        ]
        week = WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"])
        config = CalendarConfig(
            id="test",
            name="Test",
            months=months,
            week=week,
            year_variants=[],
            epoch_name="T",
        )

        errors = config.validate()
        assert len(errors) > 0
        assert any("days" in e.lower() for e in errors)

    def test_negative_day_month_rejected(self):
        """Test that a month with negative days is invalid."""
        months = [
            MonthDefinition(name="January", abbreviation="Jan", days=-5),  # Invalid!
        ]
        week = WeekDefinition(day_names=["Day1"], day_abbreviations=["D1"])
        config = CalendarConfig(
            id="test",
            name="Test",
            months=months,
            week=week,
            year_variants=[],
            epoch_name="T",
        )

        errors = config.validate()
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# CalendarConfig Year Length Tests
# ---------------------------------------------------------------------------


class TestCalendarConfigYearLength:
    """Tests for year length calculations."""

    def test_simple_year_length(self, simple_calendar: CalendarConfig):
        """Test year length for simple 12x30 calendar = 360 days."""
        assert simple_calendar.get_year_length(1) == 360
        assert simple_calendar.get_year_length(100) == 360

    def test_variable_month_year_length(self, variable_month_calendar: CalendarConfig):
        """Test year length for Gregorian-like calendar = 365 days."""
        assert variable_month_calendar.get_year_length(1) == 365

    def test_year_variant_length(self, year_variant_calendar: CalendarConfig):
        """Test that year variants have different lengths."""
        # Normal years have 12 months * 30 days = 360
        assert year_variant_calendar.get_year_length(1) == 360
        assert year_variant_calendar.get_year_length(4) == 360

        # Year 5 has only 6 months * 30 days = 180
        assert year_variant_calendar.get_year_length(5) == 180

        # Year 6 back to normal
        assert year_variant_calendar.get_year_length(6) == 360


# ---------------------------------------------------------------------------
# CalendarConverter Round-Trip Tests (CRITICAL)
# ---------------------------------------------------------------------------


class TestCalendarConverterRoundTrip:
    """Critical round-trip tests: from_float(to_float(date)) == date."""

    def test_epoch_start_round_trip(self, simple_calendar: CalendarConfig):
        """Test Year 1, Month 1, Day 1 round-trip."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=1, day=1, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day
        assert result.time_fraction == pytest.approx(date.time_fraction, abs=1e-9)

    def test_mid_year_round_trip(self, simple_calendar: CalendarConfig):
        """Test mid-year date round-trip."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=6, day=15, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day

    def test_end_of_year_round_trip(self, simple_calendar: CalendarConfig):
        """Test last day of year round-trip."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=12, day=30, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day

    def test_year_boundary_round_trip(self, simple_calendar: CalendarConfig):
        """Test first day of Year 2 round-trip."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=2, month=1, day=1, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day

    def test_high_year_round_trip(self, simple_calendar: CalendarConfig):
        """Test date far in the future round-trip."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1000, month=7, day=20, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day

    def test_variable_month_round_trip(self, variable_month_calendar: CalendarConfig):
        """Test round-trip with variable month lengths."""
        converter = CalendarConverter(variable_month_calendar)

        # Test various dates across different month lengths
        test_dates = [
            CalendarDate(year=1, month=1, day=31, time_fraction=0.0),  # Jan 31
            CalendarDate(year=1, month=2, day=28, time_fraction=0.0),  # Feb 28
            CalendarDate(year=1, month=3, day=1, time_fraction=0.0),  # Mar 1
            CalendarDate(year=1, month=12, day=31, time_fraction=0.0),  # Dec 31
        ]

        for date in test_dates:
            float_val = converter.to_float(date)
            result = converter.from_float(float_val)
            assert result.year == date.year, f"Failed for {date}"
            assert result.month == date.month, f"Failed for {date}"
            assert result.day == date.day, f"Failed for {date}"

    @pytest.mark.parametrize(
        "year,month,day",
        [
            (1, 1, 1),  # Epoch start
            (1, 6, 15),  # Mid-year
            (1, 12, 30),  # End of year
            (2, 1, 1),  # Start of year 2
            (10, 3, 10),  # Arbitrary
            (100, 12, 30),  # Far future
        ],
    )
    def test_parametrized_round_trip(
        self, simple_calendar: CalendarConfig, year: int, month: int, day: int
    ):
        """Parametrized round-trip test for various dates."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=year, month=month, day=day, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day


# ---------------------------------------------------------------------------
# CalendarConverter to_float Tests
# ---------------------------------------------------------------------------


class TestCalendarConverterToFloat:
    """Tests for to_float conversion."""

    def test_epoch_start_is_zero(self, simple_calendar: CalendarConfig):
        """Test that Year 1, Month 1, Day 1 converts to 0.0."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=1, day=1, time_fraction=0.0)

        result = converter.to_float(date)

        assert result == 0.0

    def test_second_day_is_one(self, simple_calendar: CalendarConfig):
        """Test that Year 1, Month 1, Day 2 converts to 1.0."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=1, day=2, time_fraction=0.0)

        result = converter.to_float(date)

        assert result == 1.0

    def test_second_month_correct(self, simple_calendar: CalendarConfig):
        """Test that Month 2, Day 1 = 30.0 (after 30-day first month)."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=2, day=1, time_fraction=0.0)

        result = converter.to_float(date)

        assert result == 30.0

    def test_year_two_start(self, simple_calendar: CalendarConfig):
        """Test that Year 2, Month 1, Day 1 = 360.0 (full year)."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=2, month=1, day=1, time_fraction=0.0)

        result = converter.to_float(date)

        assert result == 360.0

    def test_noon_time_fraction(self, simple_calendar: CalendarConfig):
        """Test that 0.5 time fraction represents noon."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=1, month=1, day=1, time_fraction=0.5)

        result = converter.to_float(date)

        assert result == 0.5


# ---------------------------------------------------------------------------
# CalendarConverter from_float Tests
# ---------------------------------------------------------------------------


class TestCalendarConverterFromFloat:
    """Tests for from_float conversion."""

    def test_zero_is_epoch_start(self, simple_calendar: CalendarConfig):
        """Test that 0.0 converts to Year 1, Month 1, Day 1."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(0.0)

        assert result.year == 1
        assert result.month == 1
        assert result.day == 1
        assert result.time_fraction == pytest.approx(0.0, abs=1e-9)

    def test_one_is_second_day(self, simple_calendar: CalendarConfig):
        """Test that 1.0 converts to Year 1, Month 1, Day 2."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(1.0)

        assert result.year == 1
        assert result.month == 1
        assert result.day == 2

    def test_thirty_is_month_two(self, simple_calendar: CalendarConfig):
        """Test that 30.0 converts to Month 2, Day 1."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(30.0)

        assert result.year == 1
        assert result.month == 2
        assert result.day == 1

    def test_360_is_year_two(self, simple_calendar: CalendarConfig):
        """Test that 360.0 converts to Year 2, Month 1, Day 1."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(360.0)

        assert result.year == 2
        assert result.month == 1
        assert result.day == 1

    def test_noon_fraction(self, simple_calendar: CalendarConfig):
        """Test that 0.5 time fraction is preserved."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(0.5)

        assert result.year == 1
        assert result.month == 1
        assert result.day == 1
        assert result.time_fraction == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Negative Float (Pre-Epoch) Tests
# ---------------------------------------------------------------------------


class TestCalendarConverterNegativeFloats:
    """Tests for handling negative floats (pre-Epoch dates)."""

    def test_negative_one_is_day_before_epoch(self, simple_calendar: CalendarConfig):
        """Test that -1.0 is the day before Epoch (Year 0, last day)."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(-1.0)

        # Year 0, Month 12, Day 30 (last day before Epoch)
        assert result.year == 0
        assert result.month == 12
        assert result.day == 30

    def test_negative_360_is_year_minus_one(self, simple_calendar: CalendarConfig):
        """Test that -360.0 is start of Year 0."""
        converter = CalendarConverter(simple_calendar)

        result = converter.from_float(-360.0)

        assert result.year == 0
        assert result.month == 1
        assert result.day == 1

    def test_negative_round_trip(self, simple_calendar: CalendarConfig):
        """Test round-trip for pre-Epoch date."""
        converter = CalendarConverter(simple_calendar)
        date = CalendarDate(year=-1, month=6, day=15, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day


# ---------------------------------------------------------------------------
# Year Variant Tests
# ---------------------------------------------------------------------------


class TestCalendarConverterYearVariants:
    """Tests for calendars with year-specific month structures."""

    def test_year_variant_conversion(self, year_variant_calendar: CalendarConfig):
        """Test conversion through a year with different month count."""
        converter = CalendarConverter(year_variant_calendar)

        # Calculate expected float for Year 6, Month 1, Day 1
        # Years 1-4: 4 * 360 = 1440
        # Year 5: 6 months * 30 = 180
        # Total to start of Year 6 = 1620
        date = CalendarDate(year=6, month=1, day=1, time_fraction=0.0)

        float_val = converter.to_float(date)

        assert float_val == 1620.0

    def test_year_variant_round_trip(self, year_variant_calendar: CalendarConfig):
        """Test round-trip through year variant."""
        converter = CalendarConverter(year_variant_calendar)

        # Date in the variant year (Year 5, Month 4, Day 15)
        date = CalendarDate(year=5, month=4, day=15, time_fraction=0.0)

        float_val = converter.to_float(date)
        result = converter.from_float(float_val)

        assert result.year == date.year
        assert result.month == date.month
        assert result.day == date.day

    def test_year_variant_affects_subsequent_years(
        self, year_variant_calendar: CalendarConfig
    ):
        """Test that year variant affects calculation of subsequent years."""
        converter = CalendarConverter(year_variant_calendar)

        # Year 6, Day 1 calculation
        year6_day1 = converter.to_float(
            CalendarDate(year=6, month=1, day=1, time_fraction=0.0)
        )

        # Year 7, Day 1 should be 360 days after Year 6 Day 1
        year7_day1 = converter.to_float(
            CalendarDate(year=7, month=1, day=1, time_fraction=0.0)
        )

        assert year7_day1 - year6_day1 == 360.0


# ---------------------------------------------------------------------------
# Format Date Tests
# ---------------------------------------------------------------------------


class TestCalendarConverterFormatDate:
    """Tests for date formatting."""

    def test_format_basic(self, simple_calendar: CalendarConfig):
        """Test basic date formatting."""
        converter = CalendarConverter(simple_calendar)

        result = converter.format_date(0.0)

        assert "1" in result  # Year 1
        assert "Month1" in result or "M1" in result  # Month name

    def test_format_includes_day(self, simple_calendar: CalendarConfig):
        """Test that formatted date includes day number."""
        converter = CalendarConverter(simple_calendar)

        result = converter.format_date(14.0)  # Day 15

        assert "15" in result
