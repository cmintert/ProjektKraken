"""Source-aware entity edits use the visible field owner, not world current time."""

from src.commands.temporal_entity_edit_command import TemporalEntityEditCommand
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_resolver import TemporalResolver


def _state(db_service, entity_id, lore_time):
    return TemporalResolver().resolve_entity_state(
        db_service.get_entity(entity_id),
        db_service.get_incoming_relations(entity_id),
        lore_time,
    ).to_dict()


def _world(db_service):
    entity = Entity(
        name="Harbor",
        type="Location",
        description="An old port",
        attributes={"owner": "Guild", "_tags": ["coast"]},
    )
    event = Event(name="Occupation", lore_date=10.0)
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    relation_id = db_service.insert_relation(
        event.id,
        entity.id,
        "involved",
        {
            "valid_from_event": True,
            "payload": {
                "description": "A fortified port",
                "attributes": {"owner": "Army", "size": 4},
            },
            "note": "leave untouched",
        },
    )
    return entity, event, relation_id


def test_provenance_identifies_each_winning_field(db_service):
    entity, event, relation_id = _world(db_service)
    before = _state(db_service, entity.id, 5.0)
    after = _state(db_service, entity.id, 15.0)
    assert before["description_source"] == {"kind": "baseline"}
    assert after["description_source"]["relation_id"] == relation_id
    assert after["description_source"]["event_id"] == event.id
    assert after["attribute_sources"]["owner"]["relation_id"] == relation_id
    assert after["attribute_sources"]["_tags"] == {"kind": "baseline"}


def test_mixed_source_correction_preserves_unrelated_data_and_undo(db_service):
    entity, _event, relation_id = _world(db_service)
    command = TemporalEntityEditCommand(
        entity.id,
        15.0,
        _state(db_service, entity.id, 15.0),
        [
            {"field": "description", "action": "set", "value": "A guarded port"},
            {"field": "attribute", "key": "owner", "action": "set", "value": "Navy"},
            {
                "field": "attribute",
                "key": "new_base",
                "action": "set",
                "value": "Permanent",
                "scope": "baseline",
            },
        ],
    )
    assert command.execute(db_service).success
    assert db_service.get_entity(entity.id).description == "An old port"
    assert db_service.get_entity(entity.id).attributes == {
        "owner": "Guild",
        "_tags": ["coast"],
        "new_base": "Permanent",
    }
    relation = db_service.get_relation(relation_id)
    assert relation["attributes"]["payload"] == {
        "description": "A guarded port",
        "attributes": {"owner": "Navy", "size": 4},
        "unset_attributes": [],
    }
    assert relation["attributes"]["note"] == "leave untouched"
    assert _state(db_service, entity.id, 15.0)["description"] == "A guarded port"
    command.undo(db_service)
    assert _state(db_service, entity.id, 15.0)["description"] == "A fortified port"
    assert db_service.get_entity(entity.id).attributes.get("new_base") is None
    assert command.execute(db_service).success


def test_conflict_rejects_changed_owner_and_keeps_records(db_service):
    entity, event, _relation_id = _world(db_service)
    expected = _state(db_service, entity.id, 15.0)
    db_service.insert_relation(
        event.id,
        entity.id,
        "involved",
        {
            "valid_from_event": True,
            "priority": "manual",
            "payload": {"description": "Another writer"},
        },
    )
    command = TemporalEntityEditCommand(
        entity.id,
        15.0,
        expected,
        [{"field": "description", "action": "set", "value": "Draft"}],
    )
    result = command.execute(db_service)
    assert not result.success
    assert _state(db_service, entity.id, 15.0)["description"] == "Another writer"


def test_dated_change_and_removal_meanings(db_service):
    entity, event, relation_id = _world(db_service)
    existing = _state(db_service, entity.id, 15.0)
    remove_override = TemporalEntityEditCommand(
        entity.id,
        15.0,
        existing,
        [{"field": "attribute", "key": "owner", "action": "remove_override"}],
    )
    assert remove_override.execute(db_service).success
    assert _state(db_service, entity.id, 15.0)["attributes"]["owner"] == "Guild"
    remove_override.undo(db_service)
    assert db_service.get_relation(relation_id)["attributes"]["payload"][
        "attributes"
    ]["owner"] == "Army"
    absent = TemporalEntityEditCommand(
        entity.id,
        15.0,
        _state(db_service, entity.id, 15.0),
        [{"field": "attribute", "key": "owner", "action": "unset"}],
    )
    assert absent.execute(db_service).success
    assert "owner" not in _state(db_service, entity.id, 15.0)["attributes"]
    assert _state(db_service, entity.id, 15.0)["absent_attribute_sources"][
        "owner"
    ]["relation_id"] == relation_id
    dated = TemporalEntityEditCommand(
        entity.id,
        15.0,
        _state(db_service, entity.id, 15.0),
        [
            {
                "field": "description",
                "action": "set",
                "value": "A new chapter",
                "scope": "dated",
                "event_name": "Rebuilding",
            }
        ],
    )
    assert dated.execute(db_service).success
    assert _state(db_service, entity.id, 15.0)["description"] == "A new chapter"
    assert _state(db_service, entity.id, 9.0)["description"] == "An old port"
    assert db_service.get_event(event.id).name == "Occupation"


def test_empty_description_and_expired_owner_return_to_baseline(db_service):
    entity, event, relation_id = _world(db_service)
    relation = db_service.get_relation(relation_id)
    attrs = relation["attributes"]
    attrs["valid_to"] = 20.0
    db_service.update_relation(relation_id, entity.id, "involved", attrs)
    assert _state(db_service, entity.id, 20.0)["description_source"] == {
        "kind": "baseline"
    }
    command = TemporalEntityEditCommand(
        entity.id,
        15.0,
        _state(db_service, entity.id, 15.0),
        [{"field": "description", "action": "set", "value": ""}],
    )
    assert command.execute(db_service).success
    assert _state(db_service, entity.id, 15.0)["description"] == ""
    assert _state(db_service, entity.id, 20.0)["description"] == "An old port"
    assert db_service.get_event(event.id).name == "Occupation"


def test_dated_attribute_uses_existing_event_and_undo_removes_relation(db_service):
    entity, event, _relation_id = _world(db_service)
    before_relations = len(db_service.get_incoming_relations(entity.id))
    command = TemporalEntityEditCommand(
        entity.id,
        10.0,
        _state(db_service, entity.id, 10.0),
        [
            {
                "field": "attribute",
                "key": "mood",
                "action": "set",
                "value": "Uneasy",
                "scope": "dated",
                "event_id": event.id,
            }
        ],
    )
    assert command.execute(db_service).success
    assert len(db_service.get_incoming_relations(entity.id)) == before_relations + 1
    assert _state(db_service, entity.id, 10.0)["attributes"]["mood"] == "Uneasy"
    command.undo(db_service)
    assert len(db_service.get_incoming_relations(entity.id)) == before_relations
    assert "mood" not in _state(db_service, entity.id, 10.0)["attributes"]


def test_baseline_metadata_and_hidden_attributes_are_preserved(db_service):
    entity, _event, _relation_id = _world(db_service)
    command = TemporalEntityEditCommand(
        entity.id,
        15.0,
        _state(db_service, entity.id, 15.0),
        [],
        {"name": "New Harbor", "hidden_attributes": {"_sheet_layout": [["owner"]]}},
        {"name": entity.name, "_sheet_layout": None},
    )
    assert command.execute(db_service).success
    updated = db_service.get_entity(entity.id)
    assert updated.name == "New Harbor"
    assert updated.attributes["_tags"] == ["coast"]
    assert updated.attributes["_sheet_layout"] == [["owner"]]
    command.undo(db_service)
    assert db_service.get_entity(entity.id).name == "Harbor"
    assert "_sheet_layout" not in db_service.get_entity(entity.id).attributes
