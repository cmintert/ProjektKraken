"""Fresh-record metadata planning shared by preview and transactional commands."""

from copy import deepcopy
from typing import Any

from src.core.batch_metadata import MetadataOperation, Target, values_equal
from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService


def load_record(db: DatabaseService, target: Target) -> Entity | Event:
    """Load a saved baseline object, rejecting deleted or malformed records."""
    kind, object_id = target
    record = db.get_entity(object_id) if kind == "entity" else db.get_event(object_id)
    if record is None:
        raise ValueError(f"Checked {kind} {object_id} no longer exists.")
    if not isinstance(record.attributes, dict):
        raise ValueError(f"Metadata for {kind} {object_id} is malformed.")
    return record


def prepare_metadata(
    db: DatabaseService, targets: list[Target], operation: MetadataOperation
) -> dict[str, Any]:
    """Capture affected states and object counts without mutating records."""
    rows = []
    for target in targets:
        record = load_record(db, target)
        before, after, overwritten = operation.patch(record.attributes)
        rows.append(
            {
                "kind": target[0],
                "id": target[1],
                "before": deepcopy(before),
                "after": deepcopy(after),
                "overwritten": overwritten,
            }
        )
    changed = sum(not values_equal(row["before"], row["after"]) for row in rows)
    return {
        "rows": rows,
        "changed": changed,
        "unchanged": len(rows) - changed,
        "overwritten": sum(row["overwritten"] for row in rows),
    }
