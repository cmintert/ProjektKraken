from src.core.events import Event
from src.core.entities import Entity
from src.commands.event_commands import DeleteEventCommand
from src.commands.entity_commands import DeleteEntityCommand


def test_relation_integrity_on_delete_event(db_service):
    """Confirm relations are deleted when an event is deleted."""
    # Setup
    e1 = Event(name="Event 1", lore_date=1.0)
    ent1 = Entity(name="Entity 1", type="Person")
    db_service.insert_event(e1)
    db_service.insert_entity(ent1)

    # Create Outgoing Relation: Event -> Entity
    rel1_id = db_service.insert_relation(e1.id, ent1.id, "related")

    # Create Incoming Relation: Entity -> Event
    rel2_id = db_service.insert_relation(ent1.id, e1.id, "references")

    # Sanity check
    assert db_service.get_relation(rel1_id) is not None
    assert db_service.get_relation(rel2_id) is not None

    # Delete the Event using the command to trigger cascade cleanup
    cmd = DeleteEventCommand(e1.id)
    result = cmd.execute(db_service)
    assert result.success is True

    # Check Integrity
    assert db_service.get_relation(rel1_id) is None
    assert db_service.get_relation(rel2_id) is None

    # Undo
    cmd.undo(db_service)

    # Verify exact restoration
    rel1 = db_service.get_relation(rel1_id)
    rel2 = db_service.get_relation(rel2_id)
    assert rel1 is not None
    assert rel2 is not None
    assert rel1["id"] == rel1_id
    assert rel2["id"] == rel2_id


def test_relation_integrity_on_delete_entity(db_service):
    """Confirm relations are deleted when an entity is deleted."""
    # Setup
    e1 = Event(name="Event 1", lore_date=1.0)
    ent1 = Entity(name="Entity 1", type="Person")
    db_service.insert_event(e1)
    db_service.insert_entity(ent1)

    # Create Outgoing Relation: Entity -> Event
    rel1_id = db_service.insert_relation(ent1.id, e1.id, "related")

    # Create Incoming Relation: Event -> Entity
    rel2_id = db_service.insert_relation(e1.id, ent1.id, "references")

    # Sanity check
    assert db_service.get_relation(rel1_id) is not None
    assert db_service.get_relation(rel2_id) is not None

    # Delete the Entity
    cmd = DeleteEntityCommand(ent1.id)
    result = cmd.execute(db_service)
    assert result.success is True

    # Check Integrity
    assert db_service.get_relation(rel1_id) is None
    assert db_service.get_relation(rel2_id) is None

    # Undo
    cmd.undo(db_service)

    # Verify exact restoration
    rel1 = db_service.get_relation(rel1_id)
    rel2 = db_service.get_relation(rel2_id)
    assert rel1 is not None
    assert rel2 is not None
    assert rel1["id"] == rel1_id
    assert rel2["id"] == rel2_id
