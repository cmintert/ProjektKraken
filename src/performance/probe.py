"""Hidden in-application probe used by the external measurement runner."""

from __future__ import annotations

import argparse
import cProfile
import json
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QEventLoop, QObject, QSettings, QTimer, Signal
from PySide6.QtWidgets import QApplication

from src.app.qt_invocation import invoke_queued
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.performance.resources import process_memory_bytes

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

_STALL_WARNING_MS = 50.0
_STALL_CRITICAL_MS = 100.0
_LORE_TIME_TOLERANCE = 0.0001
_LORE_DATE_SORT_INDEX = 2


@dataclass(frozen=True)
class PerformanceProbeOptions:
    """Internal arguments passed by the isolated parent runner."""

    report_path: Path
    world_path: Path
    settings_path: Path
    profile: str
    repetitions: int
    scrub_positions: int
    playback_seconds: float
    visible: bool
    timeout_seconds: float
    trace_path: Path | None


def parse_performance_probe_options(
    argv: list[str],
) -> PerformanceProbeOptions | None:
    """Parse hidden probe options without affecting ordinary application startup."""
    if "--performance-probe-report" not in argv:
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--performance-probe-report", type=Path, required=True)
    parser.add_argument("--performance-probe-world", type=Path, required=True)
    parser.add_argument("--performance-probe-settings", type=Path, required=True)
    parser.add_argument("--performance-probe-profile", required=True)
    parser.add_argument("--performance-probe-repetitions", type=int, required=True)
    parser.add_argument("--performance-probe-scrub-positions", type=int, default=300)
    parser.add_argument("--performance-probe-playback-seconds", type=float, default=60.0)
    parser.add_argument("--performance-probe-timeout", type=float, default=600.0)
    parser.add_argument("--performance-probe-visible", action="store_true")
    parser.add_argument("--performance-probe-trace", type=Path)
    options, _unknown = parser.parse_known_args(argv[1:])
    return PerformanceProbeOptions(
        report_path=options.performance_probe_report.resolve(),
        world_path=options.performance_probe_world.resolve(),
        settings_path=options.performance_probe_settings.resolve(),
        profile=options.performance_probe_profile,
        repetitions=max(1, options.performance_probe_repetitions),
        scrub_positions=max(1, options.performance_probe_scrub_positions),
        playback_seconds=max(0.0, options.performance_probe_playback_seconds),
        visible=bool(options.performance_probe_visible),
        timeout_seconds=max(1.0, options.performance_probe_timeout),
        trace_path=(
            options.performance_probe_trace.resolve()
            if options.performance_probe_trace
            else None
        ),
    )


def configure_performance_probe(options: PerformanceProbeOptions) -> None:
    """Redirect application settings and select only the generated fixture."""
    options.settings_path.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(options.settings_path),
    )
    from src.app.constants import SETTINGS_ACTIVE_DB_KEY
    from src.services.world_storage_settings import WorldStorageSettings

    settings = QSettings()
    settings.clear()
    settings.setValue(SETTINGS_ACTIVE_DB_KEY, options.world_path.name)
    storage = WorldStorageSettings(settings)
    storage.set_active_world_path(options.world_path)
    storage.register_world_path(options.world_path)
    settings.sync()


class EventLoopMonitor(QObject):
    """Measure delays in delivery of a lightweight GUI-thread timer."""

    def __init__(self, interval_ms: int = 10) -> None:
        """Initialize a timer that samples expected-versus-actual delivery."""
        super().__init__()
        self._interval_ms = interval_ms
        self._last = time.perf_counter()
        self.delays_ms: list[float] = []
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._sample)

    def start(self) -> None:
        """Start event-loop sampling."""
        self._last = time.perf_counter()
        self._timer.start()

    def stop(self) -> None:
        """Stop event-loop sampling."""
        self._timer.stop()

    def _sample(self) -> None:
        now = time.perf_counter()
        elapsed_ms = (now - self._last) * 1000.0
        self._last = now
        self.delays_ms.append(max(0.0, elapsed_ms - self._interval_ms))


class PerformanceProbeController(QObject):
    """Drive deterministic UI actions after the generated world is ready."""

    finished = Signal()

    def __init__(self, window: MainWindow, options: PerformanceProbeOptions) -> None:
        """Initialize the probe for one isolated application process."""
        super().__init__(window)
        self._window = window
        self._options = options
        self._metrics: dict[str, Any] = {}
        self._errors: list[str] = []
        self._warnings: list[str] = []
        self._started = time.perf_counter()
        self._completed = False
        self._profiler = cProfile.Profile() if options.trace_path else None
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_timeout)

    def start(self) -> None:
        """Wait for the real startup pipeline, then execute the scenarios."""
        self._window.startup_completed.connect(self._on_startup_completed)
        self._watchdog.start(int(self._options.timeout_seconds * 1000))

    def _on_startup_completed(self, success: bool) -> None:
        if self._completed:
            return
        self._record("startup.first_usable", (time.perf_counter() - self._started) * 1000)
        if not success:
            self._errors.append("Application startup reported failure.")
            self._finish(1)
            return
        QTimer.singleShot(0, self._run)

    def _run(self) -> None:
        monitor = EventLoopMonitor()
        monitor.start()
        tracemalloc.start()
        if self._profiler is not None:
            self._profiler.enable()
        process_started = time.process_time()
        wall_started = time.perf_counter()
        memory_before = process_memory_bytes()
        try:
            self._measure_ui_data()
            self._checkpoint()
            self._measure_timeline()
            self._checkpoint()
            self._measure_playbar()
            self._checkpoint()
            self._measure_playback()
            self._checkpoint()
            self._measure_mutations()
            self._checkpoint()
        except Exception as exc:
            self._errors.append(f"Probe scenario failed: {type(exc).__name__}: {exc}")
        finally:
            QApplication.processEvents()
            wall_elapsed = max(time.perf_counter() - wall_started, 0.000001)
            process_elapsed = time.process_time() - process_started
            if self._profiler is not None:
                self._profiler.disable()
                trace_path = self._options.trace_path
                if trace_path is not None:
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    self._profiler.dump_stats(str(trace_path))
            monitor.stop()
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_after = process_memory_bytes()
            self._metrics["resources.python_peak"] = {
                "unit": "bytes",
                "samples": [peak],
            }
            self._metrics["resources.working_set_before"] = {
                "unit": "bytes",
                "samples": [memory_before.get("working_set") or 0],
            }
            self._metrics["resources.working_set_after"] = {
                "unit": "bytes",
                "samples": [memory_after.get("working_set") or 0],
            }
            self._metrics["ui.event_loop_delay"] = {
                "unit": "ms",
                "samples": monitor.delays_ms,
                "metadata": {
                    "stalls_over_50_ms": sum(
                        v > _STALL_WARNING_MS for v in monitor.delays_ms
                    ),
                    "stalls_over_100_ms": sum(
                        v > _STALL_CRITICAL_MS for v in monitor.delays_ms
                    ),
                },
            }
            self._metrics["resources.process_cpu_percent"] = {
                "unit": "percent",
                "samples": [process_elapsed / wall_elapsed * 100.0],
            }
            self._finish(0 if not self._errors else 1)

    def _measure_ui_data(self) -> None:
        events = self._window.data_coordinator.cached_events
        entities = self._window.data_coordinator.cached_entities
        unified = self._window.unified_list
        self._measure_repeated(
            "explorer.model_population",
            lambda: unified.set_data(events, entities),
        )
        self._measure_repeated(
            "explorer.search",
            lambda: self._set_search(unified, "Entity 24999"),
        )
        self._set_search(unified, "")
        self._measure_repeated(
            "explorer.filter",
            lambda: self._toggle_filter(unified),
        )
        self._measure_repeated(
            "explorer.sort",
            lambda: self._toggle_sort(unified),
        )
        self._measure_event_detail()

    @staticmethod
    def _set_search(widget: Any, value: str) -> None:
        widget.search_bar.setText(value)
        QApplication.processEvents()

    @staticmethod
    def _toggle_filter(widget: Any) -> None:
        next_index = 1 if widget.filter_combo.currentIndex() != 1 else 0
        widget.filter_combo.setCurrentIndex(next_index)
        QApplication.processEvents()

    @staticmethod
    def _toggle_sort(widget: Any) -> None:
        next_index = (
            _LORE_DATE_SORT_INDEX
            if widget.sort_combo.currentIndex() != _LORE_DATE_SORT_INDEX
            else 0
        )
        widget.sort_combo.setCurrentIndex(next_index)
        QApplication.processEvents()

    def _measure_timeline(self) -> None:
        view = self._window.timeline.view
        events = self._window.data_coordinator.cached_events
        self._measure_repeated("timeline.set_events", lambda: view.set_events(events))
        settled_started = time.perf_counter()
        self._wait_until(lambda: not view._layout_in_progress)
        self._record(
            "timeline.layout_settled",
            (time.perf_counter() - settled_started) * 1000.0,
        )
        self._measure_repeated("timeline.fit_all", view.fit_all)
        self._measure_repeated("timeline.pan", lambda: self._pan(view))
        self._measure_repeated("timeline.zoom", lambda: self._zoom(view))
        self._metrics["timeline.scene_items"] = {
            "unit": "count",
            "samples": [len(view.graphics_scene.items())],
        }
        self._measure_graph_refresh()
        self._measure_map_refresh()

    def _measure_event_detail(self) -> None:
        events = self._window.data_coordinator.cached_events
        if not events:
            return
        elapsed, completed = self._time_signal_action(
            self._window.data_handler.event_details_ready,
            lambda: self._window.data_coordinator.load_event_details(events[-1].id),
        )
        self._record("explorer.event_detail", elapsed)
        if not completed:
            self._warnings.append("Timed out loading event details.")

    def _measure_graph_refresh(self) -> None:
        elapsed, completed = self._time_signal_action(
            self._window.data_handler.graph_data_ready,
            self._window.data_coordinator.load_graph_data,
        )
        self._record("visualization.graph_refresh", elapsed)
        if not completed:
            self._warnings.append("Timed out refreshing graph data.")

    def _measure_map_refresh(self) -> None:
        elapsed, completed = self._time_signal_action(
            self._window.data_handler.maps_ready,
            lambda: invoke_queued(self._window.worker, "load_maps"),
        )
        self._record("visualization.map_list_refresh", elapsed)
        if not completed:
            self._warnings.append("Timed out refreshing map data.")

    @staticmethod
    def _pan(view: Any) -> None:
        bar = view.horizontalScrollBar()
        bar.setValue(bar.value() + max(1, bar.pageStep() // 5))
        QApplication.processEvents()

    @staticmethod
    def _zoom(view: Any) -> None:
        view.scale(1.01, 1.01)
        QApplication.processEvents()
        view.scale(1 / 1.01, 1 / 1.01)

    def _measure_playbar(self) -> None:
        view = self._window.timeline.view
        events = self._window.data_coordinator.cached_events
        if not events:
            return
        self._activate_entity_consumer()
        low = float(events[0].lore_date)
        high = float(events[-1].lore_date)
        positions = [
            low + (high - low) * index / max(1, self._options.scrub_positions - 1)
            for index in range(self._options.scrub_positions)
        ]
        for snapping in (False, True):
            view.set_playhead_event_snapping(snapping)
            suffix = "snap_on" if snapping else "snap_off"
            timeline_only: list[float] = []
            all_consumers: list[float] = []
            warmup_time = positions[0]
            candidate = view._manual_playhead_time(warmup_time * view.scale_factor)
            view._playhead.set_time(candidate, view.scale_factor)
            view.update_events_temporal_state()
            QApplication.processEvents()
            view._on_playhead_moved(warmup_time * view.scale_factor)
            QApplication.processEvents()
            resolved_count = 0

            def resolved(*_args: object) -> None:
                nonlocal resolved_count
                resolved_count += 1

            self._window.worker.entity_state_resolved.connect(resolved)
            for lore_time in positions:
                started = time.perf_counter()
                candidate = view._manual_playhead_time(lore_time * view.scale_factor)
                view._playhead.set_time(candidate, view.scale_factor)
                view.update_events_temporal_state()
                QApplication.processEvents()
                timeline_only.append((time.perf_counter() - started) * 1000.0)
            for lore_time in positions:
                started = time.perf_counter()
                view._on_playhead_moved(lore_time * view.scale_factor)
                QApplication.processEvents()
                all_consumers.append((time.perf_counter() - started) * 1000.0)
            convergence_started = time.perf_counter()
            self._wait_until(lambda: resolved_count >= len(positions), timeout_ms=60_000)
            convergence_ms = (time.perf_counter() - convergence_started) * 1000.0
            try:
                self._window.worker.entity_state_resolved.disconnect(resolved)
            except RuntimeError:
                pass
            self._metrics[f"playbar.timeline_only.{suffix}"] = {
                "unit": "ms",
                "samples": timeline_only,
                "metadata": {"frame_budget_ms": 33.3},
            }
            self._metrics[f"playbar.all_consumers.{suffix}"] = {
                "unit": "ms",
                "samples": all_consumers,
                "metadata": {
                    "frame_budget_ms": 33.3,
                    "submitted_entity_resolutions": len(positions),
                    "completed_entity_resolutions": resolved_count,
                    "unsettled_entity_resolutions": max(
                        0, len(positions) - resolved_count
                    ),
                    "background_convergence_ms": convergence_ms,
                },
            }
        final_time = positions[-1]
        actual_time = self._window.timeline.get_playhead_time()
        self._metrics["playbar.final_state"] = {
            "unit": "boolean",
            "samples": [
                1 if abs(actual_time - final_time) < _LORE_TIME_TOLERANCE else 0
            ],
            "metadata": {"expected": final_time, "actual": actual_time},
        }

    def _activate_entity_consumer(self) -> None:
        entities = self._window.data_coordinator.cached_entities
        if not entities:
            return
        self._window.workspace.show_panel("entity")
        elapsed, completed = self._time_signal_action(
            self._window.data_handler.entity_details_ready,
            lambda: self._window.data_coordinator.load_entity_details(entities[0].id),
        )
        self._record("playbar.consumer_activation", elapsed)
        if not completed:
            self._warnings.append(
                "Timed out activating the entity temporal consumer."
            )

    def _measure_playback(self) -> None:
        if self._options.playback_seconds <= 0:
            return
        timeline = self._window.timeline
        start_time = timeline.get_playhead_time()
        expected_ticks = int(
            self._options.playback_seconds * 1000 / timeline.view._playback_interval
        )
        timer_samples: list[float] = []
        last = time.perf_counter()

        def sample() -> None:
            nonlocal last
            now = time.perf_counter()
            timer_samples.append((now - last) * 1000.0)
            last = now

        timeline.view._playback_timer.timeout.connect(sample)
        timeline.view.start_playback()
        self._wait_ms(int(self._options.playback_seconds * 1000))
        timeline.view.stop_playback()
        try:
            timeline.view._playback_timer.timeout.disconnect(sample)
        except RuntimeError:
            pass
        actual_ticks = round(timeline.get_playhead_time() - start_time)
        self._metrics["playback.timer_interval"] = {
            "unit": "ms",
            "samples": timer_samples,
            "metadata": {
                "expected_ticks": expected_ticks,
                "actual_ticks": actual_ticks,
                "missed_ticks": max(0, expected_ticks - actual_ticks),
            },
        }

    def _measure_mutations(self) -> None:
        events = self._window.data_coordinator.cached_events
        if not events:
            return
        created_id = "11111111-2222-4333-8444-555555555555"
        commands = [
            (
                "mutation.create_event",
                CreateEventCommand(
                    {
                        "id": created_id,
                        "name": "Performance Probe Event",
                        "lore_date": 12_345.0,
                    }
                ),
            ),
            (
                "mutation.update_event",
                UpdateEventCommand(created_id, {"name": "Performance Probe Updated"}),
            ),
            ("mutation.delete_event", DeleteEventCommand(created_id)),
        ]
        for name, command in commands:
            elapsed, metadata = self._run_command(command)
            self._record(name, elapsed)
            self._metrics[name]["metadata"] = metadata
        if self._window.command_coordinator.can_undo():
            elapsed, completed = self._time_signal_action(
                self._window.data_handler.events_ready,
                self._window.command_coordinator.undo,
            )
            self._record("mutation.undo", elapsed)
            if not completed:
                self._warnings.append("Timed out undoing the probe mutation.")
        if self._window.command_coordinator.can_redo():
            elapsed, completed = self._time_signal_action(
                self._window.data_handler.events_ready,
                self._window.command_coordinator.redo,
            )
            self._record("mutation.redo", elapsed)
            if not completed:
                self._warnings.append("Timed out redoing the probe mutation.")

    def _run_command(self, command: Any) -> tuple[float, dict[str, int]]:
        counts = {"events_ready": 0, "entities_ready": 0, "graph_data_ready": 0}

        def count_events(*_args: object) -> None:
            counts["events_ready"] += 1

        def count_entities(*_args: object) -> None:
            counts["entities_ready"] += 1

        def count_graph(*_args: object) -> None:
            counts["graph_data_ready"] += 1

        handler = self._window.data_handler
        handler.events_ready.connect(count_events)
        handler.entities_ready.connect(count_entities)
        handler.graph_data_ready.connect(count_graph)
        elapsed, completed = self._time_signal_action(
            handler.events_ready,
            lambda: self._window.command_requested.emit(command),
        )
        for signal, callback in (
            (handler.events_ready, count_events),
            (handler.entities_ready, count_entities),
            (handler.graph_data_ready, count_graph),
        ):
            try:
                signal.disconnect(callback)
            except RuntimeError:
                pass
        if not completed:
            self._warnings.append(
                f"Timed out running {command.__class__.__name__}."
            )
        return elapsed, counts

    def _measure_repeated(self, name: str, action: Callable[[], object]) -> None:
        action()
        samples = []
        for _ in range(self._options.repetitions):
            started = time.perf_counter()
            action()
            samples.append((time.perf_counter() - started) * 1000.0)
        self._metrics[name] = {"unit": "ms", "samples": samples}

    def _record(self, name: str, value: float) -> None:
        metric = self._metrics.setdefault(name, {"unit": "ms", "samples": []})
        metric["samples"].append(value)

    @staticmethod
    def _wait_ms(duration_ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(max(0, duration_ms), loop.quit)
        loop.exec()

    def _time_signal_action(
        self,
        signal: Any,
        action: Callable[[], object],
        *,
        timeout_ms: int = 60_000,
    ) -> tuple[float, bool]:
        loop = QEventLoop()
        completed = False
        timeout = QTimer()
        timeout.setSingleShot(True)

        def finish(*_args: object) -> None:
            nonlocal completed
            completed = True
            loop.quit()

        signal.connect(finish)
        timeout.timeout.connect(loop.quit)
        timeout.start(timeout_ms)
        started = time.perf_counter()
        action()
        loop.exec()
        elapsed = (time.perf_counter() - started) * 1000.0
        timeout.stop()
        try:
            signal.disconnect(finish)
        except RuntimeError:
            pass
        QApplication.processEvents()
        return elapsed, completed

    @staticmethod
    def _wait_until(predicate: Callable[[], bool], timeout_ms: int = 60_000) -> bool:
        deadline = time.perf_counter() + timeout_ms / 1000.0
        while not predicate() and time.perf_counter() < deadline:
            QApplication.processEvents()
        return predicate()

    def _on_timeout(self) -> None:
        if self._completed:
            return
        self._errors.append("Performance probe watchdog expired.")
        self._finish(2)

    def _finish(self, exit_code: int) -> None:
        if self._completed:
            return
        self._completed = True
        self._watchdog.stop()
        self._write_report(status="complete")
        self._window.close()
        QApplication.exit(exit_code)

    def _checkpoint(self) -> None:
        """Persist completed scenario evidence before starting more work."""
        self._write_report(status="running")

    def _write_report(self, *, status: str) -> None:
        report = {
            "label": "MEASUREMENT ONLY",
            "profile": self._options.profile,
            "status": status,
            "success": status == "complete" and not self._errors,
            "errors": self._errors,
            "warnings": self._warnings,
            "metrics": self._metrics,
        }
        self._options.report_path.parent.mkdir(parents=True, exist_ok=True)
        self._options.report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
