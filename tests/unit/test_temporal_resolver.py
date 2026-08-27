"""Unit tests for deterministic Payload v2 temporal resolution."""

import pytest

from src.core.entities import Entity
from src.core.temporal_resolver import TemporalResolver
from src.core.temporal_state import ResolvedEntityState


@pytest.fixture
def resolver():
    return TemporalResolver()


@pytest.fixture
def base_entity():
    return Entity(
        id="entity-1",
        name="Jon Snow",
        type="character",
        description="Base description",
        attributes={
            "status": "Alive",
            "location": "Winterfell",
            "rank": "Bastard",
            "garrison": 10,
        },
    )


def event_relation(
    relation_id: str,
    start: float,
    payload: object | None = None,
    **attributes,
):
    relation_attributes = {"valid_from": start, **attributes}
    if payload is not None:
        relation_attributes["payload"] = payload
    return {
        "id": relation_id,
        "source_event_date": start,
        "attributes": relation_attributes,
    }


def test_no_relations_returns_detached_complete_base_state(resolver, base_entity):
    state = resolver.resolve_entity_state(base_entity, [], time=100.0)

    assert state == ResolvedEntityState(
        entity_id=base_entity.id,
        description="Base description",
        attributes=base_entity.attributes,
    )
    assert state.attributes is not base_entity.attributes


def test_event_payload_sets_creates_unsets_and_preserves_null(resolver, base_entity):
    relation = event_relation(
        "relation-1",
        50.0,
        {
            "attributes": {"status": "Dead", "ruler": None},
            "unset_attributes": ["garrison", "absent"],
        },
    )

    before = resolver.resolve_entity_state(base_entity, [relation], 40.0)
    after = resolver.resolve_entity_state(base_entity, [relation], 60.0)

    assert before.attributes == base_entity.attributes
    assert after.attributes["status"] == "Dead"
    assert after.attributes["ruler"] is None
    assert "ruler" in after.attributes
    assert "garrison" not in after.attributes
    assert base_entity.attributes["status"] == "Alive"
    assert base_entity.attributes["garrison"] == 10


def test_description_presence_and_sequential_application(resolver, base_entity):
    relations = [
        event_relation("a", 10.0, {"description": "First"}),
        event_relation("b", 20.0, {"attributes": {"status": "Busy"}}),
        event_relation("c", 30.0, {"description": ""}),
    ]

    assert resolver.resolve_entity_state(base_entity, relations, 5.0).description == (
        "Base description"
    )
    assert resolver.resolve_entity_state(base_entity, relations, 15.0).description == (
        "First"
    )
    state = resolver.resolve_entity_state(base_entity, relations, 25.0)
    assert state.description == "First"
    assert state.attributes["status"] == "Busy"
    assert resolver.resolve_entity_state(base_entity, relations, 35.0).description == ""


def test_expired_payload_uses_existing_half_open_window(resolver, base_entity):
    relation = event_relation(
        "temporary",
        100.0,
        {"attributes": {"status": "Temporary King"}},
        valid_to=200.0,
    )

    assert resolver.resolve_entity_state(base_entity, [relation], 99.0).attributes[
        "status"
    ] == "Alive"
    assert resolver.resolve_entity_state(base_entity, [relation], 100.0).attributes[
        "status"
    ] == "Temporary King"
    assert resolver.resolve_entity_state(base_entity, [relation], 200.0).attributes[
        "status"
    ] == "Alive"


def test_same_date_order_remains_deterministic(resolver, base_entity):
    relations = [
        event_relation(
            "event",
            50.0,
            {"attributes": {"location": "Event Location"}},
            priority="event",
            modified_at=2.0,
        ),
        event_relation(
            "manual",
            50.0,
            {"attributes": {"location": "Manual Location"}},
            priority="manual",
            modified_at=1.0,
        ),
    ]

    state = resolver.resolve_entity_state(base_entity, relations, 60.0)
    assert state.attributes["location"] == "Manual Location"


def test_entity_sourced_payload_is_ignored(resolver, base_entity):
    relation = {
        "id": "entity-relation",
        "source_event_date": None,
        "attributes": {
            "valid_from": 0.0,
            "payload": {"attributes": {"status": "Invalid Mutation"}},
        },
    }

    state = resolver.resolve_entity_state(base_entity, [relation], 100.0)
    assert state.attributes["status"] == "Alive"


def test_event_without_payload_is_noop(resolver, base_entity):
    state = resolver.resolve_entity_state(
        base_entity,
        [event_relation("no-payload", 10.0)],
        100.0,
    )
    assert state.attributes == base_entity.attributes
    assert state.description == base_entity.description


def test_invalid_active_payload_fails_with_relation_context(resolver, base_entity):
    relation = event_relation("legacy-relation", 10.0, {"status": "Wounded"})

    with pytest.raises(ValueError, match="legacy-relation.*unsupported keys"):
        resolver.resolve_entity_state(base_entity, [relation], 100.0)


def test_invalid_inactive_payload_does_not_abort_resolution(resolver, base_entity):
    relation = event_relation("future", 200.0, {"status": "Wounded"})
    state = resolver.resolve_entity_state(base_entity, [relation], 100.0)
    assert state.attributes == base_entity.attributes
