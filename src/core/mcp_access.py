"""Transport-independent limits and failures for optional world sharing."""

from typing import Any

MAX_REQUEST_BYTES = 16 * 1024
MAX_RESULT_BYTES = 64 * 1024
MAX_IMAGE_RESULT_BYTES = 512 * 1024
SHARING_SCOPES = ("longform", "maps", "attachments", "images", "semantic")
PAGE_SIZE = 25
MAX_PENDING = 4
DEADLINE_SECONDS = 10.0
TOOLS = (
    "get_capabilities",
    "get_object_summary",
    "read_object_section",
    "read_context_section",
    "browse_facets",
    "read_longform",
    "browse_maps",
    "read_map",
    "list_attachments",
    "get_image_preview",
    "semantic_search",
    "search_shared_content",
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
    actions = {
        "WORLD_CHANGED": "restart_investigation",
        "STALE_CURSOR": "restart_query",
        "RESULT_TOO_LARGE": "read_smaller_section",
        "CONTEXT_LIMIT": "use_connections_or_object_sections",
        "BUSY": "retry_later",
        "TIMEOUT": "retry_smaller_request",
        "UNAVAILABLE": "check_local_sharing",
        "SCOPE_DISABLED": "enable_scope_locally",
    }
    return {
        "schema_version": 1,
        "status": code,
        "data": None,
        "retryable": code in {"BUSY", "TIMEOUT"},
        "restart_required": code in {"WORLD_CHANGED", "STALE_CURSOR"},
        "suggested_action": actions.get(code, "check_request"),
    }
