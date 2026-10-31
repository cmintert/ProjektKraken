"""Measure theme switching with isolated settings and deterministic GUI fixtures.

Run with ``python -m scripts.benchmark_theme_switch --output tmp/theme-before.json``.
Timing runs are unprofiled. A separate instrumented switch records operation counts.
No world files or databases are opened.
"""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import json
import logging
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_QUIET_EVENT_PASSES = 3


class _SourceOverlay(importlib.abc.MetaPathFinder):
    """Load only changed baseline modules without modifying the worktree."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        relative = Path(*fullname.split("."))
        package = self.root / relative / "__init__.py"
        if package.exists():
            return importlib.util.spec_from_file_location(
                fullname,
                package,
                submodule_search_locations=[
                    str(package.parent),
                    str(Path.cwd() / relative),
                ],
            )
        source = (self.root / relative).with_suffix(".py")
        if source.exists():
            return importlib.util.spec_from_file_location(fullname, source)
        return None


def _baseline_sources(reference: str, root: Path) -> None:
    """Snapshot changed tracked Python modules from an immutable Git reference."""
    command = ["git", "-c", f"safe.directory={Path.cwd().as_posix()}"]
    changed = subprocess.check_output(
        [*command, "diff", reference, "--name-only", "--", "src"], text=True
    ).splitlines()
    for name in changed:
        if name.endswith(".py"):
            contents = subprocess.check_output(
                [*command, "show", f"{reference}:{name}"]
            )
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)


def _wait(app: Any, predicate: Any, timeout: float = 30) -> None:
    deadline = time.perf_counter() + timeout
    while not predicate():
        app.processEvents()
        if time.perf_counter() > deadline:
            raise TimeoutError("Theme fixture did not settle")
        time.sleep(0.001)


def _settle(app: Any, graph: Any) -> None:
    # Drain layout, deferred geometry timers and paint work before browser checks.
    runtime = getattr(app, "_kraken_theme_presentation", None)
    if runtime is not None:
        _wait(app, lambda: not runtime.is_pending)
    _drain_layout(app)
    if graph is not None:
        _wait(app, lambda: getattr(graph._web_view, "_pending_theme", None) is None)
        view = graph._web_view._web_view
        ready: list[Any] = []
        script = (
            "Boolean(window.updateGraph && typeof network !== 'undefined' "
            "&& !document.hidden && document.readyState === 'complete' "
            f"&& window.__themeBenchGeneration === {graph._theme_bench_generation})"
        )
        deadline = time.perf_counter() + 30
        while True:
            ready.clear()
            view.page().runJavaScript(script, lambda value: ready.append(value))
            _wait(app, lambda: bool(ready))
            if ready[0]:
                break
            if time.perf_counter() > deadline:
                raise TimeoutError("Graph renderer did not become ready")
        view.page().runJavaScript(
            "window.__themeBenchPainted=false; requestAnimationFrame(() => "
            "requestAnimationFrame(() => {window.__themeBenchPainted=true;}));"
        )
        painted: list[Any] = []
        while not painted or not painted[0]:
            painted.clear()
            view.page().runJavaScript(
                "window.__themeBenchPainted", lambda value: painted.append(value)
            )
            _wait(app, lambda: bool(painted))
            if time.perf_counter() > deadline:
                raise TimeoutError("Graph paint acknowledgement timed out")
    _drain_layout(app)


def _drain_layout(app: Any) -> None:
    from shiboken6 import getCppPointer

    previous: Any = None
    quiet = 0
    deadline = time.perf_counter() + 10
    while quiet < _QUIET_EVENT_PASSES:
        app.processEvents()
        # Some legacy layouts keep posting redundant requests without changing
        # geometry. Require stable visible geometry after draining each batch.
        current = tuple(
            sorted(
                (getCppPointer(widget)[0], widget.geometry().getRect())
                for widget in app.allWidgets()
                if widget.isVisible()
            )
        )
        quiet = quiet + 1 if previous == current else 0
        previous = current
        if time.perf_counter() > deadline:
            raise TimeoutError("Qt layout/paint events did not settle")
        time.sleep(0.001)


def _fixtures(app: Any, scenario: str) -> tuple[list[Any], Any]:
    from PySide6.QtCore import Qt

    from scripts.capture_inspector_evidence import _EvidenceHost, _make_editor
    from src.gui.widgets.settings_center import SettingsCenter

    widgets: list[Any] = []
    for kind in ("entity", "event"):
        host = _EvidenceHost()
        editor = _make_editor(kind, host)
        editor._benchmark_host = host
        editor.setWindowFlag(Qt.WindowType.Window)
        widgets.append(editor)
    widgets.append(SettingsCenter())
    graph = None
    if scenario == "loaded":
        from src.core.events import Event
        from src.gui.widgets.graph_view.graph_widget import GraphWidget
        from src.gui.widgets.longform.content import LongformContentWidget
        from src.gui.widgets.timeline import TimelineWidget

        timeline = TimelineWidget()
        events = [
            Event(id=str(i), name=f"Event {i}", lore_date=float(i)) for i in range(100)
        ]
        timeline.set_events(events)
        graph = GraphWidget()
        graph._theme_bench_generation = 0
        original_load = graph._web_view.load_html

        def tracked_load(html: str) -> None:
            graph._theme_bench_generation += 1
            marker = (
                "<script>window.__themeBenchGeneration="
                f"{graph._theme_bench_generation};</script>"
            )
            original_load(html.replace("<head>", "<head>" + marker, 1))

        graph._web_view.load_html = tracked_load
        graph._all_nodes = [
            {"id": str(i), "name": f"Node {i}", "object_type": "entity"}
            for i in range(60)
        ]
        graph._all_edges = [
            {
                "id": str(i),
                "source_id": str(i),
                "target_id": str(i + 1),
                "rel_type": "related",
            }
            for i in range(59)
        ]
        graph._refresh_display_locally()
        longform = LongformContentWidget()
        longform.load_content(
            [
                {
                    "id": str(i),
                    "name": f"Chapter {i}",
                    "table": "events",
                    "heading_level": 1,
                    "meta": {},
                    "content": "A **passage** with [[Node 1]] and context.\n\n" * 15,
                }
                for i in range(40)
            ]
        )
        widgets.extend([timeline, graph, longform])
    for widget in widgets:
        widget.setFixedSize(960, 720)
        widget.show()
    _settle(app, graph)
    if scenario == "loaded":
        widgets[0].hide()
        widgets[2].hide()
    return widgets, graph


def _configure_fonts(app: Any) -> None:
    """Use the shipped UI's Windows face explicitly in offscreen captures."""
    from PySide6.QtGui import QFont, QFontDatabase

    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI", 10))


def _child(options: argparse.Namespace) -> None:
    if options.overlay:
        sys.meta_path.insert(0, _SourceOverlay(Path(options.overlay)))
    from scripts.gui_probe_settings import install_probe_settings

    logging.disable(logging.CRITICAL)
    with tempfile.TemporaryDirectory(prefix="kraken-theme-bench-") as settings:
        install_probe_settings(settings)
        from PySide6 import __version__ as qt_version
        from PySide6.QtCore import QEvent, QObject
        from PySide6.QtWidgets import QApplication

        from src.core.theme_manager import ThemeManager

        app = QApplication([])
        _configure_fonts(app)
        if options.presentation == "scoped":
            from src.gui.utils.theme_presentation import install_theme_presentation

            install_theme_presentation(app)
        event_names = {
            QEvent.Type.LayoutRequest: "layout",
            QEvent.Type.Paint: "paint",
            QEvent.Type.StyleChange: "style",
        }

        class Events(QObject):
            def __init__(self) -> None:
                super().__init__(app)
                self.counts = {"layout": 0, "paint": 0, "style": 0}

            def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
                key = event_names.get(event.type())
                if key:
                    self.counts[key] += 1
                return False

        observer = Events()
        manager = ThemeManager()
        manager.current_theme_name = "dark_mode"
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        widgets, graph = _fixtures(app, options.scenario)
        samples = []
        for index in range(options.warmups + options.samples):
            name = "light_mode" if index % 2 == 0 else "dark_mode"
            started = time.perf_counter()
            manager.set_theme(name, persist=False)
            switched = time.perf_counter()
            _settle(app, graph)
            ended = time.perf_counter()
            if index >= options.warmups:
                samples.append({"sync": switched - started, "settled": ended - started})
        counts: dict[str, int] = dict.fromkeys(
            [
                "setStyleSheet",
                "updateGeometry",
                "render",
                "setHtml",
                "_render_markdown_fragment",
                "load_html",
                "_flush_geometry",
            ],
            0,
        )

        def count(_frame: Any, event: str, arg: Any) -> None:
            if event == "c_call":
                name = getattr(arg, "__name__", "")
                if name in ("setStyleSheet", "updateGeometry", "render", "setHtml"):
                    counts[name] = counts.get(name, 0) + 1
            elif event == "call":
                name = _frame.f_code.co_name
                if name in (
                    "_render_markdown_fragment",
                    "load_html",
                    "_flush_geometry",
                ):
                    counts[name] = counts.get(name, 0) + 1

        app.installEventFilter(observer)
        sys.setprofile(count)
        try:
            manager.set_theme("light_mode", persist=False)
            _settle(app, graph)
        finally:
            sys.setprofile(None)
            app.removeEventFilter(observer)
        result = {
            "scenario": options.scenario,
            "samples": samples,
            "counts": counts,
            "qt_events": observer.counts,
            "widgets": len(app.allWidgets()),
            "python": platform.python_version(),
            "pyside": qt_version,
            "platform": app.platformName(),
            "viewport": [960, 720],
        }
        Path(options.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        if graph is not None:
            graph._web_view.shutdown()
        for widget in widgets:
            widget.close()


def main() -> None:
    """Run matched scenarios in fresh processes and retain raw measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--scenario", choices=("editors", "loaded"))
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--baseline-ref", help="Interleave baseline and worktree runs")
    parser.add_argument("--overlay", help=argparse.SUPPRESS)
    parser.add_argument(
        "--presentation", choices=("legacy", "scoped"), default="scoped"
    )
    options = parser.parse_args()
    if options.child:
        _child(options)
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
    runs = []
    with tempfile.TemporaryDirectory(prefix="kraken-theme-results-") as directory:
        overlay = Path(directory) / "baseline"
        variants = ["worktree"]
        if options.baseline_ref:
            _baseline_sources(options.baseline_ref, overlay)
            variants = ["baseline", "worktree"]
        for scenario in (
            [options.scenario] if options.scenario else ["editors", "loaded"]
        ):
            for index in range(options.runs):
                for variant in variants:
                    output = str(Path(directory) / f"{variant}-{scenario}-{index}.json")
                    overlay_args = (
                        ["--overlay", str(overlay)] if variant == "baseline" else []
                    )
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "scripts.benchmark_theme_switch",
                            "--child",
                            "--scenario",
                            scenario,
                            "--output",
                            output,
                            "--warmups",
                            str(options.warmups),
                            "--samples",
                            str(options.samples),
                            "--presentation",
                            "legacy" if variant == "baseline" else options.presentation,
                        ]
                        + overlay_args,
                        check=True,
                    )
                    result = json.loads(Path(output).read_text("utf-8"))
                    result["variant"] = variant
                    runs.append(result)
    summary = {}
    for variant, scenario in {(run["variant"], run["scenario"]) for run in runs}:
        entries = [
            sample
            for run in runs
            if run["scenario"] == scenario and run["variant"] == variant
            for sample in run["samples"]
        ]
        summary[f"{variant}:{scenario}"] = {
            metric: {
                "median": statistics.median(values),
                "p95": sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)],
            }
            for metric in ("sync", "settled")
            for values in [[entry[metric] for entry in entries]]
        }
    Path(options.output).parent.mkdir(parents=True, exist_ok=True)
    Path(options.output).write_text(
        json.dumps(
            {"baseline_ref": options.baseline_ref, "summary": summary, "runs": runs},
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
