"""Transport-independent limits and failures for optional world sharing."""

from typing import Any

MAX_REQUEST_BYTES = 16 * 1024
MAX_RESULT_BYTES = 64 * 1024
PAGE_SIZE = 25
MAX_PENDING = 4
DEADLINE_SECONDS = 10.0
TOOLS = (
    "get_active_world",
    "search_world",
    "get_object",
    "get_objects",
    "get_world_overview",
    "browse_world",
    "get_context",
    "list_connections",
)
DISCLOSURE = (
    "Connected AI clients can read saved content in this world. Returned content "
    "may be sent to their AI provider. Stopping sharing prevents further access; "
    "it cannot retract content already returned."
)


class McpFailure(ValueError):
    """A public, content-free error safe to return to a client."""

    def __init__(self, code: str) -> None:
        """Retain a fixed machine-readable failure code."""
        super().__init__(code)
        self.code = code


def failure(code: str) -> dict[str, Any]:
    """Return an explicit failure, never an apparently empty successful read."""
    return {"schema_version": 1, "status": code, "data": None}
