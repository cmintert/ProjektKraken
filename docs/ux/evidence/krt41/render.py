"""Capture the real timeline with current or baseline reconciliation and packing.

Run as ``python -m docs.ux.evidence.krt41.render --output artifacts/krt41/after``.
Use --baseline-ref to load all three changed GUI modules from that revision.
No database or personal settings are used. Outputs are ignored local artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.calendar import CalendarConfig, CalendarConverter, MonthDefinition
from src.core.date_parser import DateParser
from src.core.events import Event
from src.core.theme_manager import ThemeManager
from src.core.timeline_grouping import build_group_metadata, events_for_group
from src.gui.widgets import timeline

BASELINE_PATHS = (
    "src/gui/widgets/timeline_lane_packer.py",
    "src/gui/workers/layout_worker.py",
    "src/gui/widgets/timeline/timeline_view.py",
)


def install_baseline(revision: str) -> None:
    """Load baseline view, measurement/packing and worker together in this process."""
    for path in BASELINE_PATHS:
        source = subprocess.check_output(
            [
                "git",
                "-c",
                f"safe.directory={Path.cwd().as_posix()}",
                "show",
                f"{revision}:{path}",
            ],
            text=True,
        )
        name = path[:-3].replace("/", ".")
        module = types.ModuleType(name)
        module.__file__ = path
        sys.modules[name] = module
        exec(compile(source, path, "exec"), module.__dict__)
    timeline.TimelineView = sys.modules[
        "src.gui.widgets.timeline.timeline_view"
    ].TimelineView


class CachedGroups:
    """The same cached-data provider shape used by production grouping."""

    def __init__(self, view: Any) -> None:
        """Retain only the isolated fixture view."""
        self.view = view

    def get_group_metadata(self, tag_order: list, date_range: Any = None) -> list:
        """Build band summaries from the fixture's cached events."""
        return build_group_metadata(self.view.events, tag_order, {}, date_range)

    def get_events_for_group(self, tag_name: str, date_range: Any = None) -> list:
        """Read cached fixture events for a band."""
        return events_for_group(self.view.events, tag_name, date_range)


def settle(app: QApplication) -> None:
    """Flush synchronous paint, resize and deferred deletion work."""
    for _ in range(8):
        app.processEvents()


def fixture(width: int, state: str) -> timeline.TimelineWidget:
    """Use a fantasy calendar and exact, sub-day and uncertain event marks."""
    config = CalendarConfig.create_default()
    config.months = [MonthDefinition(f"Month {i}", f"M{i}", 30) for i in range(1, 13)]
    config.leap_year_rules = []
    converter = CalendarConverter(config)
    widget = timeline.TimelineWidget()
    widget.resize(width, 900)
    widget.show()
    widget.set_calendar_converter(converter)
    events = [
        Event(id="past", name="Before the epoch", lore_date=-1.5),
        Event(id="selected", name="Council", lore_date=0.125, lore_duration=0.25),
        Event(id="future", name="Arrival", lore_date=2),
    ]
    expression = DateParser(config).parse_expression("c. 1")
    events.append(
        Event(
            id="uncertain",
            name="Approximate founding",
            lore_date=expression.representative_time(converter),
            lore_duration=3,
            attributes={
                "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
            },
        )
    )
    events[1].tags = ["Council", "History"]
    widget.set_events([] if state == "empty" else events)
    view = widget.view
    view._apply_zoom(1)
    view.set_playhead_time(0.25)
    view.set_current_time(1.5)
    view.center_on_date(0.5)
    if state in {"grouped", "collapsed"}:
        widget.set_data_provider(CachedGroups(view))
        view.set_grouping_config(["Council", "History"])
        if state == "collapsed":
            view._band_manager._on_collapse_requested("Council")
    if state != "empty":
        view._event_items["selected"].setSelected(True)
    view.setFocus(Qt.FocusReason.OtherFocusReason)
    if state == "disabled":
        widget.setEnabled(False)
    return widget


def capture(output: Path, baseline_ref: str | None) -> None:
    """Capture six themes, two widths and five timeline presentation states."""
    output.mkdir(parents=True, exist_ok=True)
    if baseline_ref:
        install_baseline(baseline_ref)
    sources = {}
    for path in BASELINE_PATHS:
        content = (
            subprocess.check_output(
                [
                    "git",
                    "-c",
                    f"safe.directory={Path.cwd().as_posix()}",
                    "show",
                    f"{baseline_ref}:{path}",
                ]
            )
            if baseline_ref
            else Path(path).read_bytes()
        )
        sources[path] = hashlib.sha256(content).hexdigest()
    sources[__file__] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="krt41-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        QCoreApplication.setOrganizationName("KrakenEvidence")
        QCoreApplication.setApplicationName("KRT41")
        assert QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf") >= 0
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        captures = []
        for theme in manager.get_available_themes():
            manager.set_theme(theme, app)
            for width in (480, 1100):
                for state in ("standard", "grouped", "collapsed", "empty", "disabled"):
                    widget = fixture(width, state)
                    settle(app)
                    name = f"{theme}-{width}-{state}.png"
                    assert widget.grab().save(str(output / name))
                    view = widget.view
                    captures.append(
                        {
                            "image": name,
                            "theme": theme,
                            "state": state,
                            "requested_width": width,
                            "actual_width": widget.width(),
                            "height": widget.height(),
                            "dpr": widget.devicePixelRatioF(),
                            "font": widget.font().toString(),
                            "viewing": view.get_playhead_time(),
                            "world_time": view.get_current_time(),
                            "zoom": view._current_zoom,
                            "center_date": view._visible_center_date(),
                            "duplicates": len(view._duplicate_event_items),
                            "positions": {
                                key: [
                                    item.x(),
                                    item.y(),
                                    item.isSelected(),
                                    item.isVisible(),
                                ]
                                for key, item in view._event_items.items()
                            },
                            "sha256": hashlib.sha256(
                                (output / name).read_bytes()
                            ).hexdigest(),
                        }
                    )
                    widget.close()
                    widget.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    settle(app)
        (output / "captures.json").write_text(
            json.dumps(
                {
                    "baseline_ref": baseline_ref,
                    "method": "offscreen; no native DPI or human acceptance",
                    "baseline_modules": BASELINE_PATHS,
                    "sources": sources,
                    "captures": captures,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def compare(output: Path, before: Path) -> None:
    """Check pixels and captured scene state against the baseline matrix."""
    old = json.loads((before / "captures.json").read_text("utf-8"))["captures"]
    new = json.loads((output / "captures.json").read_text("utf-8"))["captures"]
    differences = [
        {"image": b["image"], "keys": [key for key in a if a[key] != b[key]]}
        for a, b in zip(old, new, strict=True)
        if a != b
    ]
    (output / "comparison.json").write_text(
        json.dumps(
            {
                "count": len(new),
                "identical": len(new) - len(differences),
                "differences": differences,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert not differences, differences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref")
    parser.add_argument("--compare-with", type=Path)
    args = parser.parse_args()
    capture(args.output, args.baseline_ref)
    if args.compare_with:
        compare(args.output, args.compare_with)
