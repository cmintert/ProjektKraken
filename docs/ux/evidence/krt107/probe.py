"""Reproduce detached packing metrics and disposable offscreen timeline renders.

Run python -m docs.ux.evidence.krt107.probe; artifacts stay under artifacts/krt107.
No database or existing world is opened. Screenshots are not native UX acceptance.
"""

import json
import tempfile
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
)
from src.core.theme_manager import ThemeManager
from src.core.timeline_layout import (
    TimelineLayoutInput,
    TimelineLayoutSnapshot,
    pack_stable_timeline_intervals,
)
from src.gui.widgets.timeline import EventItem, TimelineWidget


def main() -> None:
    """Write repeatable metrics and reviewable real-widget captures."""
    output = Path("artifacts/krt107")
    output.mkdir(parents=True, exist_ok=True)
    metrics = []
    for count in (50, 500, 5000):
        prior = TimelineLayoutSnapshot()
        for width in (1, 2, 1):
            spans = tuple(
                TimelineLayoutInput(str(i), i / 4, i / 4 + width, 40)
                for i in range(count)
            )
            start = perf_counter()
            lanes, heights = pack_stable_timeline_intervals(spans, prior)
            metrics.append(
                dict(
                    count=count,
                    width=width,
                    seconds=perf_counter() - start,
                    rows=len(heights),
                )
            )
            prior = TimelineLayoutSnapshot(tuple(lanes.items()), tuple(heights))
    with tempfile.TemporaryDirectory(prefix="krt107-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        calendar = CalendarConfig.create_default()
        converter = CalendarConverter(calendar)
        EventItem._calendar_converter = converter
        expression = TemporalExpression(
            calendar_id=calendar.id,
            year=1,
            month=1,
            precision=TemporalPrecision.MONTH,
            qualifier=TemporalQualifier.UNCERTAIN,
        )
        events = [
            Event(id=str(day), name=name, lore_date=converter.start_of_day(1, 1, day))
            for day, name in (
                (1, "01 - The march begins"),
                (10, "02 - The Northwatch succession"),
                (20, "04 - The new kingdom"),
            )
        ]
        events += [
            Event(
                id="disputed",
                name="03 - A disputed surrender report",
                lore_date=expression.representative_time(converter),
                attributes={
                    "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
                },
            ),
            Event(
                id="battle",
                name="Hardwood Battle",
                lore_date=converter.start_of_day(1, 1, 7) + 0.75,
            ),
        ]
        captures = []
        for theme in manager.get_available_themes():
            manager.set_theme(theme, app)
            for width in (480, 1600):
                widget = TimelineWidget()
                widget.resize(width, 430)
                widget.show()
                widget.set_events(events)
                for zoom in (2.6, 3.2, 2.6):
                    widget.view._apply_zoom(zoom)
                    app.processEvents()
                    state = widget.view._lane_history.snapshot()
                    captures.append(
                        dict(
                            theme=theme,
                            width=width,
                            zoom=zoom,
                            lanes=dict(state.lanes),
                            heights=state.heights,
                            intervals=[
                                vars(i)
                                for i in widget.view._lane_packer.measure_events(events)
                            ],
                        )
                    )
                widget.btn_fit.setFocus()
                app.processEvents()
                widget.grab().save(str(output / f"{theme}-{width}.png"))
                widget.close()
                widget.deleteLater()
                app.processEvents()
    (output / "probe.json").write_text(
        json.dumps(dict(metrics=metrics, captures=captures), indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
