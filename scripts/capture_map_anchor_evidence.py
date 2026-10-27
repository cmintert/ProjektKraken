"""Capture KRT-111 controls using disposable snapshots, without opening a world."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.map import MapLayerNode
from src.core.temporal_context import TemporalResolutionContext
from src.core.temporal_expression import TemporalExpression, TemporalPrecision
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.temporal_validity_dialog import TemporalValidityDialog
from src.gui.widgets.relation_form import RelationForm


def preview_context() -> TemporalResolutionContext:
    """Prepare independent year-only events and a separately authored end."""
    config = CalendarConfig.create_default()
    events = []
    for identity, name, year in (
        ("foundation", "Foundation of Northwatch Castle", 120),
        ("destruction", "Destruction of Northwatch Castle", 125),
    ):
        expression = TemporalExpression(
            config.id, year, precision=TemporalPrecision.YEAR
        )
        events.append(
            Event(
                name,
                id=identity,
                lore_date=year,
                attributes={
                    "_temporal_v2": {"schema": 1, "expression": expression.to_dict()}
                },
            )
        )
    return TemporalResolutionContext.build(events, CalendarConverter(config), 1)


def preview_attributes() -> dict:
    """Bind both sides to events without numeric fallbacks."""
    return {
        "temporal": {
            "schema": 2,
            "behavior": "stateful",
            **{
                side: {
                    "anchor": {
                        "anchor_id": f"event:{identity}",
                        "endpoint": "start",
                        "semantics": "strict_v2",
                        "offset": {"unit": "days", "value": 0},
                    }
                }
                for side, identity in (("start", "foundation"), ("end", "destruction"))
            },
        }
    }


def widget(kind: str, context: TemporalResolutionContext) -> QWidget:
    """Create the actual production widgets with disposable draft data."""
    if kind == "map":
        node = MapLayerNode(
            "Northwatch Castle", "marker", attributes=preview_attributes()
        )
        return TemporalValidityDialog(
            node, calendar_converter=context.converter(), temporal_context=context
        )
    return RelationForm(
        attributes=preview_attributes(),
        temporal_context=context,
        calendar_converter=context.converter(),
    )


def run(output: Path, native: bool) -> None:
    """Capture six palettes and leave one native map editor available on request."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt111-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        context = preview_context()
        if native:
            manager.set_theme("dark_mode", app, persist=False)
            dialog = widget("map", context)
            dialog.setWindowTitle("KRT-111 — disposable native visibility review")
            dialog.resize(520, 650)
            dialog.show()
            QTimer.singleShot(600_000, app.quit)
            app.exec()
            return
        manifest = []
        for theme in manager.themes:
            manager.set_theme(theme, app, persist=False)
            for kind in ("map", "relation"):
                for width in (420, 800) if kind == "map" else (360, 800):
                    control = widget(kind, context)
                    control.resize(width, 640)
                    control.show()
                    for state in ("common", "advanced-focus", "disabled"):
                        if state == "advanced-focus":
                            mapping = getattr(
                                control, "_event_controls", None
                            ) or getattr(control, "_anchor_controls")
                            for anchor in mapping.values():
                                anchor.disclosure.setChecked(True)
                            mapping["start"].unit.setFocus()
                        elif state == "disabled":
                            control.setEnabled(False)
                        app.processEvents()
                        if state == "advanced-focus":
                            for scroll in control.findChildren(QScrollArea):
                                if scroll.widget().isAncestorOf(mapping["start"].unit):
                                    scroll.ensureWidgetVisible(mapping["start"].unit)
                            app.processEvents()
                        filename = f"{theme}-{kind}-{width}-{state}.png"
                        control.grab().save(str(output / filename))
                        manifest.append(
                            {
                                "file": filename,
                                "requested_width": width,
                                "actual_size": [control.width(), control.height()],
                                "dpr": control.devicePixelRatioF(),
                                "font": control.font().toString(),
                                "platform": app.platformName(),
                            }
                        )
                    control.close()
                    control.deleteLater()
                    app.processEvents()
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/_build/krt111/rendered")
    )
    arguments = parser.parse_args()
    run(arguments.output, arguments.native)
