"""Capture isolated KRT-110 fact rows without opening a world or provider."""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.authoring_context import (
    ContextAttribute,
    ContextItem,
    ContextRelation,
    ContextSharedAssociation,
    EntityAuthoringContext,
)
from src.core.theme_manager import ThemeManager
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget


def capture(output: Path, *, browse: bool = False) -> None:
    """Record six palettes, narrow/wide rows, disclosures, focus and disabled state."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt110-") as settings:
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
        source = {"event_id": "succession", "event_name": "Northwatch succession"}
        kingdom = ContextItem("kingdom", "entity", "Kingdom of Ashford")
        event = ContextItem("succession", "event", "Northwatch succession")
        relations = tuple(
            ContextRelation(
                str(i),
                ContextItem(str(i), "entity", name),
                kingdom,
                "rules",
                0,
                "interval",
                temporal_summary=summary,
                temporal_evidence={"events": [{"id": event.id, "name": event.name}]},
            )
            for i, name, summary in (
                (
                    1,
                    "Queen Mara",
                    "Not active at the playhead; ends: Northwatch succession",
                ),
                (
                    2,
                    "Captain Ilyra",
                    "Active at the playhead; starts: Northwatch succession",
                ),
            )
        ) + (
            ContextRelation("state", event, kingdom, "changes_state", 0, "persistent"),
        )
        records = []
        for theme in manager.themes:
            manager.set_theme(theme, app, persist=False)
            for width in (360, 800):
                widget = AuthoringContextWidget(object_label="Entity")
                widget.resize(width, 650)
                context = EntityAuthoringContext(
                    kingdom.id,
                    mode="history_to_playhead",
                    context_date=19,
                    date_label="Year 1, January 20, Saturday",
                    attributes=(
                        ContextAttribute("Capital", "Ashford"),
                        ContextAttribute("Ruler", "Captain Ilyra", source),
                    )
                    + tuple(
                        ContextAttribute(f"Additional field {i}", "A saved value")
                        for i in range(4)
                    ),
                    temporal_history=relations,
                    shared_maps=(
                        ContextSharedAssociation(
                            ContextItem("keep", "entity", "Northwatch Keep"),
                            ("Northwatch — watch the border change",),
                        ),
                    ),
                    omitted_counts=(("neighborhood_relations", 5),),
                )
                widget.mode_selector.set_mode(context.mode)
                if browse:
                    widget.enable_connection_browsing()
                widget.set_entity_context(context)
                browse_rows = [
                    replace(item, id=f"{item.id}-{i}").to_dict()
                    for i in range(4)
                    for item in relations
                ]
                if browse:
                    widget.set_connection_page(
                        browse_rows, "12 loaded; total not yet known.", True
                    )
                widget.show()
                states = (
                    ("preview", "expanded-focus", "loading", "retry", "disabled")
                    if browse
                    else ("preview", "expanded-focus", "disabled")
                )
                for state in states:
                    if state == "expanded-focus":
                        widget.more_button.setChecked(True)
                        widget.activateWindow()
                        (
                            widget.load_connections if browse else widget.more_button
                        ).setFocus()
                    if state == "loading":
                        widget.set_connection_page(
                            browse_rows,
                            "Loading saved connections…",
                            False,
                            loading=True,
                        )
                    if state == "retry":
                        widget.set_connection_page(
                            browse_rows,
                            "Connections could not be loaded. Retry to continue.",
                            True,
                            retry=True,
                        )
                    if state == "disabled":
                        widget.setEnabled(False)
                    for _ in range(5):
                        app.processEvents()
                    filename = f"{theme}-{width}-{state}.png"
                    widget.scroll_content.grab().save(str(output / filename))
                    records.append(
                        {
                            "file": filename,
                            "requested_width": width,
                            "content_size": [
                                widget.scroll_content.width(),
                                widget.scroll_content.height(),
                            ],
                            "device_pixel_ratio": widget.devicePixelRatioF(),
                            "expanded": widget.more_button.isChecked(),
                            "expand_control_focused": widget.more_button.hasFocus(),
                            "browse_action": widget.load_connections.text()
                            if browse
                            else None,
                        }
                    )
                widget.close()
                widget.deleteLater()
                app.processEvents()
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "evidence": "isolated offscreen captures; human/native acceptance pending",
                    "captures": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browse", action="store_true")
    arguments = parser.parse_args()
    capture(
        Path(
            "docs/_build/krt109/rendered"
            if arguments.browse
            else "docs/_build/krt110/rendered"
        ),
        browse=arguments.browse,
    )
