"""Console-only local MCP relay; it cannot enable sharing or access world files."""

import asyncio
import logging
import sys
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from src.core.mcp_access import DEADLINE_SECONDS, failure
from src.integrations.mcp.discovery import SessionDiscovery
from src.integrations.mcp.errors import bridge_failure
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
                timeout=DEADLINE_SECONDS,
            ) as http:
                async with Client(
                    streamable_http_client(
                        f"http://127.0.0.1:{descriptor['port']}/mcp",
                        http_client=http,
                    ),
                    cache=None,
                ) as client:
                    result = await client.call_tool(tool, arguments)
                    data = result.structured_content
                    if not isinstance(data, dict) or not isinstance(
                        data.get("status"), str
                    ):
                        return failure("PROTOCOL_ERROR")
                    if result.is_error and data["status"] == "OK":
                        return failure("PROTOCOL_ERROR")
                    for content in result.content:
                        if content.type == "image" and data["status"] == "OK":
                            data["_image"] = content.data
                    return data
    except Exception as exc:
        return bridge_failure(exc)


def main() -> None:
    """Serve only protocol messages on stdout; no Qt or app startup."""
    if sys.argv[1:] == ["--image-helper"]:
        from src.services.mcp_image_helper import main as image_main

        image_main()
        return
    if sys.argv[1:] == ["--semantic-helper"]:
        from src.services.mcp_semantic_helper import main as semantic_main

        semantic_main()
        return
    logging.basicConfig(level=logging.CRITICAL)
    create_catalogue(forward).run(transport="stdio")


if __name__ == "__main__":
    main()
