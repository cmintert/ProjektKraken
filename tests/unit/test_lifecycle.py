"""Regression coverage for historical associations and derived living evidence."""

import pytest

from src.commands.event_commands import CreateEventCommand
from src.commands.lifecycle_command import (
    ChangeLifecycleAssociationCommand,
    CreateLifecycleEventCommand,
)
from src.commands.relation_commands import AddRelationCommand
from src.core.calendar import CalendarConfig, CalendarConverter, CalendarDate
from src.core.entities import Entity
from src.core.events import Event
from src.core.lifecycle import LivingClaim, resolve_living_status
from src.core.temporal_manager import TemporalManager
from src.gui.dialogs.lifecycle_event_dialog import LifecycleEventDialog


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        (0, "indeterminate"),
        (1, "alive"),
        (4, "alive"),
        (5, "indeterminate"),
        (8, "dead"),
        (10, "alive"),
        (11, "indeterminate"),
    ],
)
def test_living_status_uses_claim_bounds(time, expected):
    claims = [
        LivingClaim("birth", "e1", "birth", 1, 1),
        LivingClaim("death", "e2", "death", 5, 7),
        LivingClaim("revival", "e3", "revival", 10, 10),
    ]
    assert resolve_living_status(claims, time).value == expected


def test_lifecycle_creation_rolls_back_if_link_fails(db_service, monkeypatch):
    entity = Entity(name="Ada", type="character")
    db_service.insert_entity(entity)
    event = CreateEventCommand({"name": "Birth of Ada", "lore_date": None})
    relation = AddRelationCommand(event.event.id, entity.id, "birth")
    command = CreateLifecycleEventCommand([event, relation], "Record birth")

    def fail(_db_service):
        raise RuntimeError("relation write failed")

    monkeypatch.setattr(relation, "execute", fail)
    result = command.execute(db_service)
    assert not result.success
    assert db_service.get_event(event.event.id) is None


def test_lifecycle_form_preserves_year_precision(qtbot):
    dialog = LifecycleEventDialog(
        "Birth of Ada", CalendarConverter(CalendarConfig.create_default()), None
    )
    qtbot.addWidget(dialog)
    dialog.accept()
    assert not dialog.result()
    qtbot.keyClicks(dialog.date.txt_date, "962")
    dialog.accept()
    assert dialog.result()
    expression = dialog.event_data["attributes"]["_temporal_v2"]["expression"]
    assert expression["precision"] == "year"


def test_historical_snapshot_keeps_legacy_year_claim_qualified(db_service):
    config = CalendarConfig.create_default()
    db_service.insert_calendar_config(config)
    db_service.set_active_calendar_config(config.id)
    character = Entity(name="Ada", type="character")
    witness = Entity(name="Witness", type="character")
    db_service.insert_entity(character)
    db_service.insert_entity(witness)
    db_service.insert_relation(witness.id, character.id, "birth", {"date": "962"})
    start = CalendarConverter(config).to_float(CalendarDate(962, 1, 1))
    status = TemporalManager(db_service).get_entity_state_at(character.id, start)
    assert status.to_dict()["living_status"]["value"] == "indeterminate"


def test_failed_creation_undo_preserves_relation_and_can_retry(db_service, monkeypatch):
    entity = Entity(name="Ada", type="character")
    db_service.insert_entity(entity)
    event = CreateEventCommand({"name": "Birth of Ada", "lore_date": None})
    relation = AddRelationCommand(event.event.id, entity.id, "birth")
    command = CreateLifecycleEventCommand([event, relation], "Record birth")
    assert command.execute(db_service).success
    original = db_service.get_incoming_relations(entity.id)[0]

    def fail(_event_id):
        raise RuntimeError("Event delete failed")

    with monkeypatch.context() as patch:
        patch.setattr(db_service, "delete_event", fail)
        with pytest.raises(RuntimeError, match="Event delete failed"):
            command.undo(db_service)
    assert db_service.get_incoming_relations(entity.id) == [original]
    command.undo(db_service)
    assert db_service.get_event(event.event.id) is None
    assert command.execute(db_service).success
    assert db_service.get_incoming_relations(entity.id)[0]["id"] == original["id"]


def test_reassociate_and_unlink_preserve_event_and_relation_identity(db_service):
    entity = Entity(name="Ada", type="character")
    first = Event(name="First source", lore_date=1)
    second = Event(name="Second source", lore_date=None)
    db_service.insert_entity(entity)
    db_service.insert_event(first)
    db_service.insert_event(second)
    intent = {"entity_id": entity.id, "key": "birth", "event_id": first.id}
    link = ChangeLifecycleAssociationCommand(intent)
    assert link.execute(db_service).success
    assert not ChangeLifecycleAssociationCommand(intent).execute(db_service).success
    original = db_service.get_relation(link.relation_id)
    update = ChangeLifecycleAssociationCommand(
        {
            **intent,
            "relation_id": link.relation_id,
            "expected": original,
            "event_id": second.id,
        }
    )
    assert update.execute(db_service).success
    changed = db_service.get_relation(link.relation_id)
    assert changed["source_id"] == second.id
    unlink = ChangeLifecycleAssociationCommand(
        {
            **intent,
            "relation_id": link.relation_id,
            "expected": changed,
            "event_id": None,
        }
    )
    assert unlink.execute(db_service).success
    assert db_service.get_event(second.id) == second
    unlink.undo(db_service)
    assert db_service.get_relation(link.relation_id) == changed
    update.undo(db_service)
    assert db_service.get_relation(link.relation_id) == original


@pytest.mark.parametrize("entity_is_source", [True, False])
def test_reassociate_preserves_direction_through_undo_redo(
    db_service, entity_is_source
):
    entity = Entity(name="Ada", type="character")
    first = Event(name="First event", lore_date=1)
    second = Event(name="Second event", lore_date=2)
    db_service.insert_entity(entity)
    db_service.insert_event(first)
    db_service.insert_event(second)
    source_id, target_id = (
        (entity.id, first.id) if entity_is_source else (first.id, entity.id)
    )
    relation_id = db_service.insert_relation(
        source_id, target_id, "involved", {"note": "Authored association"}
    )
    original = db_service.get_relation(relation_id)
    command = ChangeLifecycleAssociationCommand(
        {
            "entity_id": entity.id,
            "event_id": second.id,
            "key": "involved",
            "relation_id": relation_id,
            "expected": original,
        }
    )
    expected = {
        **original,
        "source_id": entity.id if entity_is_source else second.id,
        "target_id": second.id if entity_is_source else entity.id,
    }

    assert command.execute(db_service).success
    assert db_service.get_relation(relation_id) == expected
    assert command.undo(db_service).success
    assert db_service.get_relation(relation_id) == original
    assert command.execute(db_service).success
    assert db_service.get_relation(relation_id) == expected
    assert db_service.get_event(first.id) == first
    assert db_service.get_event(second.id) == second


def test_link_detects_existing_legacy_event_reference(db_service):
    entity = Entity(name="Ada", type="character")
    witness = Entity(name="Witness", type="character")
    event = Event(name="Birth record", lore_date=None)
    db_service.insert_entity(entity)
    db_service.insert_entity(witness)
    db_service.insert_event(event)
    db_service.insert_relation(witness.id, entity.id, "birth", {"event_id": event.id})
    duplicate = ChangeLifecycleAssociationCommand(
        {"entity_id": entity.id, "key": "birth", "event_id": event.id}
    )
    assert not duplicate.execute(db_service).success
    assert len(db_service.get_incoming_relations(entity.id)) == 1
