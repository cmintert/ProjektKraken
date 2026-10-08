"""Reproduce KRT-50 baseline using production timeline items and ruler.

Run from the repository root with .venv/Scripts/python.exe.
Only comparison-row positions are controlled; temporal painting is unmodified.
"""

# Bootstrap the repository path and Qt platform before importing GUI modules.
# ruff: noqa: E402

import argparse
import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase, QTransform
from PySide6.QtWidgets import QApplication

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.temporal_display import event_temporal_display
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.timeline_view import TimelineView


def main() -> None:
    """Capture comparable rows, zoom thresholds, and semantic diagnostics."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "after" / "krt50",
    )
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt50-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication([])
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / filename))
        app.setOrganizationName("KrakenEvidence")
        app.setApplicationName("KRT50")
        app.setFont(QFont("Segoe UI", 10))
        theme = ThemeManager(str(ROOT / "themes.json"))
        theme.current_theme_name = "dark_mode"
        theme.apply_theme(
            app, (ROOT / "src/resources/main.qss").read_text(encoding="utf-8")
        )
        converter = CalendarConverter(CalendarConfig.create_default())
        parser = DateParser(converter._config)
        specs = [
            ("1 Exact date", "14 June 1218 12:00", 0),
            ("2 Exact date + 3 days", "14 June 1218 12:00", 3),
            ("3 Year only", "1218", 0),
            ("4 Approximate year", "c. 1218", 0),
            ("5 Year only + 3 days", "1218", 3),
            ("6 Approximate year + 3 days", "c. 1218", 3),
            ("7 Exact date + 240 days", "1 January 1218 12:00", 240),
            ("Neighbor: year begins", "1 January 1218 12:00", 0),
            ("Neighbor: next year begins", "1 January 1219 12:00", 0),
        ]
        events = []
        for name, authored, duration in specs:
            expression = parser.parse_expression(authored)
            events.append(
                Event(
                    name=name,
                    lore_date=expression.representative_time(converter),
                    lore_duration=duration,
                    attributes={
                        "_temporal_v2": {
                            "schema": 1,
                            "expression": expression.to_dict(),
                        }
                    },
                )
            )
        EventItem.set_calendar_converter(converter)
        view = TimelineView()
        view._ruler.set_calendar_converter(converter)
        view.resize(1900, 1350)
        view.show()
        view.set_events(events)
        view._playhead.hide()
        view._current_time_line.hide()
        app.processEvents()
        records = []
        for filename, pixels_per_day in [
            ("year-visible.png", 1.2),
            ("year-tight.png", 2.4),
            ("duration-below-6px.png", 0.015),
            ("duration-above-6px.png", 0.017),
            ("occurrence-below-24px.png", 0.064),
            ("occurrence-above-24px.png", 0.067),
        ]:
            zoom = pixels_per_day / view.scale_factor
            view.setTransform(QTransform().scale(zoom, 1))
            view._current_zoom = zoom
            # Stable independent comparison lanes, not a lane-packing claim.
            for row, event in enumerate(events):
                item = view._event_items[event.id]
                item.set_zoom(zoom)
                item.setY(95 + row * 125)
                line = view._drop_lines[event.id]
                line.setLine(item.x(), -view.RULER_HEIGHT, item.x(), item.y())
            center = converter.start_of_year(1218) + 180
            view.graphics_scene.setSceneRect(
                (center - 4000) * view.scale_factor,
                -50,
                8000 * view.scale_factor,
                1350,
            )
            view.centerOn(center * view.scale_factor, 625)
            app.processEvents()
            view.grab().save(str(output / filename))
            records.append(
                {
                    "file": filename,
                    "pixels_per_day": pixels_per_day,
                    "cases": [
                        {
                            "name": event.name,
                            "authored": authored,
                            "duration_days": duration,
                            "display": asdict(event_temporal_display(event, converter)),
                            "layout": _layout_record(view._event_items[event.id]),
                            "presence_geometry": asdict(
                                view._event_items[event.id]._geometry(
                                    event_temporal_display(event, converter)
                                )
                            ),
                        }
                        for event, (_, authored, duration) in zip(events, specs)
                    ],
                }
            )
        (output / "render.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )
        view.close()
        logging.info("Captured %s comparison timelines", len(records))


def _layout_record(item: EventItem) -> dict:
    """Record the actual paint/hit layout independently of legacy presence geometry."""
    layout = item._layout()
    return {
        "bounds": [
            layout.bounds.x(),
            layout.bounds.y(),
            layout.bounds.width(),
            layout.bounds.height(),
        ],
        "rows": [
            {
                "label": row.label,
                "y": row.y,
                "measure": row.measure,
                "value": row.value,
                "geometry": asdict(row.geometry),
            }
            for row in layout.rows
        ],
    }


if __name__ == "__main__":
    main()
