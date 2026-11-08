"""Translate typed bridge failures without exposing exception prose or credentials."""

from http import HTTPStatus
from typing import Any

import anyio
import httpx2
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED, INVALID_PARAMS, REQUEST_TIMEOUT

from src.core.mcp_access import McpFailure, failure

_SDK_FAILURES: dict[int, tuple[str, str | None]] = {
    INVALID_PARAMS: ("INVALID_INPUT", "TOOL_ARGUMENTS_INVALID"),
    REQUEST_TIMEOUT: ("TIMEOUT", None),
    CONNECTION_CLOSED: ("TRANSIENT_FAILURE", None),
}


def bridge_failure(error: Exception) -> dict[str, Any]:
    """Preserve known causes, including exceptions wrapped by SDK task groups."""
    if isinstance(error, ExceptionGroup):
        results = [bridge_failure(item) for item in error.exceptions]
        return next((item for item in results if not item["retryable"]), results[0])
    if isinstance(error, McpFailure):
        return error.as_result()
    if isinstance(error, (TimeoutError, httpx2.TimeoutException)):
        return failure("TIMEOUT")
    if isinstance(error, httpx2.HTTPStatusError):
        return _http_failure(error.response.status_code)
    if isinstance(error, httpx2.ConnectError):
        return failure("UNAVAILABLE", "APP_UNREACHABLE")
    if isinstance(
        error,
        (
            httpx2.NetworkError,
            httpx2.RemoteProtocolError,
            ConnectionError,
            anyio.EndOfStream,
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
        ),
    ):
        return failure("TRANSIENT_FAILURE")
    if isinstance(error, MCPError):
        return failure(*_SDK_FAILURES.get(error.code, ("PROTOCOL_ERROR", None)))
    return failure("PROTOCOL_ERROR", "UNEXPECTED_BRIDGE_FAILURE")


def _http_failure(status: int) -> dict[str, Any]:
    """Classify status codes, never server-supplied error text."""
    if status in {401, 403}:
        return failure("UNAVAILABLE", "AUTH_REQUIRED")
    if status in {408, 504}:
        return failure("TIMEOUT")
    if status == HTTPStatus.TOO_MANY_REQUESTS:
        return failure("BUSY")
    if status in {502, 503}:
        return failure("TRANSIENT_FAILURE", "LOCAL_SERVICE_TEMPORARILY_UNAVAILABLE")
    if status in {400, 422}:
        return failure("INVALID_INPUT", "TOOL_ARGUMENTS_INVALID")
    if status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
        return failure("REQUEST_TOO_LARGE")
    return failure("PROTOCOL_ERROR", "UNEXPECTED_HTTP_STATUS")
