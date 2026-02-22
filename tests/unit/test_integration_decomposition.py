"""Integration tests for decomposed DatabaseService.

Validates the full delegation chain: DatabaseService → Repository → SQLite
for all domain areas, ensuring the refactoring maintains backward compatibility.
"""

import json

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.services.db_service import DatabaseService


@pytest.fixture
def db():
    """Create a fully-connected in-memory DatabaseService."""
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def seeded_db(db):
    """DatabaseService with pre-seeded data for integration testing."""
    # Create events
    e1 = Event(name="Battle of Dawn", type="battle", lore_date=100.0)
    e2 = Event(name="Treaty Signing", type="diplomacy", lore_date=200.0)
    e3 = Event(name="Coronation", type="ceremony", lore_date=300.0)
    for e in [e1, e2, e3]:
        db.insert_event(e)

    # Create entities
    ent1 = Entity(name="King Arthur", type="character")
    ent2 = Entity(name="Excalibur", type="item")
    for ent in [ent1, ent2]:
        db.insert_entity(ent)

    # Create tags and assign
    db.create_tag("war")
    db.create_tag("peace")
    db.assign_tag_to_event(e1.id, "war")
    db.assign_tag_to_event(e2.id, "peace")
    db.assign_tag_to_entity(ent1.id, "war")

    # Create a relation
    db.insert_relation(e1.id, ent1.id, "involves")

    return db, {"events": [e1, e2, e3], "entities": [ent1, ent2]}


class TestTagRepositoryIntegration:
    """End-to-end tests for tag operations via DatabaseService delegation."""

    def test_full_tag_lifecycle(self, db):
        """Test create → assign → get → remove → delete cycle."""
        event = Event(name="Test", type="generic", lore_date=1.0)
        db.insert_event(event)

        # Create and assign
        tag_id = db.create_tag("lifecycle_tag")
        db.assign_tag_to_event(event.id, "lifecycle_tag")

        # Verify assignment
        tags = db.get_tags_for_event(event.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "lifecycle_tag"

        # Remove assignment
        db.remove_tag_from_event(event.id, "lifecycle_tag")
        assert len(db.get_tags_for_event(event.id)) == 0

        # Tag still exists
        assert db.get_tag_by_name("lifecycle_tag") is not None

        # Delete tag
        db.delete_tag("lifecycle_tag")
        assert db.get_tag_by_name("lifecycle_tag") is None

    def test_tag_color_round_trip(self, db):
        """Test set_tag_color → get_tag_color round-trip."""
        db.create_tag("color_test")
        db.set_tag_color("color_test", "#FF5500")
        assert db.get_tag_color("color_test") == "#FF5500"

    def test_events_by_tag(self, seeded_db):
        """Test getting events filtered by tag."""
        db, data = seeded_db
        war_events = db.get_events_by_tag("war")
        assert len(war_events) == 1
        assert war_events[0].name == "Battle of Dawn"

    def test_entities_by_tag(self, seeded_db):
        """Test getting entities filtered by tag."""
        db, data = seeded_db
        war_entities = db.get_entities_by_tag("war")
        assert len(war_entities) == 1
        assert war_entities[0].name == "King Arthur"


class TestMetaRepositoryIntegration:
    """End-to-end tests for meta/config operations."""

    def test_current_time_round_trip(self, db):
        """Test set/get current time."""
        db.set_current_time(42.5)
        assert db.get_current_time() == 42.5

    def test_timeline_grouping_full_cycle(self, db):
        """Test set → get → clear timeline grouping config."""
        db.set_timeline_grouping_config(["tag1", "tag2"], "FIRST_MATCH")
        config = db.get_timeline_grouping_config()
        assert config["tag_order"] == ["tag1", "tag2"]
        assert config["mode"] == "FIRST_MATCH"

        db.clear_timeline_grouping_config()
        assert db.get_timeline_grouping_config() is None

    def test_graph_lexicon_round_trip(self, db):
        """Test set/get graph lexicon."""
        lexicon = {
            "nodes": {"character": {"color": "#FF0000", "shape": "circle"}},
            "edges": {"involves": {"color": "#00FF00", "width": 2}},
        }
        db.set_graph_lexicon(lexicon)
        result = db.get_graph_lexicon()
        assert result == lexicon

    def test_get_name_resolution(self, seeded_db):
        """Test get_name resolves both events and entities."""
        db, data = seeded_db
        assert db.get_name(data["events"][0].id) == "Battle of Dawn"
        assert db.get_name(data["entities"][0].id) == "King Arthur"
        assert db.get_name("nonexistent") is None


class TestRelationRepositoryIntegration:
    """End-to-end tests for relation operations."""

    def test_relation_update(self, seeded_db):
        """Test update_relation changes target and type."""
        db, data = seeded_db
        relations = db.get_relations(data["events"][0].id)
        assert len(relations) >= 1

        rel = relations[0]
        db.update_relation(
            rel["id"],
            target_id=data["entities"][1].id,
            rel_type="wields",
            attributes={"note": "legendary weapon"},
        )

        updated = db.get_relation(rel["id"])
        assert updated is not None
        assert updated["rel_type"] == "wields"

    def test_get_relation_by_id(self, seeded_db):
        """Test get_relation retrieves by ID."""
        db, data = seeded_db
        relations = db.get_relations(data["events"][0].id)
        rel_id = relations[0]["id"]
        found = db.get_relation(rel_id)
        assert found is not None
        assert found["id"] == rel_id


class TestDIIntegration:
    """Tests that DI works end-to-end with custom repositories."""

    def test_custom_tag_repo(self, db):
        """Test that TagRepository can be injected."""
        from src.services.repositories.tag_repository import TagRepository

        custom_repo = TagRepository()
        service = DatabaseService(":memory:", tag_repo=custom_repo)
        service.connect()

        # Operations should work through the custom repo
        service.create_tag("injected_tag")
        tags = service.get_all_tags()
        assert any(t["name"] == "injected_tag" for t in tags)

    def test_custom_meta_repo(self, db):
        """Test that MetaRepository can be injected."""
        from src.services.repositories.meta_repository import MetaRepository

        custom_repo = MetaRepository()
        service = DatabaseService(":memory:", meta_repo=custom_repo)
        service.connect()

        service.set_current_time(99.0)
        assert service.get_current_time() == 99.0


class TestAppCoordinatorIntegration:
    """Tests for AppCoordinator facade structure."""

    def test_app_coordinator_import(self):
        """Test AppCoordinator can be imported."""
        from src.app.coordinators.app_coordinator import AppCoordinator

        assert AppCoordinator is not None

    def test_app_coordinator_has_all_coordinators(self):
        """Test AppCoordinator exposes all expected coordinator attributes."""
        from src.app.coordinators.app_coordinator import AppCoordinator

        # Verify the class defines __init__ that sets the expected attrs
        expected_attrs = ["data", "time", "editor", "navigation",
                          "backup", "fast_inject", "import_coord"]
        init_code = AppCoordinator.__init__.__code__
        # All expected attrs should be referenced in the init bytecode
        for attr in expected_attrs:
            assert attr in init_code.co_names or attr in str(init_code.co_consts), \
                f"AppCoordinator missing expected attribute: {attr}"
