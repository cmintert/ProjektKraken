"""Regressions for the six CodeRabbit MCP review issues."""

import base64
import io
import json

import numpy as np
import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.map import Map
from src.core.mcp_access import McpFailure
from src.services import mcp_embedding_protocol, mcp_semantic
from src.services.mcp_public import public_projection
from src.services.mcp_read_service import McpReadService
from src.services.mcp_read_task import McpReadTask
from tests.unit.test_mcp_reliable_reads import read, request

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize(
    "name",
    ["Telepathy", "Sympathies", "Pathfinder rank", "Tokens of office", "Secrets kept"],
)
def test_authored_attribute_names_survive_public_projection(name):
    value = {"attributes": {name: [None, "Authored fact"]}}
    assert public_projection(value) == value


@pytest.mark.parametrize(
    "name",
    [
        "api_key",
        "APIKey",
        "providerApiKey",
        "myapikey",
        "providerpassword",
        "authToken",
        "access_token",
        "refreshtoken",
        "client-secret",
        "File Path",
        "filePath",
        "filepath",
        "credentials",
        "database.password",
        "_private",
        "ａｐｉ＿ｋｅｙ",
    ],
)
def test_sensitive_fields_stay_hidden_and_counted_without_names(name):
    data = public_projection(
        {"attributes": {name: "never-share"}, "omitted_counts": {"excluded": 2}}
    )
    assert data["attributes"] == {}
    assert data["omitted_counts"] == {"excluded": 2, "restricted_fields": 1}
    assert "never-share" not in json.dumps(data)
    assert public_projection(data) == data


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("get_object", {}),
        ("get_context", {"mode": "all_history"}),
        ("read_object_section", {"section": "attributes"}),
        (
            "read_context_section",
            {"section": "attributes", "mode": "all_history"},
        ),
        ("get_object_summary", {}),
    ],
)
def test_object_and_context_routes_report_restricted_omissions(
    db_service, tool, arguments
):
    entity = Entity(
        "Reader", "person", attributes={"Telepathy": "strong", "api_key": "never-share"}
    )
    db_service.insert_entity(entity)
    data = read(db_service, tool, kind="entity", id=entity.id, **arguments)["data"]
    assert data["omitted_counts"]["restricted_fields"] >= 1
    assert "never-share" not in json.dumps(data)
    if tool != "get_object_summary":
        assert "Telepathy" in json.dumps(data)


def test_default_shared_search_uses_only_enabled_map_scope(db_service):
    world_map = Map("Ruined fortress", "unused.png")
    db_service.insert_map(world_map)
    rows = read(db_service, "search_shared_content", scopes=["maps"], query="fortress")[
        "data"
    ]["rows"]
    assert [row["id"] for row in rows] == [world_map.id]
    with pytest.raises(McpFailure, match="SCOPE_DISABLED"):
        read(db_service, "search_shared_content", query="fortress")
    with pytest.raises(McpFailure, match="SCOPE_DISABLED"):
        read(
            db_service,
            "search_shared_content",
            scopes=["maps"],
            kinds=["attachment"],
            query="fortress",
        )


@pytest.mark.parametrize("count", [1, 4])
def test_semantic_fallback_reports_top_k_truncation_without_cursor(db_service, count):
    for index in range(count):
        db_service.insert_entity(Entity(f"Ruler {index}", "person"))
    service = McpReadService()
    data = read(db_service, "semantic_search", service, query="Ruler", limit=1)["data"]
    assert data["effective_search"] == "lexical"
    assert data["truncated"] is (count > 1)
    assert data["partial"] is (count > 1)
    assert data["done"] is True and data["next_cursor"] is None
    assert service._cursors == {}
    paged = read(db_service, "search_world", service, query="Ruler", limit=1)["data"]
    assert bool(paged["next_cursor"]) is (count > 1)


def test_facets_page_assigned_and_legacy_names_without_loading_objects(
    db_service, monkeypatch
):
    root = Entity(
        "Root", "person", attributes={"_tags": [" campaign ", "漢字", None, 42]}
    )
    db_service.insert_entity(root)
    db_service.assign_tag_to_entity(root.id, "Campaign")
    for index in range(30):
        db_service.insert_entity(
            Entity(str(index), "person", attributes={"_tags": [f"Tag{index:02}"]})
        )
    event = Event("Event", 1, attributes={"_tags": ["EventOnly"]})
    db_service.insert_event(event)

    def unexpected(*args):
        pytest.fail("Facets must not materialize individual objects")

    monkeypatch.setattr(db_service, "get_entity", unexpected)
    monkeypatch.setattr(db_service, "get_event", unexpected)
    connection = db_service.require_connection()
    statements = []
    connection.set_trace_callback(statements.append)
    try:
        service, names, cursor = McpReadService(), [], None
        while True:
            before = len(statements)
            data = read(
                db_service, "browse_facets", service, category="tags", cursor=cursor
            )["data"]
            assert sum("json_each" in sql for sql in statements[before:]) == 2
            names.extend(row["name"] for row in data["rows"])
            cursor = data["next_cursor"]
            if cursor is None:
                break
        assert len(names) == 33 and len({name.casefold() for name in names}) == 33
        assert "Campaign" in names and "漢字" in names and "EventOnly" in names
        entity_only = read(
            db_service, "browse_facets", category="tags", kinds=["entity"]
        )["data"]
        assert "EventOnly" not in [row["name"] for row in entity_only["rows"]]
    finally:
        connection.set_trace_callback(None)


def test_helper_reads_full_preparation_budget_with_json_escaping():
    # Valid already-serialized public text near 64 MiB, then framed a second time.
    text = json.dumps({"description": "\\" * ((64 * 1024 * 1024 - 20) // 2)})
    payload = {"model": "installed", "texts": [text] + [""] * 49999}
    frame = mcp_embedding_protocol.encode_payload(payload)
    assert len(frame) > 70 * 1024 * 1024
    stream = io.BytesIO(frame + b'{"texts": ["next query"]}\n')
    assert mcp_embedding_protocol.read_payload(stream) == payload
    assert mcp_embedding_protocol.read_payload(stream) == {"texts": ["next query"]}
    assert mcp_embedding_protocol.read_payload(stream) is None


def test_oversize_frames_are_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(mcp_embedding_protocol, "MAX_INPUT_BYTES", 64)
    with pytest.raises(ValueError, match="byte budget"):
        mcp_embedding_protocol.encode_payload({"texts": ["x" * 64]})
    with pytest.raises(ValueError, match="byte budget"):
        mcp_embedding_protocol.read_payload(io.BytesIO(b"x" * 65))


@pytest.mark.parametrize("new_preparation", [False, True])
@pytest.mark.parametrize("expired_request", [False, True])
def test_dead_helper_state_is_queued_and_cannot_clear_new_preparation(
    db_service, qtbot, monkeypatch, new_preparation, expired_request
):
    class Process:
        def __init__(self):
            self.available = True
            self.calls = 0

        def close(self):
            self.available = False

        def encode(self, payload, expired, timeout):
            self.calls += 1
            if self.calls > 1:
                raise McpFailure("TIMEOUT")
            return {
                "vectors": base64.b64encode(
                    np.array([[1, 0]], dtype="float32").tobytes()
                ).decode(),
                "shape": [1, 2],
            }

    monkeypatch.setattr(mcp_semantic, "EmbeddingProcess", Process)
    db_service.insert_entity(Entity("King", "person"))
    expired = False
    task = McpReadTask(lambda: db_service, lambda identifier: expired)
    req = {
        **request("semantic_search", ["semantic"], query="King"),
        "request_id": "query",
        "database": str(db_service.db_path),
    }
    fallback = task._service.execute(db_service, req, lambda: False)
    revision = fallback["revision"]
    docs = [
        {
            "id": "king",
            "kind": "entity",
            "type": "person",
            "name": "King",
            "description": "Ruler",
            "text": "Ruler",
            "tags": [],
        }
    ]
    task._semantic.prepare("session", revision, "installed", docs, lambda: False)
    states, results = [], []
    task.semantic_changed.connect(states.append)
    task.finished.connect(results.append)
    try:
        task._images.submit(task._semantic_query, req, fallback, lambda: False).result(
            timeout=3
        )
        assert not task._semantic.ready("session", revision)
        assert states == []
        if new_preparation:
            task._semantic.prepare(
                "session", revision, "installed", docs, lambda: False
            )
        expired = expired_request
        qtbot.waitUntil(lambda: bool(results))
        if expired_request:
            assert results[0]["result"]["status"] == "UNAVAILABLE"
        else:
            assert (
                results[0]["result"]["data"]["fallback_reason"] == "model_unavailable"
            )
        if new_preparation:
            assert states == [] and task._semantic.ready("session", revision)
        else:
            assert states == [{"generation": "session", "state": "unavailable"}]
            assert task._semantic.documents == [] and task._semantic.vectors is None
    finally:
        task.reset()
        task._images.shutdown(wait=True)
        task.deleteLater()
