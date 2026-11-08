"""Cross-call consistency, complete sections, scoped reads and offline inference."""

import asyncio
import base64
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.core.entities import Entity
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.map import Map, MapLayerNode
from src.core.marker import Marker
from src.core.mcp_access import MAX_RESULT_BYTES, McpFailure, failure
from src.integrations.mcp.tools import create_catalogue
from src.services.mcp_images import decode_image, image_job
from src.services.mcp_read_service import McpReadService
from src.services.mcp_semantic import McpSemanticIndex
from src.services.mcp_semantic_preparation import SemanticPreparation

pytestmark = pytest.mark.ci_fast


def request(tool, scopes=(), **arguments):
    return {
        "tool": tool,
        "arguments": arguments,
        "world_id": "world",
        "world_name": "World",
        "generation": "session",
        "scopes": scopes,
    }


def read(db, tool, service=None, scopes=(), **arguments):
    return (service or McpReadService()).execute(
        db, request(tool, scopes, **arguments), lambda: False
    )


@pytest.mark.parametrize(
    "key", ["expected_revision", "expected_world_id", "expected_session_generation"]
)
def test_preconditions_reject_replacement_facts(db_service, key):
    with pytest.raises(McpFailure, match="WORLD_CHANGED"):
        read(db_service, "get_world_overview", **{key: "other"})
    envelope = read(db_service, "get_active_world")
    assert (
        read(
            db_service,
            "get_world_overview",
            expected_revision=envelope["revision"],
            expected_world_id="world",
            expected_session_generation="session",
        )["status"]
        == "OK"
    )


def test_exact_large_unicode_text_reconstructs_and_rejects_stale_page(db_service):
    entity = Entity("City", "place", 'é🦑漢字\\"\n' * 15000)
    db_service.insert_entity(entity)
    service = McpReadService()
    summary = read(db_service, "get_object_summary", kind="entity", id=entity.id)
    assert summary["data"]["sections"]["description"]["length"] == len(
        entity.description
    )
    parts, cursor = [], None
    while True:
        page = read(
            db_service,
            "read_object_section",
            service,
            kind="entity",
            id=entity.id,
            section="description",
            cursor=cursor,
        )
        assert len(json.dumps(page).encode()) <= MAX_RESULT_BYTES
        parts.append(page["data"]["text"])
        cursor = page["data"]["next_cursor"]
        if cursor is None:
            break
    assert "".join(parts) == entity.description
    first = read(
        db_service,
        "read_object_section",
        service,
        kind="entity",
        id=entity.id,
        section="description",
    )
    db_service.insert_entity(Entity("Another", "place"))
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        read(
            db_service,
            "read_object_section",
            service,
            kind="entity",
            id=entity.id,
            section="description",
            cursor=first["data"]["next_cursor"],
        )


def test_unbudgeted_historical_section_keeps_complete_value_and_source(db_service):
    entity = Entity("Queen", "person", attributes={"rank": "citizen"})
    event = Event("Coronation", 100)
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    prose = "Complete royal history. " * 600
    relation = db_service.insert_relation(
        event.id,
        entity.id,
        "changes",
        {
            "valid_from": 100,
            "payload": {"description": prose, "attributes": {"rank": "queen"}},
        },
    )
    service = McpReadService()
    result = read(
        db_service,
        "read_context_section",
        service,
        kind="entity",
        id=entity.id,
        mode="at_playhead",
        lore_day=110,
        section="effective_description",
    )["data"]
    parts = [result["text"]]
    while result["next_cursor"]:
        result = read(
            db_service,
            "read_context_section",
            service,
            kind="entity",
            id=entity.id,
            mode="at_playhead",
            lore_day=110,
            section="effective_description",
            cursor=result["next_cursor"],
        )["data"]
        assert result["source"]["relation_id"] == relation
        parts.append(result["text"])
    assert "".join(parts) == prose


def test_context_attributes_are_whole_values_and_private_names_stay_hidden(db_service):
    entity = Entity(
        "Test",
        "person",
        attributes={"meaning": {"$ref": "literal", "a": [1, 2]}, "api_key": "never"},
    )
    db_service.insert_entity(entity)
    data = read(
        db_service,
        "read_object_section",
        kind="entity",
        id=entity.id,
        section="attributes",
    )["data"]
    assert data["rows"] == [
        {"name": "meaning", "value": {"$ref": "literal", "a": [1, 2]}}
    ]


def test_relevance_unicode_deep_excerpt_and_literal_wildcards(db_service):
    for entity in [
        Entity("Other", "place", "x" * 900 + "Straße found"),
        Entity("Straße", "place"),
        Entity("Straße west", "place"),
        Entity("%_ literal", "place"),
    ]:
        db_service.insert_entity(entity)
    rows = read(db_service, "search_world", query="STRASSE", ranking="relevance")[
        "data"
    ]["rows"]
    assert [row["name"] for row in rows] == ["Straße", "Straße west", "Other"]
    assert "Straße found" in rows[-1]["snippet"]
    assert rows[-1]["snippet_offset"] > 0
    assert len(read(db_service, "search_world", query="%_")["data"]["rows"]) == 1


def test_search_filters_and_facets_reconcile_legacy_tags(db_service):
    one = Entity("North", "place", attributes={"_tags": ["Campaign", "Red"]})
    db_service.insert_entity(one)
    db_service.insert_entity(
        Entity("North", "person", attributes={"_tags": ["Campaign"]})
    )
    rows = read(
        db_service,
        "search_world",
        query="North",
        types=["place"],
        tags=["campaign", "red"],
    )["data"]["rows"]
    assert [row["id"] for row in rows] == [one.id]
    assert {
        row["name"]
        for row in read(db_service, "browse_facets", category="tags")["data"]["rows"]
    } == {"Campaign", "Red"}


@pytest.mark.parametrize(
    "tool,args",
    [
        ("read_longform", {}),
        ("browse_maps", {}),
        ("read_map", {"map_id": "missing", "section": "metadata"}),
        ("list_attachments", {"kind": "entity", "id": "missing"}),
        ("get_image_preview", {"source_kind": "map", "source_id": "missing"}),
    ],
)
def test_broader_scopes_fail_before_record_access(db_service, tool, args):
    with pytest.raises(McpFailure, match="SCOPE_DISABLED"):
        read(db_service, tool, **args)


def test_longform_saved_order_references_without_metadata_mutation(db_service):
    first = Entity(
        "First",
        "place",
        attributes={"_longform": {"default": {"position": 1, "depth": 0}}},
    )
    second = Entity(
        "Second",
        "place",
        attributes={"_longform": {"default": {"position": 2, "depth": 0}}},
    )
    excluded = Entity(
        "Excluded", "place", attributes={"_longform": {"default": {"excluded": True}}}
    )
    for item in [second, first, excluded]:
        db_service.insert_entity(item)
    before = db_service.require_connection().total_changes
    rows = read(db_service, "read_longform", scopes=["longform"])["data"]["rows"]
    assert [row["id"] for row in rows] == [first.id, second.id]
    assert db_service.require_connection().total_changes == before


def test_map_layer_temporal_boundaries_and_saved_visibility(db_service):
    child = MapLayerNode(
        "Border", layer_type="region", start_date=10, end_date=20, visible=False
    )
    root = MapLayerNode("Root", children=[child])
    item = Map("Map", "assets/map.png", layers=root)
    db_service.insert_map(item)
    page = read(
        db_service,
        "read_map",
        scopes=["maps"],
        map_id=item.id,
        section="layers",
        lore_day=20,
    )["data"]
    row = next(row for row in page["rows"] if row["id"] == child.id)
    assert row["visible"] is False
    assert row["temporal_validity"]["valid"] is False
    assert "image_path" not in json.dumps(page)


def test_image_preview_containment_and_isolated_decoder(
    db_service, tmp_path, monkeypatch
):
    monkeypatch.setattr(db_service, "db_path", str(tmp_path / "world.kraken"))
    root = Path(db_service.db_path).resolve().parent
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    path = assets / "preview.png"
    Image.new("RGB", (1500, 1000), "red").save(path)
    item = Map("Map", "assets/preview.png")
    db_service.insert_map(item)
    job = image_job(
        db_service,
        request(
            "get_image_preview",
            ["images", "maps"],
            source_kind="map",
            source_id=item.id,
        ),
    )
    decoded = decode_image(job, lambda: False)
    assert decoded["dimensions"] == [1024, 683]
    assert base64.b64decode(decoded["image"]).startswith(b"\x89PNG")
    item.image_path = "../outside.png"
    db_service.insert_map(item)
    with pytest.raises(McpFailure, match="ASSET_UNAVAILABLE"):
        image_job(
            db_service,
            request(
                "get_image_preview",
                ["images", "maps"],
                source_kind="map",
                source_id=item.id,
            ),
        )


def test_protocol_schema_errors_preconditions_and_native_image():
    captured = []

    async def call(tool, arguments):
        captured.append(arguments)
        if tool == "get_object":
            return failure("NOT_FOUND")
        return {"status": "OK", "data": {"source_id": "map"}, "_image": "aW1hZ2U="}

    async def run():
        server = create_catalogue(call)
        tools = await server.list_tools()
        tool = next(tool for tool in tools if tool.name == "get_object")
        assert "expected_revision" in tool.input_schema["properties"]
        assert "status" in tool.output_schema["properties"]
        result = await server.call_tool(
            "get_object", {"kind": "entity", "id": "missing", "expected_revision": "r"}
        )
        assert result.is_error and result.structured_content["status"] == "NOT_FOUND"
        assert captured[-1]["expected_revision"] == "r"
        image = await server.call_tool(
            "get_image_preview", {"source_kind": "map", "source_id": "m"}
        )
        assert image.content[-1].type == "image"
        assert "_image" not in image.structured_content

    asyncio.run(run())


def test_semantic_index_local_public_vectors_and_stale_revision(monkeypatch):
    from src.services import mcp_semantic

    calls = []

    def embed(payload, expired, timeout):
        calls.append(payload)
        vectors = (
            np.eye(2, dtype="float32")
            if len(payload["texts"]) == 2
            else np.array([[1, 0]], dtype="float32")
        )
        return {
            "vectors": base64.b64encode(vectors.tobytes()).decode(),
            "shape": list(vectors.shape),
        }

    processes = []

    class FakeProcess:
        def __init__(self):
            self.closed = False
            processes.append(self)

        encode = staticmethod(embed)

        def close(self):
            self.closed = True

    monkeypatch.setattr(mcp_semantic, "EmbeddingProcess", FakeProcess)
    index = McpSemanticIndex()
    docs = [
        {
            "id": str(i),
            "kind": "entity",
            "type": "person",
            "name": str(i),
            "text": "public",
            "description": "Public prose",
            "tags": [],
        }
        for i in range(2)
    ]
    index.prepare("session", "revision", "installed-model", docs, lambda: False)
    assert index.ready("session", "revision")
    result = index.query(
        request("semantic_search", query="ruler", limit=1), "revision", lambda: False
    )
    assert result[0]["id"] == "0"
    assert len(processes) == 1 and len(calls) == 2
    with pytest.raises(McpFailure, match="INDEX_STALE"):
        index.query(request("semantic_search", query="ruler"), "changed", lambda: False)
    index.clear()
    assert index.documents == [] and index.vectors is None
    assert processes[0].closed


def test_semantic_unprepared_fallback_is_explicit(db_service):
    db_service.insert_entity(Entity("Ruler", "person"))
    data = read(db_service, "semantic_search", scopes=["semantic"], query="Ruler")[
        "data"
    ]
    assert data["effective_search"] == "lexical"
    assert data["fallback_reason"] == "index_not_ready"


@pytest.mark.parametrize("mode", ["all_history", "at_playhead", "history_to_playhead"])
def test_relevant_context_matches_shared_projection(db_service, monkeypatch, mode):
    from src.services import mcp_read_service

    root = Entity(
        "Root", "person", attributes={"rank": "citizen", "_tags": ["Campaign"]}
    )
    peer = Entity("Peer", "person")
    shared = Entity("Shared tag", "person", attributes={"_tags": ["Campaign"]})
    for item in (root, peer, shared):
        db_service.insert_entity(item)
    source = Event("Coronation", 10)
    db_service.insert_event(source)
    db_service.insert_relation(
        source.id,
        root.id,
        "changes",
        {"valid_from": 10, "payload": {"attributes": {"rank": "queen"}}},
    )
    db_service.insert_relation(root.id, peer.id, "ally")
    args = {"kind": "entity", "id": root.id, "mode": mode, "lore_day": 20}
    expected = read(db_service, "get_context", **args)["data"]
    monkeypatch.setattr(mcp_read_service, "_MAX_CONTEXT_INPUT_ROWS", 1)
    actual = read(db_service, "get_context", **args)["data"]
    assert actual == expected


def test_calculated_event_context_uses_resolved_date_and_connection_anchors(db_service):
    anchor = Event("Anchor", 10)
    child = Event(
        "Child",
        999,
        attributes=EventTimingDefinition(
            EndpointDefinition(
                kind="event",
                anchor_id=f"event:{anchor.id}",
                offset={"unit": "days", "value": 5},
            )
        ).apply({}),
    )
    person = Entity("Person", "person")
    other = Entity("Other", "person")
    db_service.insert_event(anchor)
    db_service.insert_event(child)
    db_service.insert_entity(person)
    db_service.insert_entity(other)
    db_service.insert_relation(
        person.id,
        other.id,
        "ally",
        {"temporal": {"start": {"anchor": {"anchor_id": f"event:{child.id}"}}}},
    )
    data = read(
        db_service, "get_context", kind="event", id=child.id, mode="all_history"
    )["data"]
    assert data["context_date"] == 15
    connections = read(
        db_service,
        "list_connections",
        entity_id=person.id,
        mode="at_playhead",
        lore_day=20,
    )["data"]
    assert len(connections["rows"]) == 1


def test_null_context_section_is_explicit(db_service):
    entity = Entity("Entity", "person")
    db_service.insert_entity(entity)
    data = read(
        db_service,
        "read_context_section",
        kind="entity",
        id=entity.id,
        mode="all_history",
        section="effective_description",
    )["data"]
    assert data["rows"] == [None]
    assert data["done"]


def test_image_activity_logs_typed_source_but_not_authored_lookalikes():
    from src.services.mcp_compact import record_ids

    assert record_ids(
        {"source_kind": "map", "source_id": "map-a", "asset_revision": "r"}
    ) == ["map-a"]
    assert (
        record_ids(
            {
                "attributes": {
                    "source_kind": "map",
                    "source_id": "fake",
                    "asset_revision": "fake",
                }
            }
        )
        == []
    )


def test_shared_search_respects_each_scope_and_keeps_document_sources(db_service):
    entity = Entity(
        "Narrative",
        "person",
        "Ruler passage",
        attributes={"_longform": {"default": {"position": 1}}},
    )
    db_service.insert_entity(entity)
    result = read(
        db_service,
        "search_shared_content",
        scopes=["longform"],
        kinds=["longform"],
        query="ruler",
    )["data"]
    assert result["rows"][0]["id"] == entity.id
    assert result["rows"][0]["object_kind"] == "entity"
    with pytest.raises(McpFailure, match="SCOPE_DISABLED"):
        read(db_service, "search_shared_content", scopes=["longform"], query="ruler")


def test_map_features_are_paged_before_geometry_materialization(
    db_service, monkeypatch
):
    item = Map("Map", "assets/map.png")
    db_service.insert_map(item)
    expected = set()
    for index in range(60):
        owner = Entity(str(index), "place")
        db_service.insert_entity(owner)
        marker = Marker(item.id, owner.id, "entity", 0.5, 0.5)
        db_service.insert_marker(marker)
        expected.add(marker.id)

    def reject_full_scan(*args):
        raise AssertionError("MCP feature paging must not load every geometry")

    monkeypatch.setattr(db_service, "get_markers_for_map", reject_full_scan)
    service, seen, cursor = McpReadService(), [], None
    while True:
        page = read(
            db_service,
            "read_map",
            service,
            scopes=["maps"],
            map_id=item.id,
            section="markers",
            cursor=cursor,
        )["data"]
        assert len(page["rows"]) <= 25
        seen.extend(row["id"] for row in page["rows"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 60
    assert set(seen) == expected


def test_outline_read_avoids_prose_and_rejects_unreachable_metadata(db_service):
    entity = Entity(
        "Orphan",
        "person",
        "long prose" * 1000,
        attributes={"_longform": {"default": {"parent_id": "missing", "position": 1}}},
    )
    db_service.insert_entity(entity)
    with pytest.raises(McpFailure, match="INVALID_DOCUMENT"):
        read(db_service, "read_longform", scopes=["longform"])


@pytest.mark.parametrize("mutate", [False, True])
def test_semantic_preparation_yields_and_copies_only_public_projection(
    db_service, qtbot, mutate
):
    for index in range(105):
        db_service.insert_entity(
            Entity(
                str(index),
                "person",
                "Public text",
                attributes={"api_key": "excluded-mcp-secret", "rank": "ruler"},
            )
        )
    submitted, states = [], []

    class Executor:
        def submit(self, *args):
            submitted.append(args)

    from PySide6.QtCore import QObject

    owner = QObject()
    preparation = SemanticPreparation(
        lambda: db_service,
        lambda identifier: False,
        McpSemanticIndex(),
        Executor(),
        owner,
    )

    def changed(state):
        states.append(state)
        if mutate and state["state"] == "preparing" and len(states) == 1:
            db_service.insert_entity(Entity("Intervening command", "person"))

    preparation.changed.connect(changed)
    preparation.prepare(
        {
            "database": db_service.db_path,
            "generation": "session",
            "request_id": "prepare-test",
            "model": "installed",
        }
    )
    qtbot.waitUntil(
        lambda: bool(submitted) or any(state["state"] == "stale" for state in states)
    )
    if mutate:
        assert not submitted
        assert states[-1]["state"] == "stale"
    else:
        assert [state["count"] for state in states] == [100, 105]
        documents = submitted[0][2]
        assert len(documents) == 105
        assert all("excluded-mcp-secret" not in doc["text"] for doc in documents)
