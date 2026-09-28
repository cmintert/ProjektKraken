"""Validation and serialization for temporal authoring forms."""

from copy import deepcopy
from dataclasses import replace
from typing import Any
from uuid import uuid4

from src.core.calendar import CalendarConverter
from src.core.date_parser import DateParser
from src.core.temporal_constraints import TemporalConstraint, validate_constraints
from src.core.temporal_expression import TemporalExpression, TemporalPrecision


def explicit_limit_text(
    value: float, converter: CalendarConverter, *, upper: bool
) -> str:
    """Format a stored limit as an included day or second, not a nominal date."""
    whole_day = float(value).is_integer()
    coordinate = value - (1 if whole_day else 1 / 86400) if upper else value
    # Reconstruct seconds without float truncation moving a limit one second back.
    seconds = round(coordinate * 86400)
    day, second = divmod(seconds, 86400)
    date = converter.from_float(float(day))
    expression = TemporalExpression(
        converter._config.id,
        date.year,
        date.month,
        date.day,
        hour=None if whole_day else second // 3600,
        minute=None if whole_day else second // 60 % 60,
        second=None if whole_day else second % 60,
        precision=TemporalPrecision.DAY if whole_day else TemporalPrecision.SECOND,
    )
    return expression.display_text(converter)


def with_explicit_limits(
    expression: TemporalExpression,
    parser: DateParser,
    start: str,
    end: str,
) -> TemporalExpression:
    """Expand authored limit precision through the calendar, never nominal padding."""
    lower = (
        parser.parse_expression(start).resolve_bounds(parser.converter)
        if start
        else None
    )
    upper = (
        parser.parse_expression(end).resolve_bounds(parser.converter) if end else None
    )
    if lower and (lower.error or lower.hard_start is None):
        raise ValueError("Possible from needs an asserted calendar date.")
    if upper and (upper.error or upper.hard_end is None):
        raise ValueError("Possible until needs an asserted calendar date.")
    result = replace(
        expression,
        explicit_outer_start=lower.hard_start if lower else None,
        explicit_outer_end=upper.hard_end if upper else None,
    )
    error = result.resolve_bounds(parser.converter).error
    if error:
        raise ValueError(error)
    return result


def author_temporal_evidence(
    metadata: dict[str, Any],
    parser: DateParser,
    claims: list[tuple[str, str]],
    preferred: int,
    constraints: list[dict[str, Any]],
    claim_ids: list[str | None] | None = None,
) -> dict[str, Any]:
    """Keep source claims separate and change the canonical date only explicitly."""
    result = deepcopy(metadata)
    previous = metadata.get("claims", [])
    records = []
    for index, (source, text) in enumerate(claims):
        if not source.strip() or not text.strip():
            raise ValueError("Each source claim needs a source and a date.")
        original = (
            next((item for item in previous if item.get("id") == claim_ids[index]), {})
            if claim_ids is not None
            else previous[index]
            if index < len(previous)
            else {}
        )
        expression = (
            TemporalExpression.from_dict(original["expression"]) if original else None
        )
        if expression is None or expression.display_text(parser.converter) != text:
            expression = parser.parse_expression(text)
        records.append(
            {
                **original,
                "id": original.get("id", str(uuid4())),
                "source": source.strip(),
                "expression": expression.to_dict(),
            }
        )
    errors = (
        validate_constraints(
            [TemporalConstraint.from_dict(item) for item in constraints]
        )
        if constraints != metadata.get("constraints", [])
        else []
    )
    if errors:
        raise ValueError(" ".join(errors))
    result.update(schema=1, claims=records, constraints=deepcopy(constraints))
    if preferred >= 0:
        if preferred >= len(records):
            raise ValueError("Choose an existing preferred claim.")
        result["preferred_claim_id"] = records[preferred]["id"]
        result["expression"] = deepcopy(records[preferred]["expression"])
    else:
        result.pop("preferred_claim_id", None)
    return result


def conflicting_claims(metadata: dict[str, Any], converter: CalendarConverter) -> bool:
    """Report disjoint evidence periods without treating coarse dates as errors."""
    bounds = [
        TemporalExpression.from_dict(claim["expression"]).resolve_bounds(converter)
        for claim in metadata.get("claims", [])
    ]
    for index, left in enumerate(bounds):
        for right in bounds[index + 1 :]:
            if left.error or right.error:
                continue
            if (
                left.hard_end is not None
                and right.hard_start is not None
                and left.hard_end <= right.hard_start
            ) or (
                right.hard_end is not None
                and left.hard_start is not None
                and right.hard_end <= left.hard_start
            ):
                return True
    return False
