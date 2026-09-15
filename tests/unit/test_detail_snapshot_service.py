"""Tests for batched Event and Entity editor detail snapshots."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.core.entities import Entity
from src.core.events import Event
from src.services.detail_snapshot_service import DetailSnapshotService


def test_event_snapshot_preserves_relation_payloads_and_endpoint_kinds(db_service):
    event = Event(name="Source Event", lore_date=1.0)
    target_event = Event(name="Target Event", lore_date=2.0)
    entity = Entity(name="Participant", type="character")
    db_service.insert_event(event)
    db_service.insert_event(target_event)
    db_service.insert_entity(entity)
    db_service.insert_relation(event.id, entity.id, "involved", {"order": 1})
    db_service.insert_relation(event.id, target_event.id, "caused", {"order": 2})
    db_service.insert_relation(entity.id, event.id, "witnessed", {"incoming": True})

    snapshot = DetailSnapshotService(db_service).load_event(event.id)

    assert snapshot.item == event
    assert [relation["target_id"] for relation in snapshot.relations] == [
        entity.id,
        target_event.id,
    ]
    assert [relation["attributes"] for relation in snapshot.relations] == [
        {"order": 1},
        {"order": 2},
    ]
    assert [relation["target_name"] for relation in snapshot.relations] == [
        "Participant",
        "Target Event",
    ]
    assert [relation["target_kind"] for relation in snapshot.relations] == [
        "entity",
        "event",
    ]
    assert snapshot.incoming_relations[0]["source_name"] == "Participant"
    assert snapshot.incoming_relations[0]["source_event_date"] is None


def test_entity_snapshot_preserves_missing_endpoint_behavior():
    entity = Entity(name="Source", type="character")
    db_service = MagicMock()
    db_service.get_entity.return_value = entity
    db_service.get_relations.return_value = [
        {"target_id": "missing-target", "attributes": {}}
    ]
    db_service.get_incoming_relations.return_value = [
        {"source_id": "missing-source", "attributes": {}}
    ]
    db_service.get_object_display_metadata.return_value = {}

    snapshot = DetailSnapshotService(db_service).load_entity(entity.id)

    assert snapshot.relations[0]["target_name"] is None
    assert "target_kind" not in snapshot.relations[0]
    assert snapshot.incoming_relations[0]["source_name"] is None


def test_missing_items_return_empty_snapshots(db_service):
    service = DetailSnapshotService(db_service)

    event_snapshot = service.load_event("missing")
    entity_snapshot = service.load_entity("missing")

    assert event_snapshot.item is None
    assert event_snapshot.relations == []
    assert event_snapshot.incoming_relations == []
    assert entity_snapshot.item is None
    assert entity_snapshot.relations == []
    assert entity_snapshot.incoming_relations == []


def test_large_relation_fanout_uses_chunk_bounded_metadata_queries(db_service):
    source = Event(name="Source", lore_date=1.0)
    db_service.insert_event(source)
    connection = db_service.get_connection()
    assert connection is not None
    targets = [
        Entity(name=f"Entity {index}", type="character") for index in range(1_001)
    ]
    db_service.insert_entities_bulk(targets)
    connection.executemany(
        """
        INSERT INTO relations (id, source_id, target_id, rel_type, attributes, created_at)
        VALUES (?, ?, ?, 'involved', '{}', ?)
        """,
        [
            (f"relation-{index}", source.id, target.id, float(index))
            for index, target in enumerate(targets)
        ],
    )
    connection.commit()
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    try:
        snapshot = DetailSnapshotService(db_service).load_event(source.id)
    finally:
        connection.set_trace_callback(None)

    metadata_queries = [
        statement
        for statement in statements
        if "SELECT id, name FROM entities WHERE id IN" in statement
        or "SELECT id, name FROM events WHERE id IN" in statement
    ]
    assert len(snapshot.relations) == len(targets)
    assert len(metadata_queries) == 4
