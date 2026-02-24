"""Tests for TagRepository."""


import pytest

from src.services.db_service import DatabaseService


@pytest.fixture
def db():
    """Create an in-memory DatabaseService for testing."""
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def tag_repo(db):
    """Get the tag repository from the database service."""
    return db._tag_repo


class TestTagRepository:
    """Tests for TagRepository methods."""

    def test_create_and_get_all_tags(self, db, tag_repo):
        """Test creating tags and retrieving all."""
        tag_repo.create_tag("warrior")
        tag_repo.create_tag("mage")

        tags = tag_repo.get_all_tags()
        names = [t["name"] for t in tags]
        assert "warrior" in names
        assert "mage" in names

    def test_create_tag_idempotent(self, db, tag_repo):
        """Test that creating the same tag twice returns the same ID."""
        id1 = tag_repo.create_tag("hero")
        id2 = tag_repo.create_tag("hero")
        assert id1 == id2

    def test_delete_tag(self, db, tag_repo):
        """Test deleting a tag."""
        tag_repo.create_tag("temp")
        tags_before = tag_repo.get_all_tags()
        assert any(t["name"] == "temp" for t in tags_before)

        tag_repo.delete_tag("temp")
        tags_after = tag_repo.get_all_tags()
        assert not any(t["name"] == "temp" for t in tags_after)

    def test_get_tag_by_name(self, db, tag_repo):
        """Test retrieving a tag by name."""
        tag_repo.create_tag("unique")
        tag = tag_repo.get_tag_by_name("unique")
        assert tag is not None
        assert tag["name"] == "unique"

    def test_get_tag_by_name_not_found(self, db, tag_repo):
        """Test retrieving non-existent tag returns None."""
        assert tag_repo.get_tag_by_name("nonexistent") is None

    def test_assign_and_get_tags_for_event(self, db, tag_repo):
        """Test assigning tags to events and retrieving them."""
        from src.core.events import Event

        event = Event(name="Battle", type="generic", lore_date=100.0)
        db.insert_event(event)

        tag_repo.create_tag("combat")
        tag_repo.assign_tag_to_event(event.id, "combat")

        tags = tag_repo.get_tags_for_event(event.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "combat"

    def test_assign_and_get_tags_for_entity(self, db, tag_repo):
        """Test assigning tags to entities and retrieving them."""
        from src.core.entities import Entity

        entity = Entity(name="Knight", type="character")
        db.insert_entity(entity)

        tag_repo.create_tag("noble")
        tag_repo.assign_tag_to_entity(entity.id, "noble")

        tags = tag_repo.get_tags_for_entity(entity.id)
        assert len(tags) == 1
        assert tags[0]["name"] == "noble"

    def test_remove_tag_from_event(self, db, tag_repo):
        """Test removing a tag from an event."""
        from src.core.events import Event

        event = Event(name="Siege", type="generic", lore_date=200.0)
        db.insert_event(event)

        tag_repo.create_tag("war")
        tag_repo.assign_tag_to_event(event.id, "war")
        tag_repo.remove_tag_from_event(event.id, "war")

        tags = tag_repo.get_tags_for_event(event.id)
        assert len(tags) == 0

    def test_remove_tag_from_entity(self, db, tag_repo):
        """Test removing a tag from an entity."""
        from src.core.entities import Entity

        entity = Entity(name="Castle", type="location")
        db.insert_entity(entity)

        tag_repo.create_tag("fortification")
        tag_repo.assign_tag_to_entity(entity.id, "fortification")
        tag_repo.remove_tag_from_entity(entity.id, "fortification")

        tags = tag_repo.get_tags_for_entity(entity.id)
        assert len(tags) == 0

    def test_set_and_get_tag_color(self, db, tag_repo):
        """Test setting and getting tag colors."""
        tag_repo.create_tag("fire")
        tag_repo.set_tag_color("fire", "#FF0000")

        color = tag_repo.get_tag_color("fire")
        assert color == "#FF0000"

    def test_get_tag_color_generates_default(self, db, tag_repo):
        """Test that get_tag_color generates a color if none is set."""
        tag_repo.create_tag("water")
        color = tag_repo.get_tag_color("water")
        assert color.startswith("#")
        assert len(color) == 7

    def test_set_tag_color_invalid_format(self, db, tag_repo):
        """Test that invalid color format raises ValueError."""
        tag_repo.create_tag("bad")
        with pytest.raises(ValueError, match="Invalid hex color format"):
            tag_repo.set_tag_color("bad", "not-a-color")

    def test_get_events_by_tag(self, db, tag_repo):
        """Test getting events by tag."""
        from src.core.events import Event

        e1 = Event(name="Dawn", type="generic", lore_date=1.0)
        e2 = Event(name="Dusk", type="generic", lore_date=2.0)
        db.insert_event(e1)
        db.insert_event(e2)

        tag_repo.create_tag("daily")
        tag_repo.assign_tag_to_event(e1.id, "daily")
        tag_repo.assign_tag_to_event(e2.id, "daily")

        events = tag_repo.get_events_by_tag("daily")
        assert len(events) == 2

    def test_get_entities_by_tag(self, db, tag_repo):
        """Test getting entities by tag."""
        from src.core.entities import Entity

        ent1 = Entity(name="Sword", type="item")
        ent2 = Entity(name="Shield", type="item")
        db.insert_entity(ent1)
        db.insert_entity(ent2)

        tag_repo.create_tag("equipment")
        tag_repo.assign_tag_to_entity(ent1.id, "equipment")
        tag_repo.assign_tag_to_entity(ent2.id, "equipment")

        entities = tag_repo.get_entities_by_tag("equipment")
        assert len(entities) == 2

    def test_tag_color_deterministic(self, db, tag_repo):
        """Test that tag color generation is deterministic."""
        tag_repo.create_tag("deterministic")
        color1 = tag_repo.get_tag_color("deterministic")
        color2 = tag_repo.get_tag_color("deterministic")
        assert color1 == color2
        assert color1.startswith("#")

    def test_delegation_from_db_service(self, db):
        """Test that DatabaseService delegates to TagRepository."""
        db.create_tag("delegate_test")
        tags = db.get_all_tags()
        assert any(t["name"] == "delegate_test" for t in tags)


class TestMetaRepository:
    """Tests for MetaRepository via DatabaseService delegation."""

    def test_set_and_get_current_time(self, db):
        """Test setting and getting current time."""
        db.set_current_time(42.5)
        assert db.get_current_time() == 42.5

    def test_get_current_time_default(self, db):
        """Test get_current_time returns None when not set."""
        assert db.get_current_time() is None

    def test_timeline_grouping_config(self, db):
        """Test set/get/clear timeline grouping config."""
        db.set_timeline_grouping_config(["tag1", "tag2"], "DUPLICATE")
        config = db.get_timeline_grouping_config()
        assert config is not None
        assert config["tag_order"] == ["tag1", "tag2"]
        assert config["mode"] == "DUPLICATE"

        db.clear_timeline_grouping_config()
        assert db.get_timeline_grouping_config() is None

    def test_timeline_grouping_invalid_mode(self, db):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            db.set_timeline_grouping_config(["tag1"], "INVALID")

    def test_graph_lexicon(self, db):
        """Test set/get graph lexicon."""
        lexicon = {"nodes": {"character": {"color": "#FF0000"}}}
        db.set_graph_lexicon(lexicon)
        result = db.get_graph_lexicon()
        assert result == lexicon

    def test_get_name(self, db):
        """Test get_name resolves events and entities."""
        from src.core.entities import Entity
        from src.core.events import Event

        event = Event(name="TestEvent", type="generic", lore_date=1.0)
        entity = Entity(name="TestEntity", type="character")
        db.insert_event(event)
        db.insert_entity(entity)

        assert db.get_name(event.id) == "TestEvent"
        assert db.get_name(entity.id) == "TestEntity"
        assert db.get_name("nonexistent") is None
