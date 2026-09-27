"""Find persisted temporal dependencies before an event anchor is removed."""

from typing import Any

from src.services.db_service import DatabaseService


def event_temporal_dependencies(db: DatabaseService, event_id: str) -> list[str]:
    """Return stable dependency descriptions from the worker-owned database."""
    anchor = f"event:{event_id}"

    def references(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                (key in {"anchor_id", "anchor_a", "anchor_b"} and item == anchor)
                or references(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(references(item) for item in value)
        return False

    dependencies = []
    for relation in db.get_all_relations():
        attrs = relation.get("attributes", {})
        source_binding = relation.get("source_id") == event_id and (
            attrs.get("valid_from_event")
            or attrs.get("valid_to_event")
            or attrs.get("valid_at_event")
            or "source_event" in str(attrs.get("temporal", {}))
        )
        if references(attrs) or source_binding:
            dependencies.append(
                f"Relation {relation.get('id')}: {relation.get('rel_type', '')}"
            )
    for event in db.get_all_events():
        if event.id != event_id and references(
            event.attributes.get("_temporal_v2", {})
        ):
            dependencies.append(f"Event {event.id}: {event.name}")
    for map_obj in db.get_all_maps():
        if references(map_obj.attributes) or (
            map_obj.layers is not None and references(map_obj.layers.to_dict())
        ):
            dependencies.append(f"Map {map_obj.id}: {map_obj.name}")
    return sorted(dependencies)
