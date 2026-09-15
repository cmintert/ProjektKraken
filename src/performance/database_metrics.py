"""Read-only database pipeline and query-plan measurements."""

from __future__ import annotations

import sqlite3
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

from src.performance.resources import process_memory_bytes
from src.services.db_service import DatabaseService


def _measure(action: Callable[[], object], repetitions: int) -> list[float]:
    samples: list[float] = []
    action()
    for _ in range(repetitions):
        started = time.perf_counter()
        action()
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


def measure_database(database: Path, repetitions: int) -> dict[str, Any]:
    """Measure DB queries and domain hydration against a generated database."""
    service = DatabaseService(str(database))
    service.connect()
    tracemalloc.start()
    before_memory = process_memory_bytes()
    try:
        event_samples = _measure(service.get_all_events, repetitions)
        entity_samples = _measure(service.get_all_entities, repetitions)
        relation_samples = _measure(service.get_all_relations, repetitions)
        query_plans = _query_plans(database)
        _current, peak_python = tracemalloc.get_traced_memory()
        after_memory = process_memory_bytes()
    finally:
        tracemalloc.stop()
        service.close()
    return {
        "database.events_hydration": {"unit": "ms", "samples": event_samples},
        "database.entities_hydration": {"unit": "ms", "samples": entity_samples},
        "database.relations_hydration": {"unit": "ms", "samples": relation_samples},
        "database.python_peak": {"unit": "bytes", "samples": [peak_python]},
        "database.working_set_before": {
            "unit": "bytes",
            "samples": [before_memory.get("working_set") or 0],
        },
        "database.working_set_after": {
            "unit": "bytes",
            "samples": [after_memory.get("working_set") or 0],
        },
        "database.query_plans": {"unit": "text", "plans": query_plans},
    }


def _query_plans(database: Path) -> dict[str, list[str]]:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        queries = {
            "events_by_date": (
                "SELECT id, name, type, lore_date FROM events "
                "WHERE lore_date BETWEEN ? AND ? ORDER BY lore_date",
                (100.0, 1_000.0),
            ),
            "entities_by_type": (
                "SELECT id, name, type FROM entities WHERE type = ? ORDER BY name",
                ("character",),
            ),
            "relations_for_source": (
                "SELECT * FROM relations WHERE source_id = ?",
                ("missing",),
            ),
            "events_for_tag": (
                "SELECT e.id FROM events e JOIN event_tags et ON et.event_id=e.id "
                "WHERE et.tag_id = ?",
                ("missing",),
            ),
        }
        return {
            name: [str(row[3]) for row in connection.execute("EXPLAIN QUERY PLAN " + sql, args)]
            for name, (sql, args) in queries.items()
        }
    finally:
        connection.close()
