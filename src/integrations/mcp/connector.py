"""Console-only local MCP relay; it cannot enable sharing or access world files."""

import asyncio
import logging
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from src.core.mcp_access import DEADLINE_SECONDS, McpFailure, failure
from src.integrations.mcp.discovery import SessionDiscovery
from src.integrations.mcp.tools import create_catalogue


async def forward(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Discover each call afresh, so restarts never reuse revoked credentials."""
    try:
        descriptor = SessionDiscovery().read()
        async with asyncio.timeout(DEADLINE_SECONDS + 1):
            async with httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {descriptor['token']}"},
                follow_redirects=False,
                trust_env=False,
            ) as http:
                async with Client(
                    streamable_http_client(
                        f"http://127.0.0.1:{descriptor['port']}/mcp",
                        http_client=http,
                    ),
                    cache=None,
                ) as client:
                    result = await client.call_tool(tool, arguments)
                    return result.structured_content or failure("UNAVAILABLE")
    except McpFailure as exc:
        return failure(exc.code)
    except Exception:
        return failure("UNAVAILABLE")


def main() -> None:
    """Serve only protocol messages on stdout; no Qt or app startup."""
    logging.basicConfig(level=logging.CRITICAL)
    create_catalogue(forward).run(transport="stdio")


if __name__ == "__main__":
    main()
