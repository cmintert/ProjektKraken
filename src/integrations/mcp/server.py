"""Authenticated loopback-only MCP transport on an independent network thread."""

from __future__ import annotations

import asyncio
import secrets
import socket
import threading
from collections.abc import Callable
from typing import Any

import uvicorn
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.mcp_access import DEADLINE_SECONDS, MAX_PENDING, MAX_REQUEST_BYTES
from src.integrations.mcp.discovery import SessionDiscovery
from src.integrations.mcp.tools import create_catalogue
from src.services.mcp_session import McpSession


class LocalAccessGuard:
    """Authenticate and bound every protocol request before it reaches the SDK."""

    def __init__(self, app: ASGIApp, session: McpSession, port: int) -> None:
        """Keep application credentials separate from MCP protocol session IDs."""
        self.app, self.session, self.port = app, session, port
        self._pending = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject browser origins, ambiguous headers, paths and oversized bodies."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers", [])
        values: dict[bytes, list[bytes]] = {}
        for key, val in headers:
            values.setdefault(key.lower(), []).append(val)
        status = self._reject(scope, values)
        if status:
            await PlainTextResponse("Local MCP access denied", status)(
                scope, receive, send
            )
            return
        self._pending += 1
        started = False

        async def timed_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            async with asyncio.timeout(DEADLINE_SECONDS):
                await self._serve_http(scope, receive, timed_send)
        except TimeoutError:
            if not started:
                await PlainTextResponse("Request timed out", 504)(scope, receive, send)
            else:
                await send(
                    {"type": "http.response.body", "body": b"", "more_body": False}
                )
        finally:
            self._pending -= 1

    async def _serve_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Bound the body before handing the request to the SDK."""
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > MAX_REQUEST_BYTES:
                        await PlainTextResponse("Request too large", 413)(
                            scope, receive, send
                        )
                        return
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await PlainTextResponse("Request timed out", 408)(scope, receive, send)
            return
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body)}
            return await receive()

        async def checked_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() != b"content-length"
                    ]
                    + [(b"cache-control", b"no-store")],
                }
            if not self.session.active:
                # Do not release a queued response after revocation.
                if message["type"] == "http.response.start":
                    message = {**message, "status": 403}
                elif message["type"] == "http.response.body":
                    message = {**message, "body": b"", "more_body": False}
            await send(message)

        await self.app(scope, replay, checked_send)

    def _reject(self, scope: Scope, headers: dict[bytes, list[bytes]]) -> int:
        if not self.session.active:
            return 403
        if scope.get("path") != "/mcp" or scope.get("query_string"):
            return 404
        if scope.get("method") not in {"GET", "POST", "DELETE"}:
            return 405
        if b"origin" in headers:
            return 403
        if headers.get(b"host") != [f"127.0.0.1:{self.port}".encode()]:
            return 403
        supplied = headers.get(b"authorization", [])
        expected = f"Bearer {self.session.token}".encode()
        if len(supplied) != 1 or not secrets.compare_digest(supplied[0], expected):
            return 401
        if self._pending >= MAX_PENDING:
            return 429
        return 0


class LocalMcpServer(threading.Thread):
    """Own network startup, publication and shutdown without touching Qt or SQL."""

    def __init__(
        self,
        session: McpSession,
        discovery: SessionDiscovery,
        ready: Callable[[dict[str, Any]], None],
    ) -> None:
        """Prepare resources without listening until the thread is started."""
        super().__init__(name="KrakenMCP", daemon=True)
        self.session, self.discovery, self.ready = session, discovery, ready
        self._server: uvicorn.Server | None = None

    def run(self) -> None:
        """Fail closed if binding or protected credential publication fails."""
        try:
            asyncio.run(self._serve())
        except Exception:
            self.session.revoke()
            self.ready({"error": "Local MCP could not start securely."})
        finally:
            self.discovery.close()

    async def _serve(self) -> None:
        self.discovery.acquire()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            port = listener.getsockname()[1]
            sdk = create_catalogue(self.session.call)
            app = LocalAccessGuard(
                sdk.streamable_http_app(
                    json_response=True,
                    stateless_http=True,
                    max_request_body_size=MAX_REQUEST_BYTES,
                ),
                self.session,
                port,
            )
            config = uvicorn.Config(
                app,
                log_config=None,
                access_log=False,
                lifespan="on",
                timeout_graceful_shutdown=1,
                limit_concurrency=16,
                ws="none",
            )
            self._server = uvicorn.Server(config)
            serving = asyncio.create_task(self._server.serve(sockets=[listener]))
            try:
                while not self._server.started and not serving.done():
                    if not self.session.active:
                        self._server.should_exit = True
                    await asyncio.sleep(0.01)
                if self._server.started and self.session.active:
                    self.discovery.publish(port, self.session)
                    self.ready({"port": port})
                await serving
            finally:
                self._server.should_exit = True
                await serving

    def stop(self) -> None:
        """Revoke immediately; allow the network thread to finish asynchronously."""
        self.session.revoke()
        if self._server is not None:
            self._server.should_exit = True
