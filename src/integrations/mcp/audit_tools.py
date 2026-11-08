"""Read-only audit and temporal reference tools for both MCP transports."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from src.integrations.mcp.results import tool_adapter


def register_audit_tools(
    server: MCPServer,
    annotations: ToolAnnotations,
    call: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    """Expose bounded saved definitions and detached view observations."""

    @server.tool(annotations=annotations)
    @tool_adapter
    async def list_calendars(
        cursor: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        """List saved calendars in this world, including inactive definitions."""
        return await call("list_calendars", {"cursor": cursor, "limit": limit})

    @server.tool(annotations=annotations)
    @tool_adapter
    async def read_calendar_section(
        calendar_id: str | None = None,
        section: Literal[
            "summary",
            "months",
            "week",
            "leap_year_rules",
            "year_variants",
            "week_day_names",
            "week_day_abbreviations",
            "year_variant_summaries",
            "year_variant_months",
        ] = "summary",
        variant_index: int | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Read exact saved calendar rules; omitted calendar_id selects the active calendar."""
        return await call(
            "read_calendar_section",
            {key: value for key, value in locals().items() if key != "call"},
        )

    @server.tool(annotations=annotations)
    @tool_adapter
    async def get_time_context() -> dict[str, Any]:
        """Read saved world Now, observed live playhead and a distinct system UTC clock."""
        return await call("get_time_context", {})

    @server.tool(annotations=annotations)
    @tool_adapter
    async def browse_relationships(
        source_kind: Literal["entity", "event", "ambiguous", "unresolved"]
        | None = None,
        target_kind: Literal["entity", "event", "ambiguous", "unresolved"]
        | None = None,
        predicate: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Inventory saved directed edges, including Event→Event; attributes and date filtering are excluded."""
        return await call(
            "browse_relationships",
            {key: value for key, value in locals().items() if key != "call"},
        )
