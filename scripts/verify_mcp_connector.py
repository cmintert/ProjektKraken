"""Verify a built MCP console relay against a disposable queued-worker host."""

import argparse
import asyncio
import json
import sys
import threading
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from PySide6.QtCore import QMetaObject, Qt, QThread, QTimer
from PySide6.QtWidgets import QApplication

from scripts.mcp_verification_fixture import PLAYHEAD, WORLD_NOW, cases, seed
from src.app.coordinators.mcp_coordinator import McpCoordinator
from src.core.mcp_access import SHARING_SCOPES, TOOLS
from src.services.worker import DatabaseWorker


def _describe(error: BaseException, token: str) -> list[str]:
    """Keep disposable-host diagnostics useful without recording credentials."""
    if isinstance(error, BaseExceptionGroup):
        return [item for child in error.exceptions for item in _describe(child, token)]
    message = str(error).replace(token, "[redacted]") if token else str(error)
    return [f"{type(error).__name__}: {message}"]


async def _exercise(
    client: Client, facts: dict[str, str], expected: str, errors: list[dict[str, Any]]
) -> list[str]:
    """Verify every tool, exact continuation and structured tool-error forwarding."""
    tested = []
    for name, args in cases(facts).items():
        response = await client.call_tool(name, {**args, "expected_revision": expected})
        assert response.structured_content["status"] == "OK", (
            name,
            response.structured_content,
        )
        if name == "get_image_preview":
            assert any(content.type == "image" for content in response.content)
        if name == "get_time_context":
            assert (
                response.structured_content["data"]["world_now"]["lore_day"]
                == WORLD_NOW
            )
            assert (
                response.structured_content["data"]["playhead"]["lore_day"] == PLAYHEAD
            )
        if name == "get_world_overview":
            counts = response.structured_content["data"]["counts"]["relationships"]
            assert counts["total_saved"] == len(
                {facts["relation_id"], facts["event_relation_id"]}
            )
            assert counts["by_endpoint_kinds"]["event_to_event"] == 1
        if name == "browse_relationships":
            assert {
                row["id"] for row in response.structured_content["data"]["rows"]
            } == {facts["relation_id"], facts["event_relation_id"]}
        tested.append(name)
    assert set(tested) == set(TOOLS)
    text, cursor = [], None
    while True:
        response = await client.call_tool(
            "read_object_section",
            {
                "kind": "entity",
                "id": facts["entity_id"],
                "section": "description",
                "cursor": cursor,
                "expected_revision": expected,
            },
        )
        page = response.structured_content["data"]
        text.append(page["text"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert "".join(text) == facts["description"]
    missing = await client.call_tool("get_object", {"kind": "entity", "id": "missing"})
    assert missing.is_error and missing.structured_content["status"] == "NOT_FOUND"
    for tool, arguments, status, reason in (
        (
            "browse_world",
            {"cursor": "invalid-cursor"},
            "STALE_CURSOR",
            "INVALID_CURSOR",
        ),
        (
            "get_context",
            {"kind": "entity", "id": facts["entity_id"], "mode": "at_playhead"},
            "INVALID_DATE",
            "LORE_DAY_REQUIRED",
        ),
    ):
        invalid = await client.call_tool(tool, arguments)
        assert invalid.is_error
        assert invalid.structured_content["status"] == status
        assert invalid.structured_content["reason_code"] == reason
        assert invalid.structured_content["retryable"] is False
        errors.append({"tool": tool, **invalid.structured_content})
        healthy = await client.call_tool("get_active_world", {})
        assert healthy.structured_content["status"] == "OK"
    return tested


def main() -> None:
    """Verify protocol modes without installing or altering client accounts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    path = str((arguments.report.parent / "connector-test.kraken").resolve())
    facts = seed(Path(path))
    thread = QThread()
    worker = DatabaseWorker(path)
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    context = {
        "world_id": "connector-test",
        "world_name": "Connector test",
        "database": path,
    }
    coordinator = McpCoordinator(
        lambda: context,
        lambda: worker.db_service,
        thread,
        view_context=lambda: {"world_now": WORLD_NOW, "playhead": PLAYHEAD},
    )
    results: dict[str, object] = {}

    async def calls() -> None:
        for mode in ("legacy", "auto"):
            async with Client(
                StdioServerParameters(
                    command=str(arguments.executable.resolve())
                    if arguments.executable
                    else sys.executable,
                    args=[]
                    if arguments.executable
                    else ["-m", "src.integrations.mcp.connector"],
                ),
                mode=mode,
                cache=None,
            ) as client:
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == set(TOOLS)
                result = await client.call_tool("get_active_world")
                results[f"{mode}_result"] = result.structured_content
                assert result.structured_content["data"]["id"] == "connector-test"
                expected = result.structured_content["revision"]
                errors: list[dict[str, Any]] = []
                results[f"{mode}_tools"] = await _exercise(
                    client, facts, expected, errors
                )
                results[f"{mode}_errors"] = errors
                results[mode] = "passed"

    def run_client() -> None:
        try:
            asyncio.run(calls())
        except Exception as exc:
            results["error"] = type(exc).__name__
            results["error_details"] = _describe(
                exc, coordinator._session.token if coordinator._session else ""
            )

    def initialized(success: bool) -> None:
        if success:
            coordinator.set_scopes(list(SHARING_SCOPES))
            coordinator.enable()
        else:
            results["error"] = "Database initialization failed"
            app.quit()

    caller: threading.Thread | None = None

    def changed(state: dict) -> None:
        nonlocal caller
        if state["state"] == "Active" and caller is None:
            caller = threading.Thread(target=run_client)
            caller.start()

    poll = QTimer()
    poll.setInterval(50)

    def finished() -> None:
        if caller is not None and not caller.is_alive():
            coordinator.stop()
            if coordinator.snapshot()["state"] == "Off":
                app.quit()

    poll.timeout.connect(finished)
    poll.start()
    QTimer.singleShot(90000, app.quit)
    worker.initialized.connect(initialized, Qt.ConnectionType.QueuedConnection)
    coordinator.changed.connect(changed)
    QMetaObject.invokeMethod(
        worker, "initialize_db", Qt.ConnectionType.QueuedConnection
    )
    try:
        app.exec()
    finally:
        coordinator.stop()
        coordinator._poll.stop()
        QMetaObject.invokeMethod(
            worker, "cleanup", Qt.ConnectionType.BlockingQueuedConnection
        )
        thread.quit()
        thread.wait(5000)
    if caller is not None:
        caller.join(15)
    results["evidence"] = (
        "packaged connector" if arguments.executable else "source connector"
    ) + " against queued-worker verification host"
    arguments.report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if results.get("legacy") != "passed" or results.get("auto") != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
