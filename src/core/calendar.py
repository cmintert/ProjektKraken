"""Calendar System Module.

Provides domain models and conversion logic for custom fantasy calendars.
Supports variable month lengths, year variants, and bidirectional
conversion between structured dates and continuous float values.

Classes:
    MonthDefinition: Definition of a calendar month.
    WeekDefinition: Definition of week structure.
    YearVariant: Year-specific structure override.
    CalendarConfig: Complete calendar configuration.
    CalendarDate: Structured representation of a date.
    CalendarConverter: Bidirectional float/date converter.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LeapYearRule:
    """Rule for calculating algorithmic leap years.

    Attributes:
        interval: Add leap day every N years (e.g., 4).
        skip_interval: Skip adding every N years (e.g., 100). 0 = no skip.
        reset_interval: Re-add every N years (e.g., 400). 0 = no reset.
        month_index: Index of month to modify (0-based).
        extra_days: Number of days to add (usually 1).
    """

    interval: int
    skip_interval: int = 0
    reset_interval: int = 0
    month_index: int = 1  # Default to 2nd month (Feb)
    extra_days: int = 1

    def applies_to_year(self, year: int) -> bool:
        """Checks if this rule applies to the given year."""
        if year % self.interval != 0:
            return False

        if self.skip_interval > 0 and year % self.skip_interval == 0:
            if self.reset_interval > 0 and year % self.reset_interval == 0:
                pass  # It is a leap year
            else:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interval": self.interval,
            "skip_interval": self.skip_interval,
            "reset_interval": self.reset_interval,
            "month_index": self.month_index,
            "extra_days": self.extra_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeapYearRule":
        return cls(
            interval=data["interval"],
            skip_interval=data.get("skip_interval", 0),
            reset_interval=data.get("reset_interval", 0),
            month_index=data.get("month_index", 1),
            extra_days=data.get("extra_days", 1),
        )


@dataclass
class MonthDefinition:
    """Definition of a calendar month.

    Attributes:
        name: Full month name (e.g., "Hammer", "January").
        abbreviation: Short form (e.g., "Ham", "Jan").
        days: Number of days in this month (must be > 0).
    """

    name: str
    abbreviation: str
    days: int

    def to_dict(self) -> Dict[str, Any]:
        """Converts the MonthDefinition to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "name": self.name,
            "abbreviation": self.abbreviation,
            "days": self.days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonthDefinition":
        """Creates a MonthDefinition from a dictionary.

        Args:
            data: Dictionary containing month data.

        Returns:
            MonthDefinition: New instance.
        """
        return cls(
            name=data["name"],
            abbreviation=data["abbreviation"],
            days=data["days"],
        )


@dataclass
class WeekDefinition:
    """Definition of week structure.

    Attributes:
        day_names: Full names for each day of the week.
        day_abbreviations: Short forms for each day.
    """

    day_names: List[str]
    day_abbreviations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the WeekDefinition to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "day_names": self.day_names,
            "day_abbreviations": self.day_abbreviations,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeekDefinition":
        """Creates a WeekDefinition from a dictionary.

        Args:
            data: Dictionary containing week data.

        Returns:
            WeekDefinition: New instance.
        """
        return cls(
            day_names=data["day_names"],
            day_abbreviations=data["day_abbreviations"],
        )


@dataclass
class YearVariant:
    """Year-specific structure override for non-repeating calendars.

    Some fantasy calendars have years that differ from the standard
    structure (e.g., a special "Festival Year" with extra months).

    Attributes:
        year: The year number this variant applies to.
        months: Custom month structure for this year.
    """

    year: int
    months: List[MonthDefinition]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the YearVariant to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "year": self.year,
            "months": [m.to_dict() for m in self.months],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YearVariant":
        """Creates a YearVariant from a dictionary.

        Args:
            data: Dictionary containing year variant data.

        Returns:
            YearVariant: New instance.
        """
        return cls(
            year=data["year"],
            months=[MonthDefinition.from_dict(m) for m in data["months"]],
        )


@dataclass
class CalendarConfig:
    """Complete calendar configuration for a world.

    Defines the structure of a fantasy calendar including months,
    week days, and any year-specific variations.

    Attributes:
        id: Unique identifier for this calendar.
        name: Display name (e.g., "Harptos Calendar").
        months: Default month structure for standard years.
        week: Week day definitions.
        year_variants: Optional per-year structure overrides.
        epoch_name: Era designation (e.g., "DR", "AD").
        created_at: Real-world creation timestamp.
        modified_at: Real-world modification timestamp.
    """

    id: str
    name: str
    months: List[MonthDefinition]
    week: WeekDefinition
    year_variants: List[YearVariant]
    epoch_name: str
    leap_year_rules: List[LeapYearRule] = field(default_factory=list)
    is_active: bool = False
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def validate(self) -> List[str]:
        """Validates the calendar configuration.

        Returns:
            List[str]: List of validation error messages.
                       Empty list if valid.
        """
        errors: List[str] = []

        # Check for empty month list
        if not self.months:
            errors.append("Month list is empty. At least one month is required.")
            return errors  # Can't continue validation without months

        # Check for duplicate month names
        names = [m.name for m in self.months]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            errors.append(f"Duplicate month name(s) found: {set(duplicates)}")

        # Check for duplicate abbreviations
        abbrevs = [m.abbreviation for m in self.months]
        if len(abbrevs) != len(set(abbrevs)):
            duplicates = [a for a in abbrevs if abbrevs.count(a) > 1]
            errors.append(f"Duplicate abbreviation(s) found: {set(duplicates)}")

        # Check for invalid day counts
        for month in self.months:
            if month.days <= 0:
                errors.append(
                    f"Month '{month.name}' has invalid days count: {month.days}"
                )

        # Validate year variants
        for variant in self.year_variants:
            if not variant.months:
                errors.append(f"Year variant for year {variant.year} has no months.")
            else:
                for month in variant.months:
                    if month.days <= 0:
                        errors.append(
                            f"Year {variant.year}, month '{month.name}' "
                            f"has invalid days: {month.days}"
                        )

        return errors

    def get_months_for_year(self, year: int) -> List[MonthDefinition]:
        """Gets the month structure for a specific year.

        Args:
            year: The year to get months for.

        Returns:
            List[MonthDefinition]: Months for that year (may differ
                                   if a YearVariant exists or LeapYearRules apply).
        """
        # 1. Check for manual override (YearVariant)
        for variant in self.year_variants:
            if variant.year == year:
                return variant.months

        # 2. Start with base months
        # We must copy them because we might modify days
        import copy

        months = copy.deepcopy(self.months)

        # 3. Apply algorithmic leap year rules
        for rule in self.leap_year_rules:
            if rule.applies_to_year(year):
                if 0 <= rule.month_index < len(months):
                    months[rule.month_index].days += rule.extra_days

        return months

    def get_year_length(self, year: int) -> int:
        """Gets the total number of days in a specific year.

        Args:
            year: The year to calculate length for.

        Returns:
            int: Total days in that year.
        """
        months = self.get_months_for_year(year)
        return sum(m.days for m in months)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the CalendarConfig to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "months": [m.to_dict() for m in self.months],
            "week": self.week.to_dict(),
            "year_variants": [v.to_dict() for v in self.year_variants],
            "leap_year_rules": [r.to_dict() for r in self.leap_year_rules],
            "epoch_name": self.epoch_name,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    def to_json(self) -> str:
        """Converts the CalendarConfig to a JSON string.

        Returns:
            str: JSON representation.
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarConfig":
        """Creates a CalendarConfig from a dictionary.

        Args:
            data: Dictionary containing calendar data.

        Returns:
            CalendarConfig: New instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            months=[MonthDefinition.from_dict(m) for m in data["months"]],
            week=WeekDefinition.from_dict(data["week"]),
            year_variants=[
                YearVariant.from_dict(v) for v in data.get("year_variants", [])
            ],
            leap_year_rules=[
                LeapYearRule.from_dict(r) for r in data.get("leap_year_rules", [])
            ],
            epoch_name=data["epoch_name"],
            is_active=data.get("is_active", False),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CalendarConfig":
        """Creates a CalendarConfig from a JSON string.

        Args:
            json_str: JSON string containing calendar data.

        Returns:
            CalendarConfig: New instance.
        """
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def create_default(cls) -> "CalendarConfig":
        """Creates a default calendar configuration (Gregorian).

        Returns:
            CalendarConfig: A Gregorian calendar.
        """
        # Standard Gregorian Months
        month_data = [
            ("January", "Jan", 31),
            ("February", "Feb", 28),
            ("March", "Mar", 31),
            ("April", "Apr", 30),
            ("May", "May", 31),
            ("June", "Jun", 30),
            ("July", "Jul", 31),
            ("August", "Aug", 31),
            ("September", "Sep", 30),
            ("October", "Oct", 31),
            ("November", "Nov", 30),
            ("December", "Dec", 31),
        ]

        months = [
            MonthDefinition(name=n, abbreviation=a, days=d) for n, a, d in month_data
        ]

        week = WeekDefinition(
            day_names=[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            day_abbreviations=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        )

        # Gregorian Leap Year Rule:
        # Every 4 years, except every 100, unless every 400.
        # Adds 1 day to index 1 (February).
        leap_rule = LeapYearRule(
            interval=4,
            skip_interval=100,
            reset_interval=400,
            month_index=1,
            extra_days=1,
        )

        return cls(
            id=str(uuid.uuid4()),
            name="Gregorian Calendar",
            months=months,
            week=week,
            year_variants=[],
            leap_year_rules=[leap_rule],
            epoch_name="AD",
        )


@dataclass
class CalendarDate:
    """A structured representation of a calendar date.

    Uses 1-based indexing for user display (Year 1, Month 1, Day 1).

    Attributes:
        year: Year number (can be negative for pre-Epoch).
        month: Month number (1-indexed, 1-12 typically).
        day: Day of month (1-indexed, 1-30 typically).
        time_fraction: Fractional part of day (0.0-1.0, 0.5 = noon).
        month_name: Optional resolved month name.
        day_of_week_name: Optional resolved day of week name.
    """

    year: int
    month: int
    day: int
    time_fraction: float = 0.0
    month_name: Optional[str] = None
    day_of_week_name: Optional[str] = None

    def __str__(self) -> str:
        """Returns human-readable string representation.

        Returns:
            str: Formatted date string.
        """
        month_str = self.month_name or f"Month {self.month}"
        return f"Year {self.year}, {month_str}, Day {self.day}"


class CalendarConverter:
    """Bidirectional converter between float and CalendarDate.

    Handles the math to convert continuous float time values to
    structured calendar dates and vice versa. Supports:
    - Variable month lengths
    - Year-specific month structures
    - Negative floats (pre-Epoch dates)
    - Time fractions (sub-day precision)

    Internal indexing is 0-based: 0.0 = start of Year 1, Month 1, Day 1.
    """

    def __init__(self, config: CalendarConfig) -> None:
        """Initializes the converter with a calendar configuration.

        Args:
            config: The calendar configuration to use.
        """
        self._config = config
        # Cache for year start positions (year -> absolute_day)
        self._year_cache: Dict[int, float] = {}

    def to_float(self, date: CalendarDate) -> float:
        """Converts a structured date to an absolute day float.

        Args:
            date: The CalendarDate to convert.

        Returns:
            float: Absolute day value where 0.0 = start of Epoch.

        Note:
            Year 1, Month 1, Day 1 = 0.0
            Negative years produce negative floats.
        """
        if date.year >= 1:
            return self._to_float_positive(date)
        else:
            return self._to_float_negative(date)

    def _to_float_positive(self, date: CalendarDate) -> float:
        """Converts a positive-year date to float.

        Args:
            date: Date with year >= 1.

        Returns:
            float: Absolute day value.
        """
        total_days = 0.0

        # Sum all complete years before target year
        # Optimization: If we have no variants and simple rules, we could calculate faster
        # But for now, correctness first. Iterate years.
        # To avoid massive loops for huge years (e.g. Year 20000), we could optimize later.

        # Simple optimization: if no variants and logic is regular...
        # For now, just sum (naive implementation - O(N) where N is year)
        # TODO: Implement O(1) calculation for standard Gregorian

        for y in range(1, date.year):
            total_days += self._config.get_year_length(y)

        # Sum all complete months before target month
        months = self._config.get_months_for_year(date.year)
        for m_idx in range(date.month - 1):  # month is 1-indexed
            total_days += months[m_idx].days

        # Add days within the month (day is 1-indexed, so subtract 1)
        total_days += date.day - 1

        # Add time fraction
        total_days += date.time_fraction

        return total_days

    def _to_float_negative(self, date: CalendarDate) -> float:
        """Converts a negative/zero-year date to float.

        Pre-Epoch dates (year <= 0) produce negative floats.

        Args:
            date: Date with year <= 0.

        Returns:
            float: Negative absolute day value.
        """
        # For year 0: we need to count backwards from 0.0
        # Year 0, Month 12, Day 30 = -1.0 (day before Epoch)
        # Year 0, Month 1, Day 1 = -360.0 (for 360-day calendar)

        # Calculate days from start of year to the date
        months = self._config.get_months_for_year(date.year)
        days_in_year = 0
        for m_idx in range(date.month - 1):
            days_in_year += months[m_idx].days
        days_in_year += date.day - 1
        days_in_year += date.time_fraction

        # Calculate total days for all years from date.year to year 0
        total_years_days = 0.0
        for y in range(date.year, 1):  # from date.year up to but not including 1
            total_years_days += self._config.get_year_length(y)

        # The float is negative: -(remaining days to reach year 1)
        return -(total_years_days - days_in_year)

    def from_float(self, absolute_day: float) -> CalendarDate:
        """Converts an absolute day float to a structured date.

        Args:
            absolute_day: The float value to convert.

        Returns:
            CalendarDate: Structured date representation.

        Note:
            0.0 = Year 1, Month 1, Day 1
            Negative values produce pre-Epoch dates.
        """
        if absolute_day >= 0:
            return self._from_float_positive(absolute_day)
        else:
            return self._from_float_negative(absolute_day)

    def _from_float_positive(self, absolute_day: float) -> CalendarDate:
        """Converts a non-negative float to date.

        Args:
            absolute_day: Float >= 0.

        Returns:
            CalendarDate: Structured date.
        """
        remaining = absolute_day
        year = 1

        # Find the year
        while True:
            year_length = self._config.get_year_length(year)
            if remaining < year_length:
                break
            remaining -= year_length
            year += 1

        # Find the month
        months = self._config.get_months_for_year(year)
        month = 1
        for m_idx, month_def in enumerate(months):
            if remaining < month_def.days:
                month = m_idx + 1  # 1-indexed
                break
            remaining -= month_def.days
        else:
            # Edge case: exactly at year boundary
            month = len(months)
            remaining = months[-1].days - 1

        # Extract day and time fraction
        day = int(remaining) + 1  # 1-indexed
        time_fraction = remaining - int(remaining)

        # Resolve names
        month_name = months[month - 1].name if month <= len(months) else None

        return CalendarDate(
            year=year,
            month=month,
            day=day,
            time_fraction=time_fraction,
            month_name=month_name,
        )

    def _from_float_negative(self, absolute_day: float) -> CalendarDate:
        """Converts a negative float to pre-Epoch date.

        Args:
            absolute_day: Float < 0.

        Returns:
            CalendarDate: Structured date with year <= 0.
        """
        # absolute_day is negative
        # -1.0 = last day of Year 0
        # -360.0 = first day of Year 0 (for 360-day calendar)

        remaining = -absolute_day  # Make it positive for calculation
        year = 0

        # Find the year (going backwards)
        while True:
            year_length = self._config.get_year_length(year)
            if remaining <= year_length:
                break
            remaining -= year_length
            year -= 1

        # Now remaining is the offset from the END of this year
        # We need to convert to offset from START
        year_length = self._config.get_year_length(year)
        from_start = year_length - remaining

        # Find the month
        months = self._config.get_months_for_year(year)
        month = 1
        current = from_start
        for m_idx, month_def in enumerate(months):
            if current < month_def.days:
                month = m_idx + 1
                break
            current -= month_def.days
        else:
            month = len(months)
            current = months[-1].days - 1

        # Extract day and time fraction
        day = int(current) + 1
        time_fraction = current - int(current)

        month_name = months[month - 1].name if month <= len(months) else None

        return CalendarDate(
            year=year,
            month=month,
            day=day,
            time_fraction=time_fraction,
            month_name=month_name,
        )

    def format_date(self, absolute_day: float, format_str: Optional[str] = None) -> str:
        """Formats a float date as a human-readable string.

        Args:
            absolute_day: The float value to format.
            format_str: Optional format string (future expansion).

        Returns:
            str: Formatted date string.
        """
        date = self.from_float(absolute_day)

        # Get month name
        months = self._config.get_months_for_year(date.year)
        month_name = (
            months[date.month - 1].name if date.month <= len(months) else "Unknown"
        )

        # Time of day
        time_str = ""
        if date.time_fraction > 0:
            if date.time_fraction == 0.5:
                time_str = ", Noon"
            elif date.time_fraction < 0.5:
                time_str = ", Morning"
            else:
                time_str = ", Evening"

        # Day of week
        # 0.0 is the start of the epoch. Assuming epoch starts on first day of week.
        week_days = self._config.week.day_names
        if week_days:
            # floor(absolute_day) gives the integer day count from epoch
            # e.g. 0.5 -> 0 -> index 0
            day_idx = int(absolute_day) % len(week_days)
            # handle negative modulo correctly in python?
            # -1 % 7 = 6 (correct, previous day)
            day_name = week_days[day_idx]
            return f"Year {date.year}, {month_name} {date.day}, {day_name}{time_str}"

        return f"Year {date.year}, {month_name} {date.day}{time_str}"
