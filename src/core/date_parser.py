"""Date Parser Module.

Provides a unified parser for custom calendar dates supporting both structured
numeric formats and natural language expressions. Works with CalendarConfig.
"""

import re
from typing import Any, Dict, List, Optional

from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.parsed_date import DatePrecision, ParsedDate


class DateParser:
    """A unified parser for custom calendar dates using CalendarConfig.

    Supports the full range of date formats:
    - Numeric: DD.MM.YYYY, MM/DD/YYYY, YYYY-MM-DD, YYYY.MM.DD
    - Natural language exact: "15 March 3019", "the 15th day of March, 3019"
    - Month-year: "March 3019", "in March 3019"
    - Year-only: "3019", "Year 3019"
    - Season: "spring 3019", "early winter 3019"
    - Relative: "3 days before Battle", "during the Siege"
    - Fuzzy: "around March 3019", "circa 3019", "sometime in 3019"
    - Range: "from March to June 3019", "from 1 to 15 March 3019"
    - Time: "14:30", "2:30 PM"
    - Exact with time: "15 March 3019 14:30"
    """

    def __init__(self, calendar_config: CalendarConfig) -> None:
        """Initialize the date parser with calendar configuration.

        Args:
            calendar_config: The application's calendar configuration.

        """
        self.calendar_config = calendar_config
        self.converter = CalendarConverter(calendar_config)
        self._generate_month_formats()
        self._compile_all_patterns()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialization helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_month_formats(self) -> None:
        """Build month name → index lookup, including abbreviations.

        Uses CalendarConfig-defined abbreviations when available, and falls
        back to automatic generation (with collision resolution) for completeness.
        Stores both in self.month_lookup for case-insensitive lookup.
        """
        self.month_lookup: Dict[str, int] = {}
        used_abbrevs: set = set()

        for idx, month_def in enumerate(self.calendar_config.months, 1):
            name = month_def.name
            self.month_lookup[name.lower()] = idx

            # Prefer the CalendarConfig-defined abbreviation
            abbrev = month_def.abbreviation.strip() if month_def.abbreviation else ""
            if abbrev:
                self.month_lookup[abbrev.lower()] = idx
                used_abbrevs.add(abbrev.lower())
            else:
                # Auto-generate abbreviation with collision resolution
                words = name.split()
                if len(words) > 1:
                    abbrev = "".join(word[0] for word in words)
                else:
                    abbrev = name[:3]

                base_abbrev = abbrev
                counter = 1
                while abbrev.lower() in used_abbrevs:
                    if counter == 1:
                        abbrev = f"{name[:2]}{name[-1]}"
                    elif counter == 2:
                        consonants = [c for c in name[1:] if c.lower() not in "aeiou"]
                        if len(consonants) >= 2:
                            abbrev = f"{name[0]}{consonants[0]}{consonants[1]}"
                        else:
                            abbrev = f"{base_abbrev}{counter}"
                    else:
                        abbrev = f"{base_abbrev}{counter}"
                    counter += 1

                used_abbrevs.add(abbrev.lower())
                self.month_lookup[abbrev.lower()] = idx

    def _compile_all_patterns(self) -> None:
        """Compile all regex patterns for the various date formats."""
        # Month tokens (names + abbreviations) sorted longest-first for greedy match
        all_month_tokens = sorted(
            list(self.month_lookup.keys()), key=len, reverse=True
        )
        month_pattern_with_abbrev = f"({'|'.join(re.escape(t) for t in all_month_tokens)})"

        # Regex building blocks
        day = r"(\d{1,2})(?:st|nd|rd|th)?"
        year = r"(?P<year>-?\d+)"
        space = r"\s+"
        opt_space = r"\s*"
        opt_comma = r",?"

        of_part = f"(?:{opt_space}of{opt_space})?"
        the_part = f"(?:the{space})?"
        day_part = f"(?:{space}day{opt_space})?"

        # Weekday prefix (optional)
        weekday_prefix = ""
        if self.calendar_config.week and self.calendar_config.week.day_names:
            weekday_names = sorted(
                self.calendar_config.week.day_names, key=len, reverse=True
            )
            wday_pat = "|".join(re.escape(n) for n in weekday_names)
            weekday_prefix = f"(?:(?:{wday_pat}){opt_space}{opt_comma}{opt_space})?"

        season_names_str = "spring|summer|autumn|winter|harvest"
        time_modifier = f"(?:early|mid|late){space}"

        # Time sub-pattern (named groups for hour/minute/second/meridiem)
        time_pattern = (
            r"(?P<time>(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?)"
            r"(?P<meridiem>\s*(?:AM|PM|am|pm))?"
        )
        opt_time_part = f"(?:(?:{space}|T){time_pattern})?"

        # Dash character class for range notation (en-dash, em-dash, hyphen)
        dash = r"[\u2013\u2014\-]"
        opt_dash_space = f"{opt_space}{dash}{opt_space}"

        # Use abbreviation-aware month pattern for all natural-language matches
        mp = month_pattern_with_abbrev

        self.compiled_patterns: Dict[str, List[re.Pattern]] = {
            # ── Month-Year ───────────────────────────────────────────────────
            "month_year": [
                re.compile(
                    f"^{month_pattern_with_abbrev}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                re.compile(
                    f"^(?:in|during){space}{month_pattern_with_abbrev}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
                re.compile(
                    f"^{the_part}?(?:month{space}of{space})?{month_pattern_with_abbrev}"
                    f"{opt_space}{opt_comma}{opt_space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            # ── Exact ────────────────────────────────────────────────────────
            "exact": [
                # Natural language: (weekday,) (the) Nth (day) (of) Month, Year (time)
                re.compile(
                    f"^{weekday_prefix}{the_part}?{day}{day_part}{of_part}{mp}"
                    f"{opt_space}{opt_comma}{opt_space}{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # Natural language: (weekday,) Month (the) Nth, Year (time)
                re.compile(
                    f"^{weekday_prefix}{mp}{space}{the_part}?{day}"
                    f"{opt_space}{opt_comma}{opt_space}{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # Natural language: (weekday,) N Month, Year (time)
                re.compile(
                    f"^{weekday_prefix}{day}{space}{mp}"
                    f"{opt_space}{opt_comma}{opt_space}{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # Same but no weekday prefix fallback
                re.compile(
                    f"^{day}{space}{mp}"
                    f"{opt_space}{opt_comma}{opt_space}{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # Numeric EU: DD.MM.YYYY
                re.compile(
                    f"^(?P<day_num>\\d{{1,2}})\\.(?P<month_num>\\d{{1,2}})\\.{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # Numeric US: MM/DD/YYYY
                re.compile(
                    f"^(?P<month_num_us>\\d{{1,2}})/(?P<day_num_us>\\d{{1,2}})/{year}{opt_time_part}$",
                    re.IGNORECASE,
                ),
                # ISO-like: YYYY.MM.DD
                re.compile(
                    f"^{year}\\.(?P<month_num>\\d{{1,2}})\\.(?P<day_num>\\d{{1,2}}){opt_time_part}$",
                    re.IGNORECASE,
                ),
                # ISO-like: YYYY-MM-DD
                re.compile(
                    f"^{year}-(?P<month_num>\\d{{1,2}})-(?P<day_num>\\d{{1,2}}){opt_time_part}$",
                    re.IGNORECASE,
                ),
            ],
            # ── Time-only ────────────────────────────────────────────────────
            "time": [
                re.compile(f"^{time_pattern}$", re.IGNORECASE),
            ],
            # ── Year-only ────────────────────────────────────────────────────
            "year": [
                re.compile(f"^(?:year{space})?{year}$", re.IGNORECASE),
                re.compile(
                    f"^(?:in|during){space}{the_part}?(?:year{space})?{year}$",
                    re.IGNORECASE,
                ),
            ],
            # ── Season ───────────────────────────────────────────────────────
            "season": [
                re.compile(
                    f"^{time_modifier}({season_names_str}){opt_space}{of_part}{year}$",
                    re.IGNORECASE,
                ),
                re.compile(
                    f"^({season_names_str}){opt_space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            # ── Relative ─────────────────────────────────────────────────────
            "relative": [
                re.compile(
                    r"^(\d{1,2})\s+days?\s+(before|after)\s+(.+)$",
                    re.IGNORECASE,
                ),
                re.compile(r"^(?:during|amid)\s+(.+)$", re.IGNORECASE),
            ],
            # ── Fuzzy ────────────────────────────────────────────────────────
            "fuzzy": [
                re.compile(
                    f"^(?:around|approximately|about|circa){space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                re.compile(
                    f"^(?:around|approximately|about|circa){space}{day}{space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                re.compile(
                    f"^sometime{space}(?:in|during){space}{year}$",
                    re.IGNORECASE,
                ),
            ],
            # ── Range ────────────────────────────────────────────────────────
            "range": [
                # Cross-month day range: "23 AUG–6 SEP 1895"
                re.compile(
                    f"^{day}{space}{mp}{opt_dash_space}{day}{space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                # Same-month day range: "23–30 AUG 1895"
                re.compile(
                    f"^{day}{opt_dash_space}{day}{space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                # Month-to-month range (dash): "AUG–SEP 1895"
                re.compile(
                    f"^{mp}{opt_dash_space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                # Keyword: "from March to June 3019" / "between March and June 3019"
                re.compile(
                    f"^(?:from|between){space}{mp}{space}(?:and|to){space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
                # Keyword: "from 1 to 15 March 3019"
                re.compile(
                    f"^from{space}{day}{space}to{space}{day}{space}{mp}{space}{year}$",
                    re.IGNORECASE,
                ),
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def parse_date(self, date_str: str) -> ParsedDate:
        """Parse a date string into a ParsedDate object.

        Args:
            date_str: The date string to parse.

        Returns:
            ParsedDate: The parsed date with appropriate precision.

        Raises:
            ValueError: If the string is empty or cannot be parsed.

        """
        if not date_str:
            raise ValueError("Empty date string")

        date_str = date_str.strip()

        try:
            if parsed := self._try_natural_language(date_str):
                return parsed
            raise ValueError(f"Could not parse date: {date_str}")
        except Exception as e:
            raise ValueError(f"Failed to parse '{date_str}': {str(e)}")

    def calculate_timestamp(self, parsed_date: ParsedDate) -> float:
        """Convert a ParsedDate to an absolute float timestamp.

        Args:
            parsed_date: The parsed date to convert.

        Returns:
            float: Absolute day value where 0.0 = start of Epoch (Year 1, Month 1, Day 1).

        Raises:
            ValueError: If the parsed date has no year or is a relative-precision date.

        """
        if parsed_date.precision == DatePrecision.RELATIVE:
            raise ValueError(
                "Cannot calculate an absolute timestamp for a relative date. "
                "Resolve the relative offset against a reference date first."
            )

        if parsed_date.year is None:
            raise ValueError("Cannot calculate timestamp without year")

        month = parsed_date.month or 1
        day = parsed_date.day or 1

        hour = parsed_date.hour or 0
        minute = parsed_date.minute or 0
        second = parsed_date.second or 0
        time_fraction = (hour * 3600 + minute * 60 + second) / 86400.0

        cal_date = CalendarDate(
            year=parsed_date.year,
            month=month,
            day=day,
            time_fraction=time_fraction,
        )
        return self.converter.to_float(cal_date)

    def to_json(self, parsed_date: Optional[ParsedDate]) -> Optional[Dict[str, Any]]:
        """Serialize a ParsedDate to a JSON-safe dictionary.

        Args:
            parsed_date: The date to serialize, or None.

        Returns:
            Dictionary representation, or None if input is None.

        """
        if parsed_date is None:
            return None

        return {
            "year": parsed_date.year,
            "month": parsed_date.month,
            "day": parsed_date.day,
            "precision": parsed_date.precision.name,
            "relative_to": parsed_date.relative_to,
            "relative_days": parsed_date.relative_days,
            "confidence": parsed_date.confidence,
            "season": parsed_date.season,
            "hour": parsed_date.hour,
            "minute": parsed_date.minute,
            "second": parsed_date.second,
            "range_start": self.to_json(parsed_date.range_start),
            "range_end": self.to_json(parsed_date.range_end),
        }

    def from_json(self, json_data: Optional[Dict[str, Any]]) -> Optional[ParsedDate]:
        """Deserialize a ParsedDate from a dictionary.

        Args:
            json_data: Dictionary as produced by to_json(), or None.

        Returns:
            ParsedDate, or None if input is None.

        """
        if json_data is None:
            return None

        return ParsedDate(
            year=json_data["year"],
            month=json_data.get("month"),
            day=json_data.get("day"),
            precision=DatePrecision[json_data["precision"]],
            relative_to=json_data.get("relative_to"),
            relative_days=json_data.get("relative_days"),
            confidence=json_data.get("confidence", 1.0),
            season=json_data.get("season"),
            hour=json_data.get("hour"),
            minute=json_data.get("minute"),
            second=json_data.get("second"),
            range_start=self.from_json(json_data.get("range_start")),
            range_end=self.from_json(json_data.get("range_end")),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Pattern dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _try_natural_language(self, date_str: str) -> Optional[ParsedDate]:
        """Try each pattern type in priority order."""
        for pattern_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if match := pattern.match(date_str):
                    try:
                        if pattern_type == "exact":
                            return self._parse_exact_date(match)
                        elif pattern_type == "time":
                            return self._parse_time(match)
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
                    except (ValueError, IndexError, StopIteration):
                        continue
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Per-precision parsers
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_exact_date(self, match: re.Match) -> ParsedDate:
        """Parse an exact date from a regex match."""
        groups = [g.strip() for g in match.groups() if g is not None]
        groupdict = match.groupdict()

        year = int(groupdict["year"])

        # Month: numeric groups take priority over name lookup
        if groupdict.get("month_num"):
            month = int(groupdict["month_num"])
        elif groupdict.get("month_num_us"):
            month = int(groupdict["month_num_us"])
        else:
            month_name = next(g for g in groups if g.lower() in self.month_lookup)
            month = self.month_lookup[month_name.lower()]

        # Day: numeric groups take priority
        if groupdict.get("day_num"):
            day = int(groupdict["day_num"])
        elif groupdict.get("day_num_us"):
            day = int(groupdict["day_num_us"])
        else:
            day_str = next(g for g in groups if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", g))
            day_match = re.match(r"\d+", day_str)
            if day_match is None:
                raise ValueError(f"Invalid day: {day_str}")
            day = int(day_match.group())

        if not self._validate_date(year, month, day):
            raise ValueError(f"Invalid date: day {day} month {month} year {year}")

        # Time components
        hour = int(groupdict["hour"]) if groupdict.get("hour") else None
        minute = int(groupdict["minute"]) if groupdict.get("minute") else None
        second = int(groupdict["second"]) if groupdict.get("second") else None

        meridiem = groupdict.get("meridiem")
        if hour is not None and meridiem:
            m = meridiem.strip().upper()
            if m == "PM" and hour < 12:
                hour += 12
            elif m == "AM" and hour == 12:
                hour = 0

        return ParsedDate(year=year, month=month, day=day, hour=hour, minute=minute, second=second)

    def _parse_time(self, match: re.Match) -> ParsedDate:
        """Parse a time-only expression, returning a TIME-precision date."""
        groupdict = match.groupdict()
        hour = int(groupdict["hour"])
        minute = int(groupdict["minute"])
        second = int(groupdict["second"]) if groupdict.get("second") else None

        meridiem = groupdict.get("meridiem")
        if meridiem:
            m = meridiem.strip().upper()
            if m == "PM" and hour < 12:
                hour += 12
            elif m == "AM" and hour == 12:
                hour = 0

        # CalendarConfig has no current_year; default to epoch year 1
        return ParsedDate(
            year=1,
            precision=DatePrecision.TIME,
            hour=hour,
            minute=minute,
            second=second,
        )

    def _parse_month_year(self, match: re.Match) -> ParsedDate:
        """Parse a month+year date (MONTH precision)."""
        groups = [g for g in match.groups() if g is not None]
        year = int(next(g for g in reversed(groups) if re.match(r"^-?\d+$", g)))
        month_name = next(g for g in groups if g.lower() in self.month_lookup)
        return ParsedDate(
            year=year,
            month=self.month_lookup[month_name.lower()],
            precision=DatePrecision.MONTH,
        )

    def _parse_year_only(self, match: re.Match) -> ParsedDate:
        """Parse a year-only date (YEAR precision)."""
        year = int(
            next(g for g in match.groups() if g and (g.lstrip("-").isdigit()))
        )
        return ParsedDate(year=year, precision=DatePrecision.YEAR)

    def _parse_season_date(self, match: re.Match) -> ParsedDate:
        """Parse a season-based date (SEASON precision)."""
        groups = [g for g in match.groups() if g is not None]
        year = int(next(g for g in reversed(groups) if re.match(r"^-?\d+$", g)))
        season = next(
            g for g in reversed(groups)
            if re.match(r"^(spring|summer|autumn|winter|harvest)$", g, re.IGNORECASE)
        )
        return ParsedDate(year=year, precision=DatePrecision.SEASON, season=season.lower())

    def _parse_relative_date(self, match: re.Match) -> ParsedDate:
        """Parse a relative date (RELATIVE precision)."""
        groups = match.groups()
        if len(groups) == 3:
            days = int(groups[0])
            direction = groups[1]
            event = groups[2]
            relative_days = -days if direction.lower() == "before" else days
        else:
            event = groups[0]
            relative_days = 0

        return ParsedDate(
            year=1,
            precision=DatePrecision.RELATIVE,
            relative_to=event.strip().lower(),
            relative_days=relative_days,
        )

    def _parse_fuzzy_date(self, match: re.Match) -> ParsedDate:
        """Parse a fuzzy date (FUZZY precision)."""
        groups = [g for g in match.groups() if g is not None]
        year = int(next(g for g in reversed(groups) if re.match(r"^-?\d+$", g)))

        month = None
        for g in groups:
            if g.lower() in self.month_lookup:
                month = self.month_lookup[g.lower()]
                break

        day = None
        for g in groups:
            if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", g):
                day_match = re.match(r"\d+", g)
                if day_match is None:
                    raise ValueError(f"Invalid day: {g}")
                day = int(day_match.group())
                break

        confidence = 0.5 if "sometime" in match.re.pattern.lower() else 0.8
        return ParsedDate(
            year=year,
            month=month,
            day=day,
            precision=DatePrecision.FUZZY,
            confidence=confidence,
        )

    def _parse_date_range(self, match: re.Match) -> ParsedDate:
        """Parse a date range (RANGE precision).

        Handles three range shapes:
        - 2 days + 1 month: same-month day range (e.g. "23–30 AUG 1895")
        - 2 days + 2 months: cross-month day range (e.g. "23 AUG–6 SEP 1895")
        - 0 days + 2 months: month-to-month range (e.g. "AUG–SEP 1895")
        """
        groups = [g for g in match.groups() if g is not None]
        year = int(next(g for g in reversed(groups) if re.match(r"^-?\d+$", g)))

        months = [self.month_lookup[g.lower()] for g in groups if g.lower() in self.month_lookup]
        days: list[int] = []
        for group in groups:
            if not re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", group):
                continue
            day_match = re.match(r"\d+", group)
            if day_match is None:
                raise ValueError(f"Invalid day: {group}")
            days.append(int(day_match.group()))

        if len(days) == 2 and len(months) >= 2:
            # Cross-month: "23 AUG–6 SEP 1895"
            start_date = ParsedDate(year=year, month=months[0], day=days[0])
            end_date = ParsedDate(year=year, month=months[1], day=days[1])
        elif len(days) == 2:
            # Same-month: "23–30 AUG 1895"
            start_date = ParsedDate(year=year, month=months[0], day=days[0])
            end_date = ParsedDate(year=year, month=months[0], day=days[1])
        else:
            # Month-to-month: "AUG–SEP 1895"
            start_date = ParsedDate(year=year, month=months[0], precision=DatePrecision.MONTH)
            end_date = ParsedDate(year=year, month=months[1], precision=DatePrecision.MONTH)

        return ParsedDate(
            year=year,
            precision=DatePrecision.RANGE,
            range_start=start_date,
            range_end=end_date,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_date(self, year: int, month: int, day: int) -> bool:
        """Validate a date against the calendar's month structure.

        Uses get_months_for_year() so year variants and leap year rules
        are properly respected.

        Args:
            year: Calendar year.
            month: Month number (1-indexed).
            day: Day number (1-indexed).

        Returns:
            bool: True if valid, False otherwise.

        """
        months = self.calendar_config.get_months_for_year(year)
        if month < 1 or month > len(months):
            return False
        if day < 1 or day > months[month - 1].days:
            return False
        return True
