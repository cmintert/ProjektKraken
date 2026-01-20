from enum import Enum, auto
from typing import Dict, List, Optional, Any, Set, Tuple
import re
from dataclasses import dataclass


class DatePrecision(Enum):
    """Defines the precision level of a parsed date"""

    EXACT = auto()  # Complete date with day, month, year
    MONTH = auto()  # Month and year only
    YEAR = auto()  # Year only
    FUZZY = auto()  # Approximate date
    RELATIVE = auto()  # Date relative to another event
    SEASON = auto()  # Season-based date
    RANGE = auto()  # Date range


@dataclass
class ParsedDate:
    """Represents a parsed date with configurable precision"""

    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    precision: DatePrecision = DatePrecision.EXACT
    relative_to: Optional[str] = None
    relative_days: Optional[int] = None
    confidence: float = 1.0
    season: Optional[str] = None
    range_start: Optional["ParsedDate"] = None
    range_end: Optional["ParsedDate"] = None

    def __post_init__(self):
        """Validate the date components based on precision"""
        if self.precision == DatePrecision.EXACT:
            if self.month is None or self.day is None:
                # Allow missing components in range dates
                if not (self.range_start or self.range_end):
                    raise ValueError("Exact dates must have month and day")

        if self.precision == DatePrecision.RELATIVE and self.relative_to is None:
            raise ValueError("Relative dates must specify reference event")

        if self.precision == DatePrecision.SEASON and self.season is None:
            raise ValueError("Season dates must specify season")

        if self.precision == DatePrecision.RANGE and (
            self.range_start is None or self.range_end is None
        ):
            raise ValueError("Range dates must specify start and end")


class DateParser:
    """A unified parser for custom calendar dates supporting both standard and natural language formats"""

    def __init__(self, calendar_data: Dict[str, Any]):
        """Initialize the date parser with calendar configuration

        The parser supports multiple date formats:
        - Standard notation (15.3.3019, 3/15/3019)
        - Natural language ("15th day of Wintermarch, 3019")
        - Month-year ("Wintermarch 3019")
        - Year only ("Year 3019")
        - Seasons ("Early spring 3019")
        - Relative dates ("2 days after Battle")
        - Fuzzy dates ("Around Wintermarch 3019")
        - Date ranges ("From Wintermarch to Summerday 3019")

        Args:
            calendar_data: Dictionary containing calendar configuration including:
                - month_names: List of month names
                - month_days: List of days in each month
                - year_length: Total days in year
                - current_year: Current year in calendar
        """
        self.calendar = calendar_data
        self._validate_calendar()
        self._generate_month_formats()
        self._compile_all_patterns()

    def _validate_calendar(self) -> None:
        """Validate calendar configuration completeness and consistency"""
        required = {"month_names", "month_days", "year_length"}
        missing = required - set(self.calendar.keys())
        if missing:
            raise ValueError(f"Missing required calendar fields: {missing}")

        if len(self.calendar["month_names"]) != len(self.calendar["month_days"]):
            raise ValueError("Number of months must match number of month day counts")

        if sum(self.calendar["month_days"]) != self.calendar["year_length"]:
            raise ValueError("Sum of month days must match year length")

    def _generate_month_formats(self) -> None:
        """Generate standard and abbreviated month name formats

        Creates a systematic set of month name variations including:
        - Full name (e.g., "Wintermarch")
        - Abbreviation (e.g., "Win")
        - Multi-word abbreviations (e.g., "HM" for "Harvest Moon")

        Ensures all abbreviations are unique through fallback strategies.
        """
        self.month_formats = {}
        used_abbrevs = set()

        for idx, month in enumerate(self.calendar["month_names"], 1):
            formats = {"full": month, "lower": month.lower(), "upper": month.upper()}

            # Generate abbreviation
            words = month.split()
            if len(words) > 1:
                # Multi-word abbreviation using first letters
                abbrev = "".join(word[0] for word in words)
            else:
                # Single word abbreviation using first three letters
                abbrev = month[:3]

            # Ensure uniqueness through multiple strategies
            base_abbrev = abbrev
            counter = 1
            while abbrev.lower() in used_abbrevs:
                if counter == 1:
                    # Try first two + last letter
                    abbrev = f"{month[:2]}{month[-1]}"
                elif counter == 2:
                    # Try consonants after first letter
                    consonants = [c for c in month[1:] if c.lower() not in "aeiou"]
                    if len(consonants) >= 2:
                        abbrev = f"{month[0]}{consonants[0]}{consonants[1]}"
                else:
                    # Add numeric suffix as last resort
                    abbrev = f"{base_abbrev}{counter}"
                counter += 1

            used_abbrevs.add(abbrev.lower())
            formats["abbrev"] = abbrev

            # Store all formats for this month
            self.month_formats[idx] = formats

        # Create reverse lookups for parsing
        self.month_lookup = {}
        for month_num, formats in self.month_formats.items():
            for format_name, value in formats.items():
                self.month_lookup[value.lower()] = month_num

    def _compile_all_patterns(self) -> None:
        """Compile all date parsing patterns"""
        # Escape all special characters in month names and join with |
        month_names = sorted(self.calendar["month_names"], key=len, reverse=True)
        month_names = [re.escape(name) for name in month_names]
        month_pattern = f'({"|".join(month_names)})'

        # Basic components
        day = r"(\d{1,2})(?:st|nd|rd|th)?"
        year = r"(?P<year>\d{1,4})"

        # Separators and optional parts
        space = r"\s+"
        opt_space = r"\s*"
        comma = r","
        opt_comma = f"{comma}?"

        # Common phrases
        of_part = f"(?:{opt_space}of{opt_space})?"
        the_part = f"(?:the{space})?"
        day_part = f"(?:{space}day{opt_space})?"
        month_part = f"(?:month{space}of{space})?"

        # Weekday pattern (if weekdays are defined)
        weekday_prefix = ""
        if weekday_names := self.calendar.get("weekday_names"):
            weekday_names = sorted(weekday_names, key=len, reverse=True)
            weekday_pattern = "|".join(re.escape(name) for name in weekday_names)
            weekday_prefix = (
                f"(?:(?:{weekday_pattern}){opt_space}{opt_comma}{opt_space})?"
            )

        season_names = "spring|summer|autumn|winter|harvest"
        time_modifier = f"(?:early|mid|late){space}"

        # Compile patterns in specific order
        self.compiled_patterns = {
            "month_year": [
                # Basic Month Year format
                re.compile(
                    f"^{month_pattern}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                # "In Month Year" format
                re.compile(
                    f"^(?:in|during){space}{month_pattern}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                # "The month of Month, Year" format
                re.compile(
                    f"^{the_part}?(?:month{space}of{space})?{month_pattern}{opt_space}{opt_comma}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            "exact": [
                # "Weekday, the Xth day of Month, Year" format
                re.compile(
                    f"^{weekday_prefix}{the_part}?{day}{day_part}{of_part}{month_pattern}"
                    f"{opt_space}{opt_comma}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                # "Weekday, Month the Xth, Year" format
                re.compile(
                    f"^{weekday_prefix}{month_pattern}{space}{the_part}?{day}{opt_space}{opt_comma}"
                    f"{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                # "Weekday, X Month Year" format
                re.compile(
                    f"^{weekday_prefix}{day}{space}{month_pattern}{opt_space}{opt_comma}"
                    f"{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                # Basic "day Month Year" format (without weekday)
                re.compile(
                    f"^{day}{space}{month_pattern}{opt_space}{opt_comma}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            "year": [
                # Basic year format
                re.compile(
                    f"^(?:year{space})?{year}$",
                    re.IGNORECASE,
                ),
                # "In/During year" format
                re.compile(
                    f"^(?:in|during){space}{the_part}?(?:year{space})?{year}$",
                    re.IGNORECASE,
                ),
            ],
            "season": [
                # With time modifier (early/mid/late)
                re.compile(
                    f"^{time_modifier}({season_names}){opt_space}{of_part}{year}$",
                    re.IGNORECASE,
                ),
                # Without time modifier
                re.compile(
                    f"^({season_names}){opt_space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            "relative": [
                # X days before/after format - capture everything after before/after as the event
                re.compile(
                    r"^(\d{1,2})\s+days?\s+(before|after)\s+(.+)$",
                    re.IGNORECASE,
                ),
                # During event format
                re.compile(
                    r"^(?:during|amid)\s+(.+)$",
                    re.IGNORECASE,
                ),
            ],
            "fuzzy": [
                # "Around Month Year"
                re.compile(
                    f"^(?:around|approximately|about|circa){space}{month_pattern}{space}{year}$",
                    re.IGNORECASE,
                ),
                # "Around day Month Year"
                re.compile(
                    f"^(?:around|approximately|about|circa){space}{day}{space}{month_pattern}{space}{year}$",
                    re.IGNORECASE,
                ),
                # "Sometime during Year"
                re.compile(
                    f"^sometime{space}(?:in|during){space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            "range": [
                # "From/Between Month and Month Year"
                re.compile(
                    f"^(?:from|between){space}{month_pattern}{space}(?:and|to){space}{month_pattern}{space}{year}$",
                    re.IGNORECASE,
                ),
                # "From day to day Month Year"
                re.compile(
                    f"^from{space}{day}{space}to{space}{day}{space}{month_pattern}{space}{year}$",
                    re.IGNORECASE,
                ),
            ],
        }

    def parse_date(self, date_str: str) -> ParsedDate:
        """Parse a date string into a ParsedDate object"""
        if not date_str:
            raise ValueError("Empty date string")

        date_str = date_str.strip()

        try:
            if parsed := self._try_natural_language(date_str):
                return parsed
            raise ValueError(f"Could not parse date: {date_str}")
        except Exception as e:
            # Wrap all parsing errors with context
            raise ValueError(f"Failed to parse '{date_str}': {str(e)}")

    def _parse_exact_date(self, match) -> ParsedDate:
        """Parse exact dates from regex match"""
        # Get all non-None groups and clean them
        groups = [g.strip() for g in match.groups() if g is not None]
        groupdict = match.groupdict()

        try:
            # Extract year using named group
            year = int(groupdict["year"])

            # Find month name (case-insensitive)
            month_name = next(
                g
                for g in groups
                if any(
                    month.lower() == g.lower() for month in self.calendar["month_names"]
                )
            )
            month = self.month_lookup[month_name.lower()]

            # Find day number (strip ordinal suffix)
            day_match = next(
                g for g in groups if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", g)
            )
            day = int(re.match(r"\d+", day_match).group())

            # Validate components
            if not self._validate_date(year, month, day):
                raise ValueError(f"Invalid date: {day} {month_name} {year}")

            return ParsedDate(year=year, month=month, day=day)

        except (StopIteration, ValueError, AttributeError) as e:
            raise ValueError(f"Failed to parse exact date: {str(e)}")

    def _try_natural_language(self, date_str: str) -> Optional[ParsedDate]:
        """Try each pattern type in priority order"""
        try:
            # Try each pattern type
            for pattern_type, patterns in self.compiled_patterns.items():
                for pattern in patterns:
                    if match := pattern.match(date_str):
                        if pattern_type == "exact":
                            return self._parse_exact_date(match)
                        elif pattern_type == "month_year":
                            return self._parse_month_year(match)
                        elif pattern_type == "year":
                            return self._parse_year_only(match)
                        elif pattern_type == "season":
                            return self._parse_season_date(match)
                        elif pattern_type == "relative":
                            return self._parse_relative_date(match)
                        elif pattern_type == "fuzzy":
                            return self._parse_fuzzy_date(match)
                        elif pattern_type == "range":
                            return self._parse_date_range(match)
            return None
        except ValueError as e:
            # Convert parsing errors to None to allow fallback to other patterns
            return None

    def _validate_date(self, year: int, month: int, day: int) -> bool:
        """Validate a date against the calendar configuration"""
        if month < 1 or month > len(self.calendar["month_days"]):
            return False

        if day < 1 or day > self.calendar["month_days"][month - 1]:
            return False

        return True

    def _parse_month_year(self, match) -> ParsedDate:
        """Parse month-year combinations with support for compound month names"""
        groups = [g for g in match.groups() if g is not None]
        try:
            # Extract year
            year = int(next(g for g in reversed(groups) if re.match(r"^\d{1,4}$", g)))

            # Find the month name that matches a key in the month_lookup (case-insensitive)
            month_name = next(g for g in groups if g.lower() in self.month_lookup)

            # Look up month number
            month = self.month_lookup[month_name.lower()]

            return ParsedDate(year=year, month=month, precision=DatePrecision.MONTH)
        except (StopIteration, ValueError) as e:
            raise ValueError(
                f"Failed to parse month-year date: {str(e)} (groups: {groups})"
            )

    def _parse_year_only(self, match) -> ParsedDate:
        """Parse year-only dates"""
        year = int(next(g for g in match.groups() if g and g.isdigit()))
        return ParsedDate(year=year, precision=DatePrecision.YEAR)

    def _parse_season_date(self, match) -> ParsedDate:
        """Parse season-based dates"""
        groups = [g for g in match.groups() if g is not None]

        # Extract year (always last number)
        year = int(next(g for g in reversed(groups) if re.match(r"^\d{1,4}$", g)))

        # Get season (will be either last or second-to-last group depending on modifier)
        season = next(
            g
            for g in reversed(groups)
            if re.match(r"^(spring|summer|autumn|winter|harvest)$", g, re.IGNORECASE)
        )

        return ParsedDate(
            year=year, precision=DatePrecision.SEASON, season=season.lower()
        )

    def _parse_relative_date(self, match) -> ParsedDate:
        """Parse relative dates"""
        groups = match.groups()

        if len(groups) == 3:  # "X days before/after EVENT"
            days = int(groups[0])
            direction = groups[1]
            event = groups[2]
            relative_days = -days if direction.lower() == "before" else days
        else:  # "during EVENT"
            event = groups[0]
            relative_days = 0

        return ParsedDate(
            year=self.calendar.get("current_year", 1),
            precision=DatePrecision.RELATIVE,
            relative_to=event.strip().lower(),
            relative_days=relative_days,
        )

    def _parse_fuzzy_date(self, match) -> ParsedDate:
        """Parse fuzzy dates with proper confidence levels"""
        groups = [g for g in match.groups() if g is not None]

        # Extract year - always the last number in groups
        year = int(next(g for g in reversed(groups) if re.match(r"^\d{4}$", g)))

        # Try to find month name
        month = None
        for g in groups:
            if g.lower() in self.month_lookup:
                month = self.month_lookup[g.lower()]
                break

        # Try to find day number (if it exists)
        day = None
        for g in groups:
            if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", g):
                day = int(re.match(r"\d+", g).group())
                break

        # Set confidence based on pattern type
        confidence = 0.5 if "sometime" in match.re.pattern.lower() else 0.8

        return ParsedDate(
            year=year,
            month=month,
            day=day,
            precision=DatePrecision.FUZZY,
            confidence=confidence,
        )

    def _parse_date_range(self, match) -> ParsedDate:
        """Parse date ranges with proper handling of months and days"""
        groups = [g for g in match.groups() if g is not None]

        # Extract year (always last numeric group)
        year = int(next(g for g in reversed(groups) if re.match(r"^\d{4}$", g)))

        # Find months by comparing with calendar months
        months = []
        for g in groups:
            if g.lower() in self.month_lookup:
                months.append(self.month_lookup[g.lower()])

        # Find days if they exist
        days = []
        for g in groups:
            if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", g):
                days.append(int(re.match(r"\d+", g).group()))

        if len(days) == 2:  # Day-to-day range
            start_date = ParsedDate(year=year, month=months[0], day=days[0])
            end_date = ParsedDate(year=year, month=months[0], day=days[1])
        else:  # Month-to-month range
            start_date = ParsedDate(
                year=year, month=months[0], precision=DatePrecision.MONTH
            )
            end_date = ParsedDate(
                year=year, month=months[1], precision=DatePrecision.MONTH
            )

        return ParsedDate(
            year=year,
            precision=DatePrecision.RANGE,
            range_start=start_date,
            range_end=end_date,
        )

    def to_json(self, parsed_date: Optional[ParsedDate]) -> Optional[Dict[str, Any]]:
        """Convert a ParsedDate object to a JSON-serializable dictionary

        Args:
            parsed_date: The ParsedDate object to convert

        Returns:
            Dictionary representation of the date, or None if input is None
        """
        if parsed_date is None:
            return None

        range_start_json = (
            self.to_json(parsed_date.range_start) if parsed_date.range_start else None
        )
        range_end_json = (
            self.to_json(parsed_date.range_end) if parsed_date.range_end else None
        )

        return {
            "year": parsed_date.year,
            "month": parsed_date.month,
            "day": parsed_date.day,
            "precision": parsed_date.precision.name,
            "relative_to": parsed_date.relative_to,
            "relative_days": parsed_date.relative_days,
            "confidence": parsed_date.confidence,
            "season": parsed_date.season,
            "range_start": range_start_json,
            "range_end": range_end_json,
        }

    def from_json(self, json_data: Optional[Dict[str, Any]]) -> Optional[ParsedDate]:
        """Create a ParsedDate object from a JSON dictionary

        Args:
            json_data: Dictionary containing date information

        Returns:
            ParsedDate object, or None if input is None
        """
        if json_data is None:
            return None

        range_start_parsed = self.from_json(json_data.get("range_start"))
        range_end_parsed = self.from_json(json_data.get("range_end"))

        return ParsedDate(
            year=json_data["year"],
            month=json_data.get("month"),
            day=json_data.get("day"),
            precision=DatePrecision[json_data["precision"]],
            relative_to=json_data.get("relative_to"),
            relative_days=json_data.get("relative_days"),
            confidence=json_data.get("confidence", 1.0),
            season=json_data.get("season"),
            range_start=range_start_parsed,
            range_end=range_end_parsed,
        )
