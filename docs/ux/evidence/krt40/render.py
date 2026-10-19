"""Render temporal save states with isolated settings and no world database.

Run from the repository root with ``python -m docs.ux.evidence.krt40.render``.
Use --baseline-ref to render the same fixtures with the pre-extraction widget.
Generated PNGs and manifests belong under ignored artifacts/krt40/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import types
from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from scripts.capture_inspector_evidence import _EvidenceHost, _settle
from src.core.entities import Entity
from src.core.theme_manager import ThemeManager
from src.gui.widgets.entity_editor import EntityEditorWidget


def _widget_type(baseline_ref: str | None) -> type[EntityEditorWidget]:
    if baseline_ref is None:
        return EntityEditorWidget
    source = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={Path.cwd().as_posix()}",
            "show",
            f"{baseline_ref}:src/gui/widgets/entity_editor.py",
        ],
        text=True,
    )
    module = types.ModuleType("krt40_baseline_entity_editor")
    exec(compile(source, "baseline_entity_editor.py", "exec"), module.__dict__)
    return module.EntityEditorWidget


def _fixture(widget_type: type[EntityEditorWidget], state: str) -> tuple[Any, Any]:
    parent = _EvidenceHost()
    editor = widget_type(parent)
    context = editor.authoring_context
    fit_browsers = context._fit_visible_browsers

    def fit_if_alive() -> None:
        if shiboken6.isValid(context):
            fit_browsers()

    # Existing receiverless Context resize callbacks can outlive deleteLater.
    # Guard only this isolated fixture's teardown; production is outside KRT-40.
    context._fit_visible_browsers = fit_if_alive
    entity = Entity(
        id="krt40-harbor",
        name="Harbor",
        type="Location",
        description="The guild maintains this harbor.",
        attributes={"owner": "Guild"},
    )
    editor.load_entity(entity)
    editor.display_temporal_state(
        entity.id,
        {
            "entity_id": entity.id,
            "description": entity.description,
            "attributes": {"owner": "Guild"},
            "description_source": {"kind": "baseline"},
            "attribute_sources": {"owner": {"kind": "baseline"}},
            "absent_attribute_sources": {},
        },
        -12.0,
    )
    if state == "readonly":
        editor.set_read_only_mode(True, "Read Only")
    elif state != "editable":
        editor.desc_edit.editor.insertPlainText("Updated: ")
        editor._on_save()
        if state == "failed":
            editor.finish_temporal_save(False)
        elif state == "recovery":
            editor.finish_temporal_save(True, None)
    editor.autosave_manager.stop_timer()
    return parent, editor


def capture(output: Path, baseline_ref: str | None) -> None:
    """Capture six themes, two allocations and five production save states."""
    output.mkdir(parents=True, exist_ok=True)
    widget_type = _widget_type(baseline_ref)
    with tempfile.TemporaryDirectory(prefix="krt40-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        QCoreApplication.setOrganizationName("KrakenEvidence")
        QCoreApplication.setApplicationName("KRT40")
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        assert QFontDatabase.addApplicationFont(str(font_path)) >= 0
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        records = []
        for theme in manager.get_available_themes():
            manager.set_theme(theme, app)
            for width in (360, 800):
                for state in ("editable", "readonly", "pending", "failed", "recovery"):
                    parent, editor = _fixture(widget_type, state)
                    editor.setWindowFlag(Qt.WindowType.Window, True)
                    editor.resize(width, 900)
                    editor.show()
                    editor.btn_save.setFocus(Qt.FocusReason.OtherFocusReason)
                    _settle(app)
                    name = f"{theme}-{width}-{state}.png"
                    pixmap = editor.grab()
                    assert pixmap.save(str(output / name))
                    records.append(
                        {
                            "image": name,
                            "theme": theme,
                            "state": state,
                            "requested_width": width,
                            "actual_width": editor.width(),
                            "height": editor.height(),
                            "dpr": editor.devicePixelRatioF(),
                            "pixel_width": pixmap.width(),
                            "pixel_height": pixmap.height(),
                            "font": editor.font().toString(),
                            "save_text": editor.btn_save.text(),
                            "save_enabled": editor.btn_save.isEnabled(),
                            "discard_enabled": editor.btn_discard.isEnabled(),
                            "pending": editor._temporal_save_pending,
                            "dirty": editor.has_unsaved_changes(),
                            "banner": editor.temporal_snapshot_label.text(),
                            "sha256": hashlib.sha256(
                                (output / name).read_bytes()
                            ).hexdigest(),
                        }
                    )
                    editor.close()
                    _settle(app)
                    editor.deleteLater()
                    parent.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    _settle(app)
        (output / "captures.json").write_text(
            json.dumps(
                {
                    "baseline_ref": baseline_ref,
                    "method": "offscreen component captures; no native DPI or human acceptance",
                    "sources": {
                        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in [
                            Path("src/gui/widgets/entity_editor.py"),
                            Path("src/services/temporal_entity_draft_service.py"),
                            Path(__file__),
                        ]
                    },
                    "captures": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref")
    args = parser.parse_args()
    capture(args.output, args.baseline_ref)
