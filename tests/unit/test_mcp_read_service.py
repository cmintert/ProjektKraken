"""MCP's read boundary preserves authored facts and never permits SQL mutation."""

import json
import sqlite3

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.mcp_access import McpFailure
from src.services.authoring_context_builder import AuthoringContextBuilder
from src.services.mcp_read_service import McpReadService, public_projection, read_guard

pytestmark = pytest.mark.ci_fast


def request(tool, **arguments):
    return {
        "tool": tool,
        "arguments": arguments,
        "world_id": "world-a",
        "world_name": "Test world",
        "generation": "session-a",
    }


def test_search_literal_paging_and_stale_revision(db_service):
    for index in range(30):
        db_service.insert_entity(Entity(f"City {index}", "place"))
    service = McpReadService()
    first = service.execute(
        db_service, request("search_world", query="City"), lambda: False
    )
    assert len(first["data"]["rows"]) == 25
    token = first["data"]["next_cursor"]
    second = service.execute(
        db_service, request("search_world", query="City", cursor=token), lambda: False
    )
    assert len(second["data"]["rows"]) == 5
    assert second["data"]["done"]
    db_service.insert_entity(Entity("City newer", "place"))
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        service.execute(
            db_service,
            request("search_world", query="City", cursor=token),
            lambda: False,
        )
    literal = service.execute(
        db_service, request("search_world", query="%"), lambda: False
    )
    assert literal["data"]["rows"] == []


def test_object_allowlist_and_context_parity(db_service):
    entity = Entity(
        "Northwatch",
        "place",
        "A fortress",
        attributes={
            "_private": "hidden",
            "api_key": "hidden",
            "image_path": "C:/private",
        },
    )
    db_service.insert_entity(entity)
    service = McpReadService()
    result = service.execute(
        db_service, request("get_object", kind="entity", id=entity.id), lambda: False
    )
    assert result["data"]["description"] == "A fortress"
    assert result["data"]["attributes"] == {}
    assert "hidden" not in json.dumps(result)
    actual = service.execute(
        db_service,
        request("get_context", kind="entity", id=entity.id, mode="all_history"),
        lambda: False,
    )
    expected = (
        AuthoringContextBuilder(db_service).build_entity_context(entity.id).to_dict()
    )
    assert actual["data"]["entity_id"] == expected["entity_id"]
    assert actual["data"]["direct_relations"] == expected["direct_relations"]


def test_event_dates_and_missing_records(db_service):
    event = Event("Siege", 42.5, lore_duration=3)
    db_service.insert_event(event)
    service = McpReadService()
    result = service.execute(
        db_service, request("get_object", kind="event", id=event.id), lambda: False
    )
    assert result["data"]["lore_date"] == 42.5
    assert result["data"]["lore_duration"] == 3
    with pytest.raises(McpFailure, match="NOT_FOUND"):
        service.execute(
            db_service, request("get_object", kind="event", id="absent"), lambda: False
        )
    with pytest.raises(McpFailure, match="INVALID_DATE"):
        service.execute(
            db_service,
            request(
                "get_context",
                kind="event",
                id=event.id,
                mode="at_playhead",
                lore_day=float("nan"),
            ),
            lambda: False,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM entities",
        "CREATE TABLE attack (id TEXT)",
        "ATTACH DATABASE ':memory:' AS attack",
        "PRAGMA query_only = OFF",
        "INSERT INTO entities (id,name,type,description,attributes,created_at,modified_at) "
        "VALUES ('bad','bad','bad','','{}',0,0)",
    ],
)
def test_write_guard_and_restoration(db_service, sql):
    connection = db_service.require_connection()
    with read_guard(connection, lambda: False):
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute(sql)
    entity = Entity("Normal GUI command can still save", "place")
    db_service.insert_entity(entity)
    assert db_service.get_entity(entity.id) is not None


def test_expired_sql_interrupts_and_resets_handler(db_service):
    connection = db_service.require_connection()
    with read_guard(connection, lambda: True):
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            connection.execute(
                "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n "
                "WHERE x<100000) SELECT SUM(x) FROM n"
            ).fetchone()
    assert connection.execute("SELECT 1").fetchone()[0] == 1


def test_connections_preserve_direction_and_hide_internal_cursor(db_service):
    source = Entity("Source", "person")
    target = Entity("Target", "place")
    db_service.insert_entity(source)
    db_service.insert_entity(target)
    relation = db_service.insert_relation(source.id, target.id, "visited")
    result = McpReadService().execute(
        db_service,
        request("list_connections", entity_id=target.id, mode="all_history"),
        lambda: False,
    )
    row = result["data"]["rows"][0]
    assert row["id"] == relation
    assert row["source"]["id"] == source.id
    assert row["target"]["id"] == target.id
    assert "cursor" not in result["data"]
    assert result["data"]["done"]


def test_context_does_not_expose_named_secret_attributes(db_service):
    entity = Entity("City", "place", attributes={"api_key": "must-not-escape"})
    db_service.insert_entity(entity)
    result = McpReadService().execute(
        db_service,
        request("get_context", kind="entity", id=entity.id, mode="all_history"),
        lambda: False,
    )
    assert "must-not-escape" not in json.dumps(result)


def test_public_projection_preserves_null_positions_but_removes_private_metadata():
    assert public_projection(
        {
            "range": [None, 2],
            "provider_api_key": "hidden",
            "attributes": [
                {"name": "File Path", "value": "C:/hidden"},
                {"name": "Population", "value": 42},
            ],
        }
    ) == {
        "range": [None, 2],
        "attributes": [{"name": "Population", "value": 42}],
        "omitted_counts": {"restricted_fields": 2},
    }


def test_large_world_small_relevant_context_without_mutation(db_service, monkeypatch):
    import src.services.mcp_read_service as module

    monkeypatch.setattr(module, "_MAX_CONTEXT_INPUT_ROWS", 1)
    entity = Entity("One", "place")
    db_service.insert_entity(entity)
    db_service.insert_entity(Entity("Two", "place"))
    result = McpReadService().execute(
        db_service,
        request("get_context", kind="entity", id=entity.id, mode="all_history"),
        lambda: False,
    )
    assert result["status"] == "OK"
    assert db_service.get_entity(entity.id).name == "One"
