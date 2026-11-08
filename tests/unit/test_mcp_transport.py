"""Real local transport, credential discovery, protocol and revocation checks."""

import asyncio
import json
import sys
import threading

import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from src.core.mcp_access import TOOLS, McpFailure, failure
from src.integrations.mcp.discovery import SessionDiscovery
from src.integrations.mcp.server import LocalMcpServer
from src.services.mcp_session import McpSession

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def server(tmp_path):
    ready = threading.Event()
    published = {}
    session = None

    def dispatch(request):
        session.complete(
            {
                "request_id": request["request_id"],
                "result": {
                    "status": "OK",
                    "data": {"id": "world-test"},
                },
            }
        )

    session = McpSession({"world_id": "world-test"}, dispatch)
    discovery = SessionDiscovery(tmp_path / "mcp")

    def started(value):
        published.update(value)
        ready.set()

    transport = LocalMcpServer(session, discovery, started)
    transport.start()
    assert ready.wait(8)
    assert "error" not in published
    yield transport, discovery, session, published["port"]
    transport.stop()
    transport.join(8)
    assert not transport.is_alive()
    assert not (discovery.directory / "session.bin").exists()


def test_discovery_encryption_ownership_and_revocation(server):
    transport, discovery, session, port = server
    assert discovery.read()["port"] == port
    assert (
        session.token.encode() not in (discovery.directory / "session.bin").read_bytes()
    )
    other = SessionDiscovery(discovery.directory)
    with pytest.raises(Exception):
        other.acquire()
    other.close()
    assert discovery.read()["port"] == port
    transport.stop()
    assert not session.active


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_sdk_discovery_and_real_tool_calls(server, mode):
    _, _, session, port = server

    async def run():
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {session.token}"},
            follow_redirects=False,
            trust_env=False,
        ) as http:
            async with Client(
                streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp", http_client=http
                ),
                cache=None,
                mode=mode,
            ) as client:
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == set(TOOLS)
                result = await client.call_tool("get_active_world")
                assert result.structured_content["data"]["id"] == "world-test"
                for tool, arguments in (
                    ("get_world_overview", {}),
                    ("browse_world", {"kinds": ["event"], "date_from": 1}),
                    (
                        "get_objects",
                        {
                            "objects": [{"kind": "entity", "id": "a"}],
                            "detail": "compact",
                        },
                    ),
                    ("get_object", {"kind": "event", "id": "a", "detail": "compact"}),
                    (
                        "get_context",
                        {
                            "kind": "entity",
                            "id": "a",
                            "mode": "all_history",
                            "detail": "compact",
                        },
                    ),
                    (
                        "list_connections",
                        {"entity_id": "a", "mode": "all_history", "detail": "compact"},
                    ),
                ):
                    result = await client.call_tool(tool, arguments)
                    assert result.structured_content["status"] == "OK"

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_real_stdio_relay_new_tools_and_compact_arguments(server, mode):
    _, discovery, session, _ = server
    captured = []
    original = session._dispatch

    def dispatch(request):
        captured.append(request)
        if request["tool"] == "get_image_preview":
            session.complete(
                {
                    "request_id": request["request_id"],
                    "result": {
                        "status": "OK",
                        "data": {"source_id": "map-a"},
                        "_image": "aW1hZ2U=",
                    },
                }
            )
            return
        original(request)

    session._dispatch = dispatch
    # Use isolated discovery, leaving any actual user's enabled session untouched.
    bootstrap = (
        "import sys; from pathlib import Path; "
        "from src.integrations.mcp import connector; "
        "from src.integrations.mcp.discovery import SessionDiscovery; "
        "connector.SessionDiscovery=lambda: SessionDiscovery(Path(sys.argv[1])); "
        "connector.main()"
    )

    async def run():
        async with Client(
            StdioServerParameters(
                command=sys.executable,
                args=["-c", bootstrap, str(discovery.directory)],
            ),
            cache=None,
            mode=mode,
        ) as client:
            catalogue = await client.list_tools()
            assert {tool.name for tool in catalogue.tools} == set(TOOLS)
            arguments = {
                "objects": [{"kind": "entity", "id": "a"}],
                "detail": "compact",
            }
            result = await client.call_tool("get_objects", arguments)
            assert result.structured_content["status"] == "OK"
            assert captured[-1]["arguments"] == arguments
            for name in ("get_world_overview", "browse_world"):
                result = await client.call_tool(name, {})
                assert result.structured_content["status"] == "OK"
            image = await client.call_tool(
                "get_image_preview", {"source_kind": "map", "source_id": "map-a"}
            )
            assert image.content[-1].type == "image"
            assert image.content[-1].data == "aW1hZ2U="
            assert "_image" not in image.structured_content

    asyncio.run(run())


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Origin": "https://attacker.example"}, 403),
        ({"Host": "attacker.example"}, 403),
    ],
)
def test_invalid_access_returns_no_data(server, override, expected):
    _, _, session, port = server
    headers = {"Authorization": f"Bearer {session.token}", **override}
    result = httpx.post(f"http://127.0.0.1:{port}/mcp", headers=headers, json={})
    assert result.status_code == expected
    assert "world-test" not in result.text


def test_size_path_and_revoked_credentials(server):
    _, _, session, port = server
    base = f"http://127.0.0.1:{port}"
    headers = {"Authorization": f"Bearer {session.token}"}
    assert (
        httpx.post(base + "/mcp", headers=headers, content=b"x" * 17000).status_code
        == 413
    )
    assert httpx.post(base + "/mcp?token=bad", headers=headers).status_code == 404
    assert httpx.get(base + "/docs", headers=headers).status_code == 404
    session.revoke()
    assert httpx.post(base + "/mcp", headers=headers).status_code == 403


def test_revocation_discards_pending_response():
    requests = []
    session = McpSession({}, requests.append)

    async def run():
        pending = asyncio.create_task(session.call("get_active_world", {}))
        await asyncio.sleep(0)
        assert len(requests) == 1
        session.revoke()
        session.complete(
            {
                "request_id": requests[0]["request_id"],
                "result": {"data": "must not escape"},
            }
        )
        result = await pending
        assert result["status"] == "UNAVAILABLE"
        assert "must not escape" not in json.dumps(result)

    asyncio.run(run())


def test_unsafe_discovery_descriptor_fails_closed(tmp_path):
    discovery = SessionDiscovery(tmp_path / "missing")
    with pytest.raises(McpFailure, match="UNAVAILABLE"):
        discovery.read()


def test_stdio_forwarder_uses_authenticated_current_session(server, monkeypatch):
    from src.integrations.mcp import connector

    _, discovery, _, _ = server
    monkeypatch.setattr(connector, "SessionDiscovery", lambda: discovery)
    result = asyncio.run(connector.forward("get_active_world", {}))
    assert result["status"] == "OK"
    assert result["data"]["id"] == "world-test"


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_relay_preserves_actionable_tool_failures_and_recovers(server, mode):
    _, discovery, session, _ = server
    original = session._dispatch

    def dispatch(request):
        code = {
            "browse_world": ("STALE_CURSOR", "INVALID_CURSOR"),
            "get_context": ("INVALID_DATE", "LORE_DAY_REQUIRED"),
        }.get(request["tool"])
        if code:
            session.complete(
                {"request_id": request["request_id"], "result": failure(*code)}
            )
        else:
            original(request)

    session._dispatch = dispatch
    bootstrap = (
        "import sys; from pathlib import Path; "
        "from src.integrations.mcp import connector; "
        "from src.integrations.mcp.discovery import SessionDiscovery; "
        "connector.SessionDiscovery=lambda: SessionDiscovery(Path(sys.argv[1])); "
        "connector.main()"
    )

    async def run():
        async with Client(
            StdioServerParameters(
                command=sys.executable, args=["-c", bootstrap, str(discovery.directory)]
            ),
            cache=None,
            mode=mode,
        ) as client:
            for name, args, reason in [
                ("browse_world", {"cursor": "bad"}, "INVALID_CURSOR"),
                (
                    "get_context",
                    {"kind": "entity", "id": "a", "mode": "at_playhead"},
                    "LORE_DAY_REQUIRED",
                ),
            ]:
                response = await client.call_tool(name, args)
                assert response.is_error
                assert response.structured_content["reason_code"] == reason
                assert response.structured_content["retryable"] is False
                healthy = await client.call_tool("get_active_world", {})
                assert healthy.structured_content["status"] == "OK"

    asyncio.run(run())


@pytest.mark.parametrize("concurrency", [1, 2, 4, 5])
def test_parallel_bridge_calls_return_busy_or_success_not_unavailable(
    server, monkeypatch, concurrency
):
    from src.integrations.mcp import connector

    _, discovery, _, _ = server
    monkeypatch.setattr(connector, "SessionDiscovery", lambda: discovery)

    async def run():
        results = await asyncio.gather(
            *(connector.forward("get_active_world", {}) for _ in range(concurrency))
        )
        assert all(result["status"] in {"OK", "BUSY"} for result in results)
        assert all(
            result["retryable"] for result in results if result["status"] == "BUSY"
        )
        assert (await connector.forward("get_active_world", {}))["status"] == "OK"

    asyncio.run(run())


def test_interrupted_http_bridge_is_retryable_and_next_read_recovers(
    server, monkeypatch
):
    from src.integrations.mcp import connector
    from src.integrations.mcp import server as module

    _, discovery, _, _ = server
    monkeypatch.setattr(connector, "SessionDiscovery", lambda: discovery)
    original = module.LocalAccessGuard._serve_http
    interrupt = True

    async def serve(self, scope, receive, send):
        nonlocal interrupt
        if interrupt:
            interrupt = False
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            raise ConnectionResetError("Fixture interrupted the response")
        await original(self, scope, receive, send)

    monkeypatch.setattr(module.LocalAccessGuard, "_serve_http", serve)
    broken = asyncio.run(connector.forward("get_active_world", {}))
    assert broken["status"] == "TRANSIENT_FAILURE" and broken["retryable"]
    assert asyncio.run(connector.forward("get_active_world", {}))["status"] == "OK"


def test_total_http_deadline_releases_admission(monkeypatch):
    from src.integrations.mcp import server as module

    monkeypatch.setattr(module, "DEADLINE_SECONDS", 0.02)
    session = McpSession({}, lambda request: None)

    async def slow(scope, receive, send):
        await asyncio.sleep(1)

    guard = module.LocalAccessGuard(slow, session, 12345)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=guard), base_url="http://127.0.0.1:12345"
        ) as client:
            result = await client.post(
                "/mcp", headers={"Authorization": f"Bearer {session.token}"}
            )
            assert result.status_code == 504
            assert guard._pending == 0

    asyncio.run(run())
