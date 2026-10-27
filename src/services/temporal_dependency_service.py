"""Find persisted temporal dependencies before an event anchor is removed."""

from typing import Any

from src.core.temporal_references import event_reference_ids
from src.services.db_service import DatabaseService


def event_temporal_dependencies(db: DatabaseService, event_id: str) -> list[str]:
    """Return stable dependency descriptions from the worker-owned database."""

    def references(value: Any) -> bool:
        return event_id in event_reference_ids(value)

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
