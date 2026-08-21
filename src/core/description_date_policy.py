"""Detection policy for explicit dates in AI-generated descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DatePolicyViolation:
    """One explicit date found in generated description text."""

    start: int
    end: int
    text: str
    kind: str


_BASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "numeric date",
        re.compile(r"(?<!\w)\d{1,4}[./-]\d{1,2}[./-]\d{1,4}(?!\w)"),
    ),
    ("named year", re.compile(r"\bYear\s+-?\d+\b", re.IGNORECASE)),
    (
        "era year",
        re.compile(r"\b\d+\s*(?:BC|BCE|AD|CE|AE|DE)\b", re.IGNORECASE),
    ),
    (
        "labelled lore date",
        re.compile(
            r"\b(?:lore\s+date|date|day)\s*[:=]\s*-?\d+(?:\.\d+)?\b",
            re.IGNORECASE,
        ),
    ),
)


def find_description_dates(
    text: str,
    *,
    month_names: Iterable[str] = (),
    era_names: Iterable[str] = (),
    known_date_values: Iterable[float] = (),
) -> tuple[DatePolicyViolation, ...]:
    """Return non-overlapping explicit dates found in generated prose."""
    candidates: list[DatePolicyViolation] = []
    for kind, pattern in _BASE_PATTERNS:
        candidates.extend(
            DatePolicyViolation(match.start(), match.end(), match.group(0), kind)
            for match in pattern.finditer(text)
        )

    names = sorted(
        {name.strip() for name in month_names if name.strip()},
        key=len,
        reverse=True,
    )
    if names:
        month_group = "|".join(re.escape(name) for name in names)
        patterns = (
            re.compile(
                rf"\b(?:{month_group})\s+\d{{1,2}}(?:,?\s+-?\d+)?\b",
                re.IGNORECASE,
            ),
            re.compile(
                rf"\b\d{{1,2}}\s+(?:{month_group})(?:,?\s+-?\d+)?\b",
                re.IGNORECASE,
            ),
        )
        for pattern in patterns:
            candidates.extend(
                DatePolicyViolation(
                    match.start(), match.end(), match.group(0), "calendar date"
                )
                for match in pattern.finditer(text)
            )

    eras = sorted(
        {name.strip() for name in era_names if name.strip()},
        key=len,
        reverse=True,
    )
    if eras:
        era_group = "|".join(re.escape(name) for name in eras)
        pattern = re.compile(rf"\b\d+\s*(?:{era_group})\b", re.IGNORECASE)
        candidates.extend(
            DatePolicyViolation(
                match.start(), match.end(), match.group(0), "calendar era year"
            )
            for match in pattern.finditer(text)
        )

    for value in known_date_values:
        literal = format(float(value), ".12g")
        if not literal or ("." not in literal and not literal.startswith("-")):
            continue
        pattern = re.compile(rf"(?<![\w.]){re.escape(literal)}(?!\d)")
        candidates.extend(
            DatePolicyViolation(
                match.start(), match.end(), match.group(0), "known lore date"
            )
            for match in pattern.finditer(text)
        )

    candidates.sort(key=lambda item: (item.start, -(item.end - item.start), item.kind))
    results: list[DatePolicyViolation] = []
    for candidate in candidates:
        if any(
            candidate.start < existing.end and candidate.end > existing.start
            for existing in results
        ):
            continue
        results.append(candidate)
    return tuple(results)
