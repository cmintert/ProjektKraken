import pytest
from src.services.db_service import DatabaseService
from src.core.events import Event
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_add_relation_command(db_service):
    """Test Execute and Undo for adding a relation."""
    s = Event(name="S", lore_date=1)
    t = Event(name="T", lore_date=2)
    db_service.insert_event(s)
    db_service.insert_event(t)

    # Execute
    cmd = AddRelationCommand(db_service, s.id, t.id, "test_rel")
    assert cmd.execute() is True

    rels = db_service.get_relations(s.id)
    assert len(rels) == 1
    rel_id = rels[0]["id"]

    # Undo
    cmd.undo()
    assert len(db_service.get_relations(s.id)) == 0
    assert db_service.get_relation(rel_id) is None


def test_remove_relation_command(db_service):
    """Test Execute (Undo not fully implemented yet) for removing."""
    s = Event(name="S", lore_date=1)
    t = Event(name="T", lore_date=2)
    db_service.insert_event(s)
    db_service.insert_event(t)
    rel_id = db_service.insert_relation(s.id, t.id, "test_rel")

    # Execute
    cmd = RemoveRelationCommand(db_service, rel_id)
    assert cmd.execute() is True

    assert db_service.get_relation(rel_id) is None

    # Undo (Placeholder check)
    cmd.undo()
    # Currently Undo doesn't restore (Placeholder).
    # We just verify it doesn't crash.


def test_update_relation_command(db_service):
    """Test Execute and Undo for updating a relation."""
    s = Event(name="S", lore_date=1)
    t = Event(name="T", lore_date=2)
    t2 = Event(name="T2", lore_date=3)
    db_service.insert_event(s)
    db_service.insert_event(t)
    db_service.insert_event(t2)

    rel_id = db_service.insert_relation(s.id, t.id, "initial")

    # Execute Update
    cmd = UpdateRelationCommand(db_service, rel_id, t2.id, "updated")
    assert cmd.execute() is True

    updated = db_service.get_relation(rel_id)
    assert updated["target_id"] == t2.id
    assert updated["rel_type"] == "updated"

    # Undo
    cmd.undo()
    reverted = db_service.get_relation(rel_id)
    assert reverted["target_id"] == t.id
    assert reverted["rel_type"] == "initial"


def test_add_relation_bidirectional(db_service):
    """Test creating a bidirectional relation (A->B and B->A)."""
    s = Event(name="S", lore_date=1)
    t = Event(name="T", lore_date=2)
    db_service.insert_event(s)
    db_service.insert_event(t)

    # Execute
    cmd = AddRelationCommand(db_service, s.id, t.id, "mutual_link", bidirectional=True)
    assert cmd.execute() is True

    # Verify Forward
    rels_s = db_service.get_relations(s.id)
    assert len(rels_s) == 1
    assert rels_s[0]["target_id"] == t.id
    assert rels_s[0]["rel_type"] == "mutual_link"

    # Verify Reverse
    rels_t = db_service.get_relations(t.id)
    assert len(rels_t) == 1
    assert rels_t[0]["target_id"] == s.id
    assert rels_t[0]["rel_type"] == "mutual_link"

    # Undo
    cmd.undo()
    assert len(db_service.get_relations(s.id)) == 0
    assert len(db_service.get_relations(t.id)) == 0
