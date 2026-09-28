"""World-wide chronology collection, projection and consistency checks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_constraints import (
    ChronologyIssue,
    TemporalConstraint,
    TemporalConstraintKind,
    chronology_issues,
    chronology_key,
)


@dataclass(frozen=True)
class StoredChronology:
    """A rule with its physical owner and legacy row reference."""

    owner_id: str
    position: int
    data: dict[str, Any]
    constraint: TemporalConstraint

    @property
    def reference(self) -> str:
        """Stable ID when available; scoped row reference for old data."""
        return self.constraint.id or f"legacy:{self.owner_id}:{self.position}"


def collect_chronology(events: list[Event]) -> list[StoredChronology]:
    """Collect every stored rule without changing the world."""
    records = []
    for event in events:
        for position, data in enumerate(
            event.attributes.get("_temporal_v2", {}).get("constraints", [])
        ):
            records.append(
                StoredChronology(
                    event.id, position, data, TemporalConstraint.from_dict(data)
                )
            )
    return records


def direct_chronology(
    event_id: str, records: list[StoredChronology]
) -> list[tuple[StoredChronology, str, TemporalConstraintKind]]:
    """Describe all direct rules from one event's viewpoint."""
    anchor = f"event:{event_id}"
    result = []
    for record in records:
        item = record.constraint
        if item.anchor_a == anchor:
            result.append((record, item.anchor_b, item.relation))
        elif item.anchor_b == anchor:
            inverse = {
                TemporalConstraintKind.BEFORE: TemporalConstraintKind.AFTER,
                TemporalConstraintKind.AFTER: TemporalConstraintKind.BEFORE,
                TemporalConstraintKind.SAME_AS: TemporalConstraintKind.SAME_AS,
            }
            result.append((record, item.anchor_a, inverse[item.relation]))
    return result


def world_issues(
    events: list[Event], converter: CalendarConverter | None
) -> list[ChronologyIssue]:
    """Validate all asserted rules against all current event date domains."""
    records = collect_chronology(events)
    return chronology_issues(
        [record.constraint for record in records],
        resolve_event_anchors(events, converter),
    )


def new_issues(
    before: list[ChronologyIssue], after: list[ChronologyIssue]
) -> list[ChronologyIssue]:
    """Leave old world defects alone while rejecting newly introduced ones."""
    existing = Counter((issue.code, issue.anchor_ids) for issue in before)
    introduced = []
    for issue in after:
        key = issue.code, issue.anchor_ids
        if existing[key]:
            existing[key] -= 1
        else:
            introduced.append(issue)
    return introduced


def duplicate_key(data: dict[str, Any]) -> tuple[str, str, str]:
    """Normalize before/after and shared-transition authoring."""
    return chronology_key(TemporalConstraint.from_dict(data))
