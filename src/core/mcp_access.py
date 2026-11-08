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
    "list_calendars",
    "read_calendar_section",
    "get_time_context",
    "browse_relationships",
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

    def __init__(self, code: str, reason_code: str | None = None) -> None:
        """Retain a fixed machine-readable failure code."""
        super().__init__(code)
        self.code = code
        self.reason_code = reason_code

    def as_result(self) -> dict[str, Any]:
        """Preserve the machine-readable cause across queued boundaries."""
        return failure(self.code, self.reason_code)


def failure(code: str, reason_code: str | None = None) -> dict[str, Any]:
    """Return an explicit failure, never an apparently empty successful read."""
    actions = {
        "WORLD_CHANGED": "restart_investigation",
        "STALE_CURSOR": "restart_query",
        "RESULT_TOO_LARGE": "read_smaller_section",
        "CONTEXT_LIMIT": "use_connections_or_object_sections",
        "BUSY": "retry_later",
        "TIMEOUT": "retry_smaller_request",
        "UNAVAILABLE": "open_kraken_select_world_enable_sharing",
        "TRANSIENT_FAILURE": "retry_with_backoff",
        "INVALID_DATE": "supply_valid_lore_day",
        "PROTOCOL_ERROR": "check_connector_version",
        "INTERNAL_ERROR": "report_local_error",
        "SCOPE_DISABLED": "enable_scope_locally",
    }
    reasons = {
        "UNAVAILABLE": "NO_ACTIVE_SESSION",
        "INVALID_DATE": "INVALID_LORE_DAY",
        "STALE_CURSOR": "INVALID_OR_EXPIRED_CURSOR",
        "BUSY": "CONCURRENCY_LIMIT_REACHED",
        "TIMEOUT": "REQUEST_DEADLINE_EXCEEDED",
        "TRANSIENT_FAILURE": "CONNECTION_INTERRUPTED",
        "PROTOCOL_ERROR": "INVALID_BRIDGE_RESPONSE",
    }
    recovery = {
        "NO_ACTIVE_SESSION": "open_kraken_select_world_enable_sharing",
        "SHARING_DISABLED": "enable_sharing_locally",
        "SESSION_ENDED": "rediscover_session_and_restart_investigation",
        "NO_WORLD_SELECTED": "open_world_and_enable_sharing",
        "WORLD_NOT_READY": "wait_for_world_loading_then_enable_sharing",
        "APP_UNREACHABLE": "check_kraken_running_and_rediscover",
        "AUTH_REQUIRED": "rediscover_session_and_restart_investigation",
        "UNSAFE_DISCOVERY": "check_local_connector_permissions",
        "INVALID_DISCOVERY": "restart_local_sharing",
        "LORE_DAY_REQUIRED": "supply_lore_day",
        "NO_ACTIVE_CALENDAR": "select_calendar_locally_or_supply_calendar_id",
        "DATABASE_BUSY": "retry_with_backoff",
        "LOCAL_RUNTIME_UNAVAILABLE": "check_connector_installation",
    }
    reason = reason_code or reasons.get(code, code)
    result = {
        "schema_version": 1,
        "status": code,
        "data": None,
        "reason_code": reason,
        "retryable": code in {"BUSY", "TIMEOUT", "TRANSIENT_FAILURE"}
        or reason == "APP_UNREACHABLE",
        "restart_required": code in {"WORLD_CHANGED", "STALE_CURSOR"}
        or reason
        in {
            "SESSION_ENDED",
            "SHARING_DISABLED",
            "NO_WORLD_SELECTED",
            "WORLD_NOT_READY",
            "AUTH_REQUIRED",
            "NO_ACTIVE_SESSION",
        },
        "suggested_action": recovery.get(reason, actions.get(code, "check_request")),
    }
    if result["retryable"]:
        result["retry_after_ms"] = 250
    if reason == "LORE_DAY_REQUIRED":
        result["required_fields"] = ["lore_day"]
    return result
