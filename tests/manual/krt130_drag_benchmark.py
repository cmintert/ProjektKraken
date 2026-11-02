"""Native continuous-pointer benchmark using disposable, reproducible worlds."""

from __future__ import annotations

import json
import logging
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.app.coordinators.timeline_movement_coordinator import (
    TimelineMovementCoordinator,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.core.timeline_visibility import DependencyVisibility
from src.gui.widgets.timeline import TimelineWidget
from tests.unit.test_timeline_layout_boundary import CachedGroups

OUTPUT = Path("docs/ux/evidence/krt130")


def summary(values: list[float]) -> dict[str, float | int]:
    """Report observed distributions rather than an inferred frame-rate claim."""
    if not values:
        return {"samples": 0}
    ordered = sorted(values)
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
        "max_ms": round(max(values), 3),
    }


class PaintObserver(QObject):
    """Measure input-to-Qt-paint dispatch; this is not compositor latency."""

    def __init__(self, viewport: QObject) -> None:
        super().__init__(viewport)
        self.active = False
        self.input_time: float | None = None
        self.paint_times: list[float] = []
        self.latencies: list[float] = []
        viewport.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self.active and event.type() == QEvent.Type.Paint:
            now = time.perf_counter()
            self.paint_times.append(now)
            if self.input_time is not None:
                self.latencies.append((now - self.input_time) * 1000)
                self.input_time = None
        return False


def fixture(count: int, component: int) -> list[Event]:
    events = [Event("Source", 10.125, id="e0")]
    for index in range(1, count):
        event = Event(f"Event {index}", index * 20 + 10.125, id=f"e{index}")
        if index < component:
            event.attributes = EventTimingDefinition(
                EndpointDefinition(
                    "event",
                    anchor_id=f"event:e{index - 1}",
                    offset={"unit": "days", "value": 20},
                )
            ).apply({})
        event.tags = ["Alpha", "Beta"]
        events.append(event)
    events[0].tags = ["Alpha", "Beta"]
    return events


def run_case(
    app: QApplication, count: int, component: int, grouped: bool
) -> dict[str, Any]:
    widget = TimelineWidget()
    widget.resize(1100, 600)
    view = widget.view
    view.ASYNC_LAYOUT_THRESHOLD = count * 4
    view._has_done_initial_fit = True
    view.set_temporal_context(
        TemporalResolutionContext.build(fixture(count, component), None)
    )
    if grouped:
        view.set_data_provider(CachedGroups(view))
        view.set_grouping_config(["Alpha", "Beta"])
    widget.set_dependency_visibility(DependencyVisibility.ALL)
    view._apply_zoom(1)
    widget.show()
    QTest.qWait(30)
    view.focus_event(f"e{component // 2}")
    item = view.graphics_scene.selectedItems()[0]
    QTest.qWait(30)
    observer = PaintObserver(view.viewport())
    presenter = view.movement
    dispatch, presentation, slices, calculations, provisional_routing = (
        [],
        [],
        [],
        [],
        [],
    )
    route_calls = []
    submit = []
    coordinator = TimelineMovementCoordinator(presenter, submit.append, widget)
    mode = "chain" if component > 2 else "offset"
    widget.drag_mode_control.set_mode(mode)

    def measure(method, output):
        def timed(*args, **kwargs):
            start = time.perf_counter()
            result = method(*args, **kwargs)
            output.append((time.perf_counter() - start) * 1000)
            return result

        return timed

    presenter.present = measure(presenter.present, presentation)
    presenter._drain_rows = measure(presenter._drain_rows, slices)
    presenter.presentation_timer.timeout.disconnect()
    presenter.presentation_timer.timeout.connect(presenter._drain_rows)
    view._dependencies._preview_curves = measure(
        view._dependencies._preview_curves, provisional_routing
    )
    view._dependencies._route = measure(view._dependencies._route, route_calls)
    coordinator.worker.completed.connect(
        lambda raw: calculations.append(json.loads(raw))
    )
    before = view._temporal_context.events_json
    start_pos = view.mapFromScene(item.pos())
    assert view.viewport().rect().contains(start_pos), (
        "The dragged marker must be on screen"
    )
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start_pos)
    assert view.graphics_scene.mouseGrabberItem() is item
    observer.active = True
    heartbeat = []
    timer = QTimer(widget)
    timer.setInterval(8)
    timer.timeout.connect(lambda: heartbeat.append(time.perf_counter()))
    timer.start()
    max_pending = 0
    for step in range(1, 61):
        end = start_pos + QPoint(step, 0)
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(end),
            QPointF(view.viewport().mapToGlobal(end)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        observer.input_time = time.perf_counter()
        QApplication.sendEvent(view.viewport(), event)
        assert presenter.outline is not None and presenter.outline.isVisible()
        assert (
            view.viewport()
            .rect()
            .intersects(
                view.mapFromScene(presenter.outline.sceneBoundingRect()).boundingRect()
            )
        ), "Latency samples must paint a visible pending outline"
        dispatch.append((time.perf_counter() - observer.input_time) * 1000)
        max_pending = max(max_pending, int(coordinator.pending is not None))
        QTest.qWait(16)
    previews_during_motion = len(calculations)
    observer.active = False
    timer.stop()
    widget.grab().save(str(OUTPUT / f"preview-{count}-{component}.png"))
    deadline = time.monotonic() + 5
    while (
        coordinator.busy
        or coordinator.pending is not None
        or presenter._presentation_queue
    ) and time.monotonic() < deadline:
        QTest.qWait(10)
    QTest.keyClick(view, Qt.Key.Key_Escape)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert not submit
    assert before == view._temporal_context.events_json
    coordinator.shutdown()
    widget.close()
    widget.deleteLater()
    result = {
        "events": count,
        "component": component,
        "grouped": grouped,
        "mode": mode,
        "pointer_updates": 60,
        "drag_and_outline_visible": True,
        "previews_during_motion": previews_during_motion,
        "pending_targets_max": max_pending,
        "worker_threads": 1,
        "input_dispatch": summary(dispatch),
        "input_to_paint": summary(observer.latencies),
        "frame_intervals": summary(
            [
                (b - a) * 1000
                for a, b in zip(observer.paint_times, observer.paint_times[1:])
            ]
        ),
        "heartbeat_intervals": summary(
            [(b - a) * 1000 for a, b in zip(heartbeat, heartbeat[1:])]
        ),
        "presentation": summary(presentation),
        "presentation_slices": summary(slices),
        "provisional_routing": summary(provisional_routing),
        "obstacle_route_calls_during_drag": len(route_calls),
        "calculation": summary(
            [row["calculation_ms"] for row in calculations if "calculation_ms" in row]
        ),
        "solver_scope": sorted(
            {row["component_size"] for row in calculations if "component_size" in row}
        ),
        "errors": [row["error"] for row in calculations if row.get("error")],
        "authored_sources_unchanged": True,
    }
    logging.info("%s", json.dumps(result))
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = QApplication([])
    app.setOrganizationName("KrakenTests")
    app.setApplicationName("KRT130Benchmark")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-drag-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        manager = ThemeManager()
        manager.apply_theme(
            app, Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
        manager.set_theme("dark_mode", app, persist=False)
        cases = [
            (100, 2, False),
            (100, 100, True),
            (500, 2, False),
            (500, 100, True),
            (2000, 2, False),
            (2000, 500, True),
        ]
        results = [run_case(app, *case) for case in cases]
        report = {
            "platform": app.platformName(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "fixture": "disposable linear dependencies, 20-day spacing, all wires, two tags plus All events when grouped",
            "measurement": "Qt input dispatch and paint dispatch; not desktop compositor or independent human UX evidence",
            "results": results,
        }
        (OUTPUT / "native-benchmark.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
