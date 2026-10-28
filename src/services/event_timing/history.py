"""Expected-state checks for recorded commands predating prepared timing plans."""

from typing import Any

from src.core.events import Event
from src.services.db_service import DatabaseService


def recorded_event(db: DatabaseService, expected: Event, updated: Event) -> Event:
    """Restore a recorded Event snapshot without forward-edit reinterpretation."""
    current = db.get_event(expected.id)
    if current is None or current.to_dict() != expected.to_dict():
        raise ValueError(
            "Event changed since undo; the recorded update cannot be reapplied"
        )
    db.insert_event(updated)
    return updated


def check_recorded_calendar(db: DatabaseService, expected: dict[str, Any]) -> None:
    """A legacy calendar redo must still match its recorded before state."""
    if expected["kind"] == "active":
        current = db.get_active_calendar_config()
        matches = (current.id if current else None) == expected["id"]
    else:
        current = db.get_calendar_config(expected["id"])
        matches = (current.to_dict() if current else None) == expected["config"]
    if not matches:
        raise ValueError(
            "Calendar changed since undo; the recorded operation cannot be reapplied"
        )


def check_recorded_deletion(
    db: DatabaseService,
    expected: Event,
    relations: list[dict[str, Any]],
    dependencies: list[str],
) -> None:
    """Allow historical deletion only while its restored inputs still match."""
    from src.services.temporal_dependency_service import event_temporal_dependencies

    current = db.get_event(expected.id)
    current_relations = db.get_relations_for_item(expected.id)
    if (
        current is None
        or current.to_dict() != expected.to_dict()
        or sorted(current_relations, key=lambda row: row["id"])
        != sorted(relations, key=lambda row: row["id"])
        or event_temporal_dependencies(db, expected.id) != sorted(dependencies)
    ):
        raise ValueError("Deletion inputs changed since undo; redo cannot safely apply")


def restore_recorded_chronology(
    db: DatabaseService,
    previous: dict[str, dict[str, Any]],
    updated: dict[str, dict[str, Any]],
) -> None:
    """Check all owners before restoring an already accepted chronology operation."""
    for identity, snapshot in previous.items():
        current = db.get_event(identity)
        if current is None or current.to_dict() != snapshot:
            raise ValueError("Chronology changed since undo; redo cannot safely apply")
    for snapshot in updated.values():
        db.insert_event(Event.from_dict(snapshot))
