"""Thread-safe request ownership and revocation without Qt or transport coupling."""

import asyncio
import concurrent.futures
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any

from src.core.mcp_access import DEADLINE_SECONDS, MAX_PENDING, TOOLS, failure


class McpSession:
    """Own one revocable capability and bounded request futures."""

    def __init__(
        self,
        world: dict[str, str],
        dispatch: Callable[[dict[str, Any]], None],
        scopes: tuple[str, ...] = (),
    ) -> None:
        """Capture immutable world context when the user explicitly enables access."""
        self.world = dict(world)
        self.scopes = tuple(scopes)
        self.generation = secrets.token_urlsafe(24)
        self.token = secrets.token_urlsafe(32)
        self._dispatch = dispatch
        self._lock = threading.RLock()
        self._active = True
        self._pending: dict[
            str, tuple[float, concurrent.futures.Future[dict[str, Any]]]
        ] = {}

    @property
    def active(self) -> bool:
        """Return current authorization independently of network connection state."""
        with self._lock:
            return self._active

    def expired(self, identifier: str) -> bool:
        """Let SQL and worker boundaries check cancellation without GUI access."""
        with self._lock:
            entry = self._pending.get(identifier)
            return not self._active or entry is None or time.monotonic() >= entry[0]

    async def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Await a queued read without blocking either the GUI or network loop."""
        with self._lock:
            if not self._active:
                return failure("UNAVAILABLE")
            if tool not in TOOLS:
                return failure("INVALID_TOOL")
            if len(self._pending) >= MAX_PENDING:
                return failure("BUSY")
            identifier = secrets.token_urlsafe(18)
            future: concurrent.futures.Future[dict[str, Any]] = (
                concurrent.futures.Future()
            )
            self._pending[identifier] = (time.monotonic() + DEADLINE_SECONDS, future)
            request = {
                **self.world,
                "generation": self.generation,
                "request_id": identifier,
                "tool": tool,
                "arguments": arguments,
                "scopes": list(self.scopes),
            }
        try:
            self._dispatch(request)
            return await asyncio.wait_for(asyncio.wrap_future(future), DEADLINE_SECONDS)
        except TimeoutError:
            return failure("TIMEOUT")
        finally:
            with self._lock:
                self._pending.pop(identifier, None)

    def complete(self, response: dict[str, Any]) -> None:
        """Deliver only a still-authorized result; late completions are discarded."""
        identifier = response["request_id"]
        with self._lock:
            entry = self._pending.get(identifier)
            if entry is None or entry[1].done():
                return
            result = (
                failure("UNAVAILABLE")
                if self.expired(identifier)
                else response["result"]
            )
            entry[1].set_result(result)

    def revoke(self) -> None:
        """Close admission first and release all awaiting callers without data."""
        with self._lock:
            self._active = False
            for _, future in self._pending.values():
                if not future.done():
                    future.set_result(failure("UNAVAILABLE"))
            self._pending.clear()
