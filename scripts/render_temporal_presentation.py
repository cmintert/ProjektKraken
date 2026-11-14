"""Render KRT-163 production widgets with synthetic facts and isolated settings."""

import json
import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from scripts.render_timeline_dependencies import _settle
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.date_parser import DateParser
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.event_timing.presentation import present_event
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline import EventItem, TimelineWidget
from src.gui.widgets.timeline.group_band_item import GroupBandItem

OUTPUT = Path("artifacts/krt163")


def _events(converter: CalendarConverter) -> list[Event]:
    """Keep examples detached from every saved world."""
    parser = DateParser(converter._config)
    result = []
    for identity, name, text in (
        ("day", "Known day", "15 March 561"),
        ("minute", "Coastal Race (minute precision)", "1 April 561 12:00"),
        ("month", "Known month", "May 561"),
        ("approximate", "Approximate year", "c. 561"),
        ("repeat", "Repeating race", "6 April 561"),
    ):
        expression = parser.parse_expression(text)
        definition = EventTimingDefinition(
            EndpointDefinition(expression=expression.to_dict())
        )
        result.append(
            Event(
                name=name,
                id=identity,
                lore_date=None,
                attributes=definition.apply({}),
            )
        )
    result[-1].attributes["_recurrence"] = {
        "frequency": "years",
        "interval": 3,
        "calendar_id": converter._config.id,
    }
    base = converter.start_of_day(561, 4, 1)
    result.append(Event(name="Numeric instant", id="numeric", lore_date=base - 50))
    return result


def main() -> None:
    """Capture ordinary, collapsed and recurring views across themes and widths."""
    logging.basicConfig(level=logging.WARNING)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt163-") as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        app = QApplication.instance() or QApplication([])
        for filename in ("segoeui.ttf", "segoeuib.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / filename))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        converter = CalendarConverter(CalendarConfig.create_default())
        context = TemporalResolutionContext.build(_events(converter), converter)
        presentations = {
            event.id: present_event(event, converter) for event in context.view_events()
        }
        metadata = []
        for theme in manager.themes:
            manager.set_theme(theme, persist=False)
            manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
            for width in (1200, 480):
                panel = TimelineWidget()
                panel.resize(width, 560)
                panel.set_calendar_converter(converter)
                panel.show()
                _settle(app, panel)
                panel.view.set_temporal_context(context)
                _settle(app, panel)
                for zoom in (0.05, 1.0):
                    panel.view._apply_zoom(zoom)
                    panel.view.center_on_date(presentations["minute"].start.anchor)
                    panel.view.verticalScrollBar().setValue(0)
                    panel.view.recurrence_strip.refresh()
                    item = panel.view._event_items["minute"]
                    item.setSelected(True)
                    item.setFocus()
                    _settle(app, panel)
                    stem = f"{theme}-{width}-{zoom:g}"
                    panel.grab().save(str(OUTPUT / f"{stem}.png"))
                    # A collapsed production band uses the very same start models.
                    band = GroupBandItem(
                        "Collapsed comparison",
                        manager.get_theme()["event_main"],
                        len(presentations),
                        0,
                        1,
                        True,
                    )
                    band.set_event_presentations(
                        [p.start for p in presentations.values()]
                    )
                    panel.view.graphics_scene.addItem(band)
                    band.setY(330)
                    _settle(app, panel)
                    panel.grab().save(str(OUTPUT / f"{stem}-collapsed.png"))
                    panel.view.graphics_scene.removeItem(band)
                    metadata.append({"theme": theme, "width": width, "zoom": zoom})
                panel.close()
                panel.deleteLater()
                app.processEvents()
        EventItem.set_calendar_converter(None)
        (OUTPUT / "captures.json").write_text(json.dumps(metadata, indent=2), "utf-8")


if __name__ == "__main__":
    main()
