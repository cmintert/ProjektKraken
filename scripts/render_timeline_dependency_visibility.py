"""Capture KRT-115 modes and measure real-layer cache reuse in isolated settings."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRectF, QSettings
from PySide6.QtGui import QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from scripts.render_timeline_dependencies import _events, _settle
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.core.timeline_visibility import DependencyVisibility
from src.gui.widgets.help_viewer import HelpViewer
from src.gui.widgets.timeline import EventItem, TimelineWidget
from src.gui.widgets.timeline.wire_router import route_wires
from src.services.help_bundle_service import HelpBundleService
from src.services.help_search_service import HelpSearchService

OUTPUT = Path("docs/ux/evidence/krt114/krt115")
NORMAL_WIDTH = 1200


def _save_sheet(images: list[QImage], path: Path) -> None:
    """Stack captures without scaling their readable text or altering their pixels."""
    sheet = QImage(
        max(image.width() for image in images),
        sum(image.height() for image in images),
        QImage.Format.Format_ARGB32,
    )
    sheet.fill(0)
    painter = QPainter(sheet)
    y = 0
    for image in images:
        painter.drawImage(0, y, image)
        y += image.height()
    painter.end()
    sheet.save(str(path))


def _captures(
    app: QApplication, manager: ThemeManager, converter: CalendarConverter
) -> None:
    """Keep a four-mode sheet per palette/width plus focus/menu/disabled controls."""
    for theme in manager.themes:
        manager.set_theme(theme, persist=False)
        for width in (NORMAL_WIDTH, 400):
            panel = TimelineWidget()
            panel.resize(width, 460)
            panel.show()
            _settle(app, panel)
            panel.view.set_temporal_context(
                TemporalResolutionContext.build(_events(True, converter), converter)
            )
            _settle(app, panel)
            panel.view._apply_zoom(2.0 if width == NORMAL_WIDTH else 0.8)
            panel.view.center_on_date(4)
            panel.view.verticalScrollBar().setValue(0)
            panel.set_selected_event_navigation("a", "The march begins")
            panel.view._event_items["a"].setSelected(True)
            images = []
            for mode in DependencyVisibility:
                panel.set_dependency_visibility(mode.value, persist=False)
                _settle(app, panel)
                images.append(panel.grab().toImage())
            _save_sheet(images, OUTPUT / f"{theme}-{width}-modes.png")
            if width == NORMAL_WIDTH:
                controls = []
                control = panel.dependency_control
                control.setFocus()
                _settle(app, panel)
                controls.append(control.grab().toImage())
                control.mode_menu.popup(
                    control.mapToGlobal(QPoint(0, control.height()))
                )
                control.mode_menu.setActiveAction(
                    control.mode_actions[DependencyVisibility.TRAIL]
                )
                app.processEvents()
                controls.append(control.mode_menu.grab().toImage())
                control.mode_menu.close()
                control.setEnabled(False)
                _settle(app, panel)
                controls.append(control.grab().toImage())
                _save_sheet(controls, OUTPUT / f"{theme}-control-states.png")
            panel.close()
            panel.deleteLater()
            app.processEvents()


def _benchmark(app: QApplication, crowded: bool, count: int) -> dict:
    """Measure cold preparation separately from warmed mode/selection paints."""
    events = []
    for index in range(count):
        source = f"source-{index}"
        target = f"target-{index}"
        timing = EventTimingDefinition(
            EndpointDefinition(
                kind="event",
                anchor_id=f"event:{source}",
                offset={"unit": "days", "value": 10},
            )
        )
        events.extend(
            [
                Event(id=source, name=source, lore_date=0),
                Event(
                    id=target, name=target, lore_date=10, attributes=timing.apply({})
                ),
            ]
        )
    panel = TimelineWidget()
    panel.view.set_events(events)
    panel.set_dependency_visibility("all", persist=False)
    # Fixed real label geometry: dense rows and interfering labels vs clear space.
    for index in range(count):
        y = 200 + index * (24 if crowded else 80)
        panel.view._event_items[f"source-{index}"].setPos(100, y)
        panel.view._event_items[f"target-{index}"].setPos(
            850, y + (48 if crowded else 0)
        )
    layer = panel.view._dependencies
    items = list(panel.view._event_items.values())
    image = QImage(1200, 900, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    started = perf_counter()
    curves, _ = layer.curves(items, painter, 0)
    cold_ms = (perf_counter() - started) * 1000
    baseline = [curve.path() for curve in curves]
    positions = [item.pos() for item in items]
    metrics = {}
    with patch(
        "src.gui.widgets.timeline.dependency_layer.route_wires", wraps=route_wires
    ) as router:
        for mode in DependencyVisibility:
            timings = []
            for iteration in range(5):
                started = perf_counter()
                panel.set_dependency_visibility(mode.value, persist=False)
                panel.view.set_dependency_selection(f"source-{iteration % count}")
                layer.paint(
                    painter,
                    items,
                    [],
                    QRectF(image.rect()),
                    ThemeManager().get_theme(),
                    prepared_only=True,
                )
                timings.append((perf_counter() - started) * 1000)
            metrics[mode.value] = {
                "warm_ms": timings,
                "median_ms": median(timings),
                "eligible_edges": len(layer.visible_dependencies()),
            }
        assert baseline == [
            curve.path() for curve in layer.curves(items, painter, 0)[0]
        ]
        assert positions == [item.pos() for item in items]
        assert router.call_count == 0
    painter.end()
    panel.close()
    panel.deleteLater()
    app.processEvents()
    return {
        "count": count,
        "crowded": crowded,
        "cold_ms": cold_ms,
        "missing_routes": sum(path.isEmpty() for path in baseline),
        "mode_metrics": metrics,
        "reroutes": router.call_count,
        "routes_and_positions_unchanged": True,
    }


def _help_captures(app: QApplication, manager: ThemeManager) -> None:
    """Check the real generated excerpt and render it through the Help companion."""
    bundle = HelpBundleService()
    excerpt = bundle.load_inspection_excerpt(
        "timeline.viewing", "help-inspect-timeline-show-dependencies"
    )
    assert excerpt is not None
    assert "Show dependency trail" in excerpt and "branches and merges" in excerpt
    results = HelpSearchService(bundle.search_documents()).search(
        "Show dependency trail"
    )
    assert any("timeline.viewing" in result.topic_ids for result in results[:5])
    owner = QWidget()
    for theme, width in (("dark_mode", 400), ("light_mode", 680)):
        manager.set_theme(theme, persist=False)
        viewer = HelpViewer(owner)
        viewer.resize(width, 600)
        viewer.set_content(excerpt)
        viewer.show()
        app.processEvents()
        viewer.grab().save(str(OUTPUT / f"help-{theme}-{width}.png"))
        viewer.close()
        viewer.deleteLater()
        app.processEvents()


def main() -> int:
    """Write reproducible offscreen evidence without reading or modifying a world."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--help-only", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-visibility-") as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        app = QApplication.instance() or QApplication([])
        for filename in ("segoeui.ttf", "segoeuib.ttf"):
            font = Path("C:/Windows/Fonts") / filename
            if font.exists():
                QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        converter = CalendarConverter(CalendarConfig.create_default())
        EventItem.set_calendar_converter(converter)
        try:
            _help_captures(app, manager)
            if args.help_only:
                return 0
            _captures(app, manager, converter)
            metrics = []
            for crowded in (False, True):
                for count in (5, 20, 50, 100):
                    metrics.append(_benchmark(app, crowded, count))
                    logging.info("Measured %s connections; crowded=%s", count, crowded)
            (OUTPUT / "metrics.json").write_text(
                json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
            )
        finally:
            EventItem.set_calendar_converter(None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
