"""Measure Settings Apply/OK through a verified, correctly colored Qt frame."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def _verify_pixels(host: Any, editor: Any, view: Any, theme: dict) -> dict[str, str]:
    """Verify finished pixels independently of stylesheet/palette bookkeeping."""
    main_image = host.grab().toImage()
    input_image = editor.name_edit.grab().toImage()
    pixels = {
        "window": main_image.pixelColor(2, 2).name(),
        "input": input_image.pixelColor(
            input_image.width() - 10, input_image.height() // 2
        ).name(),
    }
    expected = {"window": theme["app_bg"].lower(), "input": theme["surface"].lower()}
    if pixels != expected:
        raise AssertionError(f"Theme frame mismatch: {pixels} != {expected}")
    if view.isVisible():
        actual = view.grab().toImage().pixelColor(2, 2).name()
        if actual != theme["app_bg"].lower():
            raise AssertionError(f"Settings frame mismatch: {actual}")
    return pixels


def _child(options: argparse.Namespace) -> None:
    from scripts.gui_probe_settings import install_probe_settings

    with tempfile.TemporaryDirectory(prefix="kraken-apply-frame-") as directory:
        install_probe_settings(directory)
        from PySide6.QtCore import QEvent, QObject, Qt, QTimer
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QMainWindow

        from scripts.benchmark_theme_switch import (
            _configure_fonts,
            _drain_layout,
            _wait,
        )
        from scripts.capture_inspector_evidence import _EvidenceWorker, _make_editor
        from src.app.coordinators.settings_coordinator import SettingsCoordinator
        from src.app.settings_composition import _apply_effective_theme
        from src.core.theme_manager import ThemeManager
        from src.gui.utils.theme_presentation import (
            install_theme_presentation,
            register_theme_scope,
        )

        app = QApplication([])
        _configure_fonts(app)
        if options.presentation == "scoped":
            install_theme_presentation(app)
        manager = ThemeManager()
        manager.current_theme_name = "dark_mode"
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        host = QMainWindow()
        host.worker = _EvidenceWorker(host)
        host.setFixedSize(960, 900)
        editor = _make_editor("entity", host)
        register_theme_scope(editor)
        host.setCentralWidget(editor)
        coordinator = SettingsCoordinator(lambda: {}, lambda command: None, host)
        coordinator.preferences_changed.connect(
            lambda _: _apply_effective_theme(coordinator)
        )
        coordinator.open_settings("appearance.theme")
        host.show()
        _drain_layout(app)
        active: dict[str, Any] | None = None

        def verify_first_result(entry: dict[str, Any], target: Any) -> None:
            if active is not entry or "first_result_verified_ms" in entry:
                return
            image = target.grab().toImage()
            expected = manager.get_theme()["app_bg"].lower()
            actual = image.pixelColor(2, 2).name()
            if actual != expected:
                raise AssertionError(f"First result mismatch: {actual} != {expected}")
            if options.button == "apply":
                field = coordinator.view.controls["appearance.theme"]
                field_image = field.grab().toImage()
                actual = field_image.pixelColor(
                    field_image.width() - 35, field_image.height() // 2
                ).name()
                expected = manager.get_theme()["surface"].lower()
                if actual != expected:
                    raise AssertionError(
                        f"First control mismatch: {actual} != {expected}"
                    )
            entry["first_result_verified_ms"] = (
                time.perf_counter() - entry["started"]
            ) * 1000

        class Paints(QObject):
            def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
                if (
                    active is not None
                    and event.type() == QEvent.Type.Paint
                    and manager.current_theme_name == active["theme"]
                ):
                    active.setdefault(
                        "first_new_theme_paint_ms",
                        (time.perf_counter() - active["started"]) * 1000,
                    )
                    target = coordinator.view if options.button == "apply" else host
                    if watched is target and "handler_return_ms" in active:
                        runtime = getattr(app, "_kraken_theme_presentation", None)
                        check = (
                            coordinator.view if options.button == "apply" else editor
                        )
                        scope = (
                            runtime._scope_for(check) if runtime is not None else None
                        )
                        if scope is None or scope.generation == runtime._generation:
                            entry = active
                            QTimer.singleShot(
                                0, lambda: verify_first_result(entry, target)
                            )
                return False

        observer = Paints(host)
        host.installEventFilter(observer)
        assert coordinator.view is not None
        coordinator.view.installEventFilter(observer)
        results = []
        names = [name for name in manager.themes if name != "dark_mode"] + ["dark_mode"]
        for index in range(options.warmups + options.samples):
            coordinator.open_settings("appearance.theme")
            view = coordinator.view
            assert view is not None
            name = names[index % len(names)]
            combo = view.controls["appearance.theme"]
            combo.setCurrentIndex(combo.findData(name))
            coordinator._sync()
            _drain_layout(app)
            button = view.ok_button if options.button == "ok" else view.apply_button
            assert button.isEnabled()
            active = {"theme": name, "started": time.perf_counter()}
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            active["handler_return_ms"] = (
                time.perf_counter() - active["started"]
            ) * 1000
            _wait(app, lambda: "first_result_verified_ms" in active)
            runtime = getattr(app, "_kraken_theme_presentation", None)
            if runtime is not None:
                _wait(app, lambda: not runtime.is_pending)
            _drain_layout(app)
            pixels = _verify_pixels(host, editor, view, manager.get_theme())
            active["verified_frame_ms"] = (
                time.perf_counter() - active["started"]
            ) * 1000
            active["pixels"] = pixels
            active.pop("started")
            if index >= options.warmups:
                results.append(active)
            active = None
        Path(options.output).write_text(
            json.dumps(
                {
                    "presentation": options.presentation,
                    "button": options.button,
                    "platform": app.platformName(),
                    "samples": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        coordinator._poll.stop()
        editor.set_dirty(False)
        if coordinator.view is not None:
            coordinator.view.hide()
        host.close()


def main() -> None:
    """Run each presentation/Apply choice in fresh, explicitly isolated processes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--presentation", choices=("legacy", "scoped"), default="scoped"
    )
    parser.add_argument("--button", choices=("apply", "ok"), default="apply")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--child", action="store_true")
    options = parser.parse_args()
    if options.child:
        _child(options)
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    runs = []
    with tempfile.TemporaryDirectory(prefix="kraken-apply-results-") as directory:
        for index in range(options.runs):
            path = str(Path(directory) / f"{index}.json")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.benchmark_theme_apply",
                    "--child",
                    "--presentation",
                    options.presentation,
                    "--button",
                    options.button,
                    "--samples",
                    str(options.samples),
                    "--warmups",
                    str(options.warmups),
                    "--output",
                    path,
                ],
                check=True,
            )
            runs.append(json.loads(Path(path).read_text("utf-8")))
    samples = [sample for run in runs for sample in run["samples"]]
    metrics = {}
    for key in ("handler_return_ms", "first_result_verified_ms", "verified_frame_ms"):
        values = sorted(sample[key] for sample in samples)
        metrics[key] = {
            "median": statistics.median(values),
            "p95": values[math.ceil(len(values) * 0.95) - 1],
        }
    Path(options.output).parent.mkdir(parents=True, exist_ok=True)
    Path(options.output).write_text(
        json.dumps({"summary_ms": metrics, "runs": runs}, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
