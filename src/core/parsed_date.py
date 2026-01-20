from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class DatePrecision(Enum):
    """Defines the precision level of a parsed date"""

    EXACT = auto()  # Complete date with day, month, year
    MONTH = auto()  # Month and year only
    YEAR = auto()  # Year only
    FUZZY = auto()  # Approximate date
    RELATIVE = auto()  # Date relative to another event
    SEASON = auto()  # Season-based date
    RANGE = auto()  # Date range
    TIME = auto()  # Time only


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
    hour: Optional[int] = None
    minute: Optional[int] = None
    second: Optional[int] = None
