"""Persisted historical assertions, independent of their display coordinates.

Only hard bounds are evidence. Approximation never supplies implicit padding.
Calendar identities are checked on every resolution so a changed world calendar
cannot silently reinterpret an assertion from a different calendar.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any

from src.core.calendar import CalendarConverter

TEMPORAL_SCHEMA_VERSION = 1
TEMPORAL_ATTRIBUTE = "_temporal_v2"


class TemporalPrecision(str, Enum):
    """Smallest supplied calendar component."""

    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"


class TemporalQualifier(str, Enum):
    """Qualification is independent of component precision."""

    ASSERTED = "asserted"
    APPROXIMATE = "approximate"
    UNCERTAIN = "uncertain"
    APPROXIMATE_UNCERTAIN = "approximate_uncertain"
    ESTIMATED = "estimated"
    CALCULATED = "calculated"


@dataclass(frozen=True)
class ResolvedTemporalBounds:
    """Hard occurrence bounds are half-open; equal bounds mean a legacy instant."""

    hard_start: float | None = None
    hard_end: float | None = None
    soft_start: float | None = None
    soft_end: float | None = None
    anchor_id: str | None = None
    error: str | None = None
    label: str | None = None

    @property
    def has_hard_bounds(self) -> bool:
        """Whether both evidence bounds are known."""
        return self.hard_start is not None and self.hard_end is not None


@dataclass(frozen=True)
class TemporalExpression:
    """A user assertion that survives save, reload, and export without completion."""

    calendar_id: str
    year: int | None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None
    precision: TemporalPrecision = TemporalPrecision.DAY
    qualifier: TemporalQualifier = TemporalQualifier.ASSERTED
    original_text: str | None = None
    explicit_outer_start: float | None = None
    explicit_outer_end: float | None = None
    schema_version: int = TEMPORAL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe semantic data, never cached calendar projections."""
        result = asdict(self)
        result["precision"] = self.precision.value
        result["qualifier"] = self.qualifier.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalExpression:
        """Read a versioned assertion, rejecting unsupported schemas."""
        values = dict(data)
        if values.get("schema_version", 1) != TEMPORAL_SCHEMA_VERSION:
            raise ValueError("Unsupported temporal expression version")
        values["precision"] = TemporalPrecision(values.get("precision", "day"))
        values["qualifier"] = TemporalQualifier(values.get("qualifier", "asserted"))
        return cls(**values)

    def resolve_bounds(self, converter: CalendarConverter) -> ResolvedTemporalBounds:
        """Resolve through the active custom calendar without inventing certainty."""
        if converter._config.id != self.calendar_id:
            return ResolvedTemporalBounds(
                error="The assertion's calendar is unavailable."
            )
        try:
            nominal_start, nominal_end = converter.resolve_precision_bounds(self)
            start, end = self.explicit_outer_start, self.explicit_outer_end
            for bound in (start, end):
                if bound is not None and not math.isfinite(bound):
                    raise ValueError("Temporal bounds must be finite")
            if start is not None and end is not None and start >= end:
                raise ValueError("Possible-until must be after possible-from")
            if (
                start is None
                and end is None
                and self.qualifier
                in {TemporalQualifier.ASSERTED, TemporalQualifier.CALCULATED}
            ):
                start, end = nominal_start, nominal_end
            return ResolvedTemporalBounds(
                start,
                end,
                nominal_start,
                nominal_end,
                label=self.display_text(converter),
            )
        except (ValueError, TypeError, IndexError, OverflowError) as exc:
            return ResolvedTemporalBounds(error=str(exc))

    def representative_time(self, converter: CalendarConverter) -> float:
        """Return a lossy layout coordinate; never use it as historical truth."""
        bounds = self.resolve_bounds(converter)
        if bounds.error:
            raise ValueError(bounds.error)
        if bounds.has_hard_bounds:
            assert bounds.hard_start is not None and bounds.hard_end is not None
            return (bounds.hard_start + bounds.hard_end) / 2
        if bounds.soft_start is None:
            raise ValueError("No representative date is available")
        return bounds.soft_start

    def display_text(self, converter: CalendarConverter | None = None) -> str:
        """Show only supplied components, preferring the author's expression."""
        if self.original_text:
            return self.original_text
        text = str(self.year) if self.year is not None else "Date unknown"
        if self.month is not None:
            month = str(self.month)
            if converter is not None and self.year is not None:
                months = converter._config.get_months_for_year(self.year)
                if 1 <= self.month <= len(months):
                    month = months[self.month - 1].name
            text = f"{month} {text}"
        if self.day is not None:
            text = f"{self.day} {text}"
        if self.hour is not None:
            text += f" {self.hour:02d}"
        if self.minute is not None:
            text += f":{self.minute:02d}"
        if self.second is not None:
            text += f":{self.second:02d}"
        if self.qualifier in {
            TemporalQualifier.APPROXIMATE,
            TemporalQualifier.APPROXIMATE_UNCERTAIN,
        }:
            text = "c. " + text
        if self.qualifier in {
            TemporalQualifier.UNCERTAIN,
            TemporalQualifier.APPROXIMATE_UNCERTAIN,
        }:
            text += "?"
        if self.qualifier in {
            TemporalQualifier.ESTIMATED,
            TemporalQualifier.CALCULATED,
        }:
            text = f"{self.qualifier.value} {text}"
        return text


def expression_from_attributes(attributes: dict[str, Any]) -> TemporalExpression | None:
    """Read semantic metadata; absence alone means legacy exact time."""
    metadata = attributes.get(TEMPORAL_ATTRIBUTE)
    if metadata is None:
        return None
    if not isinstance(metadata, dict) or metadata.get("schema") != 1:
        raise ValueError("Unsupported temporal metadata")
    data = metadata.get("expression")
    return TemporalExpression.from_dict(data) if data is not None else None


def move_expression(
    expression: TemporalExpression, target: float, converter: CalendarConverter
) -> TemporalExpression:
    """Move an assertion while retaining precision and explicit-window width."""
    date = converter.from_float(target)
    order = list(TemporalPrecision)
    precision = order.index(expression.precision)
    seconds = min(86399, int(date.time_fraction * 86400))
    moved = replace(
        expression,
        year=date.year,
        month=date.month if precision >= order.index(TemporalPrecision.MONTH) else None,
        day=date.day if precision >= order.index(TemporalPrecision.DAY) else None,
        hour=seconds // 3600
        if precision >= order.index(TemporalPrecision.HOUR)
        else None,
        minute=seconds // 60 % 60
        if precision >= order.index(TemporalPrecision.MINUTE)
        else None,
        second=seconds % 60
        if precision >= order.index(TemporalPrecision.SECOND)
        else None,
        original_text=None,
    )
    # Explicit windows are translated together, never converted to duration.
    delta = replace(
        moved, explicit_outer_start=None, explicit_outer_end=None
    ).representative_time(converter) - replace(
        expression, explicit_outer_start=None, explicit_outer_end=None
    ).representative_time(converter)
    moved = replace(
        moved,
        explicit_outer_start=None
        if expression.explicit_outer_start is None
        else expression.explicit_outer_start + delta,
        explicit_outer_end=None
        if expression.explicit_outer_end is None
        else expression.explicit_outer_end + delta,
    )
    return _restore_moved_bound_text(expression, moved, delta, converter)


def _restore_moved_bound_text(
    original: TemporalExpression,
    moved: TemporalExpression,
    delta: float,
    converter: CalendarConverter,
) -> TemporalExpression:
    """Retain before/after/between meaning when regenerating dragged labels."""
    import re

    from src.core.date_parser import DateParser

    text = original.original_text or ""
    nominal = replace(moved, explicit_outer_start=None, explicit_outer_end=None)
    prefix = re.match(r"^(before|after|by)\s+", text, re.I)
    if prefix:
        return replace(
            moved, original_text=f"{prefix[1]} {nominal.display_text(converter)}"
        )
    between = re.fullmatch(r"between\s+(.+?)\s+and\s+(.+)", text, re.I)
    if between:
        end = DateParser(converter._config).parse_expression(between[2])
        end = move_expression(
            end, end.representative_time(converter) + delta, converter
        )
        return replace(
            moved,
            original_text=f"between {nominal.display_text(converter)} and {end.display_text(converter)}",
        )
    return moved
