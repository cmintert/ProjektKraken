"""Actionable MCP errors, complete audit reads and observed time semantics."""

import asyncio
import json
import sqlite3
import uuid

import httpx2
import pytest
from mcp.shared.exceptions import MCPError

from src.core.calendar import (
    CalendarConfig,
    CalendarConverter,
    LeapYearRule,
    MonthDefinition,
    YearVariant,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.mcp_access import McpFailure, failure
from src.integrations.mcp.errors import bridge_failure
from src.services.mcp_read_service import McpReadService
from src.services.repositories.calendar_repository import CalendarRepository
from tests.unit.test_mcp_reliable_reads import read, request

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize(
    "error,status,reason,retryable",
    [
        (
            McpFailure("STALE_CURSOR", "INVALID_CURSOR"),
            "STALE_CURSOR",
            "INVALID_CURSOR",
            False,
        ),
        (
            McpFailure("INVALID_DATE", "LORE_DAY_REQUIRED"),
            "INVALID_DATE",
            "LORE_DAY_REQUIRED",
            False,
        ),
        (
            httpx2.ConnectError("secret local path"),
            "UNAVAILABLE",
            "APP_UNREACHABLE",
            True,
        ),
        (
            httpx2.ReadError("secret auth value"),
            "TRANSIENT_FAILURE",
            "CONNECTION_INTERRUPTED",
            True,
        ),
        (TimeoutError("secret"), "TIMEOUT", "REQUEST_DEADLINE_EXCEEDED", True),
        (
            MCPError(-32602, "secret input"),
            "INVALID_INPUT",
            "TOOL_ARGUMENTS_INVALID",
            False,
        ),
        (
            MCPError(-32001, "secret timeout"),
            "TIMEOUT",
            "REQUEST_DEADLINE_EXCEEDED",
            True,
        ),
        (
            MCPError(-32000, "secret disconnect"),
            "TRANSIENT_FAILURE",
            "CONNECTION_INTERRUPTED",
            True,
        ),
        (
            ValueError("secret response"),
            "PROTOCOL_ERROR",
            "UNEXPECTED_BRIDGE_FAILURE",
            False,
        ),
    ],
)
def test_bridge_errors_remain_specific_and_content_free(
    error, status, reason, retryable
):
    for wrapped in (error, ExceptionGroup("SDK group", [error])):
        data = bridge_failure(wrapped)
        assert (data["status"], data["reason_code"], data["retryable"]) == (
            status,
            reason,
            retryable,
        )
        assert "secret" not in json.dumps(data)
        assert data["data"] is None


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "UNAVAILABLE"),
        (403, "UNAVAILABLE"),
        (408, "TIMEOUT"),
        (413, "REQUEST_TOO_LARGE"),
        (429, "BUSY"),
        (502, "TRANSIENT_FAILURE"),
        (503, "TRANSIENT_FAILURE"),
        (504, "TIMEOUT"),
        (500, "PROTOCOL_ERROR"),
    ],
)
def test_http_recovery_is_based_on_status_not_error_prose(status, expected):
    request = httpx2.Request("POST", "http://127.0.0.1/mcp")
    error = httpx2.HTTPStatusError(
        "private exception text",
        request=request,
        response=httpx2.Response(status, request=request),
    )
    assert bridge_failure(error)["status"] == expected
    assert "private" not in json.dumps(bridge_failure(error))


def test_invalid_dates_and_cursors_are_distinct_before_transport(db_service):
    entity = Entity("Root", "person")
    db_service.insert_entity(entity)
    db_service.insert_entity(Entity("Other", "person"))
    with pytest.raises(McpFailure) as missing:
        read(db_service, "get_context", kind="entity", id=entity.id, mode="at_playhead")
    assert missing.value.as_result() == failure("INVALID_DATE", "LORE_DAY_REQUIRED")
    assert missing.value.as_result()["required_fields"] == ["lore_day"]
    with pytest.raises(McpFailure) as invalid:
        read(db_service, "browse_world", cursor="bad cursor")
    assert invalid.value.as_result()["reason_code"] == "INVALID_CURSOR"
    service = McpReadService()
    page = read(db_service, "browse_world", service, limit=1)["data"]
    token = page["next_cursor"]
    with pytest.raises(McpFailure) as mismatch:
        read(db_service, "browse_world", service, limit=2, cursor=token)
    assert mismatch.value.as_result()["reason_code"] == "CURSOR_BINDING_MISMATCH"
    service._cursors[token]["expires"] = 0
    with pytest.raises(McpFailure) as expired:
        read(db_service, "browse_world", service, limit=1, cursor=token)
    assert expired.value.as_result()["reason_code"] == "CURSOR_EXPIRED"


@pytest.mark.parametrize(
    "scopes", [[], ["attachments"], ["attachments", "images"], ["maps", "images"]]
)
def test_context_omission_is_not_a_session_scope_or_attachment_count(
    db_service, scopes
):
    entity = Entity("Root", "person")
    db_service.insert_entity(entity)
    for tool, args in [
        ("get_context", {}),
        ("read_context_section", {"section": "attributes"}),
    ]:
        data = read(
            db_service,
            tool,
            scopes=scopes,
            kind="entity",
            id=entity.id,
            mode="all_history",
            **args,
        )["data"]
        policy = data["attachment_access"]
        assert policy["included_by_this_tool"] is False
        assert policy["session_metadata_scope_enabled"] is ("attachments" in scopes)
        assert policy["session_attachment_images_enabled"] is (
            "attachments" in scopes and "images" in scopes
        )
        assert policy["legacy_flag_is_count"] is False


def test_calendar_rules_round_trip_and_stale_pages(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    config.leap_year_rules = [
        LeapYearRule(4, 100, 400, 1, 1),
        LeapYearRule(7, 0, 0, 0, 2),
    ]
    config.year_variants = [
        YearVariant(year, [MonthDefinition(f"M{year}", "M", 13)])
        for year in range(-2, 32)
    ]
    db_service.insert_calendar_config(config)
    inactive = CalendarConfig.create_default()
    db_service.insert_calendar_config(inactive)
    for section in ("months", "leap_year_rules", "year_variants"):
        service, rows, cursor = McpReadService(), [], None
        while True:
            data = read(
                db_service,
                "read_calendar_section",
                service,
                section=section,
                limit=2,
                cursor=cursor,
            )["data"]
            assert data["calendar_id"] == config.id
            rows.extend(data["rows"])
            cursor = data["next_cursor"]
            if cursor is None:
                break
        assert rows == config.to_dict()[section]
    week = read(db_service, "read_calendar_section", section="week")["data"]["rows"][0]
    assert week == config.week.to_dict()
    summary = read(db_service, "read_calendar_section")["data"]["rows"][0]
    assert summary["month_index_base"] == 0
    assert "first_matching_year_variant" in summary["rule_precedence"]
    assert config.get_months_for_year(0) == config.year_variants[2].months
    assert (
        read(db_service, "read_calendar_section", calendar_id=inactive.id)["data"][
            "calendar_id"
        ]
        == inactive.id
    )
    service = McpReadService()
    first = read(
        db_service, "read_calendar_section", service, section="months", limit=1
    )["data"]
    db_service.insert_entity(Entity("Revision changed", "person"))
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        read(
            db_service,
            "read_calendar_section",
            service,
            section="months",
            limit=1,
            cursor=first["next_cursor"],
        )


def test_calendar_absence_is_not_empty_rules_or_gregorian_default(db_service):
    CalendarRepository(db_service.require_connection()).clear_active()
    assert read(db_service, "list_calendars")["data"]["rows"] == []
    with pytest.raises(McpFailure) as error:
        read(db_service, "read_calendar_section")
    assert error.value.as_result()["reason_code"] == "NO_ACTIVE_CALENDAR"
    with pytest.raises(McpFailure) as error:
        read(db_service, "read_calendar_section", calendar_id="missing")
    assert error.value.as_result()["reason_code"] == "CALENDAR_NOT_FOUND"


def test_large_calendar_variant_has_recoverable_exact_month_pages(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    months = [
        MonthDefinition(str(index) + "長" * 500, str(index), index + 1)
        for index in range(80)
    ]
    config.year_variants = [YearVariant(-1, months)]
    db_service.insert_calendar_config(config)
    with pytest.raises(McpFailure, match="RESULT_TOO_LARGE"):
        read(db_service, "read_calendar_section", section="year_variants")
    summaries = read(
        db_service, "read_calendar_section", section="year_variant_summaries"
    )["data"]["rows"]
    assert summaries == [{"variant_index": 0, "year": -1, "month_count": 80}]
    rows, cursor, service = [], None, McpReadService()
    while True:
        page = read(
            db_service,
            "read_calendar_section",
            service,
            section="year_variant_months",
            variant_index=0,
            cursor=cursor,
        )["data"]
        rows.extend(page["rows"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert rows == [month.to_dict() for month in months]


def test_calendar_inventory_is_paged_without_changing_activation(db_service):
    configs = [CalendarConfig.create_default() for _ in range(3)]
    configs[0].is_active = True
    for config in configs:
        db_service.insert_calendar_config(config)
    service, rows, cursor = McpReadService(), [], None
    before = db_service.require_connection().total_changes
    while True:
        page = read(db_service, "list_calendars", service, limit=1, cursor=cursor)[
            "data"
        ]
        rows.extend(page["rows"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert [row["id"] for row in rows] == sorted(config.id for config in configs)
    assert [row["id"] for row in rows if row["is_active"]] == [configs[0].id]
    assert db_service.require_connection().total_changes == before


def test_world_relationship_inventory_reconciles_every_endpoint_pair(db_service):
    entities = [Entity(str(index), "person") for index in range(2)]
    events = [Event(str(index), float(index)) for index in range(2)]
    for entity in entities:
        db_service.insert_entity(entity)
    for event in events:
        db_service.insert_event(event)
    pairs = [
        (entities[0].id, entities[1].id),
        (entities[0].id, events[0].id),
        (events[0].id, entities[0].id),
        (events[0].id, events[1].id),
        (events[0].id, events[0].id),
        (events[0].id, events[1].id),
        (events[0].id, str(uuid.uuid4())),
    ]
    ids = set()
    # Storage-level fixture intentionally includes parallel and legacy dangling rows.
    db_service.require_connection().execute(
        "DROP TRIGGER validate_relation_endpoints_insert"
    )
    for source, target in pairs:
        identity = str(uuid.uuid4())
        ids.add(identity)
        db_service.require_connection().execute(
            "INSERT INTO relations(id,source_id,target_id,rel_type,attributes,created_at) VALUES (?,?,?,?,?,?)",
            (identity, source, target, "linked", '{"private":"never loaded"}', 0.0),
        )
    overview = read(db_service, "get_world_overview")
    counts = overview["data"]["counts"]["relationships"]
    assert counts["total_saved"] == len(ids) == 7
    assert counts["by_endpoint_kinds"]["event_to_event"] == 3
    assert counts["by_endpoint_kinds"]["unresolved_or_ambiguous"] == 1
    assert sum(counts["by_endpoint_kinds"].values()) == 7
    service, rows, cursor = McpReadService(), [], None
    while True:
        page = read(
            db_service,
            "browse_relationships",
            service,
            limit=2,
            cursor=cursor,
            expected_revision=overview["revision"],
        )["data"]
        rows.extend(page["rows"])
        assert page["attributes_included"] is False
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert {row["id"] for row in rows} == ids and len(rows) == len(ids)
    assert "never loaded" not in json.dumps(rows)
    filtered = read(
        db_service, "browse_relationships", source_kind="event", target_kind="event"
    )["data"]["rows"]
    assert len(filtered) == 3


def test_time_context_separates_saved_now_displayed_now_and_playhead(db_service):
    db_service.set_current_time(-2.0)
    req = request("get_time_context")
    req["view_context"] = {
        "world_now": 3.0,
        "playhead": 0.0,
        "view_version": 7,
        "observed_at_utc": "2026-11-08T12:00:00+00:00",
        "system_time": {"utc": "2026-11-08T12:00:00+00:00", "utc_offset_seconds": 3600},
    }
    service = McpReadService()
    first = service.execute(db_service, req, lambda: False)
    assert first["data"]["world_now"]["lore_day"] == -2.0
    assert first["data"]["displayed_world_now"]["lore_day"] == 3.0
    assert first["data"]["playhead"]["lore_day"] == 0.0
    req["view_context"]["playhead"] = -1.0
    req["view_context"]["view_version"] = 8
    second = service.execute(db_service, req, lambda: False)
    assert second["revision"] == first["revision"]
    assert second["data"]["view_version"] == 8
    assert second["data"]["playhead"]["lore_day"] == -1.0
    assert second["data"]["calendar_id"] is None
    assert second["data"]["playhead"]["caption"] is None
    missing = read(db_service, "get_time_context")["data"]
    assert missing["playhead"]["lore_day"] is None


def test_event_only_edges_and_ambiguous_identity_remain_auditable(db_service):
    events = [Event(str(index), float(index)) for index in range(2)]
    for event in events:
        db_service.insert_event(event)
    identity = db_service.insert_relation(events[0].id, events[1].id, "precedes", {})
    counts = read(db_service, "get_world_overview")["data"]["counts"]
    assert counts["entity"]["total"] == 0
    assert counts["relationships"]["by_endpoint_kinds"]["event_to_event"] == 1
    page = read(db_service, "browse_relationships")["data"]
    assert page["rows"][0]["id"] == identity
    # A legacy cross-kind ID collision must not be silently classified as Entity.
    db_service.require_connection().execute(
        "INSERT INTO entities(id,type,name,attributes) VALUES (?,?,?,?)",
        (events[0].id, "person", "Collision", "{}"),
    )
    changed = read(db_service, "get_world_overview")["data"]["counts"]["relationships"]
    assert changed["total_saved"] == 1
    assert changed["by_endpoint_kinds"]["unresolved_or_ambiguous"] == 1
    assert (
        read(db_service, "browse_relationships")["data"]["rows"][0]["source"]["kind"]
        == "ambiguous"
    )


def test_relationship_pages_reject_a_changed_world(db_service):
    events = [Event(str(index), float(index)) for index in range(3)]
    for event in events:
        db_service.insert_event(event)
    for target in events[1:]:
        db_service.insert_relation(events[0].id, target.id, "precedes", {})
    service = McpReadService()
    first = read(db_service, "browse_relationships", service, limit=1)
    db_service.insert_entity(Entity("New saved revision", "person"))
    with pytest.raises(McpFailure, match="STALE_CURSOR"):
        read(
            db_service,
            "browse_relationships",
            service,
            limit=1,
            cursor=first["data"]["next_cursor"],
        )


def test_session_admission_limit_recovery_and_revocation():
    from src.services.mcp_session import McpSession

    async def exercise():
        submitted = []
        session = McpSession({}, submitted.append)
        pending = [
            asyncio.create_task(session.call("get_active_world", {})) for _ in range(4)
        ]
        await asyncio.sleep(0)
        busy = await session.call("get_active_world", {})
        assert busy["status"] == "BUSY" and busy["retryable"]
        for item in submitted:
            session.complete(
                {
                    "request_id": item["request_id"],
                    "result": {"status": "OK", "data": {}},
                }
            )
        assert all(
            result["status"] == "OK" for result in await asyncio.gather(*pending)
        )
        session.revoke("SHARING_DISABLED")
        ended = await session.call("get_active_world", {})
        assert ended["reason_code"] == "SHARING_DISABLED" and not ended["retryable"]

    asyncio.run(exercise())


def test_absent_discovery_does_not_guess_app_or_world_state(tmp_path):
    from src.integrations.mcp.discovery import SessionDiscovery

    with pytest.raises(McpFailure) as error:
        SessionDiscovery(tmp_path / "absent").read()
    data = error.value.as_result()
    assert data["reason_code"] == "NO_ACTIVE_SESSION"
    assert not data["retryable"] and data["restart_required"]


def test_time_caption_uses_saved_calendar_and_keeps_fractional_day(db_service):
    config = CalendarConfig.create_default()
    config.is_active = True
    db_service.insert_calendar_config(config)
    req = request("get_time_context")
    req["view_context"] = {"playhead": 0.5, "world_now": 0.0, "view_version": 1}
    data = McpReadService().execute(db_service, req, lambda: False)["data"]
    assert data["playhead"]["lore_day"] == 0.5
    assert data["playhead"]["caption"] == CalendarConverter(config).format_datetime(0.5)
    assert data["calendar_id"] == config.id


@pytest.mark.parametrize(
    "number,reason",
    [(2, "NO_ACTIVE_SESSION"), (5, "UNSAFE_DISCOVERY"), (13, "INVALID_DISCOVERY")],
)
def test_discovery_win32_errors_are_classified_without_prose(
    tmp_path, monkeypatch, number, reason
):
    from src.integrations.mcp import discovery

    folder = tmp_path / "discovery"
    folder.mkdir()
    (folder / "session.bin").write_bytes(b"fixture")

    class WindowsFailure(Exception):
        winerror = number

    def protect(*args, **kwargs):
        raise WindowsFailure("private OS details")

    monkeypatch.setattr(discovery, "protect", protect)
    with pytest.raises(McpFailure) as error:
        discovery.SessionDiscovery(folder).read()
    data = error.value.as_result()
    assert data["reason_code"] == reason
    assert "private" not in json.dumps(data)


def test_worker_database_busy_remains_retryable(db_service, qtbot, monkeypatch):
    from src.services.mcp_read_task import McpReadTask

    task = McpReadTask(lambda: db_service, lambda identifier: False)
    problem = sqlite3.OperationalError("private database details")
    problem.sqlite_errorcode = sqlite3.SQLITE_BUSY

    def execute(*args):
        raise problem

    monkeypatch.setattr(task._service, "execute", execute)
    results = []
    task.finished.connect(results.append)
    task.run(
        {
            **request("get_active_world"),
            "request_id": "busy",
            "database": str(db_service.db_path),
        }
    )
    assert results[0]["result"]["status"] == "BUSY"
    assert results[0]["result"]["reason_code"] == "DATABASE_BUSY"
    assert results[0]["result"]["retryable"]
    assert "private" not in json.dumps(results)
    task._images.shutdown(wait=True)
    task.deleteLater()


def test_missing_bridge_envelope_is_protocol_error_not_absent_sharing(monkeypatch):
    from mcp.types import CallToolResult, TextContent

    from src.integrations.mcp import connector

    class Discovery:
        def read(self):
            return {"port": 1, "token": "fixture-not-a-credential"}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def call_tool(self, *args):
            return CallToolResult(
                is_error=True,
                content=[TextContent(type="text", text="private unstructured prose")],
            )

    monkeypatch.setattr(connector, "SessionDiscovery", Discovery)
    monkeypatch.setattr(connector, "Client", Client)
    result = asyncio.run(connector.forward("get_active_world", {}))
    assert result["status"] == "PROTOCOL_ERROR"
    assert "private" not in json.dumps(result)
