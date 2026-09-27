"""Evidence-aware validation for explicitly exclusive relationship roles."""

from collections import defaultdict
from itertools import combinations
from typing import Any

from src.core.analysis import SeverityLevel, TemporalConflict
from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_constraints import TemporalConstraint, overlap_status
from src.core.temporal_window import TemporalValidity, resolve_temporal_window


def exclusive_role_conflicts(
    relations: list[dict[str, Any]],
    events: list[Event],
    converter: CalendarConverter,
) -> list[TemporalConflict]:
    """Check roles explicitly marked exclusive; never infer exclusivity from names."""
    anchors = resolve_event_anchors(events, converter)
    event_map = {event.id: event for event in events}
    constraints = [
        TemporalConstraint.from_dict(item)
        for event in events
        for item in event.attributes.get("_temporal_v2", {}).get("constraints", [])
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        groups[(relation.get("target_id", ""), relation.get("rel_type", ""))].append(
            relation
        )
    conflicts = []
    for (_, role), group in groups.items():
        if not any(rel.get("attributes", {}).get("exclusive") is True for rel in group):
            continue
        for first, second in combinations(group, 2):
            if first.get("source_id") == second.get("source_id"):
                continue
            windows = []
            for relation in (first, second):
                event = event_map.get(relation.get("source_id", ""))
                windows.append(
                    resolve_temporal_window(
                        relation.get("attributes", {}),
                        event.lore_date if event else None,
                        source_event_attributes=event.attributes if event else None,
                        source_event_id=event.id if event else None,
                        converter=converter,
                        anchors=anchors,
                    )
                )
            status = overlap_status(windows[0], windows[1], constraints=constraints)
            if status == TemporalValidity.INACTIVE:
                continue
            definite = status == TemporalValidity.DEFINITE
            conflicts.append(
                TemporalConflict(
                    conflict_type="exclusive_role_overlap",
                    entity_id=str(first.get("target_id", "")),
                    entity_name=role,
                    problem_date=None,
                    message=(
                        f"Exclusive role '{role}' has overlapping holders."
                        if definite
                        else f"Exclusive role '{role}' may have overlapping holders; the dates do not establish this."
                    ),
                    suggestion="Review the boundaries and any shared transition or ordering evidence.",
                    severity=SeverityLevel.CRITICAL
                    if definite
                    else SeverityLevel.WARNING,
                    related_ids=[str(first.get("id", "")), str(second.get("id", ""))],
                    fingerprint=f"exclusive:{first.get('id')}:{second.get('id')}",
                )
            )
    return conflicts
