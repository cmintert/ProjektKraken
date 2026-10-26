"""Reproduce KRT-109 synthetic read costs without opening a user world."""

from __future__ import annotations

import json
import platform
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication

from src.core.authoring_context import EntityAuthoringContext
from src.core.entities import Entity
from src.core.entity_context_mode import EntityContextMode
from src.core.theme_manager import ThemeManager
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.services.authoring_context_builder import AuthoringContextBuilder
from src.services.db_service import DatabaseService
from src.services.entity_connection_browse_service import EntityConnectionBrowseService
from src.services.entity_connection_browse_task import EntityConnectionBrowseTask


def queue_wait(path: str, query: dict[str, Any]) -> float:
    """Measure a queued command sentinel behind one bounded read batch."""
    thread = QThread()
    loop = QEventLoop()
    result: list[float] = []

    class Probe(QObject):
        """Own the borrowed database and sentinel on the same worker thread."""

        read = Signal(dict)
        sentinel = Signal()
        completed = Signal()

        def __init__(self) -> None:
            super().__init__()
            self.db: DatabaseService | None = None
            self.enqueued = 0.0

        def database(self) -> DatabaseService:
            """Open once on the owner thread, as in production."""
            if self.db is None:
                self.db = DatabaseService(path)
                self.db.connect()
            return self.db

        @Slot()
        def mark(self) -> None:
            """Run after the browse batch and confirm its transaction ended."""
            assert self.db is not None
            assert not self.db.require_connection().in_transaction
            result.append((time.perf_counter() - self.enqueued) * 1000)
            self.completed.emit()

        @Slot()
        def close(self) -> None:
            """Close only on the owning thread."""
            if self.db is not None:
                self.db.close()

    probe = Probe()
    task = EntityConnectionBrowseTask(probe.database)
    probe.moveToThread(thread)
    task.moveToThread(thread)
    probe.read.connect(task.run, Qt.ConnectionType.QueuedConnection)
    probe.sentinel.connect(probe.mark, Qt.ConnectionType.QueuedConnection)
    probe.completed.connect(loop.quit, Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(probe.close, Qt.ConnectionType.DirectConnection)
    thread.finished.connect(task.deleteLater)
    thread.finished.connect(probe.deleteLater)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    thread.start()
    probe.enqueued = time.perf_counter()
    probe.read.emit({"kind": "page", "request_id": "measure", "query": query})
    probe.sentinel.emit()
    timeout.start(10000)
    loop.exec()
    thread.quit()
    if not thread.wait(10000) or not result:
        raise RuntimeError("Queue measurement failed to finish")
    return result[0]


def measure(path: str, degree: int, unrelated: int) -> dict[str, Any]:
    """Compare the existing bounded snapshot with complete direct browsing."""
    db = DatabaseService(path)
    db.connect()
    root, target, detached = (
        Entity("Root", "person"),
        Entity("Target", "place"),
        Entity("Unrelated", "place"),
    )
    with db.transaction():
        for item in (root, target, detached):
            db.insert_entity(item)
        for index in range(degree):
            db.insert_relation(
                root.id,
                target.id,
                f"custom {index:05}",
                {"valid_from": 100.0} if index % 4 == 0 else {},
            )
        for index in range(unrelated):
            db.insert_relation(detached.id, target.id, f"other {index:05}", {})
    db.close()
    db.connect()
    queries: list[str] = []
    db.require_connection().set_trace_callback(queries.append)
    query = {
        "entity_id": root.id,
        "mode": "at_playhead",
        "date": 20.0,
        "session": "measure",
        "generation": 0,
        "world": path,
    }
    started = time.perf_counter()
    context = AuthoringContextBuilder(db).build_entity_context(
        root.id, mode=EntityContextMode.AT_PLAYHEAD, context_date=20.0
    )
    baseline_ms = (time.perf_counter() - started) * 1000
    baseline_queries = len(queries)
    assert context is not None
    queries.clear()
    tracemalloc.start()
    service = EntityConnectionBrowseService(db)
    cursor = None
    rows = []
    durations = []
    started = time.perf_counter()
    while True:
        step_started = time.perf_counter()
        response = service.step({"query": query, "cursor": cursor})
        durations.append((time.perf_counter() - step_started) * 1000)
        rows.extend(response["rows"])
        cursor = response["cursor"]
        if response["done"]:
            break
    total_ms = (time.perf_counter() - started) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    browse_queries = len(queries)
    candidate_sql = next(sql for sql in queries if "WITH touching AS" in sql)
    plan = [
        row[3]
        for row in db.require_connection().execute(
            "EXPLAIN QUERY PLAN " + candidate_sql
        )
    ]
    warm_started = time.perf_counter()
    service.step({"query": query})
    warm_ms = (time.perf_counter() - warm_started) * 1000
    assert len(rows) == degree - ((degree + 3) // 4)
    db.close()
    render = measure_render(root.id, rows)
    return {
        "direct_candidates": degree,
        "unrelated_edges": unrelated,
        "eligible_total": len(rows),
        "baseline_snapshot_ms": baseline_ms,
        "baseline_snapshot_queries": baseline_queries,
        "baseline_direct_rows": len(context.direct_relations)
        + len(context.temporal_history),
        "first_step_ms_with_tracemalloc": durations[0],
        "warm_first_step_ms": warm_ms,
        "continuation_median_ms_with_tracemalloc": statistics.median(durations[1:])
        if len(durations) > 1
        else None,
        "complete_scan_ms_with_tracemalloc": total_ms,
        "browse_queries": browse_queries,
        "steps": len(durations),
        "retained_rows_peak_python_bytes": peak_bytes,
        "queued_sentinel_delay_ms": queue_wait(path, query),
        "candidate_query_plan": plan,
        **render,
    }


def measure_render(entity_id: str, rows: list[dict[str, Any]]) -> dict[str, float]:
    """Measure actual offscreen widget layout for first and accumulated rows."""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    view = AuthoringContextWidget(object_label="Entity")
    view.resize(360, 600)
    view.enable_connection_browsing()
    view.set_entity_context(
        EntityAuthoringContext(
            entity_id, mode="at_playhead", context_date=20.0, date_label="20 lore days"
        )
    )
    view.show()
    app.processEvents()
    started = time.perf_counter()
    view.set_connection_page(rows[:25], "First page", True)
    app.processEvents()
    first_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    view.set_connection_page(
        rows, "All eligible connections loaded", False, reveal=True
    )
    app.processEvents()
    accumulated_ms = (time.perf_counter() - started) * 1000
    view.close()
    view.deleteLater()
    app.processEvents()
    return {
        "first_25_row_render_ms": first_ms,
        "all_loaded_row_render_ms": accumulated_ms,
    }


def main() -> None:
    """Retain repeatable synthetic evidence beneath the ignored build tree."""
    app = QApplication.instance() or QApplication([])
    output = Path("docs/_build/krt109/implementation")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt109-measure-") as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary
        )
        ThemeManager().apply_theme(
            app, Path("src/resources/main.qss").read_text("utf-8")
        )
        results = [
            measure(str(Path(temporary) / f"world-{degree}.kraken"), degree, other)
            for degree, other in ((100, 500), (1000, 5000))
        ]
    report = {
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "limits": "Synthetic local worlds, not representative author sessions. First measured browse follows the snapshot baseline, so it is not a cold disk read. Tracemalloc affects scan timings; warm step and queue sentinel omit it. Queue sentinel includes opening its connection. Cancellation fairness is tested separately. No performance thresholds or UX improvement claim.",
        "worlds": results,
    }
    (output / "timings.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    app.processEvents()


if __name__ == "__main__":
    main()
