from src.core.events import Event
from src.core.entities import Entity


def test_event_crud(db_service):
    """Test Create, Read, Update, Delete for Events."""
    # Create
    event = Event(name="Battle of Hastings", lore_date=1066.0)
    event.attributes["weather"] = "foggy"
    db_service.insert_event(event)

    # Read
    fetched = db_service.get_event(event.id)
    assert fetched is not None
    assert fetched.name == "Battle of Hastings"
    assert fetched.lore_date == 1066.0
    assert fetched.attributes["weather"] == "foggy"

    # Update
    event.name = "The Battle of Hastings (Revised)"
    db_service.insert_event(event)  # Should upsert
    fetched_updated = db_service.get_event(event.id)
    assert fetched_updated.name == "The Battle of Hastings (Revised)"

    # Delete
    db_service.delete_event(event.id)
    assert db_service.get_event(event.id) is None


def test_entity_crud(db_service):
    """Test Create, Read for Entities."""
    # Create
    entity = Entity(name="Excalibur", type="artifact")
    entity.description = "A sword."
    db_service.insert_entity(entity)

    # Read
    fetched = db_service.get_entity(entity.id)
    assert fetched is not None
    assert fetched.name == "Excalibur"
    assert fetched.type == "artifact"
    assert fetched.description == "A sword."


def test_get_all_events(db_service):
    """Test fetching all events ordered by date."""
    e1 = Event(name="Future", lore_date=5000.0)
    e2 = Event(name="Ancient Past", lore_date=-1000.0)
    e3 = Event(name="Present", lore_date=2025.0)

    db_service.insert_event(e1)
    db_service.insert_event(e2)
    db_service.insert_event(e3)

    events = db_service.get_all_events()
    assert len(events) == 3
    assert events[0].name == "Ancient Past"
    assert events[1].name == "Present"
    assert events[2].name == "Future"


def test_relation_crud(db_service):
    """Test Create, Read, Update, Delete for Relations."""
    # Setup source/target
    s = Event(name="Source", lore_date=1.0)
    t = Event(name="Target", lore_date=2.0)
    db_service.insert_event(s)
    db_service.insert_event(t)

    # 1. Create
    rel_id = db_service.insert_relation(s.id, t.id, "caused", {"certainty": 0.9})
    assert rel_id is not None
    assert isinstance(rel_id, str)

    # 2. Read (get_relations - list)
    rels = db_service.get_relations(s.id)
    assert len(rels) == 1
    assert rels[0]["id"] == rel_id
    assert rels[0]["target_id"] == t.id
    assert rels[0]["rel_type"] == "caused"
    assert rels[0]["attributes"]["certainty"] == 0.9

    # 3. Read (get_relation - single)
    rel = db_service.get_relation(rel_id)
    assert rel is not None
    assert rel["id"] == rel_id
    assert rel["source_id"] == s.id

    # 4. Update
    new_t = Event(name="New Target", lore_date=3.0)
    db_service.insert_event(new_t)

    db_service.update_relation(rel_id, new_t.id, "prevented", {"certainty": 1.0})

    updated = db_service.get_relation(rel_id)
    assert updated["target_id"] == new_t.id
    assert updated["rel_type"] == "prevented"
    assert updated["attributes"]["certainty"] == 1.0

    # 5. Delete
    db_service.delete_relation(rel_id)
    assert db_service.get_relation(rel_id) is None
    assert len(db_service.get_relations(s.id)) == 0
