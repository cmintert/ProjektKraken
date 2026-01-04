"""Tests for Relation attributes and CRUD operations.

Tests the full lifecycle of relation attributes including:
- Creating relations with attributes
- Reading and deserializing attributes
- Updating attributes
- Round-trip serialization
- Default behavior (empty dict)
"""

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.relations import Relation
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """Create an in-memory database for testing."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_relation_dataclass_creation():
    """Test creating a Relation dataclass with attributes."""
    rel = Relation(
        source_id="src-123",
        target_id="tgt-456",
        rel_type="caused",
        attributes={"weight": 0.8, "confidence": 0.9},
    )

    assert rel.source_id == "src-123"
    assert rel.target_id == "tgt-456"
    assert rel.rel_type == "caused"
    assert rel.attributes == {"weight": 0.8, "confidence": 0.9}
    assert rel.id is not None
    assert rel.created_at > 0


def test_relation_dataclass_default_attributes():
    """Test that Relation defaults to empty dict for attributes."""
    rel = Relation(source_id="src-123", target_id="tgt-456", rel_type="involved")

    assert rel.attributes == {}


def test_relation_to_dict():
    """Test Relation.to_dict() serialization."""
    rel = Relation(
        source_id="src-123",
        target_id="tgt-456",
        rel_type="located_in",
        attributes={"start_date": 100.0, "end_date": 200.0},
    )

    data = rel.to_dict()

    assert data["source_id"] == "src-123"
    assert data["target_id"] == "tgt-456"
    assert data["rel_type"] == "located_in"
    assert data["attributes"]["start_date"] == 100.0
    assert data["attributes"]["end_date"] == 200.0
    assert "id" in data
    assert "created_at" in data


def test_relation_from_dict():
    """Test Relation.from_dict() deserialization."""
    data = {
        "id": "rel-789",
        "source_id": "src-123",
        "target_id": "tgt-456",
        "rel_type": "involved",
        "attributes": {"weight": 0.5},
        "created_at": 1234567890.0,
    }

    rel = Relation.from_dict(data)

    assert rel.id == "rel-789"
    assert rel.source_id == "src-123"
    assert rel.target_id == "tgt-456"
    assert rel.rel_type == "involved"
    assert rel.attributes == {"weight": 0.5}
    assert rel.created_at == 1234567890.0


def test_relation_from_dict_null_attributes():
    """Test Relation.from_dict() handles None attributes."""
    data = {
        "id": "rel-789",
        "source_id": "src-123",
        "target_id": "tgt-456",
        "rel_type": "involved",
        "attributes": None,
        "created_at": 1234567890.0,
    }

    rel = Relation.from_dict(data)

    assert rel.attributes == {}


def test_relation_weight_property():
    """Test weight property accessor."""
    rel = Relation(source_id="src-123", target_id="tgt-456", rel_type="allied_with")

    # Default weight
    assert rel.weight == 1.0

    # Set weight
    rel.weight = 0.75
    assert rel.weight == 0.75
    assert rel.attributes["weight"] == 0.75


def test_relation_confidence_property():
    """Test confidence property accessor."""
    rel = Relation(source_id="src-123", target_id="tgt-456", rel_type="caused")

    # Default confidence
    assert rel.confidence == 1.0

    # Set confidence
    rel.confidence = 0.6
    assert rel.confidence == 0.6
    assert rel.attributes["confidence"] == 0.6


def test_create_relation_with_attributes(db_service):
    """Test creating a relation with attributes and reading it back."""
    # Create test objects
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Create relation with attributes
    attributes = {
        "weight": 0.8,
        "confidence": 0.9,
        "start_date": 150.0,
        "source": "Historical records",
    }
    rel_id = db_service.insert_relation(e1.id, e2.id, "caused", attributes)

    # Read it back
    rel = db_service.get_relation(rel_id)

    assert rel is not None
    assert rel["source_id"] == e1.id
    assert rel["target_id"] == e2.id
    assert rel["rel_type"] == "caused"
    assert isinstance(rel["attributes"], dict)
    assert rel["attributes"]["weight"] == 0.8
    assert rel["attributes"]["confidence"] == 0.9
    assert rel["attributes"]["start_date"] == 150.0
    assert rel["attributes"]["source"] == "Historical records"


def test_create_relation_without_attributes(db_service):
    """Test creating a relation without attributes defaults to empty dict."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Create relation without attributes
    rel_id = db_service.insert_relation(e1.id, e2.id, "involved")

    # Read it back
    rel = db_service.get_relation(rel_id)

    assert rel is not None
    assert isinstance(rel["attributes"], dict)
    assert rel["attributes"] == {}


def test_update_relation_attributes(db_service):
    """Test updating relation attributes."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Create relation with initial attributes
    rel_id = db_service.insert_relation(e1.id, e2.id, "caused", {"weight": 0.5})

    # Update with new attributes
    new_attributes = {"weight": 0.9, "confidence": 0.8, "notes": "Updated information"}
    db_service.update_relation(rel_id, e2.id, "caused", new_attributes)

    # Verify update
    rel = db_service.get_relation(rel_id)
    assert rel["attributes"]["weight"] == 0.9
    assert rel["attributes"]["confidence"] == 0.8
    assert rel["attributes"]["notes"] == "Updated information"


def test_relation_attributes_round_trip(db_service):
    """Test that complex attributes survive round-trip through database."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Complex nested attributes
    attributes = {
        "weight": 0.75,
        "dates": {"start": 100.0, "end": 200.0},
        "tags": ["important", "verified"],
        "metadata": {"source": "Primary document", "page": 42},
    }

    rel_id = db_service.insert_relation(e1.id, e2.id, "related", attributes)
    rel = db_service.get_relation(rel_id)

    # Verify exact match
    assert rel["attributes"] == attributes
    assert rel["attributes"]["weight"] == 0.75
    assert rel["attributes"]["dates"]["start"] == 100.0
    assert rel["attributes"]["tags"] == ["important", "verified"]
    assert rel["attributes"]["metadata"]["page"] == 42


def test_relations_with_entities(db_service):
    """Test relations between entities with attributes."""
    ent1 = Entity(name="Character A", type="character")
    ent2 = Entity(name="Location B", type="location")
    db_service.insert_entity(ent1)
    db_service.insert_entity(ent2)

    # Create relation with attributes
    attributes = {"relationship": "home", "start_date": 50.0, "confidence": 0.95}
    rel_id = db_service.insert_relation(ent1.id, ent2.id, "located_in", attributes)

    # Verify
    rel = db_service.get_relation(rel_id)
    assert rel["source_id"] == ent1.id
    assert rel["target_id"] == ent2.id
    assert rel["attributes"]["relationship"] == "home"
    assert rel["attributes"]["confidence"] == 0.95


def test_get_relations_with_attributes(db_service):
    """Test that get_relations returns attributes correctly."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    e3 = Event(name="Event C", lore_date=300.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)
    db_service.insert_event(e3)

    # Create multiple relations with different attributes
    db_service.insert_relation(e1.id, e2.id, "caused", {"weight": 0.9})
    db_service.insert_relation(e1.id, e3.id, "preceded", {"weight": 0.5})

    # Get all outgoing relations
    relations = db_service.get_relations(e1.id)

    assert len(relations) == 2
    for rel in relations:
        assert isinstance(rel["attributes"], dict)
        assert "weight" in rel["attributes"]


def test_incoming_relations_with_attributes(db_service):
    """Test that get_incoming_relations returns attributes correctly."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Create relation
    db_service.insert_relation(
        e1.id, e2.id, "caused", {"weight": 0.8, "confidence": 0.7}
    )

    # Get incoming relations for e2
    relations = db_service.get_incoming_relations(e2.id)

    assert len(relations) == 1
    assert relations[0]["attributes"]["weight"] == 0.8
    assert relations[0]["attributes"]["confidence"] == 0.7


def test_multiple_relations_same_pair_different_attributes(db_service):
    """Test multi-edges: multiple relations between same source/target."""
    e1 = Event(name="Event A", lore_date=100.0)
    e2 = Event(name="Event B", lore_date=200.0)
    db_service.insert_event(e1)
    db_service.insert_event(e2)

    # Create multiple relations between same pair
    rel1_id = db_service.insert_relation(e1.id, e2.id, "caused", {"confidence": 0.9})
    rel2_id = db_service.insert_relation(
        e1.id, e2.id, "influenced", {"confidence": 0.6}
    )

    # Verify both exist with different attributes
    rel1 = db_service.get_relation(rel1_id)
    rel2 = db_service.get_relation(rel2_id)

    assert rel1["rel_type"] == "caused"
    assert rel1["attributes"]["confidence"] == 0.9

    assert rel2["rel_type"] == "influenced"
    assert rel2["attributes"]["confidence"] == 0.6

    # Verify get_relations returns both
    relations = db_service.get_relations(e1.id)
    assert len(relations) == 2
