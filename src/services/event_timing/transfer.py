"""Integrate imported row deltas with the same timing planner as authoring."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from src.core.events import Event
from src.services.db_service import DatabaseService
from src.services.event_timing.planning import TimingChangeRequest, prepare_change
from src.services.event_timing.store import capture, relation_consumer


def _row(row: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(row)
    if isinstance(result.get("attributes"), str):
        result["attributes"] = json.loads(result["attributes"] or "{}")
    return result


def request_from_delta(
    snapshot: dict[str, Any], delta: list[dict[str, Any]]
) -> TimingChangeRequest:
    """Interpret only incoming changes; existing dependents keep their IDs."""
    updates = {}
    creates = []
    deletes = []
    consumers = {
        (item["kind"], item["id"]): deepcopy(item)
        for item in snapshot.get("consumers", [])
    }
    for change in delta:
        old, new = change["before"], change["after"]
        if change["table"] == "events":
            if new is None:
                deletes.append(old["id"])
            elif old is None:
                creates.append(_row(new))
            else:
                updates[new["id"]] = _row(new)
        elif change["table"] == "relations":
            row = new or old
            key = ("relation", row["id"])
            if new is None:
                consumers.pop(key, None)
            else:
                parsed = _row(new)
                consumers[key] = relation_consumer(parsed)
    return TimingChangeRequest(
        updates=updates,
        creates=tuple(creates),
        deletes=tuple(deletes),
        imported=True,
        consumers=tuple(consumers.values()),
        world_id=snapshot["world_id"],
    )


def requires_prepared_import(db: DatabaseService, delta: list[dict[str, Any]]) -> bool:
    """A raw SQL preview cannot bypass schema-2 Event timing validation."""
    from src.services.event_timing.guards import has_calculated_events

    changes = [item for item in delta if item["table"] == "events"]
    if not changes:
        return False
    incoming = [
        Event.from_dict(_row(item["after"]))
        for item in changes
        if item["after"] is not None
    ]
    return has_calculated_events([*db.get_all_events(), *incoming])


def project_import(
    db: DatabaseService, delta: list[dict[str, Any]], clone: DatabaseService
) -> dict[str, Any] | None:
    """Calculate on a private preview world, then materialize its derived deltas."""
    if not any(change["table"] == "events" for change in delta):
        return None
    snapshot = capture(db)
    request = request_from_delta(snapshot, delta)
    plan = prepare_change(snapshot, request)
    if not plan.errors:
        for row in plan.updated.values():
            clone.insert_event(Event.from_dict(deepcopy(row)))
    return plan.review()
