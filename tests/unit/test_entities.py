"""
Unit tests for Entity dataclass and DatabaseService entity operations.
"""

import pytest
import sqlite3
from src.core.entities import Entity
from src.services.db_service import DatabaseService


@pytest.fixture
def db():
    """Returns an in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_entity_serialization():
    """Test Entity to_dict and from_dict."""
    entity = Entity(
        name="Gandalf",
        type="Character",
        description="A wizard",
        attributes={"level": 20, "items": ["Staff"]},
    )

    data = entity.to_dict()
    assert data["name"] == "Gandalf"
    assert data["type"] == "Character"
    assert data["attributes"]["level"] == 20

    recreated = Entity.from_dict(data)
    assert recreated.id == entity.id
    assert recreated.name == entity.name
    assert recreated.attributes == entity.attributes


def test_insert_and_get_entity(db):
    """Test inserting and retrieving an entity."""
    entity = Entity(name="Rivendell", type="Location")

    db.insert_entity(entity)

    retrieved = db.get_entity(entity.id)
    assert retrieved is not None
    assert retrieved.name == "Rivendell"
    assert retrieved.type == "Location"


def test_get_all_entities(db):
    """Test retrieving all entities."""
    e1 = Entity(name="E1", type="Type1")
    e2 = Entity(name="E2", type="Type2")

    db.insert_entity(e1)
    db.insert_entity(e2)

    all_entities = db.get_all_entities()
    assert len(all_entities) == 2
    # Order isn't guaranteed by default unless sorted, but let's check content
    ids = [e.id for e in all_entities]
    assert e1.id in ids
    assert e2.id in ids


def test_delete_entity(db):
    """Test deleting an entity."""
    entity = Entity(name="To Delete", type="Temp")
    db.insert_entity(entity)

    assert db.get_entity(entity.id) is not None

    db.delete_entity(entity.id)

    assert db.get_entity(entity.id) is None


def test_update_entity_via_insert(db):
    """Test updating an entity using upsert behavior."""
    entity = Entity(name="Original", type="Type")
    db.insert_entity(entity)

    entity.name = "Updated"
    db.insert_entity(entity)

    retrieved = db.get_entity(entity.id)
    assert retrieved.name == "Updated"
