"""Capture remaining production timeline indicators without editing world data."""

# Qt platform and repository path must be configured before GUI imports.
# ruff: noqa: E402

import argparse
import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict, replace
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
from src.core.temporal_expression import TemporalPrecision
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline import EventItem, TimelineWidget
from src.gui.widgets.timeline.group_band_item import GroupBandItem


def main() -> None:
    """Render comparable occurrence, duration, navigation and grouping states."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "after" / "indicators",
    )
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-indicator-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication([])
        app.setOrganizationName("KrakenEvidence")
        app.setApplicationName("TimelineIndicators")
        for filename in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / filename))
        app.setFont(QFont("Segoe UI", 10))
        theme = ThemeManager(str(ROOT / "themes.json"))
        theme.current_theme_name = "dark_mode"
        theme.apply_theme(
            app, (ROOT / "src/resources/main.qss").read_text(encoding="utf-8")
        )
        converter = CalendarConverter(CalendarConfig.create_default())
        parser = DateParser(converter._config)

        def event(
            name: str, authored: str, duration: float = 0, end: str | None = None
        ) -> Event:
            expression = parser.parse_expression(authored)
            metadata = {"schema": 1, "expression": expression.to_dict()}
            if end:
                metadata["end_expression"] = parser.parse_expression(end).to_dict()
            return Event(
                name=name,
                lore_date=expression.representative_time(converter),
                lore_duration=duration,
                attributes={"_temporal_v2": metadata},
            )

        widget = TimelineWidget()
        widget.set_calendar_converter(converter)
        view = widget.view
        widget.show()
        records = []

        def contrast(foreground: str, background: str, opacity: float) -> float:
            """Calculate solid-stroke contrast after item opacity compositing."""
            srgb_linear_threshold = 0.04045

            def rgb(value: str) -> list[float]:
                return [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]

            def luminance(channels: list[float]) -> float:
                linear = [
                    c / 12.92
                    if c <= srgb_linear_threshold
                    else ((c + 0.055) / 1.055) ** 2.4
                    for c in channels
                ]
                return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))

            bg = rgb(background)
            fg = [a * opacity + b * (1 - opacity) for a, b in zip(rgb(foreground), bg)]
            first, second = sorted((luminance(fg), luminance(bg)))
            return (second + 0.05) / (first + 0.05)

        def capture(
            filename: str,
            events: list[Event],
            scale: float,
            center: float,
            width: int = 1700,
            playhead: float | None = None,
            current: float | None = None,
            selected: bool = False,
            focus: bool = False,
        ) -> None:
            widget.resize(width, max(470, 220 + len(events) * 125))
            app.processEvents()
            view.set_events(events)
            zoom = scale / view.scale_factor
            view.setTransform(QTransform().scale(zoom, 1))
            view._current_zoom = zoom
            view._playhead.set_zoom(zoom)
            view.set_playhead_time(center if playhead is None else playhead)
            view.set_current_time(center + 80 if current is None else current)
            if playhead is None:
                view._playhead.hide()
                view._current_time_line.hide()
            # Match comparison rows across frames; retain native item painting.
            for row, owner in enumerate(events):
                item = view._event_items[owner.id]
                item.set_zoom(zoom)
                item.setY(110 + row * 125)
                item.setSelected(selected)
                line = view._drop_lines[owner.id]
                line.setLine(item.x(), -view.RULER_HEIGHT, item.x(), item.y())
            view.time_indicators.settle()
            app.processEvents()
            height = view.viewport().height()
            view._horizontal_rebase_in_progress = True
            view.graphics_scene.setSceneRect(
                (center - 100000) * view.scale_factor,
                -50,
                200000 * view.scale_factor,
                height,
            )
            view.centerOn(center * view.scale_factor, height / 2 - 50)
            view._horizontal_rebase_in_progress = False
            if focus:
                widget.btn_go_to_date.setFocus()
            else:
                view.setFocus()
            app.processEvents()
            widget.grab().save(str(output / filename))
            records.append(
                {
                    "file": filename,
                    "theme": theme.current_theme_name,
                    "pixels_per_day": scale,
                    "width": width,
                    "playhead": playhead,
                    "world_time": current,
                    "requested_toolbar_focus": focus,
                    "toolbar_has_focus": widget.btn_go_to_date.hasFocus(),
                    "cases": [
                        {
                            "event": owner.to_dict(),
                            "display": asdict(event_temporal_display(owner, converter)),
                            "layout": _layout_record(view._event_items[owner.id]),
                            "presence_geometry": asdict(
                                view._event_items[owner.id]._geometry(
                                    event_temporal_display(owner, converter)
                                )
                            ),
                            "future": view._event_items[owner.id].is_future,
                            "past": view._event_items[owner.id].is_past,
                            "opacity": view._event_items[owner.id].opacity(),
                            "selected": view._event_items[owner.id].isSelected(),
                        }
                        for owner in events
                    ],
                }
            )

        year = converter.start_of_year(1218)
        minute = event("Minute precision", "14 June 1218 12:00")
        hour = event("Hour precision", "14 June 1218 12:00")
        expression = replace(
            hour.temporal_expression,
            minute=None,
            precision=TemporalPrecision.HOUR,
            original_text=None,
        )
        hour.attributes["_temporal_v2"]["expression"] = expression.to_dict()
        hour.lore_date = expression.representative_time(converter)
        day = event("Day precision", "14 June 1218")
        occurrences = [
            minute,
            hour,
            day,
            event("Month precision", "June 1218"),
            event("Year precision", "1218"),
            event("Calculated year", "calculated 1218"),
            event("Approximate year", "c. 1218"),
            event("Uncertain year", "1218?"),
            event("Estimated year", "estimated 1218"),
            event("Before year", "before 1218"),
            event("After year", "after 1218"),
            event("Explicit occurrence window", "between June 1218 and October 1218"),
        ]
        capture("occurrences-visible.png", occurrences, 1.2, year + 180)
        capture("occurrences-compact.png", occurrences, 0.03, year + 180)
        capture("day-below-24px.png", [minute, hour, day], 23, day.lore_date)
        capture("day-above-24px.png", [minute, hour, day], 25, day.lore_date)
        capture("precision-close.png", [minute, hour, day], 1000, day.lore_date)

        invalid = event("Invalid expression", "1218")
        invalid.attributes["_temporal_v2"]["expression"]["schema_version"] = 999
        unavailable = event("Unavailable assertion calendar", "1218")
        unavailable.attributes["_temporal_v2"]["expression"]["calendar_id"] = "missing"
        endpoints = [
            event("Independent uncertain endpoints", "June 1218", end="October 1218"),
            event("Duration longer than start uncertainty", "June 1218", 90),
            event("One-sided start + duration", "after 1218", 3),
            event("Approximate endpoints", "c. 1218", end="c. 1219"),
            invalid,
            unavailable,
        ]
        capture("endpoints-errors.png", endpoints, 1.2, year + 180)
        states = [
            minute,
            event("Year occurrence", "1218"),
            event("Approximate occurrence", "c. 1218"),
            event("Known 240-day duration", "1 January 1218 12:00", 240),
            event("Month start + 90 days", "June 1218", 90),
        ]
        for label, offset in [("before", -20), ("during", 190), ("after", 380)]:
            capture(
                f"state-{label}.png",
                states,
                1.2,
                year + 180,
                playhead=year + offset,
                current=year + 250,
            )
        for palette in theme.themes:
            theme.set_theme(palette, app)
            capture(
                f"theme-{palette}.png",
                states,
                1.2,
                year + 180,
                playhead=year + 100,
                current=year + 250,
                selected=True,
                focus=True,
            )
        theme.set_theme("dark_mode", app)
        capture(
            "toolbar-unfocused.png",
            states,
            1.2,
            year + 180,
            playhead=year + 100,
            current=year + 250,
            selected=True,
        )
        view._playhead_hovered = True
        capture(
            "navigation-hover.png",
            states,
            1.2,
            year + 180,
            playhead=year + 100,
            current=year + 250,
        )
        view._playhead_hovered = False
        view._dragging_playhead = True
        capture(
            "navigation-drag.png",
            states,
            1.2,
            year + 180,
            playhead=year + 100,
            current=year + 250,
        )
        view._dragging_playhead = False
        capture(
            "navigation-coincident.png",
            states,
            1.2,
            year + 180,
            playhead=year + 180,
            current=year + 180,
        )
        capture(
            "navigation-narrow.png",
            [minute, day],
            1.2,
            minute.lore_date,
            width=380,
            playhead=minute.lore_date,
            current=minute.lore_date + 30,
        )
        widget.chk_snap_playhead_to_events.setChecked(True)
        capture(
            "navigation-snapped-uncertain.png",
            [occurrences[4]],
            1.2,
            year + 180,
            playhead=occurrences[4].lore_date,
            current=year + 250,
        )
        candidate = occurrences[4].lore_date + 5
        view._playhead.setPos(
            view._manual_playhead_time(candidate * view.scale_factor)
            * view.scale_factor,
            0,
        )
        view.time_indicators.settle()
        app.processEvents()
        widget.grab().save(str(output / "navigation-snapped-uncertain.png"))
        records[-1]["snap_probe"] = {
            "candidate": candidate,
            "resolved": view._manual_playhead_time(candidate * view.scale_factor),
        }

        neutral = [
            event("Council A", "1218", 3),
            event("Council B", "c. 1218", 3),
            event("Council C", "1 January 1218 12:00", 240),
        ]
        capture(
            "human-interpretation.png",
            neutral,
            1.2,
            year + 180,
            playhead=year + 190,
            current=year + 250,
        )
        # Isolated production bands/overlay: same inputs used by band manager.
        capture(
            "groups-reference.png", [occurrences[4], occurrences[6]], 1.2, year + 180
        )
        for row, (name, collapsed) in enumerate(
            [
                ("Expanded uncertain events", False),
                ("Collapsed uncertain events", True),
            ]
        ):
            band = GroupBandItem(
                name, theme.get_theme()["event_main"], 2, year, year + 182.5, collapsed
            )
            band.set_event_dates([occurrences[4].lore_date, occurrences[6].lore_date])
            band.setY(370 + row * 55)
            view.graphics_scene.addItem(band)
        view._label_overlay.setGeometry(0, view.RULER_HEIGHT, 150, view.height())
        view._label_overlay.set_labels(
            [
                {
                    "tag_name": name,
                    "y_pos": view.mapFromScene(0, 370 + row * 55).y()
                    - view.RULER_HEIGHT,
                    "color": theme.get_theme()["event_main"],
                    "is_collapsed": collapsed,
                }
                for row, (name, collapsed) in enumerate(
                    [
                        ("Expanded uncertain events", False),
                        ("Collapsed uncertain events", True),
                    ]
                )
            ]
        )
        app.processEvents()
        widget.grab().save(str(output / "groups-expanded-collapsed.png"))
        records.append(
            {
                "file": "groups-expanded-collapsed.png",
                "tick_dates": [occurrences[4].lore_date, occurrences[6].lore_date],
            }
        )
        _capture_grouped(widget, app, output, occurrences, converter)
        (output / "render.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )
        contrast_rows = [
            {
                "theme": name,
                "role": role,
                "normal": contrast(palette[role], palette["app_bg"], 1),
                "future": contrast(palette[role], palette["app_bg"], 1.0),
            }
            for name, palette in theme.themes.items()
            for role in ("text_main", "supporting_caption")
        ]
        (output / "text-contrast.json").write_text(
            json.dumps(contrast_rows, indent=2), encoding="utf-8"
        )
        widget.close()
        logging.info("Captured %s indicator states", len(records))


def _capture_grouped(
    widget: TimelineWidget,
    app: QApplication,
    output: Path,
    occurrences: list[Event],
    converter: CalendarConverter,
) -> None:
    """Exercise actual production grouping layout with cached snapshot callbacks."""
    from src.core.theme_manager import ThemeManager

    owners = [occurrences[4], occurrences[6]]
    for owner in owners:
        owner.attributes["_tags"] = ["Council"]

    class Provider:
        def get_events_for_group(
            self, tag_name: str, date_range: tuple[float, float] | None = None
        ) -> list[Event]:
            return owners

        def get_group_metadata(
            self, tag_order: list[str], date_range: tuple[float, float] | None = None
        ) -> list[dict]:
            return [
                {
                    "tag_name": tag,
                    "color": ThemeManager().get_theme()["event_main"],
                    "count": len(owners),
                    "earliest_date": min(e.lore_date for e in owners),
                    "latest_date": max(e.lore_date for e in owners),
                }
                for tag in tag_order
            ]

    widget.view.clear_grouping()
    for item in list(widget.view.graphics_scene.items()):
        from src.gui.widgets.timeline.group_band_item import GroupBandItem

        if isinstance(item, GroupBandItem):
            widget.view.graphics_scene.removeItem(item)
    widget.resize(1700, 650)
    widget.set_data_provider(Provider())
    widget.set_events(owners)
    widget.set_grouping_config(["Council"])
    widget.view._apply_zoom(1.2 / widget.view.scale_factor)
    widget.center_on_date(converter.start_of_year(1218) + 180)
    widget.view.verticalScrollBar().setValue(widget.view.verticalScrollBar().minimum())
    app.processEvents()
    widget.grab().save(str(output / "grouped-production-expanded.png"))
    widget.view._band_manager._on_collapse_requested("Council")
    app.processEvents()
    widget.grab().save(str(output / "grouped-production-collapsed.png"))
    widget.view._band_manager._on_expand_requested("Council")
    app.processEvents()
    widget.btn_go_to_date.setEnabled(False)
    widget.grab().save(str(output / "toolbar-disabled.png"))


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
