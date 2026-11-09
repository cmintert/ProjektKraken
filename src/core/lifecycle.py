"""Lifecycle meanings and evidence-based character living status."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations
from math import isfinite
from typing import Any, Literal

from src.core.date_parser import DateParser
from src.core.temporal_expression import ResolvedTemporalBounds

CHARACTER_TRANSITIONS = frozenset({"birth", "death", "revival"})


def lifecycle_options(entity_type: str) -> tuple[tuple[str, str], ...]:
    """Return the common transitions offered by the Entity Timeline."""
    return {
        "character": (("birth", "Birth"), ("death", "Death")),
        "item": (("creation", "Created"), ("destruction", "Destroyed")),
        "faction": (("founding", "Founded"), ("dissolution", "Dissolved")),
    }.get(entity_type.casefold(), ())


def additional_lifecycle_options(entity_type: str) -> tuple[tuple[str, str], ...]:
    """Return optional reversals for the secondary authoring menu."""
    return {
        "character": (("revival", "Revival"),),
        "faction": (("restoration", "Restoration"),),
    }.get(entity_type.casefold(), ())


def allowed_lifecycle_key(entity_type: str, key: str) -> bool:
    """Validate a new shortcut's meaning against the saved Entity type."""
    return key == "involved" or any(
        candidate == key
        for candidate, _ in (
            *lifecycle_options(entity_type),
            *additional_lifecycle_options(entity_type),
        )
    )


@dataclass(frozen=True)
class LivingClaim:
    """One authored transition and its feasible start bounds."""

    relation_id: str
    event_id: str | None
    kind: str
    lower: float | None
    upper: float | None


@dataclass(frozen=True)
class LivingStatus:
    """Derived status at a viewed time, with evidence for the answer."""

    value: Literal["alive", "dead", "indeterminate"]
    reason: str
    claims: tuple[LivingClaim, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize status without copying it into mutable Entity attributes."""
        return {
            "value": self.value,
            "reason": self.reason,
            "relation_ids": list(
                dict.fromkeys(claim.relation_id for claim in self.claims)
            ),
            "event_ids": list(
                dict.fromkeys(
                    claim.event_id
                    for claim in self.claims
                    if claim.event_id is not None
                )
            ),
        }


def character_claims(
    entity_id: str,
    relations: list[dict[str, Any]],
    anchors: dict[str, ResolvedTemporalBounds],
    legacy_parser: DateParser | None = None,
) -> list[LivingClaim]:
    """Read recognized claims in either direction without changing legacy rows."""
    claims = []
    for relation in relations:
        kind = str(relation.get("rel_type", "")).strip().casefold()
        if kind not in CHARACTER_TRANSITIONS:
            continue
        source, target = relation["source_id"], relation["target_id"]
        if entity_id not in (source, target):
            continue
        other = target if source == entity_id else source
        attributes = relation.get("attributes") or {}
        event_id = next(
            (
                identity
                for identity in (other, attributes.get("event_id"))
                if identity and f"event:{identity}" in anchors
            ),
            None,
        )
        if event_id is not None:
            bounds = anchors[f"event:{event_id}"]
            lower, upper = (
                (None, None) if bounds.error else (bounds.hard_start, bounds.hard_end)
            )
        else:
            date = attributes.get("date")
            if kind == "revival" or date is None:
                continue
            lower, upper = _legacy_boundary(date, legacy_parser)
        claims.append(LivingClaim(relation["id"], event_id, kind, lower, upper))
    return claims


def _legacy_boundary(
    value: Any, parser: DateParser | None
) -> tuple[float | None, float | None]:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    ):
        return float(value), float(value)
    if parser is not None and isinstance(value, str):
        try:
            bounds = parser.parse_expression(value).resolve_bounds(parser.converter)
        except (TypeError, ValueError, OverflowError):
            return None, None
        if not bounds.error:
            return bounds.hard_start, bounds.hard_end
    return None, None


def definitely_outside_life(
    claims: list[LivingClaim], bounds: ResolvedTemporalBounds
) -> bool:
    """Test an Event's full start range against recorded living intervals."""
    lower, upper = bounds.hard_start, bounds.hard_end
    if bounds.error or lower is None or upper is None:
        return False
    starts = [claim for claim in claims if claim.kind != "death"]
    if starts and all(
        claim.lower is not None and upper < claim.lower for claim in starts
    ):
        return any(claim.kind == "birth" for claim in starts)
    for death in claims:
        if death.kind != "death" or death.upper is None or death.upper >= lower:
            continue
        if all(_cannot_restart_after(claim, death, upper) for claim in starts):
            return True
    return False


def _cannot_restart_after(start: LivingClaim, death: LivingClaim, upper: float) -> bool:
    return (
        start.upper is not None
        and death.lower is not None
        and start.upper < death.lower
    ) or (start.lower is not None and start.lower > upper)


def competing_claims(
    claims: list[LivingClaim],
) -> Iterator[tuple[LivingClaim, LivingClaim, bool]]:
    """Yield opposing claims whose feasible windows allow a shared boundary."""
    for left, right in combinations(claims, 2):
        if (left.kind == "death") == (right.kind == "death"):
            continue
        if not _can_overlap(left, right):
            continue
        exact = (
            left.lower is not None
            and left.lower == left.upper == right.lower == right.upper
        )
        yield left, right, exact


def _can_overlap(left: LivingClaim, right: LivingClaim) -> bool:
    return not (
        (
            left.upper is not None
            and right.lower is not None
            and left.upper < right.lower
        )
        or (
            right.upper is not None
            and left.lower is not None
            and right.upper < left.lower
        )
    )


def resolve_living_status(claims: list[LivingClaim], time: float) -> LivingStatus:
    """Resolve only conclusions shared by the feasible transition orderings."""
    relevant = [claim for claim in claims if claim.lower is None or claim.lower <= time]
    if not relevant:
        return LivingStatus("indeterminate", "no_established_boundary")
    definite = [
        claim for claim in relevant if claim.upper is not None and claim.upper <= time
    ]
    latest = max(
        (claim.lower for claim in definite if claim.lower is not None), default=None
    )
    if latest is None:
        return LivingStatus(
            "indeterminate", "transition_timing_unresolved", tuple(relevant)
        )
    contenders = tuple(
        claim for claim in relevant if claim.upper is None or claim.upper >= latest
    )
    kinds = {claim.kind == "death" for claim in contenders}
    if len(kinds) != 1:
        return LivingStatus("indeterminate", "competing_transitions", contenders)
    if True in kinds:
        return LivingStatus("dead", "death_established", contenders)
    if any(claim.lower == claim.upper == time for claim in definite):
        return LivingStatus("alive", "exact_life_start", contenders)
    future = tuple(
        claim for claim in claims if claim.lower is not None and claim.lower > time
    )
    if _next_boundary_is_death(future):
        return LivingStatus("alive", "bounded_living_interval", contenders + future)
    return LivingStatus("indeterminate", "life_start_without_later_death", contenders)


def _next_boundary_is_death(claims: tuple[LivingClaim, ...]) -> bool:
    death_ends = [
        claim.upper
        for claim in claims
        if claim.kind == "death" and claim.upper is not None
    ]
    if not death_ends:
        return False
    earliest_death_end = min(death_ends)
    return all(
        claim.kind == "death"
        or (claim.lower is not None and claim.lower > earliest_death_end)
        for claim in claims
    )
