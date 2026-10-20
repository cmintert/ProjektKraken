"""Capture spelling/editor/dialog fixtures without opening a world or using HTTP."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QContextMenuEvent, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.theme_manager import ThemeManager
from src.gui.widgets import wiki_text_edit
from src.services.language_tool_service import LanguageToolWorker, LTMatch


def _module(baseline_ref: str | None) -> Any:
    if baseline_ref is None:
        return wiki_text_edit
    source = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={Path.cwd().as_posix()}",
            "show",
            f"{baseline_ref}:src/gui/widgets/wiki_text_edit.py",
        ],
        text=True,
        encoding="utf-8",
    )
    module = types.ModuleType("krt39_baseline_wiki_text_edit")
    exec(compile(source, "baseline_wiki_text_edit.py", "exec"), module.__dict__)
    return module


def capture(output: Path, baseline_ref: str | None) -> None:
    """Capture six themes, normal/narrow editors, menus and settings states."""
    output.mkdir(parents=True, exist_ok=True)
    module = _module(baseline_ref)
    with tempfile.TemporaryDirectory(prefix="krt39-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        QCoreApplication.setOrganizationName("KrakenEvidence")
        QCoreApplication.setApplicationName("KRT39")
        for name in ("segoeui.ttf", "consola.ttf"):
            assert QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{name}") >= 0
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        records = []

        def save(widget: Any, name: str, requested_width: int, **metadata: Any) -> None:
            app.processEvents()
            pixmap = widget.grab()
            assert pixmap.save(str(output / name))
            records.append(
                {
                    "image": name,
                    "requested_width": requested_width,
                    "actual_width": widget.width(),
                    "height": widget.height(),
                    "dpr": widget.devicePixelRatioF(),
                    "pixel_width": pixmap.width(),
                    "pixel_height": pixmap.height(),
                    "font": widget.font().toString(),
                    "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    **metadata,
                }
            )

        with patch.object(LanguageToolWorker, "check", lambda *a, **kw: None):
            for theme in manager.get_available_themes():
                manager.set_theme(theme, app)
                for width in (360, 800):
                    for state in ("enabled", "disabled", "readonly", "source"):
                        enabled = state != "disabled"
                        QSettings().setValue("SpellCheck/enabled", enabled)
                        editor = module.WikiTextEdit()
                        editor.set_adaptive_width(True)
                        editor.resize(width, 380)
                        editor.set_wiki_text(
                            "Hello wrld in this sentence. See [[Harbor]]."
                        )
                        if state == "source":
                            editor.toggle_view_mode()
                        editor.editor.setReadOnly(state == "readonly")
                        editor.show()
                        editor.editor.setFocus(Qt.FocusReason.OtherFocusReason)
                        if enabled:
                            matches = [
                                LTMatch(
                                    6,
                                    4,
                                    "Spelling",
                                    ["world", "word", "whirled"],
                                    "SPELL",
                                    "misspelling",
                                )
                            ]
                            if baseline_ref:
                                editor.editor._apply_lt_results(matches)
                            else:
                                editor.editor.spell_check._apply_results(matches)
                        save(
                            editor,
                            f"{theme}-{width}-{state}-editor.png",
                            width,
                            theme=theme,
                            state=state,
                            surface="editor",
                            focus=editor.editor.hasFocus(),
                            underlines=len(editor.editor.extraSelections()),
                        )

                        def show_menu(menu: Any, _position: Any) -> None:
                            menu.popup(editor.mapToGlobal(editor.rect().center()))
                            save(
                                menu,
                                f"{theme}-{width}-{state}-menu.png",
                                width,
                                theme=theme,
                                state=state,
                                surface="menu",
                                actions=[
                                    {
                                        "text": a.text(),
                                        "enabled": a.isEnabled(),
                                        "visible": a.isVisible(),
                                    }
                                    for a in menu.actions()
                                ],
                            )
                            menu.close()

                        editor.editor._show_context_menu = show_menu
                        cursor = editor.editor.textCursor()
                        cursor.setPosition(7)
                        position = editor.editor.cursorRect(cursor).center()
                        editor.editor.contextMenuEvent(
                            QContextMenuEvent(
                                QContextMenuEvent.Reason.Mouse,
                                position,
                                editor.editor.mapToGlobal(position),
                            )
                        )
                        editor.close()
                        editor.deleteLater()
                        QCoreApplication.sendPostedEvents(
                            None, QEvent.Type.DeferredDelete
                        )
                    for enabled in (False, True):
                        QSettings().setValue("SpellCheck/enabled", enabled)
                        dialog = module.SpellCheckSettingsDialog()
                        dialog.resize(width, dialog.sizeHint().height())
                        dialog.show()
                        dialog._language_combo.setFocus(Qt.FocusReason.OtherFocusReason)
                        save(
                            dialog,
                            f"{theme}-{width}-{enabled}-dialog.png",
                            width,
                            theme=theme,
                            state="enabled" if enabled else "disabled",
                            surface="dialog",
                            enabled=dialog._enabled_cb.isChecked(),
                        )
                        dialog.close()
                        dialog.deleteLater()
                        QCoreApplication.sendPostedEvents(
                            None, QEvent.Type.DeferredDelete
                        )
        (output / "captures.json").write_text(
            json.dumps(
                {
                    "baseline_ref": baseline_ref,
                    "method": "offscreen component captures; native acceptance separate",
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
