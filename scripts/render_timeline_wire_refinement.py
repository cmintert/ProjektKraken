"""Reproduce KRT-116 geometry comparisons without opening a saved world.

Run before editing the router, then again with --phase after. Captures use the
same logical geometry at both zooms; metrics distinguish missing paths from
unavoidable crossings. The JSON includes per-run latency, not a UI frame claim.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter
from types import ModuleType
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, QSettings
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication

from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.wire_router import Wire, route_wires

OUTPUT = Path("docs/ux/evidence/krt114/krt116")
GEOMETRY_EPSILON = 1e-6
BASELINE = "9b6554bebce91f086c45bbcbca27e7c7beb68b98"


class Router(Protocol):
    """Both the original and current renderer retain the optional routing floor."""

    def __call__(
        self,
        wires: list[Wire],
        obstacles: list[QRectF],
        minimum_y: float | None = None,
        /,
    ) -> list[QPainterPath]:
        """Route one ordered batch in logical display coordinates."""
        ...


def baseline_router() -> Router:
    """Load the immutable original router without checking out or changing files."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "show",
            f"{BASELINE}:src/gui/widgets/timeline/wire_router.py",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    module = ModuleType("krt116_original_router")
    sys.modules[module.__name__] = module
    exec(compile(result.stdout, "<KRT-114 baseline router>", "exec"), module.__dict__)
    return module.route_wires


def corridor(count: int, zoom: float = 1.0) -> tuple[list[Wire], list[QRectF]]:
    """A shared corridor with fixed endpoints and more than eight competitors."""
    wires = [
        Wire(QPointF(40, 220 + i * 8), QPointF(720, 220 + i * 8), 1, -1)
        for i in range(count)
    ]
    obstacles = [QRectF(290, 205, 130, count * 8 + 30)]
    return (
        [
            Wire(w.source * zoom, w.target * zoom, w.source_side, w.target_side)
            for w in wires
        ],
        [QRectF(r.topLeft() * zoom, r.size() * zoom) for r in obstacles],
    )


def segments(path: object) -> list[tuple[float, float, float, float]]:
    """Return flattened segments for independent visual-comparison metrics."""
    from PySide6.QtGui import QPainterPath

    assert isinstance(path, QPainterPath)
    return [
        (a.x(), a.y(), b.x(), b.y())
        for polygon in path.toSubpathPolygons()
        for points in [list(polygon)]
        for a, b in zip(points, points[1:])
    ]


def shared_length(paths: list) -> float:
    """Measure exact collinear runs, excluding point-only crossings."""
    total = 0.0
    prior: list[tuple[float, float, float, float]] = []
    for path in paths:
        current = segments(path)
        for x, y, xx, yy in current:
            for u, v, uu, vv in prior:
                if (
                    abs(y - yy) < GEOMETRY_EPSILON
                    and abs(y - v) + abs(y - vv) < GEOMETRY_EPSILON
                ):
                    total += max(
                        0, min(max(x, xx), max(u, uu)) - max(min(x, xx), min(u, uu))
                    )
                elif (
                    abs(x - xx) < GEOMETRY_EPSILON
                    and abs(x - u) + abs(x - uu) < GEOMETRY_EPSILON
                ):
                    total += max(
                        0, min(max(y, yy), max(v, vv)) - max(min(y, yy), min(v, vv))
                    )
        prior.extend(current)
    return total


def measure(
    wires: list[Wire], obstacles: list[QRectF], router: Router = route_wires
) -> tuple[list, dict]:
    """Time three identical batches and quantify stroke/body intersections."""
    from PySide6.QtGui import QPainterPathStroker

    timings = []
    paths = []
    for _ in range(3):
        start = perf_counter()
        paths = router(wires, obstacles)
        timings.append((perf_counter() - start) * 1000)
    stroker = QPainterPathStroker()
    stroker.setWidth(3)
    strokes = [stroker.createStroke(path) for path in paths]
    return paths, {
        "routing_ms": timings,
        "median_ms": median(timings),
        "missing": sum(path.isEmpty() for path in paths),
        "obstacle_collisions": sum(
            any(stroke.intersects(rect) for rect in obstacles) for stroke in strokes
        ),
        "intersecting_pairs": sum(
            stroke.intersects(other)
            for index, stroke in enumerate(strokes)
            for other in strokes[:index]
        ),
        "shared_straight_px": shared_length(paths),
        "path_elements": sum(path.elementCount() for path in paths),
        "length_px": sum(path.length() for path in paths),
        "detour_bounds": [
            [r.x(), r.y(), r.width(), r.height()]
            for path in paths
            for r in [path.boundingRect()]
        ],
    }


def blocker_scenes() -> dict[str, tuple[list[Wire], list[QRectF]]]:
    """Multiple independent wires, shared endpoints, and staggered painted blockers."""
    single = [Wire(QPointF(30, 220), QPointF(900, 220), 1, -1)]
    cluster = single + [
        Wire(QPointF(30, 280), QPointF(900, 320), 1, -1),
        Wire(QPointF(30, 380), QPointF(900, 400), 1, -1),
    ]
    blockers = [
        QRectF(300, 180, 100, 80),
        QRectF(420, 240, 90, 120),
        QRectF(530, 150, 100, 80),
    ]
    branches = cluster + [
        Wire(QPointF(30, 220), QPointF(900, 540), 1, -1),
        Wire(QPointF(30, 540), QPointF(900, 400), 1, -1),
        Wire(QPointF(30, 620), QPointF(900, 620), 1, -1),
    ]
    return {
        "single-blocker": (single, blockers[:1]),
        "staggered-cluster": (cluster, blockers),
        "branches-and-merges": (branches, [*blockers, QRectF(600, 400, 100, 70)]),
    }


def render_blockers(output: Path, manager: ThemeManager, router: Router) -> dict:
    """Capture the requested multi-Event/multi-blocker visual comparisons."""
    metrics = {}
    for name, (wires, obstacles) in blocker_scenes().items():
        for zoom in (0.8, 2.0):
            scaled_wires = [
                Wire(w.source * zoom, w.target * zoom, w.source_side, w.target_side)
                for w in wires
            ]
            scaled_rects = [
                QRectF(r.topLeft() * zoom, r.size() * zoom) for r in obstacles
            ]
            paths, result = measure(scaled_wires, scaled_rects, router)
            metrics[f"{name}-{zoom}"] = result
            for theme in ("dark_mode", "light_mode"):
                manager.set_theme(theme, persist=False)
                for width in (400, 1200):
                    capture(
                        output / f"{theme}-{name}-{zoom}-{width}.png",
                        width,
                        manager.get_theme(),
                        scaled_wires,
                        scaled_rects,
                        paths,
                    )
    return metrics


def render_widget(
    output: Path, app: QApplication, manager: ThemeManager, router: Router
) -> dict:
    """Exercise real Event captions, duration marks, paint, pan and zoom."""
    import src.gui.widgets.timeline.dependency_layer as layer_module
    from scripts.render_timeline_dependencies import _follow
    from src.core.calendar import CalendarConfig, CalendarConverter
    from src.core.events import Event
    from src.core.temporal_context import TemporalResolutionContext
    from src.gui.widgets.timeline import EventItem, TimelineWidget

    events = [
        Event(id="source", name="The first signal", lore_date=0),
        Event(id="dur", name="The siege", lore_date=6, lore_duration=4),
        Event(id="block1", name="An intervening council", lore_date=4),
        Event(id="block2", name="The bridges close", lore_date=9),
        Event(id="block3", name="A second council", lore_date=14),
        _follow("a", "source", 20, "The army arrives"),
        _follow("b", "source", 24, "The fleet arrives"),
        _follow("c", "a", 8, "The treaty is signed"),
        _follow("d", "dur", 18, "The gates reopen"),
    ]
    converter = CalendarConverter(CalendarConfig.create_default())
    context = TemporalResolutionContext.build(events, converter)
    EventItem.set_calendar_converter(converter)
    original = layer_module.route_wires
    layer_module.route_wires = router
    measurements = {}
    try:
        for theme in ("dark_mode", "light_mode"):
            manager.set_theme(theme, persist=False)
            for width in (400, 1200):
                for zoom in (0.8, 2.0):
                    panel = TimelineWidget()
                    panel.resize(width, 1000)
                    panel.show()
                    panel.view.set_ruler_calendar(converter)
                    panel.view.set_temporal_context(context)
                    panel.view._apply_zoom(zoom)
                    panel.view.center_on_date(12)
                    start = perf_counter()
                    for _ in range(4):
                        app.processEvents()
                    panel.grab().save(
                        str(output / f"widget-{theme}-{zoom}-{width}.png")
                    )
                    measurements[f"{theme}-{width}-{zoom}"] = {
                        "settle_and_capture_ms": (perf_counter() - start) * 1000,
                        "events": len(events),
                        "dependencies": len(panel.view._dependencies.dependencies),
                    }
                    measurements[f"{theme}-{width}-{zoom}"].update(
                        profile_widget(panel, app, router)
                    )
                    panel.close()
                    panel.deleteLater()
                    app.processEvents()
    finally:
        layer_module.route_wires = original
        EventItem.set_calendar_converter(None)
    return measurements


def profile_widget(panel: object, app: QApplication, router: Router) -> dict:
    """Measure actual cached captures and count pan/selection/zoom cache misses."""
    import src.gui.widgets.timeline.dependency_layer as layer_module
    from src.gui.widgets.timeline import TimelineWidget

    assert isinstance(panel, TimelineWidget)
    durations = []

    def timed(
        wires: list[Wire], obstacles: list[QRectF], floor: float | None = None
    ) -> list[QPainterPath]:
        start = perf_counter()
        paths = router(wires, obstacles, floor)
        durations.append((perf_counter() - start) * 1000)
        return paths

    original = layer_module.route_wires
    layer_module.route_wires = timed
    try:
        panel.view._dependencies._routing_key = None
        panel.view._prepare_dependency_routes()
        cold = list(durations)
        durations.clear()
        frames = []
        for _ in range(5):
            start = perf_counter()
            panel.grab()
            app.processEvents()
            frames.append((perf_counter() - start) * 1000)
        repaint_misses = len(durations)
        durations.clear()
        panel.view._event_items["source"].setSelected(True)
        app.processEvents()
        selection_misses = len(durations)
        durations.clear()
        scrollbar = panel.view.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() + 30)
        app.processEvents()
        pan_misses = len(durations)
        durations.clear()
        panel.view._apply_zoom(panel.view._current_zoom * 1.05)
        for _ in range(4):
            app.processEvents()
        return {
            "cold_route_ms": cold,
            "warm_capture_ms": frames,
            "repaint_misses": repaint_misses,
            "selection_misses": selection_misses,
            "pan_misses": pan_misses,
            "zoom_route_ms": durations,
        }
    finally:
        layer_module.route_wires = original


def render_help(output: Path, app: QApplication, manager: ThemeManager) -> None:
    """Inspect the actual offline reference at its unchanged contextual anchor."""
    from src.gui.widgets.help_viewer import HelpViewer
    from src.services.help_bundle_service import HelpBundleService
    from src.services.help_search_service import HelpSearchService

    service = HelpBundleService(root=Path("docs/_build/help"))
    topic = service.resolve_topic("timeline.viewing")
    results = HelpSearchService(service.search_documents()).search("Show dependencies")
    assert any("timeline.viewing" in result.topic_ids for result in results)
    for theme in ("dark_mode", "light_mode"):
        manager.set_theme(theme, persist=False)
        for width in (400, 680):
            viewer = HelpViewer(None)
            viewer.title.setText(topic.title)
            viewer.set_content(service.load_page(topic.page))
            viewer.resize(width, 900)
            viewer.show()
            app.processEvents()
            viewer.browser.scrollToAnchor("help-inspect-timeline-show-dependencies")
            app.processEvents()
            viewer.grab().save(str(output / f"help-{theme}-{width}.png"))
            viewer.close()
            viewer.deleteLater()
            app.processEvents()


def capture(
    destination: Path,
    width: int,
    theme: dict,
    wires: list[Wire],
    obstacles: list[QRectF],
    paths: list,
) -> None:
    """Draw complete geometry on a scroll-equivalent fixed-width viewport."""
    height = int(max((p.boundingRect().bottom() for p in paths), default=500) + 80)
    image = QImage(width, max(500, height), QImage.Format.Format_ARGB32)
    image.fill(QColor(theme["surface"] if "surface" in theme else theme["app_bg"]))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(theme["text_main"]), 1))
        for index, rect in enumerate(obstacles):
            painter.drawRect(rect)
            painter.drawText(
                rect.topLeft() + QPointF(4, 16), f"Painted blocker {index}"
            )
        for index, (wire, path) in enumerate(zip(wires, paths)):
            painter.setPen(QPen(QColor(theme[f"timeline_dependency_{index % 8}"]), 2.5))
            painter.drawPath(path)
            painter.drawEllipse(wire.source, 2, 2)
            end = wire.target
            painter.drawLine(end, end + QPointF(wire.target_side * 6, -4))
            painter.drawLine(end, end + QPointF(wire.target_side * 6, 4))
    finally:
        painter.end()
    image.save(str(destination))


def main() -> int:
    """Retain before/after metrics and dark/light captures of the same fixtures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--scenes-only", action="store_true")
    args = parser.parse_args()
    output = OUTPUT / args.phase
    output.mkdir(parents=True, exist_ok=True)
    router = baseline_router() if args.phase == "before" else route_wires
    with tempfile.TemporaryDirectory(prefix="kraken-wire-refinement-") as preferences:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, preferences
        )
        app = QApplication.instance() or QApplication([])
        for filename in ("segoeui.ttf", "segoeuib.ttf"):
            font = Path("C:/Windows/Fonts") / filename
            if font.exists():
                QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        results = {}
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        for count in () if args.scenes_only else (5, 20, 50, 100):
            for zoom in (0.8, 2.0):
                wires, obstacles = corridor(count, zoom)
                paths, metrics = measure(wires, obstacles, router)
                results[f"corridor-{count}-{zoom}"] = metrics
                for theme_name in ("dark_mode", "light_mode"):
                    manager.set_theme(theme_name, persist=False)
                    for width in (400, 1200):
                        capture(
                            output / f"{theme_name}-{count}-{zoom}-{width}.png",
                            width,
                            manager.get_theme(),
                            wires,
                            obstacles,
                            paths,
                        )
        if not args.scenes_only:
            (output / "metrics.json").write_text(json.dumps(results, indent=2), "utf-8")
        scenes = render_blockers(output, manager, router)
        scenes["widget"] = render_widget(output, app, manager, router)
        (output / "scenes.json").write_text(json.dumps(scenes, indent=2), "utf-8")
        if args.phase == "after":
            render_help(output, app, manager)
    logging.info("KRT-116 %s evidence: %s", args.phase, output)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
