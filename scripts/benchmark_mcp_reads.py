"""Reproducible service-only MCP fixtures and metrics; never desktop acceptance."""

import argparse
import json
import time
import tracemalloc
import uuid
from pathlib import Path
from typing import Any

from src.core.entities import Entity
from src.core.events import Event
from src.core.mcp_access import DEADLINE_SECONDS, McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_read_service import McpReadService


def benchmark(directory: Path, count: int) -> dict[str, Any]:
    """Build an isolated world and verify known historical/text/staleness evidence."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "benchmark.kraken"
    if path.exists():
        raise ValueError("Use a fresh output directory; fixtures are never overwritten")
    db = DatabaseService(str(path))
    db.connect()
    try:
        queen = Entity(
            "Ilyra",
            "person",
            description="Exact 🦑 historical prose.\n" * 4000,
            attributes={"rank": "citizen", "_longform": {"default": {"position": 1}}},
        )
        event = Event("Coronation", 100)
        db.insert_entity(queen)
        db.insert_event(event)
        relation = db.insert_relation(
            event.id,
            queen.id,
            "changes",
            {"valid_from": 100, "payload": {"attributes": {"rank": "queen"}}},
        )
        with db.transaction():
            db.require_connection().executemany(
                "INSERT INTO entities(id,name,type,description,attributes,created_at,modified_at) "
                "VALUES(?,?,'unrelated','Unrelated fixture','{}',0,0)",
                [
                    (str(uuid.uuid4()), f"Unrelated {index:06}")
                    for index in range(count)
                ],
            )
        service = McpReadService()
        metrics: list[dict[str, Any]] = []
        tracemalloc.start()

        def read(tool: str, **args: Any) -> dict[str, Any]:
            started = time.perf_counter()
            result = service.execute(
                db,
                {
                    "tool": tool,
                    "arguments": args,
                    "world_id": "benchmark",
                    "world_name": "Benchmark",
                    "generation": "fixture",
                },
                lambda: time.perf_counter() - started >= DEADLINE_SECONDS,
            )
            metrics.append(
                {
                    "tool": tool,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "bytes": len(json.dumps(result).encode()),
                }
            )
            return result

        identity = read("get_active_world")
        context = read(
            "get_context",
            kind="entity",
            id=queen.id,
            mode="at_playhead",
            lore_day=110,
            expected_revision=identity["revision"],
        )
        rank = next(
            row for row in context["data"]["attributes"] if row["name"] == "rank"
        )
        assert rank["value"] == "queen" and rank["source"]["relation_id"] == relation
        text, cursor = [], None
        while True:
            page = read(
                "read_object_section",
                kind="entity",
                id=queen.id,
                section="description",
                cursor=cursor,
            )
            text.append(page["data"]["text"])
            cursor = page["data"]["next_cursor"]
            if cursor is None:
                break
        assert "".join(text) == queen.description
        db.insert_entity(Entity("Intervening edit", "person"))
        try:
            read(
                "get_object",
                kind="entity",
                id=queen.id,
                expected_revision=identity["revision"],
            )
        except McpFailure as exc:
            assert exc.code == "WORLD_CHANGED"
        else:
            raise AssertionError("Mixed revisions were accepted")
        _, peak = tracemalloc.get_traced_memory()
        return {
            "unrelated_entities": count,
            "evidence": "service-only; no desktop/client acceptance",
            "calls": metrics,
            "peak_python_bytes": peak,
            "expected_sources": {
                "entity_id": queen.id,
                "event_id": event.id,
                "relation_id": relation,
            },
            "verified": ["historical_source", "exact_paged_text", "revision_rejection"],
        }
    finally:
        tracemalloc.stop()
        db.close()


def main() -> None:
    """Write reviewable metrics and disposable worlds under a fresh artifact directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 10000, 50000])
    args = parser.parse_args()
    reports = [benchmark(args.output / str(count), count) for count in args.sizes]
    (args.output / "metrics.json").write_text(
        json.dumps(reports, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
