"""Read-only choices for hierarchy authoring, shared by presentation clients."""

from src.core.map import Map
from src.core.map_hierarchy import HierarchyError, MapHierarchy


def candidate_parents(maps: list[Map], map_id: str) -> list[Map]:
    """Return structurally valid destinations, including independent maps."""
    hierarchy = MapHierarchy(maps)
    result = []
    for record in maps:
        try:
            hierarchy.validate_change_parent(map_id, record.id)
        except HierarchyError:
            continue
        result.append(record)
    return result
