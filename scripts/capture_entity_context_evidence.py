"""Capture isolated KRT-96 widgets; no world database or provider is opened."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.authoring_context import (
    ContextAttribute,
    ContextItem,
    ContextRelation,
    EntityAuthoringContext,
)
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.prepared_generation_dialog import PreparedGenerationDialog
from src.gui.widgets.authoring_context_widget import AuthoringContextWidget
from src.services.authoring_context_builder import format_entity_authoring_context


def capture(output: Path) -> None:
    """Record themes, modes, narrow layouts and stale/disabled preview states."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt96-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        for font in ("segoeui.ttf", "consola.ttf"):
            font_path = Path("C:/Windows/Fonts") / font
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        source = {
            "kind": "relation",
            "relation_id": "reign",
            "event_id": "coronation",
            "event_name": "Coronation",
        }
        relation = ContextRelation(
            "reign",
            ContextItem("ilyra", "entity", "Ilyra"),
            ContextItem("bestril", "entity", "Bestril"),
            "rules",
            0,
            "interval",
            temporal_summary="Active at the playhead; starts: Coronation; ends: Abdication",
            temporal_evidence={
                "events": [
                    {"id": "coronation", "name": "Coronation"},
                    {"id": "abdication", "name": "Abdication"},
                ]
            },
        )
        records = []
        for theme in manager.themes:
            manager.set_theme(theme, app)
            for width in (360, 800):
                for mode in ("at_playhead", "history_to_playhead", "all_history"):
                    context = EntityAuthoringContext(
                        "ilyra",
                        mode=mode,
                        context_date=135.0 if mode != "all_history" else None,
                        date_label="Year 135",
                        attributes=(ContextAttribute("Office", "Queen", source),),
                        temporal_history=(relation,),
                        possible_changes=(
                            ContextAttribute(
                                "Alliance", "May join the coast", source, "possible"
                            ),
                        ),
                    )
                    widget = AuthoringContextWidget(object_label="Entity")
                    widget.mode_selector.set_mode(mode)
                    widget.set_entity_context(context)
                    widget.more_button.setChecked(True)
                    widget.resize(width, 650)
                    widget.show()
                    for _ in range(4):
                        app.processEvents()
                    widget.mode_selector.combo.setFocus()
                    app.processEvents()
                    name = f"{theme}-{width}-{mode}.png"
                    widget.grab().save(str(output / name))
                    records.append(
                        {
                            "file": name,
                            "size": [widget.width(), widget.height()],
                            "device_pixel_ratio": widget.devicePixelRatioF(),
                        }
                    )
                    widget.close()
                    widget.deleteLater()
                    app.processEvents()
                preview = PreparedGenerationDialog(None)
                preview.present(
                    {"user": format_entity_authoring_context(context)},
                    "Captured All history; spatial facts use viewing year 135.",
                )
                preview.resize(width, 650)
                preview.show()
                for state in ("ready", "stale"):
                    if state == "stale":
                        preview.invalidate()
                    for _ in range(4):
                        app.processEvents()
                    name = f"{theme}-{width}-preview-{state}.png"
                    preview.grab().save(str(output / name))
                    records.append(
                        {
                            "file": name,
                            "size": [preview.width(), preview.height()],
                            "device_pixel_ratio": preview.devicePixelRatioF(),
                        }
                    )
                preview.close()
                preview.deleteLater()
                app.processEvents()
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "evidence": "isolated offscreen rendering; no native or human acceptance",
                    "captures": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    capture(Path("docs/_build/krt96/rendered"))
