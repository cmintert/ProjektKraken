"""Lossless anchor transformations and strict calendar offsets."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from src.core.calendar import CalendarConverter, CalendarDate
from src.core.calendar_index import locate_year, month_span
from src.core.temporal_expression import MAX_LORE_DAY, ResolvedTemporalBounds


def calendar_shift(
    value: float, amount: int, unit: str, converter: CalendarConverter
) -> float:
    """Shift calendar components without clamping invalid dates."""
    date = converter.from_float(value)
    if unit == "years":
        year, month = date.year + amount, date.month
    else:
        ordinal = month_span(converter._config, date.year) + date.month - 1 + amount
        year = locate_year(ordinal, lambda y: month_span(converter._config, y))
        month = ordinal - month_span(converter._config, year) + 1
    converter.start_of_day(year, month, date.day)
    return converter.to_float(CalendarDate(year, month, date.day, date.time_fraction))


def _calendar_domain(
    start: float, end: float, amount: int, unit: str, converter: CalendarConverter
) -> tuple[tuple[float, float], ...]:
    """Validate calendar pieces while preserving gaps in their possible image."""
    shifted_start = calendar_shift(start, amount, unit, converter)
    if start == end:
        return ((shifted_start, shifted_start),)
    if _globally_affine(amount, unit, converter):
        return ((shifted_start, shifted_start + (end - start)),)
    pieces = []
    for lower, upper, regular in _calendar_regions(start, end, amount, unit, converter):
        if regular:
            target = calendar_shift(lower, amount, unit, converter)
            pieces.append((target, target + upper - lower))
        else:
            pieces.extend(_month_images(lower, upper, amount, unit, converter))
    merged: list[tuple[float, float]] = []
    for lower, upper in pieces:
        if merged and lower <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(upper, merged[-1][1]))
        else:
            merged.append((lower, upper))
    return tuple(merged)


def _month_images(
    start: float, end: float, amount: int, unit: str, converter: CalendarConverter
) -> list[tuple[float, float]]:
    """A month piece is affine; checking its extreme days covers every candidate."""
    pieces = []
    cursor = start
    while cursor < end:
        date = converter.from_float(cursor)
        upper = min(end, converter.start_of_next_month(date.year, date.month))
        target = calendar_shift(cursor, amount, unit, converter)
        calendar_shift(max(cursor, math.ceil(upper) - 1), amount, unit, converter)
        pieces.append((target, target + upper - cursor))
        cursor = upper
    return pieces


def _calendar_regions(
    start: float, end: float, amount: int, unit: str, converter: CalendarConverter
) -> list[tuple[float, float, bool]]:
    """Skip ordinary leap cycles between sparse source/target year variants."""
    config = converter._config
    periods = [
        part
        for rule in config.leap_year_rules
        for part in (rule.interval, rule.skip_interval, rule.reset_interval)
        if part > 0
    ]
    if unit != "years" or amount % math.lcm(*periods):
        return [(start, end, False)]
    special = {
        year
        for variant in config.year_variants
        for year in (variant.year, variant.year - amount)
    }
    points = {start, end}
    for year in special:
        for boundary in (
            converter.start_of_year(year),
            converter.start_of_year(year + 1),
        ):
            if start < boundary < end:
                points.add(boundary)
    ordered = sorted(points)
    return [
        (lower, upper, converter.from_float(lower).year not in special)
        for lower, upper in zip(ordered, ordered[1:])
    ]


def _globally_affine(amount: int, unit: str, converter: CalendarConverter) -> bool:
    """Recognize globally valid calendar translations without enumerating dates."""
    config = converter._config
    if config.year_variants:
        return False
    if unit == "months":
        if not config.leap_year_rules and len({m.days for m in config.months}) == 1:
            return True
        if amount % len(config.months):
            return False
        amount //= len(config.months)
    periods = [
        part
        for rule in config.leap_year_rules
        for part in (rule.interval, rule.skip_interval, rule.reset_interval)
        if part > 0
    ]
    return amount % math.lcm(*periods) == 0


def shift_anchor(
    bounds: ResolvedTemporalBounds,
    ref: dict[str, Any],
    converter: CalendarConverter | None,
) -> ResolvedTemporalBounds:
    """Apply a versioned offset with identity independent of caption rounding."""
    offset = ref.get("offset", {"unit": "days", "value": ref.get("offset_days", 0)})
    if not isinstance(offset, dict):
        raise ValueError("Event offset must be an object")
    unit, value = offset.get("unit", "days"), float(offset.get("value", 0))
    if unit not in {"days", "months", "years"} or not math.isfinite(value):
        raise ValueError("Choose a finite day, month or year offset")
    if unit != "days" and not value.is_integer():
        raise ValueError("Calendar month and year offsets must be whole numbers")
    if value == 0:
        return bounds
    identity = _identity(bounds, unit, value, offset.get("calendar_id"))
    if bounds.error:
        return replace(bounds, **identity)
    if unit != "days" and (
        converter is None or offset.get("calendar_id") != converter._config.id
    ):
        return replace(
            bounds,
            **identity,
            hard_start=None,
            hard_end=None,
            error="The offset's calendar is unavailable.",
        )
    try:
        if unit == "days":
            ranges = (
                tuple(
                    (lower + value, upper + value)
                    for lower, upper in bounds.possible_ranges
                )
                if bounds.possible_ranges is not None
                else None
            )
            shifted = [
                None if v is None else v + value
                for v in (
                    bounds.hard_start,
                    bounds.hard_end,
                    bounds.soft_start,
                    bounds.soft_end,
                )
            ]
            for original, result in zip(
                (bounds.hard_start, bounds.hard_end), shifted[:2], strict=True
            ):
                if original is not None and result == original:
                    raise ValueError("Offset cannot be represented at this lore date")
        else:
            assert converter is not None
            shifted, ranges = _calendar_values(bounds, int(value), unit, converter)
        if any(
            v is not None and (not math.isfinite(v) or abs(v) > MAX_LORE_DAY)
            for v in shifted
        ):
            raise ValueError("Offset is outside the supported ±10^12 lore-day range")
    except (ValueError, OverflowError) as exc:
        return replace(
            bounds,
            **identity,
            hard_start=None,
            hard_end=None,
            error=f"Cannot apply event offset: {exc}",
        )
    return replace(
        bounds,
        hard_start=shifted[0],
        hard_end=shifted[1],
        soft_start=shifted[2],
        soft_end=shifted[3],
        possible_ranges=ranges,
        **identity,
        label=f"{bounds.label or bounds.anchor_id} ({value:+.17g} {unit})",
    )


def _calendar_values(
    bounds: ResolvedTemporalBounds, amount: int, unit: str, converter: CalendarConverter
) -> tuple[list[float | None], tuple[tuple[float, float], ...] | None]:
    """Project evidence pairs independently, never filling an unknown side."""
    shifted: list[float | None] = []
    hard_ranges = None
    for index, (start, end) in enumerate(
        (
            (bounds.hard_start, bounds.hard_end),
            (bounds.soft_start, bounds.soft_end),
        )
    ):
        if start is None and end is None:
            shifted.extend((None, None))
        elif start is None or end is None:
            if not _globally_affine(amount, unit, converter):
                raise ValueError(
                    "Calendar offsets need bounded occurrence dates for this calendar"
                )
            shifted.extend(
                None if v is None else calendar_shift(v, amount, unit, converter)
                for v in (start, end)
            )
        else:
            ranges = _calendar_domain(start, end, amount, unit, converter)
            shifted.extend((ranges[0][0], ranges[-1][1]))
            if index == 0:
                hard_ranges = ranges
    return shifted, hard_ranges


def _identity(
    bounds: ResolvedTemporalBounds, unit: str, value: float, calendar_id: str | None
) -> dict[str, Any]:
    """Retain transformation identity even when its evidence is unavailable."""
    base = (
        (bounds.base_anchor or bounds.anchor_id or "")
        if unit == "days"
        else bounds.anchor_id or ""
    )
    total = bounds.day_offset + value if unit == "days" else value
    kind = unit if unit == "days" else f"{unit}:{calendar_id}"
    key = total.hex() if unit == "days" else str(int(value))
    identity = base if unit == "days" and total == 0 else f"{base}|{kind}:{key}"
    return {
        "transition": (base, kind, key),
        "anchor_id": identity,
        "base_anchor": base if unit == "days" else identity,
        "day_offset": total if unit == "days" else 0,
    }
