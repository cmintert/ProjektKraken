"""Deterministic temporal context matrix, identity, privacy and budget gates."""

import json

import pytest

from src.core.authoring_context import EntityAuthoringContext
from src.core.entities import Entity
from src.core.entity_context_mode import EntityContextMode as Mode
from src.core.events import Event
from src.core.temporal_relation_policy import (
    RelationTemporalMode,
    evaluate_temporal_relation,
)
from src.services.authoring_context_builder import (
    AuthoringContextBuilder,
    format_entity_authoring_context,
)

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def reign(db_service):
    person = Entity(
        "Ilyra", "character", attributes={"rank": "citizen", "_secret": "private"}
    )
    realm = Entity("Bestril", "place")
    db_service.insert_entity(person)
    db_service.insert_entity(realm)
    coronation = Event("Coronation", 120.0)
    abdication = Event("Abdication", 147.0)
    db_service.insert_event(coronation)
    db_service.insert_event(abdication)
    attrs = {"valid_from": 120.0, "valid_to": 147.0}
    relation_id = db_service.insert_relation(person.id, realm.id, "rules", attrs)
    return person, realm, coronation, abdication, relation_id


def relations(context):
    return (*context.direct_relations, *context.temporal_history)


@pytest.mark.parametrize(
    "date,active", [(110, False), (120, True), (135, True), (147, False), (155, False)]
)
@pytest.mark.parametrize("endpoint", [0, 1])
def test_reign_truth_and_identity_from_both_endpoints(
    db_service, reign, date, active, endpoint
):
    context = AuthoringContextBuilder(db_service).build_entity_context(
        reign[endpoint].id, mode=Mode.AT_PLAYHEAD, context_date=float(date)
    )
    assert context is not None
    found = relations(context)
    assert bool(found) is active
    if active:
        relation = found[0]
        assert relation.id == reign[-1]
        assert relation.source.id == reign[0].id
        assert relation.target.id == reign[1].id
        assert relation.temporal_status == "definite"
        assert relation.rel_type == "rules"
    assert EntityAuthoringContext.from_dict(context.to_dict()) == context
    assert "private" not in json.dumps(context.to_dict())


@pytest.mark.parametrize(
    "date,count,status", [(110, 0, None), (135, 1, "definite"), (155, 1, "inactive")]
)
def test_history_to_playhead_qualifies_ended_state(
    db_service, reign, date, count, status
):
    context = AuthoringContextBuilder(db_service).build_entity_context(
        reign[0].id, mode=Mode.HISTORY_TO_PLAYHEAD, context_date=float(date)
    )
    assert len(relations(context)) == count
    if count:
        assert relations(context)[0].temporal_status == status


def test_event_bound_reign_tracks_rescheduling_and_sources(db_service, reign):
    person, realm, coronation, abdication, _ = reign
    db_service.insert_relation(
        person.id,
        realm.id,
        "event_bound_rules",
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {"anchor": {"anchor_id": f"event:{coronation.id}"}},
                "end": {"anchor": {"anchor_id": f"event:{abdication.id}"}},
            }
        },
    )
    builder = AuthoringContextBuilder(db_service)
    context = builder.build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=135.0
    )
    relation = next(x for x in relations(context) if x.rel_type == "event_bound_rules")
    assert {x["id"] for x in relation.temporal_evidence["events"]} == {
        coronation.id,
        abdication.id,
    }
    coronation.lore_date = 140.0
    db_service.insert_event(coronation)
    refreshed = builder.build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=135.0
    )
    assert "event_bound_rules" not in {x.rel_type for x in relations(refreshed)}


def test_current_state_provenance_and_private_candidates(db_service, reign):
    person, _, coronation, _, _ = reign
    db_service.insert_relation(
        coronation.id,
        person.id,
        "changes",
        {
            "valid_from": 120.0,
            "payload": {
                "description": "Crowned ruler",
                "attributes": {"rank": "queen"},
            },
        },
    )
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=135.0
    )
    rank = next(x for x in context.attributes if x.name == "rank")
    assert rank.value == "queen"
    assert rank.source["event_id"] == coronation.id
    assert context.effective_description.value == "Crowned ruler"
    assert (
        context.effective_description.source["relation_id"]
        == rank.source["relation_id"]
    )


@pytest.mark.parametrize("status", ["unknown", "open"])
def test_unknown_boundary_is_not_an_exact_or_open_boundary(db_service, reign, status):
    person, realm, *_ = reign
    db_service.insert_relation(
        person.id,
        realm.id,
        "uncertain",
        {
            "temporal": {
                "schema": 1,
                "behavior": "stateful",
                "start": {"status": status},
                "end": {"status": "open"},
            }
        },
    )
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=0.0
    )
    item = next(x for x in relations(context) if x.rel_type == "uncertain")
    assert item.temporal_status == (
        "indeterminate" if status == "unknown" else "definite"
    )
    assert item.valid_from is None


def test_future_appearance_cannot_seed_context_or_coappearance(db_service, reign):
    person, realm, coronation, *_ = reign
    db_service.insert_relation(coronation.id, person.id, "involved")
    db_service.insert_relation(coronation.id, realm.id, "involved")
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.HISTORY_TO_PLAYHEAD, context_date=110.0
    )
    assert not context.event_appearances
    assert not context.co_appearances
    assert not context.neighborhood_relations


def test_legacy_default_and_invalid_date_contract(db_service, reign):
    builder = AuthoringContextBuilder(db_service)
    legacy = builder.build_entity_context(reign[0].id)
    assert legacy.mode == "all_history" and legacy.context_date is None
    assert len(relations(legacy)) == 1
    for date in (None, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            builder.build_entity_context(
                reign[0].id, mode=Mode.AT_PLAYHEAD, context_date=date
            )


def test_scoped_limits_keep_sources_atomic_and_report_omissions(db_service, reign):
    person = reign[0]
    person.attributes = {
        str(i): {"public": "x" * 500, "_secret": "private"} for i in range(100)
    }
    db_service.insert_entity(person)
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=135.0
    )
    serialized = json.dumps(context.to_dict(), ensure_ascii=False)
    assert len(serialized) <= 12000
    assert "private" not in serialized
    assert context.omitted_counts
    assert all(x.source is not None for x in context.attributes)
    assert "omitted" in format_entity_authoring_context(context)


def test_projection_relation_policy_is_the_graph_policy():
    from src.core.graph_temporal import evaluate_graph_relation

    assert evaluate_graph_relation is evaluate_temporal_relation
    item = {"id": "edge", "attributes": {"valid_from": 120.0, "valid_to": 147.0}}
    assert (
        evaluate_graph_relation(item, 155, None, RelationTemporalMode.AT_PLAYHEAD)
        is None
    )


def test_custom_calendar_coarse_changes_keep_candidates_and_sources(db_service, reign):
    from src.core.calendar import CalendarConfig, CalendarConverter, MonthDefinition
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    config.months = [MonthDefinition("Moon", "M", 50)]
    config.leap_year_rules = []
    db_service.insert_calendar_config(config)
    db_service.set_active_calendar_config(config.id)
    converter = CalendarConverter(config)
    expression = DateParser(config).parse_expression("120")
    person = reign[0]
    for name, value in (("First claim", "queen"), ("Second claim", "regent")):
        event = Event(
            name,
            expression.representative_time(converter),
            attributes={
                "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
            },
        )
        db_service.insert_event(event)
        db_service.insert_relation(
            event.id,
            person.id,
            "changes",
            {
                "valid_from_event": True,
                "payload": {
                    "attributes": {
                        "rank": value,
                        "details": {"public": "known", "_secret": "private-candidate"},
                    }
                },
            },
        )
    date = converter.start_of_year(121)
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=date
    )
    rank = next(x for x in context.attributes if x.name == "rank")
    assert rank.value == "citizen" and rank.temporal_status == "possible"
    assert {
        x.value.strip('"') for x in context.possible_changes if x.name == "rank"
    } == {"queen", "regent"}
    assert all(x.source["event_id"] for x in context.possible_changes)
    assert "private-candidate" not in json.dumps(context.to_dict())
    assert context.date_label == converter.format_datetime(date)


def test_uncertain_event_appearance_is_qualified_without_invented_day(
    db_service, reign
):
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.date_parser import DateParser

    config = CalendarConfig.create_default()
    db_service.insert_calendar_config(config)
    db_service.set_active_calendar_config(config.id)
    converter = CalendarConverter(config)
    expression = DateParser(config).parse_expression("120")
    event = Event(
        "Uncertain coronation",
        expression.representative_time(converter),
        attributes={"_temporal_v2": {"schema": 1, "expression": expression.to_dict()}},
    )
    db_service.insert_event(event)
    db_service.insert_relation(event.id, reign[0].id, "involved")
    context = AuthoringContextBuilder(db_service).build_entity_context(
        reign[0].id,
        mode=Mode.HISTORY_TO_PLAYHEAD,
        context_date=converter.start_of_year(120) + 10,
    )
    appearance = next(x for x in context.event_appearances if x.event.id == event.id)
    assert appearance.event.temporal_status == "possible"
    assert "unknown" in appearance.event.temporal_label
    assert "unknown" in format_entity_authoring_context(context)


@pytest.mark.parametrize(
    "behavior,expected_current", [("occurrence", False), ("historical", True)]
)
def test_occurrence_and_established_history_are_distinct(
    db_service, reign, behavior, expected_current
):
    db_service.insert_relation(
        reign[0].id,
        reign[1].id,
        behavior,
        {
            "temporal": {
                "schema": 1,
                "behavior": behavior,
                "at": {"exact": 100.0},
            }
        },
    )
    context = AuthoringContextBuilder(db_service).build_entity_context(
        reign[0].id, mode=Mode.AT_PLAYHEAD, context_date=155.0
    )
    assert (behavior in {x.rel_type for x in relations(context)}) is expected_current


def test_legacy_tag_classification_survives_scoped_public_attribute_filter(
    db_service, reign
):
    person = reign[0]
    person.tags = ["archivist"]
    db_service.insert_entity(person)
    context = AuthoringContextBuilder(db_service).build_entity_context(
        person.id, mode=Mode.AT_PLAYHEAD, context_date=135.0
    )
    assert [tag.name for tag in context.tags] == ["archivist"]
    assert "_tags" not in {item.name for item in context.attributes}
