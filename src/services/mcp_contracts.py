"""Public contracts and permission checks independent of transport and Qt."""

from typing import Any, NotRequired, TypedDict

from src.core.mcp_access import (
    MAX_IMAGE_RESULT_BYTES,
    MAX_RESULT_BYTES,
    PAGE_SIZE,
    SHARING_SCOPES,
    TOOLS,
    McpFailure,
)


class ReadPayload(TypedDict, total=False):
    """Common result shapes; authored attributes and tool-specific facts stay extensible."""

    rows: list[Any]
    results: list[dict[str, Any]]
    text: str
    offset: int
    until: int
    total_length: int
    next_cursor: str | None
    done: bool
    partial: bool
    truncated: bool
    omitted_counts: dict[str, int]
    provenance: dict[str, Any]
    content: dict[str, Any]
    references: dict[str, dict[str, Any]]


class ReadEnvelope(TypedDict):
    """Stable additive envelope; factual payloads retain their tool-specific shape."""

    status: str
    data: ReadPayload | None
    schema_version: NotRequired[int]
    world_id: NotRequired[str]
    revision: NotRequired[str]
    session_generation: NotRequired[str]
    evaluation: NotRequired[dict[str, Any]]
    retryable: NotRequired[bool]
    restart_required: NotRequired[bool]
    suggested_action: NotRequired[str]
    detail: NotRequired[str]


def check_preconditions(
    args: dict[str, Any], request: dict[str, Any], revision: str
) -> None:
    """Reject mixed investigations without publishing replacement world facts."""
    expected = {
        "expected_world_id": request["world_id"],
        "expected_revision": revision,
        "expected_session_generation": request["generation"],
    }
    for key, actual in expected.items():
        value = args.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise McpFailure("INVALID_INPUT")
            if value != actual:
                raise McpFailure("WORLD_CHANGED")


def require_scope(request: dict[str, Any], scope: str) -> None:
    """Only local session intent can grant additional content access."""
    if scope not in request.get("scopes", []):
        raise McpFailure("SCOPE_DISABLED")


def capabilities(request: dict[str, Any]) -> dict[str, Any]:
    """Describe limits without exposing paths, model settings or credentials."""
    return {
        "read_only": True,
        "schema_versions": [1],
        "scopes": {key: key in request.get("scopes", []) for key in SHARING_SCOPES},
        "limits": {
            "json_bytes": MAX_RESULT_BYTES,
            "image_bytes": MAX_IMAGE_RESULT_BYTES,
            "page_size": PAGE_SIZE,
            "text_characters": 8000,
        },
        "semantic": request.get("semantic_state", "unprepared"),
        "tools": list(TOOLS),
    }
