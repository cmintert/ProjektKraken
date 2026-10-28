"""Database-thread prepared-plan ownership and fresh snapshot verification."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from weakref import WeakKeyDictionary

from src.services.db_service import DatabaseService
from src.services.event_timing.planning import TimingChangePlan, snapshot_fingerprint

_stores: WeakKeyDictionary[DatabaseService, dict[str, TimingChangePlan]] = (
    WeakKeyDictionary()
)


def relation_consumer(relation: dict[str, Any]) -> dict[str, Any]:
    """Retain implicit source-Event bindings alongside explicit endpoint links."""
    attributes = deepcopy(relation.get("attributes", {}))
    if any(
        attributes.get(flag)
        for flag in ("valid_from_event", "valid_to_event", "valid_at_event")
    ) or "source_event" in str(attributes.get("temporal", {})):
        attributes["source_reference"] = {
            "anchor_id": f"event:{relation.get('source_id')}"
        }
    return {
        "kind": "relation",
        "id": relation["id"],
        "name": relation.get("rel_type", "Relation"),
        "attributes": attributes,
    }


def capture(db: DatabaseService) -> dict[str, Any]:
    """Capture source records and review labels on the database-owning thread."""
    config = db.get_active_calendar_config()
    consumers: list[dict[str, Any]] = []
    for relation in db.get_all_relations():
        consumers.append(relation_consumer(relation))
    for map_obj in db.get_all_maps():
        attributes = deepcopy(map_obj.attributes)
        if map_obj.layers is not None:
            attributes["layers"] = map_obj.layers.to_dict()
        consumers.append(
            {
                "kind": "map",
                "id": map_obj.id,
                "name": map_obj.name,
                "attributes": attributes,
            }
        )
        for marker in db.get_markers_for_map(map_obj.id):
            consumers.append(
                {
                    "kind": "map feature",
                    "id": marker.id,
                    "name": marker.label or map_obj.name,
                    "attributes": deepcopy(marker.attributes),
                }
            )
    return {
        "world_id": db.db_path,
        "events": [event.to_dict() for event in db.get_all_events()],
        "calendar": config.to_json() if config else None,
        "calendars": [calendar.to_dict() for calendar in db.get_all_calendar_configs()],
        "consumers": consumers,
    }


def register(db: DatabaseService, plan: TimingChangePlan) -> str:
    """Accept a completed internal calculation only against its original snapshot."""
    if plan.errors:
        raise ValueError("\n".join(plan.errors))
    if snapshot_fingerprint(capture(db)) != plan.base_fingerprint:
        raise ValueError("Timing inputs changed. Review a refreshed calculation.")
    _stores.setdefault(db, {})[plan.identity] = plan
    return plan.identity


def consume(db: DatabaseService, identity: str, confirmation: str) -> TimingChangePlan:
    """Consume one worker-owned plan; forged, stale and reused handles fail closed."""
    plan = _stores.get(db, {}).pop(identity, None)
    if plan is None:
        raise ValueError(
            "The timing plan is unavailable. Calculate and review it again."
        )
    if confirmation != plan.fingerprint:
        raise ValueError("The timing cascade has not been confirmed")
    if snapshot_fingerprint(capture(db)) != plan.base_fingerprint:
        raise ValueError("Timing inputs changed. Review a refreshed calculation.")
    return plan


def clear(db: DatabaseService) -> None:
    """Invalidate pending plans when a world adapter closes."""
    _stores.pop(db, None)


def discard(db: DatabaseService, identity: str) -> None:
    """A cancelled review cannot leave an applicable prepared plan behind."""
    _stores.get(db, {}).pop(identity, None)
