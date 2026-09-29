import pytest

from src.commands.temporal_entity_edit_command import TemporalEntityEditCommand
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_manager import TemporalManager
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    service = DatabaseService(":memory:")
    service.connect()
    return service


@pytest.fixture
def temporal_manager(db_service):
    return TemporalManager(db_service)


def _ordered_year_only_changes(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    converter = CalendarConverter(config)
    expression = DateParser(config).parse_expression("961")
    temporal = {"schema": 1, "expression": expression.to_dict()}
    entity = Entity(name="Tasgillia", type="Character", attributes={"office": "None"})
    first = Event(
        name="Appointment",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": dict(temporal)},
    )
    second = Event(
        name="Succession",
        lore_date=expression.representative_time(converter),
        attributes={"_temporal_v2": dict(temporal)},
    )
    first.attributes["_temporal_v2"]["constraints"] = [
        {
            "anchor_a": first.temporal_anchor_id,
            "relation": "before",
            "anchor_b": second.temporal_anchor_id,
            "min_offset_days": 0.0,
        }
    ]
    db_service.insert_entity(entity)
    db_service.insert_event(first)
    db_service.insert_event(second)
    first_relation = db_service.insert_relation(
        first.id,
        entity.id,
        "involved",
        {"valid_from_event": True, "payload": {"attributes": {"office": "Praetor"}}},
    )
    second_relation = db_service.insert_relation(
        second.id,
        entity.id,
        "involved",
        {"valid_from_event": True, "payload": {"attributes": {"office": "Consul"}}},
    )
    return entity, first, second_relation, converter.start_of_next_year(961), (
        first_relation,
        second_relation,
    )


def test_chronology_view_and_historical_edit_agree(db_service, temporal_manager):
    entity, first, winning_relation, time, relation_ids = _ordered_year_only_changes(
        db_service
    )
    viewed = temporal_manager.get_entity_state_at(entity.id, time).to_dict()
    assert viewed["attributes"]["office"] == "Consul"
    assert viewed["attribute_sources"]["office"]["relation_id"] == winning_relation
    assert viewed["ambiguous_attributes"] == {}

    command = TemporalEntityEditCommand(
        entity.id,
        time,
        viewed,
        [{"field": "attribute", "key": "office", "action": "set", "value": "Archon"}],
    )
    assert command._current_state(db_service) == viewed
    assert command.execute(db_service).success
    temporal_manager.clear_all_cache()
    assert temporal_manager.get_entity_state_at(entity.id, time).attributes["office"] == (
        "Archon"
    )
    command.undo(db_service)
    temporal_manager.clear_all_cache()
    assert temporal_manager.get_entity_state_at(entity.id, time).to_dict() == viewed
    assert set(relation_ids) == {
        relation["id"] for relation in db_service.get_incoming_relations(entity.id)
    }

    first.attributes["_temporal_v2"].pop("constraints")
    db_service.insert_event(first)
    temporal_manager.clear_all_cache()
    unordered = temporal_manager.get_entity_state_at(entity.id, time)
    assert unordered.attributes["office"] == "None"
    assert len(unordered.possible_effects) == 2
    assert set(unordered.ambiguous_attributes["office"]) == {
        "None",
        "Praetor",
        "Consul",
    }


@pytest.mark.parametrize("change", ["chronology", "source"])
def test_historical_edit_rejects_stale_temporal_state(
    db_service, temporal_manager, change
):
    entity, first, winning_relation, time, relation_ids = _ordered_year_only_changes(
        db_service
    )
    viewed = temporal_manager.get_entity_state_at(entity.id, time).to_dict()
    command = TemporalEntityEditCommand(
        entity.id,
        time,
        viewed,
        [{"field": "attribute", "key": "office", "action": "set", "value": "Archon"}],
    )
    if change == "chronology":
        first.attributes["_temporal_v2"].pop("constraints")
        db_service.insert_event(first)
    else:
        relation = db_service.get_relation(winning_relation)
        relation["attributes"]["payload"]["attributes"]["office"] = "Regent"
        db_service.update_relation(
            winning_relation, entity.id, "involved", relation["attributes"]
        )
    before = {
        relation_id: db_service.get_relation(relation_id) for relation_id in relation_ids
    }
    result = command.execute(db_service)
    assert not result.success
    assert "Reload before saving" in result.message
    assert not command.is_executed
    assert db_service.get_entity(entity.id).attributes["office"] == "None"
    assert {
        relation_id: db_service.get_relation(relation_id) for relation_id in relation_ids
    } == before


def test_temporal_resolution_flow(db_service, temporal_manager):
    """
    Integration test:
    1. Create an Entity.
    2. Create an Event with a Relation to that Entity (temporal).
    3. Resolve state via TemporalManager at different times.
    """

    # 1. Create Entity
    entity = Entity(
        name="Jon Snow",
        type="Character",
        attributes={"status": "Alive", "location": "Winterfell"},
    )
    db_service.insert_entity(entity)

    # 2. Create Event
    event = Event(
        name="Battle of the Bastards",
        lore_date=300.0,
        # date logic usually handled by relation VALID_FROM, but event date provides context
    )
    db_service.insert_event(event)

    # 3. Create Relation (Temporal Override)
    # Relation: valid_from=300, valid_to=None, payload={status: 'King in the North'}
    relation_attrs = {
        "valid_from": 300.0,
        "payload": {
            "attributes": {
                "status": "King in the North",
                "location": "Winterfell",
            }
        },
    }

    db_service.insert_relation(
        source_id=event.id,
        target_id=entity.id,
        rel_type="participated_in",
        attributes=relation_attrs,
    )

    # 4. Resolve State via Manager

    # T=200 (Before Event)
    state_before = temporal_manager.get_entity_state_at(entity.id, 200.0)
    assert state_before.attributes["status"] == "Alive"

    # T=300 (At Event)
    state_at = temporal_manager.get_entity_state_at(entity.id, 300.0)
    assert state_at.attributes["status"] == "King in the North"

    # T=400 (After Event)
    state_after = temporal_manager.get_entity_state_at(entity.id, 400.0)
    assert state_after.attributes["status"] == "King in the North"


def test_temporal_invalidation(db_service, temporal_manager):
    """
    Test that modifying a relation invalidates the cache.
    """
    # Setup
    entity = Entity(name="Ghost", type="Wolf", attributes={"color": "White"})
    db_service.insert_entity(entity)

    event = Event(name="Battle", lore_date=100.0)
    db_service.insert_event(event)

    # Initial Relation
    db_service.insert_relation(
        source_id=event.id,
        target_id=entity.id,
        rel_type="owned_by",
        attributes={
            "valid_from": 100.0,
            "payload": {"attributes": {"color": "Dirty White"}},
        },
    )

    # Cache Prime
    state_1 = temporal_manager.get_entity_state_at(entity.id, 150.0)
    assert state_1.attributes["color"] == "Dirty White"

    # Need to simulate invalidation manually since signals aren't wired up in integration test
    temporal_manager.invalidate_entity(entity.id)

    # New Relation overriding
    db_service.insert_relation(
        source_id=event.id,
        target_id=entity.id,
        rel_type="cleaned",
        attributes={
            "valid_from": 101.0,
            "payload": {"attributes": {"color": "Sparkling White"}},
        },
    )

    # Fetch again
    state_2 = temporal_manager.get_entity_state_at(entity.id, 150.0)
    assert state_2.attributes["color"] == "Sparkling White"


def test_grey_ford_payload_v2_acceptance_scenario(db_service, temporal_manager):
    grey_ford = Entity(
        name="Grey Ford",
        type="Location",
        description="A fortified crossing over the Grey River.",
        attributes={"controller": "Crown", "garrison": 600},
    )
    battle = Event(name="Battle of Grey Ford", lore_date=732.0)
    destruction = Event(name="Destruction of Grey Ford", lore_date=735.0)
    db_service.insert_entity(grey_ford)
    db_service.insert_events_bulk([battle, destruction])

    db_service.insert_relation(
        source_id=battle.id,
        target_id=grey_ford.id,
        rel_type="affects",
        attributes={
            "valid_from_event": True,
            "payload": {
                "attributes": {"controller": "Northern League"},
            },
        },
    )
    db_service.insert_relation(
        source_id=destruction.id,
        target_id=grey_ford.id,
        rel_type="destroys",
        attributes={
            "valid_from_event": True,
            "payload": {
                "attributes": {"status": "Ruined"},
                "unset_attributes": ["garrison"],
                "description": (
                    "The ruined remains of Grey Ford lie beside the river."
                ),
            },
        },
    )

    state_731 = temporal_manager.get_entity_state_at(grey_ford.id, 731.0)
    state_733 = temporal_manager.get_entity_state_at(grey_ford.id, 733.0)
    state_736 = temporal_manager.get_entity_state_at(grey_ford.id, 736.0)
    revisited_731 = temporal_manager.get_entity_state_at(grey_ford.id, 731.0)

    assert state_731.description == grey_ford.description
    assert state_731.attributes == {"controller": "Crown", "garrison": 600}
    assert state_733.description == grey_ford.description
    assert state_733.attributes == {
        "controller": "Northern League",
        "garrison": 600,
    }
    assert state_736.description == (
        "The ruined remains of Grey Ford lie beside the river."
    )
    assert state_736.attributes == {
        "controller": "Northern League",
        "status": "Ruined",
    }
    assert revisited_731 == state_731

    persisted = db_service.get_entity(grey_ford.id)
    assert persisted is not None
    assert persisted.description == grey_ford.description
    assert persisted.attributes == {"controller": "Crown", "garrison": 600}


def test_event_to_event_payload_does_not_mutate_an_entity(
    db_service, temporal_manager
):
    entity = Entity(name="Observer", type="Character", attributes={"status": "Base"})
    source = Event(name="Source Event", lore_date=10.0)
    target = Event(name="Target Event", lore_date=20.0)
    db_service.insert_entity(entity)
    db_service.insert_events_bulk([source, target])
    db_service.insert_relation(
        source_id=source.id,
        target_id=target.id,
        rel_type="causes",
        attributes={
            "valid_from_event": True,
            "payload": {"attributes": {"status": "Changed"}},
        },
    )

    state = temporal_manager.get_entity_state_at(entity.id, 30.0)
    assert state.attributes["status"] == "Base"
