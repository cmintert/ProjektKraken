import time
import uuid

import pytest

from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.core.events import Event
from src.services.db_service import DatabaseService

pytestmark = pytest.mark.ci_fast


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
    cmd = AddRelationCommand(s.id, t.id, "test_rel")
    result = cmd.execute(db_service)
    assert result.success is True

    rels = db_service.get_relations(s.id)
    assert len(rels) == 1
    rel_id = rels[0]["id"]

    # Undo
    cmd.undo(db_service)
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
    cmd = RemoveRelationCommand(rel_id)
    result = cmd.execute(db_service)
    assert result.success is True

    assert db_service.get_relation(rel_id) is None

    # Undo (Placeholder check)
    cmd.undo(db_service)
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
    cmd = UpdateRelationCommand(rel_id, t2.id, "updated")
    result = cmd.execute(db_service)
    assert result.success is True

    updated = db_service.get_relation(rel_id)
    assert updated["target_id"] == t2.id
    assert updated["rel_type"] == "updated"

    # Undo
    cmd.undo(db_service)
    reverted = db_service.get_relation(rel_id)
    assert reverted["target_id"] == t.id
    assert reverted["rel_type"] == "initial"


def test_add_relation_bidirectional(db_service):
    """Fresh creation fails and legacy replay retains both saved identities."""
    s = Event(name="S", lore_date=1)
    t = Event(name="T", lore_date=2)
    db_service.insert_event(s)
    db_service.insert_event(t)

    # Execute
    cmd = AddRelationCommand(s.id, t.id, "mutual_link", bidirectional=True)
    assert not cmd.execute(db_service).success
    assert not db_service.get_all_relations()
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    cmd = AddRelationCommand.from_dict({**cmd.to_dict(), "created_rel_ids": ids})
    result = cmd.execute(db_service)
    assert result.success
    assert result.data["relation_ids"] == ids

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
    cmd.undo(db_service)
    assert len(db_service.get_relations(s.id)) == 0
    assert len(db_service.get_relations(t.id)) == 0
    assert cmd.execute(db_service).data["relation_ids"] == ids


@pytest.mark.parametrize("kind", ["knows", "sibling_of"])
def test_one_assertion_is_visible_from_both_endpoints(db_service, kind):
    source, target = (
        Event(name="Source", lore_date=1),
        Event(name="Target", lore_date=2),
    )
    db_service.insert_event(source)
    db_service.insert_event(target)
    command = AddRelationCommand(source.id, target.id, kind)
    result = command.execute(db_service)
    assert result.success
    relation_id = result.data["relation_id"]
    for item in (source, target):
        assert [row["id"] for row in db_service.get_relations_for_item(item.id)] == [
            relation_id
        ]
    reverse = AddRelationCommand(target.id, source.id, "trusts", {"notes": "Separate"})
    assert reverse.execute(db_service).success
    assert len(db_service.get_relations_for_item(source.id)) == 2
    reverse.undo(db_service)
    assert db_service.get_relation(relation_id)["rel_type"] == kind


@pytest.mark.parametrize(
    ("saved_attributes", "proposed_attributes", "reverse", "expected_error"),
    [
        ({"valid_from_event": True}, {}, True, "source"),
        ({}, {"temporal": {"at": {"binding": "source_event"}}}, True, "source"),
        ({"payload": {"attributes": {"rank": "Captain"}}}, {}, False, "endpoints"),
    ],
)
def test_endpoint_change_protects_saved_and_proposed_semantics(
    db_service, saved_attributes, proposed_attributes, reverse, expected_error
):
    source, target, other = [
        Event(name=name, lore_date=date)
        for date, name in enumerate(("Source", "Target", "Other"))
    ]
    for event in (source, target, other):
        db_service.insert_event(event)
    relation_id = db_service.insert_relation(
        source.id, target.id, "related", saved_attributes
    )
    before = db_service.get_relation(relation_id)
    command = UpdateRelationCommand(
        relation_id,
        source.id if reverse else other.id,
        "related",
        proposed_attributes,
        source_id=target.id if reverse else None,
    )
    result = command.execute(db_service)
    assert not result.success
    assert expected_error in result.message
    assert db_service.get_relation(relation_id) == before


def test_endpoint_change_preserves_absolute_timing(db_service):
    source = Event(name="Source", lore_date=1)
    target = Event(name="Target", lore_date=2)
    db_service.insert_event(source)
    db_service.insert_event(target)
    attributes = {
        "notes": "Original note",
        "temporal": {
            "schema": 1,
            "behavior": "stateful",
            "start": {"exact": 5.0},
            "end": {"status": "open"},
        },
    }
    relation_id = db_service.insert_relation(source.id, target.id, "knows", attributes)
    command = UpdateRelationCommand(
        relation_id, source.id, "knows", attributes, source_id=target.id
    )
    assert command.execute(db_service).success
    saved = db_service.get_relation(relation_id)
    assert (saved["source_id"], saved["target_id"]) == (target.id, source.id)
    assert saved["attributes"] == attributes


def test_legacy_endpoint_change_replays_against_recorded_snapshot(db_service):
    source = Event(name="Source", lore_date=1)
    target = Event(name="Target", lore_date=2)
    db_service.insert_event(source)
    db_service.insert_event(target)
    attributes = {"valid_at_event": True}
    relation_id = db_service.insert_relation(source.id, target.id, "caused", attributes)
    before = db_service.get_relation(relation_id)
    command = UpdateRelationCommand(
        relation_id, source.id, "caused", attributes, source_id=target.id
    )
    assert not command.execute(db_service).success
    restored = UpdateRelationCommand.from_dict(
        {**command.to_dict(), "previous_state": before}
    )
    assert restored.execute(db_service).success
    assert db_service.get_relation(relation_id)["source_id"] == target.id
    restored.undo(db_service)
    assert db_service.get_relation(relation_id) == before


def test_manual_commands_cannot_mutate_system_mentions(db_service):
    source = Event(name="Source", lore_date=1)
    target = Event(name="Target", lore_date=2)
    db_service.insert_event(source)
    db_service.insert_event(target)

    add_result = AddRelationCommand(
        source.id,
        target.id,
        "mentions",
    ).execute(db_service)
    assert add_result.success is False

    normal_id = db_service.insert_relation(
        source.id,
        target.id,
        "related",
    )
    update_result = UpdateRelationCommand(
        normal_id,
        target.id,
        "mentions",
    ).execute(db_service)
    assert update_result.success is False

    mention_id = str(uuid.uuid4())
    db_service._relation_repo.insert(
        mention_id,
        source.id,
        target.id,
        "mentions",
        {
            "is_auto_generated": True,
            "generator": "wikilink",
            "occurrences": [],
        },
        time.time(),
    )
    remove_result = RemoveRelationCommand(mention_id).execute(db_service)
    assert remove_result.success is False
    assert db_service.get_relation(mention_id) is not None
