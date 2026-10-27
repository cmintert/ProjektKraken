"""Indexed calendar arithmetic independent of Qt and persistence."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.calendar import CalendarConfig


def multiples(start: int, stop: int, divisor: int) -> int:
    """Count multiples in a half-open integer interval, including negative years."""
    return (stop - 1) // divisor - (start - 1) // divisor


def year_span(config: CalendarConfig, start: int, stop: int) -> int:
    """Count days without visiting every intervening year."""
    if stop < start:
        return -year_span(config, stop, start)
    base = sum(month.days for month in config.months)
    if base <= 0:
        raise ValueError("Calendar years must have positive lengths")
    days = (stop - start) * base
    for rule in config.leap_year_rules:
        if rule.interval <= 0:
            raise ValueError("Leap intervals must be positive")
        if not 0 <= rule.month_index < len(config.months):
            continue
        count = multiples(start, stop, rule.interval)
        if rule.skip_interval > 0:
            skipped = math.lcm(rule.interval, rule.skip_interval)
            count -= multiples(start, stop, skipped)
            if rule.reset_interval > 0:
                count += multiples(start, stop, math.lcm(skipped, rule.reset_interval))
        days += count * rule.extra_days
    # A manual year variant replaces, rather than augments, leap rules.
    seen: set[int] = set()
    for variant in config.year_variants:
        if variant.year in seen or not start <= variant.year < stop:
            continue
        seen.add(variant.year)
        normal = base + sum(
            rule.extra_days
            for rule in config.leap_year_rules
            if 0 <= rule.month_index < len(config.months)
            and rule.applies_to_year(variant.year)
        )
        days += sum(month.days for month in variant.months) - normal
    return days


def month_span(config: CalendarConfig, year: int) -> int:
    """Return the ordinal of the first month in a year, relative to year one."""
    start, stop = sorted((1, year))
    value = (stop - start) * len(config.months)
    seen: set[int] = set()
    for variant in config.year_variants:
        if start <= variant.year < stop and variant.year not in seen:
            seen.add(variant.year)
            value += len(variant.months) - len(config.months)
    return -value if year < 1 else value


def locate_year(value: float, start_of_year: Callable[[int], float]) -> int:
    """Locate a year using exponential bounds and binary search."""
    coordinate = start_of_year
    if not math.isfinite(value):
        raise ValueError("Calendar coordinate must be finite")
    lower, upper = 0, 1
    while coordinate(lower) > value:
        lower = lower * 2 - 1
    while coordinate(upper) <= value:
        upper = upper * 2 + 1
    while upper - lower > 1:
        middle = (lower + upper) // 2
        if coordinate(middle) <= value:
            lower = middle
        else:
            upper = middle
    return lower
