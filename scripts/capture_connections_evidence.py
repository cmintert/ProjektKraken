"""Capture KRT-93 Qt layouts with synthetic lore and isolated preferences.

Run ``python -m scripts.capture_connections_evidence``. PNGs and geometry metadata
go to ignored tmp/krt93; these are automated evidence, not human UX acceptance.
"""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from scripts.action_label_audit import audit_widget  # noqa: E402
from scripts.capture_inspector_evidence import _EvidenceHost, _settle  # noqa: E402
from src.core.entities import Entity  # noqa: E402
from src.core.events import Event  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.entity_editor import EntityEditorWidget  # noqa: E402
from src.gui.widgets.event_editor import EventEditorWidget  # noqa: E402


def main() -> None:
    """Capture both live inspectors at each requested width and shipped theme."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", action="append")
    parser.add_argument("--width", action="append", type=int)
    parser.add_argument("--height", type=int, default=900)
    options = parser.parse_args()
    output = Path("tmp/krt93/final")
    output.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str((output / "settings").resolve()),
    )
    app = QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    app.setFont(QFont("Segoe UI", 10))
    manager = ThemeManager()
    # Use the same shipped QSS template as production startup.
    template = Path("src/resources/main.qss")
    qss = template.read_text(encoding="utf-8")
    metadata = []
    for kind, editor_type in (
        ("entity", EntityEditorWidget),
        ("event", EventEditorWidget),
    ):
        parent = _EvidenceHost()
        editor = editor_type(parent)
        owner = (
            Entity(id="source", name="Tasgillia", type="Character")
            if kind == "entity"
            else Event(
                id="source",
                name="Winter Council",
                lore_date=100.0,
            )
        )
        rows = [
            {
                "id": f"relation-{i}",
                "source_id": "source",
                "target_id": f"target-{i}",
                "source_name": owner.name,
                "target_name": (
                    "House Bjornaer of the Northern Forest and Forgotten Marshes"
                    if i == 0
                    else f"Connection {i}"
                ),
                "rel_type": (
                    "member_of",
                    "involved",
                    "located_at",
                    "caused",
                    "parent_of",
                    "owns",
                    "mentions",
                )[i % 7],
                "attributes": {"notes": "Preserved lore", "valid_from": 120.0},
            }
            for i in range(20)
        ]
        getattr(editor, f"load_{kind}")(owner, relations=rows)
        editor._suggestion_items = [
            (r["target_id"], r["target_name"], "entity") for r in rows
        ]
        editor.inspector.activate_section_id("connections")
        editor.show()
        parent.show()
        for theme in options.theme or manager.themes:
            manager.current_theme_name = theme
            manager.apply_theme(app, qss)
            manager.theme_changed.emit(manager.get_theme())
            for width in options.width or (360, 380, 640, 650, 920):
                parent.resize(width, options.height)
                editor.resize(width, options.height)
                editor.relation_authoring.cancel()
                _settle(app)
                prefix = f"{kind}-{theme}-{width}x{options.height}"
                editor.grab().save(str(output / f"{prefix}-browse.png"))
                editor.connections.select_relation("relation-0")
                editor.connections.edit_selected()
                editor.relation_authoring.apply_button.setFocus()
                _settle(app)
                editor.grab().save(str(output / f"{prefix}-edit.png"))
                editor.relation_authoring.timing_disclosure.setChecked(True)
                _settle(app)
                scroll = editor.relation_authoring.body_scroll.verticalScrollBar()
                timing = editor.relation_authoring.form.temporal_group
                scroll.setValue(
                    timing.mapTo(
                        editor.relation_authoring.body, timing.rect().topLeft()
                    ).y()
                )
                _settle(app)
                editor.grab().save(str(output / f"{prefix}-timing.png"))
                label_failures = [
                    failure.to_dict() for failure in audit_widget(editor.tab_relations)
                ]
                editor.setEnabled(False)
                _settle(app)
                editor.grab().save(str(output / f"{prefix}-disabled.png"))
                disabled_failures = [
                    failure.to_dict() for failure in audit_widget(editor.tab_relations)
                ]
                editor.setEnabled(True)
                metadata.append(
                    {
                        "kind": kind,
                        "theme": theme,
                        "requested_width": width,
                        "actual_width": editor.width(),
                        "requested_height": options.height,
                        "actual_height": editor.height(),
                        "connections_width": editor.tab_relations.width(),
                        "tree_geometry": editor.connections.tree.geometry().getRect(),
                        "summary_geometry": editor.connections.summary.geometry().getRect(),
                        "overview_geometry": editor.connections.geometry().getRect(),
                        "overview_minimum_hint": editor.connections.minimumSizeHint().toTuple(),
                        "draft_viewport_height": editor.relation_authoring.body_scroll.viewport().height(),
                        "device_pixel_ratio": editor.devicePixelRatioF(),
                        "font": editor.font().toString(),
                        "capture": f"{prefix}-timing.png",
                        "action_label_failures": label_failures,
                        "disabled_action_label_failures": disabled_failures,
                    }
                )
        parent.close()
        parent.deleteLater()
        app.processEvents()
    (output / f"geometry-{options.height}.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
