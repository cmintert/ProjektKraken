"""Preserve typed MCP content across HTTP and console transports."""

import inspect
import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any

from mcp.types import CallToolResult, ImageContent, TextContent

from src.services.mcp_contracts import ReadEnvelope


def tool_adapter(
    function: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[CallToolResult]]:
    """Add optional investigation preconditions to every fixed catalogue tool."""
    signature = inspect.signature(function)
    parameters = list(signature.parameters.values())
    keys = ("expected_world_id", "expected_revision", "expected_session_generation")
    parameters.extend(
        inspect.Parameter(
            key, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str | None
        )
        for key in keys
    )

    @wraps(function)
    async def adapted(*args: Any, **kwargs: Any) -> CallToolResult:
        preconditions = {key: kwargs.pop(key) for key in keys if key in kwargs}
        preconditions = {
            key: value for key, value in preconditions.items() if value is not None
        }
        # Preconditions are consumed by the catalogue's call closure, not the SDK.
        token = _preconditions.set(preconditions)
        try:
            result = await function(*args, **kwargs)
        finally:
            _preconditions.reset(token)
        content: list[Any] = []
        image = result.pop("_image", None)
        content.append(TextContent(type="text", text=json.dumps(result)))
        if image is not None:
            content.append(
                ImageContent(type="image", data=image, mime_type="image/png")
            )
        return CallToolResult(
            content=content,
            structured_content=result,
            is_error=result.get("status") != "OK",
        )

    setattr(
        adapted,
        "__signature__",
        signature.replace(parameters=parameters, return_annotation=ReadEnvelope),
    )
    adapted.__annotations__ = {**function.__annotations__, "return": ReadEnvelope}
    return adapted


# Context-local storage keeps parallel SDK calls' preconditions isolated.
_preconditions: ContextVar[dict[str, Any]] = ContextVar("mcp_preconditions", default={})


def preconditions() -> dict[str, Any]:
    """Read only the arguments belonging to the current protocol invocation."""
    return _preconditions.get()
