"""Comprehensive tests for DateParser (CalendarConfig-based implementation).

Tests cover:
- Standard calendars (12 months, variable lengths, numeric formats)
- Fantasy calendars (Middle-earth, Forgotten Realms, Game of Thrones)
- All 7 precision levels: EXACT, MONTH, YEAR, SEASON, RELATIVE, FUZZY, RANGE
- TIME precision and AM/PM conversion
- Numeric date formats: DD.MM.YYYY, MM/DD/YYYY, YYYY-MM-DD, YYYY.MM.DD
- Timestamps via calculate_timestamp()
- Edge cases: first/last day of month, invalid dates, ordinal suffixes
- JSON round-trip serialization
- CalendarConfig validation (year variants, leap year rules)
"""

import pytest

from src.core.calendar import (
    CalendarConfig,
    LeapYearRule,
    MonthDefinition,
    WeekDefinition,
    YearVariant,
)
from src.core.date_parser import DateParser
from src.core.parsed_date import DatePrecision, ParsedDate


# ─────────────────────────────────────────────────────────────────────────────
# Calendar fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_calendar(
    name: str,
    month_data: list,
    day_names: list = None,
    year_variants: list = None,
    leap_year_rules: list = None,
) -> CalendarConfig:
    """Helper to build a CalendarConfig from (name, abbrev, days) tuples."""
    months = [MonthDefinition(name=n, abbreviation=a, days=d) for n, a, d in month_data]
    day_names = day_names or ["Day1", "Day2", "Day3", "Day4", "Day5", "Day6", "Day7"]
    week = WeekDefinition(
        day_names=day_names,
        day_abbreviations=[d[:2] for d in day_names],
    )
    return CalendarConfig(
        id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        months=months,
        week=week,
        year_variants=year_variants or [],
        leap_year_rules=leap_year_rules or [],
        epoch_name="SE",
    )


@pytest.fixture
def gregorian_like() -> CalendarConfig:
    """12-month Gregorian-like calendar (no leap year rule)."""
    data = [
        ("January", "Jan", 31), ("February", "Feb", 28), ("March", "Mar", 31),
        ("April", "Apr", 30), ("May", "May", 31), ("June", "Jun", 30),
        ("July", "Jul", 31), ("August", "Aug", 31), ("September", "Sep", 30),
        ("October", "Oct", 31), ("November", "Nov", 30), ("December", "Dec", 31),
    ]
    return _make_calendar("Gregorian-like", data)


@pytest.fixture
def tolkien_calendar() -> CalendarConfig:
    """Shire Reckoning – 12 months of 30 days, 7-day week."""
    data = [
        ("Afteryule", "Aft", 30), ("Solmath", "Sol", 30), ("Rethe", "Ret", 30),
        ("Astron", "Ast", 30), ("Thrimidge", "Thr", 30), ("Forelithe", "For", 30),
        ("Afterlithe", "Afl", 30), ("Wedmath", "Wed", 30), ("Halimath", "Hal", 30),
        ("Winterfilth", "Win", 30), ("Blotmath", "Blo", 30), ("Foreyule", "Foy", 30),
    ]
    return _make_calendar(
        "Shire Reckoning",
        data,
        day_names=["Sterday", "Sunday", "Monday", "Trewsday", "Hevensday", "Mersday", "Highday"],
    )


@pytest.fixture
def forgotten_realms_calendar() -> CalendarConfig:
    """Faerûnian Calendar of Harptos – 12 months of 30 days."""
    data = [
        ("Hammer", "Ham", 30), ("Alturiak", "Alt", 30), ("Ches", "Che", 30),
        ("Tarsakh", "Tar", 30), ("Mirtul", "Mir", 30), ("Kythorn", "Kyt", 30),
        ("Flamerule", "Fla", 30), ("Eleasis", "Ele", 30), ("Eleint", "Eli", 30),
        ("Marpenoth", "Map", 30), ("Uktar", "Ukt", 30), ("Nightal", "Nig", 30),
    ]
    return _make_calendar("Harptos Calendar", data)


@pytest.fixture
def got_calendar() -> CalendarConfig:
    """GoT-style calendar with multi-word month names."""
    data = [
        ("Moon of Long Night", "MoLN", 28), ("Moon of the Crone", "MoCr", 28),
        ("Moon of the Maiden", "MoMa", 28), ("Moon of the Mother", "MoMo", 28),
        ("Moon of the Warrior", "MoWa", 28), ("Moon of the Smith", "MoSm", 28),
        ("Moon of the Stranger", "MoSt", 28), ("Moon of the Father", "MoFa", 28),
        ("Moon of the Old Gods", "MoOG", 28), ("Moon of Ice", "MoI", 28),
        ("Moon of Fire", "MoF", 28), ("Moon of Dragons", "MoD", 28),
    ]
    return _make_calendar("GoT Calendar", data)


@pytest.fixture
def compact_calendar() -> CalendarConfig:
    """4-month, 10-days each."""
    data = [("First", "Fst", 10), ("Second", "Sec", 10), ("Third", "Thi", 10), ("Fourth", "Fou", 10)]
    return _make_calendar("Compact", data)


@pytest.fixture
def uneven_calendar() -> CalendarConfig:
    """3-month calendar with very different lengths."""
    data = [("Longmonth", "Lon", 40), ("Shortmonth", "Sho", 5), ("Midmonth", "Mid", 20)]
    return _make_calendar("Uneven", data)


@pytest.fixture
def leap_year_calendar() -> CalendarConfig:
    """12-month calendar with a Gregorian-style leap rule on February."""
    data = [
        ("January", "Jan", 31), ("February", "Feb", 28), ("March", "Mar", 31),
        ("April", "Apr", 30), ("May", "May", 31), ("June", "Jun", 30),
        ("July", "Jul", 31), ("August", "Aug", 31), ("September", "Sep", 30),
        ("October", "Oct", 31), ("November", "Nov", 30), ("December", "Dec", 31),
    ]
    leap = LeapYearRule(interval=4, skip_interval=100, reset_interval=400, month_index=1, extra_days=1)
    months = [MonthDefinition(name=n, abbreviation=a, days=d) for n, a, d in data]
    week = WeekDefinition(
        day_names=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        day_abbreviations=["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    )
    return CalendarConfig(
        id="test-leap",
        name="Leap Calendar",
        months=months,
        week=week,
        year_variants=[],
        leap_year_rules=[leap],
        epoch_name="AD",
    )


@pytest.fixture
def year_variant_calendar() -> CalendarConfig:
    """Calendar with a special year variant for year 100."""
    data = [("A", "Aa", 10), ("B", "Bb", 10), ("C", "Cc", 10)]
    normal_months = [MonthDefinition(name=n, abbreviation=a, days=d) for n, a, d in data]
    variant_months = [
        MonthDefinition(name="A", abbreviation="Aa", days=10),
        MonthDefinition(name="B", abbreviation="Bb", days=10),
        MonthDefinition(name="C", abbreviation="Cc", days=15),  # extended
    ]
    variant = YearVariant(year=100, months=variant_months)
    week = WeekDefinition(day_names=["D1", "D2", "D3"], day_abbreviations=["1", "2", "3"])
    return CalendarConfig(
        id="test-variant",
        name="Variant Calendar",
        months=normal_months,
        week=week,
        year_variants=[variant],
        leap_year_rules=[],
        epoch_name="VE",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parser construction
# ─────────────────────────────────────────────────────────────────────────────


class TestParserInit:
    def test_stores_config(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        assert p.calendar_config is tolkien_calendar

    def test_month_lookup_populated(self, gregorian_like):
        p = DateParser(gregorian_like)
        assert p.month_lookup["january"] == 1
        assert p.month_lookup["december"] == 12

    def test_abbreviation_lookup(self, gregorian_like):
        p = DateParser(gregorian_like)
        assert p.month_lookup["jan"] == 1
        assert p.month_lookup["dec"] == 12

    def test_case_insensitive_lookup(self, gregorian_like):
        p = DateParser(gregorian_like)
        assert p.month_lookup["january"] == p.month_lookup["JANUARY".lower()]


# ─────────────────────────────────────────────────────────────────────────────
# Exact dates – natural language
# ─────────────────────────────────────────────────────────────────────────────


class TestExactNaturalLanguage:
    def test_day_month_year(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023")
        assert (r.year, r.month, r.day, r.precision) == (2023, 3, 15, DatePrecision.EXACT)

    def test_ordinal_1st(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("1st January 2000")
        assert (r.day, r.month) == (1, 1)

    def test_ordinal_2nd(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("2nd February 2000").day == 2

    def test_ordinal_3rd(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("3rd March 2000").day == 3

    def test_ordinal_4th(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("4th April 2000").day == 4

    def test_ordinal_21st(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("21st December 1999").day == 21

    def test_first_day(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("1 January 2024").day == 1

    def test_last_day_january(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("31 January 2024").day == 31

    def test_last_day_february(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("28 February 2024").day == 28

    def test_month_day_year_order(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("March 15 2023")
        assert (r.year, r.month, r.day) == (2023, 3, 15)

    def test_case_insensitive(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("15 march 2023").month == 3

    def test_uppercase_month(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("15 MARCH 2023").month == 3

    def test_comma_separator(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("15 March, 2023").year == 2023

    def test_the_nth_day_of(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("the 15th day of March 2023")
        assert (r.day, r.month) == (15, 3)

    def test_invalid_day_31_april(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("31 April 2023")

    def test_invalid_day_29_february_no_leap(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("29 February 2023")

    def test_invalid_day_0(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("0 March 2023")

    def test_weekday_prefix_stripped(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("Highday 25 Rethe 1419")
        assert (r.day, r.month, r.year) == (25, 3, 1419)

    def test_negative_year(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("1 Rethe -100")
        assert r.year == -100

    def test_all_tolkien_month_last_days(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        for m_idx in range(1, 13):
            month_name = tolkien_calendar.months[m_idx - 1].name
            r = p.parse_date(f"30 {month_name} 1419")
            assert r.day == 30, f"Failed for {month_name}"


# ─────────────────────────────────────────────────────────────────────────────
# Exact dates – numeric formats
# ─────────────────────────────────────────────────────────────────────────────


class TestExactNumericFormats:
    def test_dot_eu(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15.3.2023")
        assert (r.year, r.month, r.day) == (2023, 3, 15)

    def test_slash_us(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("3/15/2023")
        assert (r.year, r.month, r.day) == (2023, 3, 15)

    def test_iso_dash(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("2023-03-15")
        assert (r.year, r.month, r.day) == (2023, 3, 15)

    def test_iso_dot(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("2023.03.15")
        assert (r.year, r.month, r.day) == (2023, 3, 15)

    def test_negative_year_iso(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("-100.1.1")
        assert (r.year, r.month, r.day) == (-100, 1, 1)

    def test_epoch_start_dot(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("1.1.1")
        assert (r.year, r.month, r.day) == (1, 1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Time support
# ─────────────────────────────────────────────────────────────────────────────


class TestTimeSupport:
    def test_24h_time_on_exact(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 14:30")
        assert (r.hour, r.minute) == (14, 30)

    def test_seconds_on_exact(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 14:30:45")
        assert r.second == 45

    def test_am(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 2:30 AM")
        assert r.hour == 2

    def test_pm(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 2:30 PM")
        assert r.hour == 14

    def test_noon_12pm(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 12:00 PM")
        assert r.hour == 12

    def test_midnight_12am(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15 March 2023 12:00 AM")
        assert r.hour == 0

    def test_iso_with_time(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("2023-03-15 14:30")
        assert (r.year, r.month, r.day, r.hour, r.minute) == (2023, 3, 15, 14, 30)

    def test_time_only_precision(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("14:30")
        assert r.precision == DatePrecision.TIME

    def test_time_only_values(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("14:30:45")
        assert (r.hour, r.minute, r.second) == (14, 30, 45)

    def test_time_only_year_defaults_1(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("10:00").year == 1

    def test_epoch_start_with_time(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("1.1.1 00:00:00")
        assert (r.year, r.month, r.day, r.hour, r.minute, r.second) == (1, 1, 1, 0, 0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Month-year
# ─────────────────────────────────────────────────────────────────────────────


class TestMonthYear:
    def test_plain(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("March 2023")
        assert (r.precision, r.month, r.year, r.day) == (DatePrecision.MONTH, 3, 2023, None)

    def test_in_prefix(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("in March 2023").precision == DatePrecision.MONTH

    def test_during_prefix(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("during March 2023").precision == DatePrecision.MONTH

    def test_month_of(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("month of March, 2023")
        assert (r.precision, r.month) == (DatePrecision.MONTH, 3)

    def test_tolkien(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("Forelithe 1419")
        assert (r.month, r.year) == (6, 1419)

    def test_abbreviation(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("Mar 2023")
        assert r.month == 3

    def test_forgotten_realms(self, forgotten_realms_calendar):
        r = DateParser(forgotten_realms_calendar).parse_date("Alturiak 1492")
        assert r.month == 2


# ─────────────────────────────────────────────────────────────────────────────
# Year-only
# ─────────────────────────────────────────────────────────────────────────────


class TestYearOnly:
    def test_bare(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("2024")
        assert (r.year, r.precision, r.month) == (2024, DatePrecision.YEAR, None)

    def test_year_keyword(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("Year 2024").year == 2024

    def test_in_year(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("in 2024").year == 2024

    def test_in_the_year(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("in the year 2024").year == 2024

    def test_during_the_year(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("during the year 2024").year == 2024

    def test_single_digit(self, compact_calendar):
        assert DateParser(compact_calendar).parse_date("Year 1").year == 1

    def test_four_digit(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("9999").year == 9999

    def test_negative(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("-500").year == -500


# ─────────────────────────────────────────────────────────────────────────────
# Season
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("season", ["spring", "summer", "autumn", "winter", "harvest"])
def test_bare_season(gregorian_like, season):
    r = DateParser(gregorian_like).parse_date(f"{season} 2024")
    assert (r.precision, r.season) == (DatePrecision.SEASON, season)


@pytest.mark.parametrize("modifier", ["early", "mid", "late"])
def test_season_with_modifier(gregorian_like, modifier):
    r = DateParser(gregorian_like).parse_date(f"{modifier} winter 2024")
    assert (r.precision, r.season) == (DatePrecision.SEASON, "winter")


def test_season_case_insensitive(gregorian_like):
    assert DateParser(gregorian_like).parse_date("Summer 2024").season == "summer"


def test_harvest_season(tolkien_calendar):
    r = DateParser(tolkien_calendar).parse_date("harvest 1419")
    assert (r.season, r.year) == ("harvest", 1419)


# ─────────────────────────────────────────────────────────────────────────────
# Relative
# ─────────────────────────────────────────────────────────────────────────────


class TestRelative:
    def test_before(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("3 days before Battle of Pelennor")
        assert (r.precision, r.relative_days) == (DatePrecision.RELATIVE, -3)

    def test_after(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("7 days after destruction of the Ring")
        assert r.relative_days == 7

    def test_singular_day(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("1 day before the Council").relative_days == -1

    def test_during(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("during the War of the Ring")
        assert (r.precision, r.relative_days) == (DatePrecision.RELATIVE, 0)

    def test_amid(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("amid the great plague").relative_days == 0

    def test_lowercased(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("3 days after Battle of Helm's Deep")
        assert r.relative_to == "battle of helm's deep"

    def test_defaults_year_1(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("5 days after event").year == 1


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy
# ─────────────────────────────────────────────────────────────────────────────


class TestFuzzy:
    def test_around(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("around March 2023")
        assert (r.precision, r.month, r.confidence) == (DatePrecision.FUZZY, 3, 0.8)

    def test_approximately(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("approximately December 2020").precision == DatePrecision.FUZZY

    def test_about(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("about June 2021").precision == DatePrecision.FUZZY

    def test_circa(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("circa January 2019").precision == DatePrecision.FUZZY

    def test_sometime_in(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("sometime in 2023")
        assert (r.precision, r.confidence) == (DatePrecision.FUZZY, 0.5)

    def test_sometime_during(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("sometime during 2020").confidence == 0.5

    def test_around_day_month(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("around 15 March 2023")
        assert (r.day, r.month) == (15, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Range
# ─────────────────────────────────────────────────────────────────────────────


class TestRange:
    def test_from_to(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("from January to March 2023")
        assert (r.precision, r.range_start.month, r.range_end.month) == (DatePrecision.RANGE, 1, 3)

    def test_between(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("between June and August 2023")
        assert (r.range_start.month, r.range_end.month) == (6, 8)

    def test_day_to_day(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("from 5 to 20 March 2023")
        assert (r.range_start.day, r.range_end.day) == (5, 20)

    def test_year_field(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("from January to June 2023").year == 2023

    def test_tolkien(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("from Astron to Thrimidge 1419")
        assert (r.range_start.month, r.range_end.month) == (4, 5)

    def test_multiword_months(self, got_calendar):
        r = DateParser(got_calendar).parse_date("from Moon of Ice to Moon of Fire 300")
        assert (r.range_start.month, r.range_end.month) == (10, 11)

    def test_month_range_precision(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("from January to March 2023")
        assert r.range_start.precision == DatePrecision.MONTH


# ─────────────────────────────────────────────────────────────────────────────
# Leap years and year variants
# ─────────────────────────────────────────────────────────────────────────────


class TestLeapYears:
    def test_non_leap_feb_28_valid(self, leap_year_calendar):
        r = DateParser(leap_year_calendar).parse_date("28 February 2023")
        assert r.day == 28

    def test_non_leap_feb_29_invalid(self, leap_year_calendar):
        with pytest.raises(ValueError):
            DateParser(leap_year_calendar).parse_date("29 February 2023")

    def test_leap_year_feb_29_valid(self, leap_year_calendar):
        r = DateParser(leap_year_calendar).parse_date("29 February 2024")
        assert r.day == 29

    def test_century_not_leap(self, leap_year_calendar):
        with pytest.raises(ValueError):
            DateParser(leap_year_calendar).parse_date("29 February 1900")

    def test_400_year_is_leap(self, leap_year_calendar):
        r = DateParser(leap_year_calendar).parse_date("29 February 2000")
        assert r.day == 29


class TestYearVariants:
    def test_variant_year_extends_month(self, year_variant_calendar):
        r = DateParser(year_variant_calendar).parse_date("15 C 100")
        assert r.day == 15

    def test_normal_year_still_restricted(self, year_variant_calendar):
        with pytest.raises(ValueError):
            DateParser(year_variant_calendar).parse_date("15 C 101")


# ─────────────────────────────────────────────────────────────────────────────
# Compact and uneven calendars
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCalendars:
    def test_compact_first(self, compact_calendar):
        r = DateParser(compact_calendar).parse_date("1 First 1")
        assert (r.year, r.month, r.day) == (1, 1, 1)

    def test_compact_last(self, compact_calendar):
        r = DateParser(compact_calendar).parse_date("10 Fourth 1")
        assert (r.day, r.month) == (10, 4)

    def test_compact_overflow(self, compact_calendar):
        with pytest.raises(ValueError):
            DateParser(compact_calendar).parse_date("11 First 1")

    def test_uneven_longmonth_last(self, uneven_calendar):
        assert DateParser(uneven_calendar).parse_date("40 Longmonth 1000").day == 40

    def test_uneven_longmonth_overflow(self, uneven_calendar):
        with pytest.raises(ValueError):
            DateParser(uneven_calendar).parse_date("41 Longmonth 1000")

    def test_uneven_shortmonth_last(self, uneven_calendar):
        assert DateParser(uneven_calendar).parse_date("5 Shortmonth 1000").day == 5

    def test_uneven_shortmonth_overflow(self, uneven_calendar):
        with pytest.raises(ValueError):
            DateParser(uneven_calendar).parse_date("6 Shortmonth 1000")


# ─────────────────────────────────────────────────────────────────────────────
# Fantasy calendar integration
# ─────────────────────────────────────────────────────────────────────────────


class TestForgottenRealms:
    def test_basic(self, forgotten_realms_calendar):
        r = DateParser(forgotten_realms_calendar).parse_date("1 Hammer 1492")
        assert (r.year, r.month, r.day) == (1492, 1, 1)

    def test_flamerule(self, forgotten_realms_calendar):
        assert DateParser(forgotten_realms_calendar).parse_date("15 Flamerule 1492").month == 7

    def test_nightal_last_day(self, forgotten_realms_calendar):
        r = DateParser(forgotten_realms_calendar).parse_date("30 Nightal 1490")
        assert (r.month, r.day) == (12, 30)

    def test_range(self, forgotten_realms_calendar):
        r = DateParser(forgotten_realms_calendar).parse_date("from Hammer to Alturiak 1492")
        assert (r.range_start.month, r.range_end.month) == (1, 2)

    def test_circa(self, forgotten_realms_calendar):
        r = DateParser(forgotten_realms_calendar).parse_date("circa Uktar 1490")
        assert (r.precision, r.month) == (DatePrecision.FUZZY, 11)


class TestGoTCalendar:
    def test_multiword_exact(self, got_calendar):
        r = DateParser(got_calendar).parse_date("15 Moon of Long Night 298")
        assert (r.year, r.month, r.day) == (298, 1, 15)

    def test_multiword_month_year(self, got_calendar):
        r = DateParser(got_calendar).parse_date("Moon of Dragons 300")
        assert (r.month, r.precision) == (12, DatePrecision.MONTH)

    def test_last_day_28(self, got_calendar):
        assert DateParser(got_calendar).parse_date("28 Moon of Fire 300").day == 28

    def test_day_29_invalid(self, got_calendar):
        with pytest.raises(ValueError):
            DateParser(got_calendar).parse_date("29 Moon of Fire 300")


# ─────────────────────────────────────────────────────────────────────────────
# calculate_timestamp
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateTimestamp:
    def test_epoch_start_is_zero(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        r = p.parse_date("1.1.1 00:00:00")
        assert p.calculate_timestamp(r) == 0.0

    def test_day_2_is_1(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        assert p.calculate_timestamp(p.parse_date("2 Afteryule 1")) == 1.0

    def test_second_month_start(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        assert p.calculate_timestamp(p.parse_date("1 Solmath 1")) == 30.0

    def test_negative_year_negative_float(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        assert p.calculate_timestamp(p.parse_date("-100.1.1")) < 0.0

    def test_month_precision_defaults_day_1(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        ts_month = p.calculate_timestamp(p.parse_date("Afteryule 1"))
        ts_exact = p.calculate_timestamp(p.parse_date("1 Afteryule 1"))
        assert ts_month == ts_exact

    def test_noon_adds_half(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        assert p.calculate_timestamp(p.parse_date("1.1.1 12:00:00")) == pytest.approx(0.5)

    def test_positive_float_for_real_date(self, gregorian_like):
        p = DateParser(gregorian_like)
        assert p.calculate_timestamp(p.parse_date("2023-03-15")) > 0.0

    def test_no_year_raises(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        with pytest.raises((ValueError, TypeError)):
            pd = ParsedDate.__new__(ParsedDate)
            object.__setattr__(pd, "year", None)
            p.calculate_timestamp(pd)

    def test_relative_precision_raises(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        relative = p.parse_date("7 days after destruction of the Ring")
        assert relative.precision == DatePrecision.RELATIVE
        with pytest.raises(ValueError, match="Cannot calculate an absolute timestamp for a relative date"):
            p.calculate_timestamp(relative)


# ─────────────────────────────────────────────────────────────────────────────
# JSON round-trips
# ─────────────────────────────────────────────────────────────────────────────


class TestJsonRoundTrip:
    def _rt(self, p: DateParser, date_str: str):
        orig = p.parse_date(date_str)
        return orig, p.from_json(p.to_json(orig))

    def test_exact(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "25 Rethe 1419")
        assert o == r

    def test_month_year(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "Halimath 1419")
        assert o == r

    def test_year_only(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "1419")
        assert o == r

    def test_season(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "spring 1419")
        assert o == r

    def test_relative(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "3 days after Battle of Pelennor")
        assert o == r

    def test_fuzzy(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "around Halimath 1419")
        assert o == r

    def test_range(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "from Rethe to Astron 1419")
        assert o == r

    def test_exact_with_time(self, tolkien_calendar):
        p = DateParser(tolkien_calendar)
        o, r = self._rt(p, "25 Rethe 1419 14:30:00")
        assert o == r

    def test_to_json_none(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).to_json(None) is None

    def test_from_json_none(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).from_json(None) is None

    def test_precision_name_in_json(self, gregorian_like):
        p = DateParser(gregorian_like)
        assert p.to_json(p.parse_date("15 March 2023"))["precision"] == "EXACT"

    def test_nested_range_in_json(self, gregorian_like):
        p = DateParser(gregorian_like)
        d = p.to_json(p.parse_date("from January to March 2023"))
        assert d["range_start"]["month"] == 1
        assert d["range_end"]["month"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestErrors:
    def test_empty_string(self, gregorian_like):
        with pytest.raises(ValueError, match="Empty date string"):
            DateParser(gregorian_like).parse_date("")

    def test_whitespace_only(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("   ")

    def test_unknown_month(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("15 Rethe 2024")

    def test_completely_invalid(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("not a date at all ???")

    def test_month_without_year(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("March")

    def test_day_without_context(self, gregorian_like):
        with pytest.raises(ValueError):
            DateParser(gregorian_like).parse_date("15th")


# ─────────────────────────────────────────────────────────────────────────────
# Whitespace
# ─────────────────────────────────────────────────────────────────────────────


class TestWhitespace:
    def test_leading_trailing(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("  15 March 2023  ").year == 2023

    def test_multiple_internal_spaces(self, gregorian_like):
        assert DateParser(gregorian_like).parse_date("15  March  2023").year == 2023


# ─────────────────────────────────────────────────────────────────────────────
# Importer integration scenarios
# ─────────────────────────────────────────────────────────────────────────────


class TestImporterScenarios:
    def test_battle_exact(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("25 Rethe 1419")
        assert (r.day, r.month, r.year) == (25, 3, 1419)

    def test_historical_month_only(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("Winterfilth 1418")
        assert (r.precision, r.month) == (DatePrecision.MONTH, 10)

    def test_founding_year(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("Year 1").year == 1

    def test_uncertain_circa(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("circa Forelithe 1400").precision == DatePrecision.FUZZY

    def test_siege_day_range(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("from 10 to 15 Rethe 1419")
        assert (r.range_start.day, r.range_end.day) == (10, 15)

    def test_relative_after(self, tolkien_calendar):
        r = DateParser(tolkien_calendar).parse_date("2 days after the destruction of the One Ring")
        assert r.relative_days == 2
        assert "one ring" in r.relative_to

    def test_harvest_season(self, tolkien_calendar):
        assert DateParser(tolkien_calendar).parse_date("harvest 1419").season == "harvest"

    def test_iso_import(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("2023-11-15")
        assert (r.year, r.month, r.day) == (2023, 11, 15)

    def test_eu_numeric_import(self, gregorian_like):
        r = DateParser(gregorian_like).parse_date("15.11.2023")
        assert (r.year, r.month, r.day) == (2023, 11, 15)
