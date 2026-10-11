"""Render production-widget UI-GATE-01 matrices without changing application data.

Run the fast matrix before push and the full matrix before release. Native
Windows review is independently mandatory; this offscreen gate cannot supply it.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCALES = (1.0, 1.25, 1.5, 2.0)
LARGE_CLIENT_WIDTH = 1600
LARGE_CLIENT_HEIGHT = 900
MINIMUM_CLIENT_WIDTH = 1280
SETTINGS_NAME_COUNT = 2
logger = logging.getLogger(__name__)


def source_inventory() -> list[dict[str, Any]]:
    """Inventory constructor/action sites; absence of fixtures is reported."""
    names = {
        "QPushButton",
        "QToolButton",
        "QCheckBox",
        "QRadioButton",
        "QDialogButtonBox",
        "OverflowToolBar",
        "StandardButton",
        "PrimaryButton",
        "DestructiveButton",
        "WrappingPushButton",
        "WrappingToolButton",
        "WrappingCheckBox",
        "WrappingRadioButton",
        "WrappingComboBox",
        "ScrollSafeComboBox",
        "QComboBox",
    }
    records = []
    for directory in (ROOT / "src/gui", ROOT / "src/app"):
        for path in sorted(directory.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            sites = [
                node.lineno
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (
                    isinstance(node.func, ast.Name)
                    and node.func.id in names
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("addAction", "addTab")
                )
            ]
            if sites:
                records.append(
                    {
                        "source": path.relative_to(ROOT).as_posix(),
                        "lines": sites,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
    return records


def _settle(app: Any) -> None:
    for _ in range(20):
        app.processEvents()


def _enlarge_fonts(root: Any, factor: float) -> None:
    if factor == 1.0:
        return
    from PySide6.QtWidgets import QWidget

    widgets = [root, *root.findChildren(QWidget)]
    originals = [(widget, widget.styleSheet()) for widget in widgets]
    for widget, stylesheet in originals:
        if stylesheet:
            widget.setStyleSheet(
                re.sub(
                    r"(font-size\s*:\s*)([\d.]+)(px|pt)",
                    lambda match: f"{match[1]}{float(match[2]) * factor:g}{match[3]}",
                    stylesheet,
                )
            )
    for widget in reversed(widgets):
        if widget.layout() is not None:
            widget.layout().invalidate()
        widget.updateGeometry()


def _long_labels(root: Any) -> None:
    from PySide6.QtWidgets import QAbstractButton, QToolButton

    for button in root.findChildren(QAbstractButton):
        if button.text() and any(char.isalpha() for char in button.text()):
            # Standard pseudo-localization expands vowels and adds delimiters.
            # It stresses actual action wording instead of appending new prose.
            expanded = (
                "["
                + re.sub(r"[aeiouAEIOU]", lambda match: match[0] * 2, button.text())
                + "]"
            )
            if isinstance(button, QToolButton) and button.defaultAction():
                button.defaultAction().setText(expanded)
            else:
                button.setText(expanded)


def _capture_surface(
    surface: Any, app: Any, directory: Path, configuration: dict, temporary: Path
) -> list[dict]:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QAbstractButton, QDialog, QMenu

    from scripts.action_label_audit import (
        _opened_menu,
        audit_widget,
        control_path,
        menu_failures,
    )
    from scripts.action_label_fixtures import make_surface, surface_states

    records = []
    for width in surface.widths:
        root = make_surface(surface, temporary)
        _enlarge_fonts(root, configuration["text_scale"])
        if configuration["long_labels"]:
            _long_labels(root)
        height = (
            900
            if surface.name == "WorkspaceShell" and width == LARGE_CLIENT_WIDTH
            else 720
        )
        root.resize(width, height)
        root.show()
        for state in surface_states(root):
            _settle(app)
            failures = audit_widget(root)
            menu_records = []
            for number, menu in enumerate(root.findChildren(QMenu)):
                menu.aboutToShow.emit()
                if not any(
                    action.isVisible() and not action.isSeparator()
                    for action in menu.actions()
                ):
                    continue
                with _opened_menu(menu):
                    menu_errors = menu_failures(menu)
                    failures.extend(menu_errors)
                    capture = None
                    if menu_errors or state == "default":
                        capture = f"{surface.name}-{width}-{state}-{configuration['theme']}-text{configuration['text_scale']}-long{int(configuration['long_labels'])}-menu{number}.png"
                        if not menu.grab().save(str(directory / capture)):
                            raise OSError(f"Cannot save {capture}")
                menu_records.append(
                    {
                        "name": menu.objectName(),
                        "screenshot": capture,
                        "actions": [
                            action.text()
                            for action in menu.actions()
                            if action.isVisible()
                        ],
                    }
                )
            record = {
                "surface": surface.key,
                "state": state,
                "configuration": configuration,
                "requested_logical_size": [width, height],
                "actual_logical_size": [root.width(), root.height()],
                "device_pixel_ratio": root.devicePixelRatioF(),
                "font": root.font().toString(),
                "menus": menu_records,
                "controls": [
                    {
                        "control": control_path(button, root),
                        "text": button.text(),
                        "font": button.font().toString(),
                        "geometry": button.geometry().getRect(),
                        "accessible_name": button.accessibleName(),
                        "visible": button.isVisibleTo(root),
                        "enabled": button.isEnabled(),
                    }
                    for button in root.findChildren(QAbstractButton)
                ],
                "failures": [failure.to_dict() for failure in failures],
            }
            if (
                isinstance(root, QDialog)
                and (root.width() > MINIMUM_CLIENT_WIDTH or root.height() > height)
            ) or (
                surface.name == "WorkspaceShell"
                and root.size().toTuple() != (width, height)
            ):
                record["failures"].append(
                    {
                        "kind": "unsupported_client_geometry",
                        "required": [root.width(), root.height()],
                        "available": [width, height],
                    }
                )
            if record["failures"] or state == "default":
                filename = f"{surface.name}-{width}-{state}-{configuration['theme']}-text{configuration['text_scale']}-long{int(configuration['long_labels'])}.png"
                pixmap = root.grab()
                if not pixmap.save(str(directory / filename)):
                    raise OSError(f"Cannot save {filename}")
                record["screenshot"] = filename
                record["physical_size"] = [pixmap.width(), pixmap.height()]
            records.append(record)
            with (directory / "records.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
        root.close()
        host = getattr(root, "_action_audit_host", None)
        root.deleteLater()
        if host is not None:
            host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _settle(app)
    return records


def run_child(args: argparse.Namespace) -> int:
    """Run one scale with isolated settings and serializable reports."""
    # Isolate settings before importing any production component. The existing
    # capture helper uses the same test-scoped QSettings redirection pattern.
    from PySide6 import QtCore
    from PySide6 import __version__ as binding_version
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from scripts.action_label_coverage import coverage_records
    from scripts.action_label_fixtures import FAST_KEYS, SURFACES
    from scripts.action_label_review import presentation_fingerprint

    output = args.report_dir
    starting_fingerprint = presentation_fingerprint(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    (output / "records.jsonl").write_text("", encoding="utf-8")
    (output / "report.json").write_text(
        json.dumps({"status": "running", "native_review": "pending"}), encoding="utf-8"
    )
    records: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="kraken-action-labels-") as temporary:
        temporary_root = Path(temporary)
        native_settings = QtCore.QSettings

        class AuditSettings(native_settings):
            """Redirect constructor variants away from personal settings."""

            def __init__(self, *values: Any, **kwargs: Any) -> None:
                names = (
                    values
                    if len(values) == SETTINGS_NAME_COUNT
                    else ("ProjektKrakenAudit", "ActionLabels")
                )
                super().__init__(
                    self.Format.IniFormat, self.Scope.UserScope, *names, **kwargs
                )

        native_settings.setPath(
            native_settings.Format.IniFormat, native_settings.Scope.UserScope, temporary
        )
        QtCore.QSettings = AuditSettings
        app = QApplication.instance() or QApplication([])
        app.setOrganizationName("ProjektKrakenAudit")
        app.setApplicationName("ActionLabels")
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Segoe UI", 10))
        from src.core.theme_manager import ThemeManager

        themes = ThemeManager(str(ROOT / "themes.json"))
        template = (ROOT / "src/resources/main.qss").read_text(encoding="utf-8")
        theme_names = (
            tuple(themes.themes)
            if args.matrix == "full"
            else ("dark_mode", "light_mode")
        )
        if args.theme:
            theme_names = (args.theme,)
        text_scales = SCALES if args.matrix == "full" else (1.0, 2.0)
        if args.text_scale:
            text_scales = (args.text_scale,)
        surfaces = [
            surface
            for surface in SURFACES
            if args.matrix == "full" or surface.name in FAST_KEYS
        ]
        if args.surface:
            surfaces = [surface for surface in SURFACES if surface.name in args.surface]
            missing = set(args.surface) - {surface.name for surface in surfaces}
            if missing:
                raise ValueError(f"Missing registered fixtures: {sorted(missing)}")
        for theme in theme_names:
            themes.set_theme(theme)
            themes.apply_theme(app, template)
            for text_scale in text_scales:
                app.setFont(QFont("Segoe UI", round(10 * text_scale)))
                app.setStyleSheet(
                    re.sub(
                        r"(font-size\s*:\s*)([\d.]+)(px|pt)",
                        lambda match: f"{match[1]}{float(match[2]) * text_scale:g}{match[3]}",
                        themes.format_stylesheet(template),
                    )
                )
                for long_labels in (False, True) if args.matrix == "full" else (False,):
                    configuration = {
                        "theme": theme,
                        "qt_scale": args.scale,
                        "text_scale": text_scale,
                        "long_labels": long_labels,
                        "method": "offscreen-simulated-scale; native-review-required",
                    }
                    for surface in surfaces:
                        (output / "progress.json").write_text(
                            json.dumps(
                                {
                                    "surface": surface.key,
                                    "configuration": configuration,
                                    "records_completed": len(records),
                                }
                            ),
                            encoding="utf-8",
                        )
                        try:
                            records.extend(
                                _capture_surface(
                                    surface, app, output, configuration, temporary_root
                                )
                            )
                        except Exception as error:
                            logger.exception("Fixture failed: %s", surface.key)
                            records.append(
                                {
                                    "surface": surface.key,
                                    "configuration": configuration,
                                    "failures": [
                                        {
                                            "kind": "fixture_failure",
                                            "detail": str(error),
                                        }
                                    ],
                                }
                            )
    report = {
        "schema": 1,
        "matrix": args.matrix,
        "scale": args.scale,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "qt_binding": binding_version,
        "qt_runtime": QtCore.qVersion(),
        "screen_logical_size": app.primaryScreen().size().toTuple(),
        "revision": subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "presentation_fingerprint": starting_fingerprint,
        "requested_filters": {
            "surfaces": args.surface,
            "theme": args.theme,
            "text_scale": args.text_scale,
        },
        "complete_scale_matrix": args.matrix == "full"
        and not (args.surface or args.theme or args.text_scale),
        "native_review": "pending",
        "source_inventory": source_inventory(),
        "coverage": coverage_records(source_inventory(), SURFACES),
        "records": records,
    }
    report["presentation_changed_during_audit"] = (
        presentation_fingerprint(ROOT) != starting_fingerprint
    )
    (output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    count = sum(len(record["failures"]) for record in records)
    if report["presentation_changed_during_audit"]:
        logger.error("Presentation sources changed during this audit")
        count += 1
    if args.matrix == "full" and not args.surface:
        count += sum(record["status"] != "registered" for record in report["coverage"])
    logger.info(
        "%s records; %s failures; report: %s",
        len(records),
        count,
        output / "report.json",
    )
    return int(count > 0)


def main(argv: list[str] | None = None) -> int:
    """Run each DPI factor in a fresh process and fail on any violation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", choices=("fast", "full"), default="fast")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--surface", nargs="+")
    parser.add_argument("--theme")
    parser.add_argument("--text-scale", type=float, choices=SCALES)
    parser.add_argument("--scale", type=float, choices=SCALES)
    parser.add_argument("--require-native-review", action="store_true")
    parser.add_argument(
        "--native-review-manifest",
        type=Path,
        default=ROOT / "docs/ux/evidence/krt82/native-review.json",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.child:
        return run_child(args)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    scales = (
        (args.scale,) if args.scale else (SCALES if args.matrix == "full" else (1.0,))
    )
    statuses = []
    children = []
    for scale in scales:
        command = [
            sys.executable,
            "-m",
            "scripts.check_action_labels",
            "--child",
            "--scale",
            str(scale),
            "--matrix",
            args.matrix,
            "--report-dir",
            str(args.report_dir / f"scale-{scale}"),
        ]
        for flag, value in (("--theme", args.theme), ("--text-scale", args.text_scale)):
            if value is not None:
                command.extend([flag, str(value)])
        if args.surface:
            command.extend(["--surface", *args.surface])
        env = dict(
            os.environ,
            QT_QPA_PLATFORM="offscreen",
            QT_SCALE_FACTOR=str(scale),
            QT_OPENGL="software",
            QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-gpu-compositing",
        )
        screen = args.report_dir / f"screen-{scale}.json"
        screen.write_text(
            json.dumps(
                {
                    "windowFrameMargins": False,
                    "screens": [
                        {
                            "name": "UI-GATE-01",
                            "width": round(1920 * scale),
                            "height": round(1080 * scale),
                            "logicalDpi": 96,
                            "logicalBaseDpi": 96,
                            "dpr": 1.0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        configuration_path = os.path.relpath(screen, ROOT).replace("\\", "/")
        env["QT_QPA_PLATFORM"] = f"offscreen:configfile={configuration_path}"
        start = time.monotonic()
        status = subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
        statuses.append(status)
        children.append(
            {
                "scale": scale,
                "exit_code": status,
                "elapsed_seconds": round(time.monotonic() - start, 2),
                "report": f"scale-{scale}/report.json",
                "progress": f"scale-{scale}/progress.json",
            }
        )
        (args.report_dir / "matrix.json").write_text(
            json.dumps(
                {"matrix": args.matrix, "runs": children, "native_review": "pending"},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.require_native_review:
        from scripts.action_label_fixtures import SURFACES
        from scripts.action_label_review import native_review_failures

        failures = native_review_failures(args.native_review_manifest, ROOT, SURFACES)
        (args.report_dir / "native-review-result.json").write_text(
            json.dumps({"failures": failures}, indent=2) + "\n", encoding="utf-8"
        )
        for failure in failures:
            logger.error("%s", failure)
        statuses.append(int(bool(failures)))
    return int(any(statuses))


if __name__ == "__main__":
    raise SystemExit(main())
