"""Read-only choices for hierarchy authoring, shared by presentation clients."""

from src.core.map import Map
from src.core.map_hierarchy import MapHierarchy


def candidate_parents(maps: list[Map], map_id: str) -> list[Map]:
    """Return structurally valid destinations, including independent maps."""
    candidates = MapHierarchy(maps).candidate_parent_ids(map_id)
    return [record for record in maps if record.id in candidates]
