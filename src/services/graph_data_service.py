"""
Graph Data Service Module.

Provides data fetching and filtering for graph visualization.
Separates data access concerns from the widget layer.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)


class GraphDataService:
    """
    Service for fetching graph visualization data.

    Provides methods to retrieve entities, events, and relations
    for graph visualization, with support for positive (include-only)
    filtering by tags and relation types.
    """

    def get_graph_data(
        self,
        db_service: "DatabaseService",
        include_tags: list[str] | None = None,
        include_rel_types: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Fetches nodes (entities/events) and edges (relations) for graph display.

        Args:
            db_service: Database service instance.
            include_tags: If provided, only include items with any of these tags.
            include_rel_types: If provided, only include relations of these types.

        Returns:
            Tuple of (nodes, edges) where:
            - nodes: List of dicts with id, name, type, object_type keys
            - edges: List of dicts with source_id, target_id, rel_type keys
        """
        # Collect all relations by iterating over all entities and events
        all_relations = self._collect_all_relations(db_service)

        # Filter relations by type if specified
        if include_rel_types:
            relations = [
                r for r in all_relations if r.get("rel_type") in include_rel_types
            ]
        else:
            relations = all_relations

        # Helper to strip 'id:' prefix if present
        def strip_id_prefix(id_str: str) -> str:
            return id_str[3:] if id_str.startswith("id:") else id_str

        # If filtering by rel_type, only include connected nodes
        if include_rel_types:
            connected_ids = set()
            for rel in relations:
                connected_ids.add(strip_id_prefix(rel["source_id"]))
                connected_ids.add(strip_id_prefix(rel["target_id"]))

            nodes = self._get_nodes_by_ids(db_service, connected_ids, include_tags)
        else:
            nodes = self._get_all_nodes(db_service, include_tags)

        # Build edges list using strip_id_prefix to match node ID format
        edges = [
            {
                "source_id": strip_id_prefix(r["source_id"]),
                "target_id": strip_id_prefix(r["target_id"]),
                "rel_type": r["rel_type"],
            }
            for r in relations
        ]

        # If filtering by tags, also filter edges to only include those
        # where both source and target are in the filtered nodes
        if include_tags:
            node_ids = {n["id"] for n in nodes}
            edges = [
                e
                for e in edges
                if e["source_id"] in node_ids and e["target_id"] in node_ids
            ]

        return nodes, edges

    def get_all_tags(self, db_service: "DatabaseService") -> list[str]:
        """
        Returns all unique tags across entities and events.

        Args:
            db_service: Database service instance.

        Returns:
            List of unique tag strings, sorted alphabetically.
        """
        tags: set[str] = set()

        # Get tags from entities (returns Entity objects)
        for entity in db_service.get_all_entities():
            entity_tags = getattr(entity, "tags", [])
            tags.update(entity_tags)

        # Get tags from events (returns Event objects)
        for event in db_service.get_all_events():
            event_tags = getattr(event, "tags", [])
            tags.update(event_tags)

        return sorted(tags)

    def get_all_relation_types(self, db_service: "DatabaseService") -> list[str]:
        """
        Returns all unique relation types.

        Args:
            db_service: Database service instance.

        Returns:
            List of unique rel_type strings, sorted alphabetically.
        """
        all_relations = self._collect_all_relations(db_service)
        return sorted({r.get("rel_type", "") for r in all_relations})

    def _collect_all_relations(
        self, db_service: "DatabaseService"
    ) -> list[dict[str, Any]]:
        """
        Collects all relations by iterating over all entities and events.

        Since DatabaseService doesn't expose a get_all_relations() method,
        we collect relations by querying outgoing relations for each source.

        Args:
            db_service: Database service instance.

        Returns:
            List of relation dictionaries.
        """
        seen_ids: set[str] = set()
        relations: list[dict[str, Any]] = []

        # Get relations from all entities
        for entity in db_service.get_all_entities():
            for rel in db_service.get_relations(entity.id):
                if rel["id"] not in seen_ids:
                    seen_ids.add(rel["id"])
                    relations.append(rel)

        # Get relations from all events
        for event in db_service.get_all_events():
            for rel in db_service.get_relations(event.id):
                if rel["id"] not in seen_ids:
                    seen_ids.add(rel["id"])
                    relations.append(rel)

        return relations

    def _get_all_nodes(
        self,
        db_service: "DatabaseService",
        include_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Gets all entities and events as nodes.

        Args:
            db_service: Database service instance.
            include_tags: If provided, filter to items with any of these tags.

        Returns:
            List of node dicts.
        """
        nodes = []

        # Add entities (returns Entity objects)
        for entity in db_service.get_all_entities():
            if self._entity_matches_tags(entity, include_tags):
                nodes.append(self._entity_to_node(entity))

        # Add events (returns Event objects)
        for event in db_service.get_all_events():
            if self._event_matches_tags(event, include_tags):
                nodes.append(self._event_to_node(event))

        return nodes

    def _get_nodes_by_ids(
        self,
        db_service: "DatabaseService",
        ids: set[str],
        include_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Gets nodes for specific IDs only.

        Args:
            db_service: Database service instance.
            ids: Set of entity/event IDs to include.
            include_tags: If provided, additionally filter by tags.

        Returns:
            List of node dicts.
        """
        nodes = []

        # Check entities
        for entity in db_service.get_all_entities():
            if entity.id in ids and self._entity_matches_tags(entity, include_tags):
                nodes.append(self._entity_to_node(entity))

        # Check events
        for event in db_service.get_all_events():
            if event.id in ids and self._event_matches_tags(event, include_tags):
                nodes.append(self._event_to_node(event))

        return nodes

    def _entity_to_node(self, entity: Any) -> dict[str, Any]:
        """
        Converts an Entity object to a node dictionary.

        Args:
            entity: The Entity object to convert.

        Returns:
            A dictionary with id, name, type, object_type, and tags keys.
        """
        return {
            "id": entity.id,
            "name": getattr(entity, "name", "Unnamed"),
            "type": getattr(entity, "type", "entity"),
            "object_type": "entity",
            "tags": getattr(entity, "tags", []),
        }

    def _event_to_node(self, event: Any) -> dict[str, Any]:
        """
        Converts an Event object to a node dictionary.

        Args:
            event: The Event object to convert.

        Returns:
            A dictionary with id, name, type, object_type, and tags keys.
        """
        return {
            "id": event.id,
            "name": getattr(event, "name", "Unnamed"),
            "type": getattr(event, "type", "event"),
            "object_type": "event",
            "tags": getattr(event, "tags", []),
        }

    def _entity_matches_tags(self, entity: Any, include_tags: list[str] | None) -> bool:
        """
        Checks if an entity matches the tag filter (OR semantics).

        Args:
            entity: The Entity object to check.
            include_tags: List of tags to match (any). None or empty means no filter.

        Returns:
            True if the entity has at least one of the specified tags, or if no filter.
        """
        if not include_tags:  # None or empty list = no filter
            return True
        entity_tags = getattr(entity, "tags", [])
        return any(tag in entity_tags for tag in include_tags)

    def _event_matches_tags(self, event: Any, include_tags: list[str] | None) -> bool:
        """
        Checks if an event matches the tag filter (OR semantics).

        Args:
            event: The Event object to check.
            include_tags: List of tags to match (any). None or empty means no filter.

        Returns:
            True if the event has at least one of the specified tags, or if no filter.
        """
        if not include_tags:  # None or empty list = no filter
            return True
        event_tags = getattr(event, "tags", [])
        return any(tag in event_tags for tag in include_tags)
