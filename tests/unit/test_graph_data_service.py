"""
Tests for GraphDataService.

Tests the data layer that fetches and filters graph visualization data.
"""

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.services.graph_data_service import GraphDataService


@pytest.fixture
def db_service():
    """Provides a DatabaseService with in-memory database."""
    from src.services.db_service import DatabaseService

    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


@pytest.fixture
def populated_db(db_service):
    """Populates db with test entities, events, and relations."""
    # Create entities with tags
    entity1 = Entity(name="Character A", type="character")
    entity1.tags = ["protagonist", "hero"]
    db_service.insert_entity(entity1)

    entity2 = Entity(name="Location B", type="location")
    entity2.tags = ["city", "capital"]
    db_service.insert_entity(entity2)

    entity3 = Entity(name="Character C", type="character")
    entity3.tags = ["antagonist"]
    db_service.insert_entity(entity3)

    # Create events with tags
    event1 = Event(name="Battle of X", lore_date=1000.0)
    event1.tags = ["war", "major"]
    db_service.insert_event(event1)

    event2 = Event(name="Treaty of Y", lore_date=2000.0)
    event2.tags = ["peace", "major"]
    db_service.insert_event(event2)

    # Create relations
    db_service.insert_relation(entity1.id, entity2.id, "located_at")
    db_service.insert_relation(entity1.id, event1.id, "involved")
    db_service.insert_relation(entity3.id, event1.id, "caused")

    return {
        "db": db_service,
        "entities": [entity1, entity2, entity3],
        "events": [event1, event2],
    }


class TestGraphDataServiceInit:
    """Tests for GraphDataService initialization."""

    def test_init_creates_service(self):
        """GraphDataService can be instantiated."""
        service = GraphDataService()
        assert service is not None


class TestGetGraphData:
    """Tests for GraphDataService.get_graph_data method."""

    def test_get_graph_data_returns_all_nodes_without_filters(self, populated_db):
        """Returns all entities and events when no filters applied."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(populated_db["db"])

        # Should have 3 entities + 2 events = 5 nodes
        assert len(nodes) == 5
        # Should have 3 relations = 3 edges
        assert len(edges) == 3

    def test_get_graph_data_filters_by_single_tag(self, populated_db):
        """Filters nodes by a single tag (include semantics)."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"], include_tags=["protagonist"]
        )

        # Only entity1 has "protagonist" tag
        assert len(nodes) == 1
        assert nodes[0]["name"] == "Character A"

    def test_get_graph_data_filters_by_multiple_tags_or(self, populated_db):
        """Multiple tags filter with OR semantics (any tag matches)."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"], include_tags=["protagonist", "city"]
        )

        # entity1 has "protagonist", entity2 has "city"
        assert len(nodes) == 2
        names = {n["name"] for n in nodes}
        assert names == {"Character A", "Location B"}

    def test_get_graph_data_filters_by_rel_type(self, populated_db):
        """Filters edges by relation type."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"], include_rel_types=["involved"]
        )

        # Only edges with rel_type="involved" should be returned
        assert len(edges) == 1
        assert edges[0]["rel_type"] == "involved"

    def test_get_graph_data_filters_edges_include_connected_nodes(self, populated_db):
        """When filtering by rel_type, only connected nodes are included."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"], include_rel_types=["located_at"]
        )

        # located_at connects entity1 -> entity2
        assert len(edges) == 1
        # Nodes should only include the two connected entities
        assert len(nodes) == 2
        names = {n["name"] for n in nodes}
        assert names == {"Character A", "Location B"}

    def test_get_graph_data_combined_filters(self, populated_db):
        """Combined tag and rel_type filters."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"],
            include_tags=["protagonist"],
            include_rel_types=["involved"],
        )

        # When combining filters:
        # 1. rel_type filter: only "involved" edge (entity1→event1)
        # 2. Candidate nodes: entity1, event1 (connected by that edge)
        # 3. tag filter: only entity1 has "protagonist" tag
        # 4. Edges filtered: both source and target must be in filtered nodes
        # Since event1 doesn't have "protagonist", the edge is filtered out
        assert len(nodes) == 1
        assert nodes[0]["name"] == "Character A"
        assert len(edges) == 0  # Edge removed because target not in filtered nodes

    def test_get_graph_data_empty_result_for_nonexistent_tag(self, populated_db):
        """Returns empty result for non-existent tag."""
        service = GraphDataService()
        nodes, edges = service.get_graph_data(
            populated_db["db"], include_tags=["nonexistent"]
        )

        assert len(nodes) == 0
        assert len(edges) == 0


class TestGetAllTags:
    """Tests for GraphDataService.get_all_tags method."""

    def test_get_all_tags_returns_unique_tags(self, populated_db):
        """Returns all unique tags across entities and events."""
        service = GraphDataService()
        tags = service.get_all_tags(populated_db["db"])

        expected = {
            "protagonist",
            "hero",
            "city",
            "capital",
            "antagonist",
            "war",
            "major",
            "peace",
        }
        assert set(tags) == expected

    def test_get_all_tags_empty_db(self, db_service):
        """Returns empty list for empty database."""
        service = GraphDataService()
        tags = service.get_all_tags(db_service)

        assert tags == []


class TestGetAllRelationTypes:
    """Tests for GraphDataService.get_all_relation_types method."""

    def test_get_all_relation_types_returns_unique_types(self, populated_db):
        """Returns all unique relation types."""
        service = GraphDataService()
        rel_types = service.get_all_relation_types(populated_db["db"])

        expected = {"located_at", "involved", "caused"}
        assert set(rel_types) == expected

    def test_get_all_relation_types_empty_db(self, db_service):
        """Returns empty list for empty database."""
        service = GraphDataService()
        rel_types = service.get_all_relation_types(db_service)

        assert rel_types == []
