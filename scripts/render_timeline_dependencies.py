"""Render reproducible offscreen KRT-114 evidence without opening a world."""

import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline import EventItem, TimelineWidget

OUTPUT = Path("docs/ux/evidence/krt114")


def _follow(identity: str, source: str, offset: float, name: str) -> Event:
    definition = EventTimingDefinition(
        EndpointDefinition(
            kind="event",
            anchor_id=f"event:{source}",
            offset={"unit": "days", "value": offset},
        )
    )
    return Event(
        id=identity, name=name, lore_date=None, attributes=definition.apply({})
    )


def _events(crowded: bool, converter: CalendarConverter) -> list[Event]:
    events = [
        Event(id="a", name="The march begins", lore_date=0),
        _follow("b", "a", 4, "Hardwood Battle"),
        Event(id="x", name="The fleet departs", lore_date=1),
        _follow("y", "x", 6, "The fleet reaches port"),
    ]
    if crowded:
        expression = DateParser(converter._config).parse_expression("January 1")
        events.extend(
            [
                _follow("c", "b", 1, "The city surrenders"),
                _follow("d", "a", 2, "Scouts reach the crossing"),
                _follow("e", "d", 1, "A messenger returns"),
                _follow("z", "y", -2, "The signal arrives before the fleet"),
                Event(id="q", name="The siege", lore_date=2, lore_duration=3),
                _follow("r", "q", 4, "Reinforcements arrive"),
                Event(
                    id="u",
                    name="An uncertain winter council",
                    lore_date=None,
                    attributes=EventTimingDefinition(
                        EndpointDefinition(expression=expression.to_dict()),
                        "duration",
                        duration_days=2,
                    ).apply({}),
                ),
                _follow("v", "u", 2, "A decree follows the council"),
            ]
        )
        end = EventTimingDefinition(
            EndpointDefinition(instant=1),
            "independent",
            EndpointDefinition(
                kind="event",
                anchor_id="event:q",
                endpoint="end",
                offset={"unit": "days", "value": 2},
            ),
        )
        events.append(
            Event(id="s", name="The blockade", lore_date=None, attributes=end.apply({}))
        )
    return events


def _settle(app: QApplication, panel: TimelineWidget) -> None:
    for _ in range(4):
        app.processEvents()
        panel.action_toolbar.refresh()
        panel.layout().activate()


def main() -> int:
    """Capture six palettes, normal/narrow layouts and two zoom levels."""
    logging.basicConfig(level=logging.INFO)
    with tempfile.TemporaryDirectory(prefix="kraken-strand-render-") as settings_path:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_path
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
        OUTPUT.mkdir(parents=True, exist_ok=True)
        try:
            for theme in manager.themes:
                manager.set_theme(theme, persist=False)
                for crowded in (False, True):
                    for width, zoom in ((1200, 2.0), (400, 0.8)):
                        panel = TimelineWidget()
                        panel.set_dependency_visibility("all", persist=False)
                        panel.resize(width, 850 if crowded else 600)
                        panel.show()
                        _settle(app, panel)
                        panel.view.set_ruler_calendar(converter)
                        panel.view.set_temporal_context(
                            TemporalResolutionContext.build(
                                _events(crowded, converter), converter
                            )
                        )
                        _settle(app, panel)
                        panel.view._apply_zoom(zoom)
                        panel.view.center_on_date(7 if crowded else 3.5)
                        panel.view.verticalScrollBar().setValue(0)
                        panel.view._event_items["b"].setSelected(True)
                        panel.set_selected_event_navigation("b", "Hardwood Battle")
                        _settle(app, panel)
                        scene = "crowded" if crowded else "sparse"
                        name = f"{theme}-{scene}-{width}.png"
                        panel.grab().save(str(OUTPUT / name))
                        panel.close()
                        panel.deleteLater()
                        app.processEvents()
        finally:
            EventItem.set_calendar_converter(None)
    logging.info("Rendered dependency evidence: %s", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
