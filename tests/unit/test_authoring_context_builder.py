"""Tests for deterministic Event authoring-context projection."""

from uuid import NAMESPACE_URL, uuid5

from src.core.authoring_context import EntityAuthoringContext, EventAuthoringContext
from src.core.entities import Entity
from src.core.events import Event
from src.core.image_attachment import ImageAttachment
from src.core.map import Map
from src.core.marker import Marker
from src.services.authoring_context_builder import (
    AuthoringContextBuilder,
    format_entity_authoring_context,
)


def _id(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"kraken-authoring-context:{label}"))


def _event(db_service, name: str, date: float, *, event_id: str) -> Event:
    event = Event(name=name, lore_date=date, id=_id(event_id))
    db_service.insert_event(event)
    return event


def _entity(
    db_service,
    name: str,
    *,
    entity_id: str,
    attributes: dict | None = None,
) -> Entity:
    entity = Entity(
        name=name,
        type="character",
        id=_id(entity_id),
        attributes=attributes or {},
    )
    db_service.insert_entity(entity)
    return entity


def test_snapshot_round_trip_and_event_classification(db_service) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    person = _entity(db_service, "Ada", entity_id="person")
    place = _entity(db_service, "Bay", entity_id="place")
    mentioned = _entity(db_service, "Cipher", entity_id="mentioned")
    backlink = _entity(db_service, "Backlink", entity_id="backlink")
    db_service.insert_relation(
        root.id,
        person.id,
        "involved",
        {"valid_from": 20.0},
    )
    db_service.insert_relation(root.id, place.id, "located_at")
    occurrence = {"field": "description", "start_offset": 0, "end_offset": 8}
    db_service.reconcile_mentions(root.id, "description", {mentioned.id: [occurrence]})
    db_service.insert_relation(backlink.id, root.id, "involved")
    db_service.reconcile_mentions(mentioned.id, "description", {root.id: [occurrence]})

    result = AuthoringContextBuilder(db_service).build_event_context(root.id)

    assert result is not None
    assert [item.id for item in result.participants] == [person.id]
    assert [item.id for item in result.locations] == [place.id]
    assert [item.id for item in result.mentions] == [mentioned.id]
    assert [(rel.source.id, rel.rel_type) for rel in result.direct_relations] == [
        (backlink.id, "involved")
    ]
    assert EventAuthoringContext.from_dict(result.to_dict()) == result


def test_draft_date_controls_chronology_and_root_dynamic_relation(
    db_service,
) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    before = _event(db_service, "Before", 15.0, event_id="before")
    same = _event(db_service, "Same", 20.0, event_id="same")
    after = _event(db_service, "After", 25.0, event_id="after")
    target = _entity(db_service, "Target", entity_id="target")
    db_service.insert_relation(
        root.id,
        target.id,
        "revealed",
        {"valid_at_event": True},
    )

    result = AuthoringContextBuilder(db_service).build_event_context(
        root.id, context_date=20.0
    )

    assert result is not None
    assert [event.id for event in result.previous_events] == [before.id]
    assert [event.id for event in result.concurrent_events] == [same.id]
    assert [event.id for event in result.next_events] == [after.id]
    assert [relation.temporal_kind for relation in result.direct_relations] == [
        "instant"
    ]


def test_temporal_relations_use_shared_active_window_semantics(db_service) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    targets = [
        _entity(db_service, f"Target {index}", entity_id=f"target-{index}")
        for index in range(5)
    ]
    db_service.insert_relation(root.id, targets[0].id, "persistent")
    db_service.insert_relation(
        root.id,
        targets[1].id,
        "active",
        {"valid_from": 5.0, "valid_to": 15.0},
    )
    db_service.insert_relation(
        root.id,
        targets[2].id,
        "future",
        {"valid_from": 11.0},
    )
    db_service.insert_relation(
        root.id,
        targets[3].id,
        "invalid",
        {"valid_from": 15.0, "valid_to": 5.0},
    )
    db_service.insert_relation(
        root.id,
        targets[4].id,
        "instant",
        {"valid_at_event": True},
    )

    result = AuthoringContextBuilder(db_service).build_event_context(root.id)

    assert result is not None
    assert {relation.rel_type for relation in result.direct_relations} == {
        "active",
        "instant",
        "persistent",
    }


def test_neighborhood_stops_at_two_hops_and_excludes_root_and_mentions(
    db_service,
) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    seed = _entity(db_service, "Seed", entity_id="seed")
    hop_one = _entity(db_service, "One", entity_id="one")
    hop_two = _entity(db_service, "Two", entity_id="two")
    hop_three = _entity(db_service, "Three", entity_id="three")
    db_service.insert_relation(root.id, seed.id, "involved")
    first_id = db_service.insert_relation(seed.id, hop_one.id, "knows")
    second_id = db_service.insert_relation(hop_one.id, hop_two.id, "serves")
    db_service.insert_relation(hop_two.id, hop_three.id, "guards")
    db_service.reconcile_mentions(
        seed.id,
        "description",
        {
            hop_two.id: [
                {"field": "description", "start_offset": 0, "end_offset": 3}
            ]
        },
    )

    result = AuthoringContextBuilder(db_service).build_event_context(root.id)

    assert result is not None
    assert [relation.id for relation in result.neighborhood_relations] == [
        first_id,
        second_id,
    ]
    assert [relation.hop for relation in result.neighborhood_relations] == [1, 2]


def test_limits_and_output_are_deterministic(db_service) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    for index in range(15):
        _event(
            db_service,
            f"Concurrent {index:02d}",
            10.0,
            event_id=f"concurrent-{index:02d}",
        )
    for index in range(14):
        entity = _entity(
            db_service,
            f"Person {index:02d}",
            entity_id=f"person-{index:02d}",
        )
        db_service.insert_relation(root.id, entity.id, "involved")

    builder = AuthoringContextBuilder(db_service)
    first = builder.build_event_context(root.id)
    second = builder.build_event_context(root.id)

    assert first is not None
    assert second is not None
    assert first.to_dict() == second.to_dict()
    assert len(first.concurrent_events) == 12
    assert len(first.participants) == 12
    assert dict(first.omitted_counts) == {
        "concurrent_events": 3,
        "participants": 2,
    }


def test_missing_event_and_broken_endpoint_fail_safely(db_service) -> None:
    root = _event(db_service, "Root", 10.0, event_id="root")
    target = _entity(db_service, "Temporary", entity_id="temporary")
    db_service.insert_relation(root.id, target.id, "related")
    db_service.delete_entity(target.id)

    builder = AuthoringContextBuilder(db_service)
    result = builder.build_event_context(root.id)

    assert builder.build_event_context(_id("missing")) is None
    assert result is not None
    assert result.direct_relations == ()


def test_entity_context_classifies_durable_facts_and_round_trips(db_service) -> None:
    root = _entity(
        db_service,
        "Ada",
        entity_id="entity-root",
        attributes={"Role": "Navigator", "_summary_data": {"text": "hidden"}},
    )
    ally = _entity(db_service, "Bram", entity_id="entity-ally")
    appearance = _event(db_service, "Arrival", 20.0, event_id="appearance")
    mention = _event(db_service, "Rumour", 30.0, event_id="mention")
    db_service.insert_relation(root.id, ally.id, "knows")
    db_service.insert_relation(appearance.id, root.id, "involved")
    occurrence = {"field": "description", "start_offset": 0, "end_offset": 3}
    db_service.reconcile_mentions(
        mention.id, "description", {root.id: [occurrence]}
    )

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert [(item.name, item.value) for item in result.attributes] == [
        ("Role", "Navigator")
    ]
    assert [item.event.id for item in result.event_appearances] == [appearance.id]
    assert result.event_appearances[0].roles == ("involved",)
    assert [item.id for item in result.mentions] == [mention.id]
    assert [item.rel_type for item in result.direct_relations] == ["knows"]
    assert EntityAuthoringContext.from_dict(result.to_dict()) == result


def test_entity_context_keeps_valid_temporal_relations_as_history(db_service) -> None:
    root = _entity(db_service, "Ada", entity_id="temporal-root")
    source = _event(db_service, "Appointment", 12.0, event_id="source-event")
    db_service.insert_relation(
        source.id,
        root.id,
        "appointed",
        {"valid_at_event": True},
    )
    db_service.insert_relation(
        root.id,
        source.id,
        "invalid",
        {"valid_from": 20.0, "valid_to": 10.0},
    )

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert [(item.rel_type, item.temporal_kind) for item in result.temporal_history] == [
        ("appointed", "instant")
    ]
    assert not result.direct_relations


def test_entity_context_map_appearance_is_durable_and_date_neutral(db_service) -> None:
    root = _entity(db_service, "Ada", entity_id="map-root")
    map_item = Map(name="Coast", image_path="coast.png")
    db_service.insert_map(map_item)
    db_service.insert_marker(
        Marker(
            map_id=map_item.id,
            object_id=root.id,
            object_type="entity",
            x=0.25,
            y=0.75,
            feature_type="region",
        )
    )

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert [item.to_dict() for item in result.map_appearances] == [
        {
            "map_id": map_item.id,
            "map_name": "Coast",
            "feature_type": "region",
            "marker_label": None,
            "parent_maps": [],
        }
    ]


def test_entity_context_aggregates_public_structured_knowledge(db_service) -> None:
    root = _entity(
        db_service,
        "Harbour",
        entity_id="aggregation-root",
        attributes={
            "Population": 900,
            "_tags": ["settlement", "coastal"],
            "_sheet_layout": {"private": True},
            "_secret": "hidden",
        },
    )
    ally = _entity(
        db_service,
        "Lighthouse",
        entity_id="aggregation-ally",
    )
    db_service.assign_tag_to_entity(root.id, "settlement")
    db_service.assign_tag_to_entity(root.id, "coastal")
    db_service.assign_tag_to_entity(ally.id, "coastal")
    event = _event(db_service, "Storm", 12.0, event_id="aggregation-event")
    db_service.insert_relation(event.id, root.id, "involved")
    db_service.insert_relation(event.id, root.id, "located_at")
    db_service.insert_relation(event.id, ally.id, "involved")
    occurrence = {"field": "description", "start_offset": 0, "end_offset": 4}
    db_service.reconcile_mentions(root.id, "description", {ally.id: [occurrence]})

    parent = Map(
        name="World",
        image_path="world.png",
        attributes={"map_role": "master"},
    )
    detail = Map(
        name="Coast",
        image_path="coast.png",
        attributes={"map_role": "detail", "parent_map_id": parent.id},
    )
    db_service.insert_map(parent)
    db_service.insert_map(detail)
    db_service.insert_marker(
        Marker(
            map_id=detail.id,
            object_id=root.id,
            object_type="entity",
            x=0.2,
            y=0.3,
            label="Old Harbour",
        )
    )
    db_service.insert_marker(
        Marker(
            map_id=detail.id,
            object_id=ally.id,
            object_type="entity",
            x=0.4,
            y=0.5,
        )
    )
    db_service.get_attachment_repo().insert(
        ImageAttachment(
            id=_id("caption"),
            owner_type="entity",
            owner_id=root.id,
            image_rel_path="private/path.webp",
            caption="The harbour seal",
        )
    )

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert [(item.name, item.value) for item in result.attributes] == [
        ("Population", 900)
    ]
    assert [item.name for item in result.tags] == ["coastal", "settlement"]
    assert result.event_appearances[0].roles == ("involved", "located_at")
    assert result.co_appearances[0].item.id == ally.id
    assert result.co_appearances[0].events[0].id == event.id
    assert result.linked_references[0].target.id == ally.id
    assert result.shared_tags[0].evidence == ("coastal",)
    assert result.shared_maps[0].evidence == ("Coast",)
    assert result.map_appearances[0].marker_label == "Old Harbour"
    assert [item.name for item in result.map_appearances[0].parent_maps] == [
        "World"
    ]
    assert [item.caption for item in result.attachments] == ["The harbour seal"]
    assert "private/path.webp" not in str(result.to_dict())
    formatted = format_entity_authoring_context(result)
    assert "Event appearances and roles:" in formatted
    assert "Explicit linked references:" in formatted
    assert "Appears with in Events" in formatted
    assert "Shares tags (classification only):" in formatted
    assert "_sheet_layout" not in formatted
    assert "_secret" not in formatted


def test_entity_neighborhood_stops_at_two_hops(db_service) -> None:
    root = _entity(db_service, "Root", entity_id="entity-neighborhood-root")
    seed = _entity(db_service, "Seed", entity_id="entity-neighborhood-seed")
    one = _entity(db_service, "One", entity_id="entity-neighborhood-one")
    two = _entity(db_service, "Two", entity_id="entity-neighborhood-two")
    three = _entity(db_service, "Three", entity_id="entity-neighborhood-three")
    db_service.insert_relation(root.id, seed.id, "knows")
    first = db_service.insert_relation(seed.id, one.id, "serves")
    second = db_service.insert_relation(one.id, two.id, "guards")
    db_service.insert_relation(two.id, three.id, "visits")

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert [item.id for item in result.neighborhood_relations] == [first, second]
    assert [item.hop for item in result.neighborhood_relations] == [1, 2]


def test_entity_attribute_values_are_bounded(db_service) -> None:
    root = _entity(
        db_service,
        "Root",
        entity_id="bounded-attributes",
        attributes={"Chronicle": "x" * 1000},
    )

    result = AuthoringContextBuilder(db_service).build_entity_context(root.id)

    assert result is not None
    assert len(str(result.attributes[0].value)) <= 400
    assert str(result.attributes[0].value).endswith("…")
    assert dict(result.omitted_counts)["attribute_details"] == 1
