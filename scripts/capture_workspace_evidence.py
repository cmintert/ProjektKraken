"""Isolated workspace rail/selector comparison; no personal worlds or settings."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QToolBar

from scripts.action_label_fixtures import SURFACES, make_surface
from scripts.action_label_review import presentation_fingerprint
from src.core.theme_manager import ThemeManager
from src.core.workspaces import BUILTIN_WORKSPACES


def capture(output: Path) -> None:
    """Record real widget geometry and variants without claiming human task results."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-workspace-evidence-") as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        template = Path("src/resources/main.qss").read_text("utf-8")
        surface = next(item for item in SURFACES if item.name == "WorkspaceShell")
        window = make_surface(surface, Path(temporary))
        shell = window.workspace
        coordinator = window.workspace_coordinator
        rail = shell.activity_bar
        # Comparison-only selector above the Project pane; never shipped in the app.
        selector = QComboBox(shell.panes["left"])
        for item in BUILTIN_WORKSPACES:
            selector.addItem(item.name, item.id)
        selector.currentIndexChanged.connect(
            lambda index: coordinator.activate(str(selector.itemData(index)))
        )
        shell.panes["left"].layout().insertWidget(0, selector)
        selector.hide()
        # Reproduce the previous rail's panel-reveal behavior for baseline captures.
        legacy = QToolBar("Previous panel launchers", shell)
        legacy.setOrientation(Qt.Orientation.Vertical)
        legacy.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for identifier, label in (
            ("project", "Project"),
            ("map", "Map"),
            ("timeline", "Timeline"),
            ("graph", "Graph"),
            ("longform", "Longform"),
            ("analysis", "Analysis"),
        ):
            legacy.addAction(label).triggered.connect(
                lambda _checked=False, target=identifier: shell.show_panel(target)
            )
        shell.layout().insertWidget(0, legacy)
        legacy.hide()
        records: list[dict[str, Any]] = []
        state_records: list[dict[str, Any]] = []
        for palette in manager.get_available_themes():
            manager.set_theme(palette, persist=False)
            app.setStyleSheet(manager.format_stylesheet(template))
            for width, height in ((1280, 720), (1600, 900)):
                window.resize(width, height)
                window.show()
                for variant in ("expanded", "collapsed", "selector", "previous"):
                    rail.setVisible(variant in ("expanded", "collapsed"))
                    rail.set_expanded(variant != "collapsed")
                    selector.setVisible(variant == "selector")
                    legacy.setVisible(variant == "previous")
                    selector.setCurrentIndex(2)
                    for _ in range(3):
                        app.processEvents()
                    coordinator.activate("chronology")
                    coordinator.reset()
                    for _ in range(8):
                        app.processEvents()
                    name = f"{palette}-{width}-{variant}.png"
                    pixmap = window.grab()
                    pixmap.save(str(output / name))
                    records.append(
                        {
                            "file": name,
                            "variant": variant,
                            "requested_size": [width, height],
                            "actual_size": [window.width(), window.height()],
                            "navigation_width": legacy.width()
                            if variant == "previous"
                            else (rail.width() if rail.isVisible() else 0),
                            "project_width": shell.panes["left"].width(),
                            "font_points": rail.font().pointSizeF(),
                            "device_pixel_ratio": window.devicePixelRatioF(),
                            "physical_capture": [pixmap.width(), pixmap.height()],
                        }
                    )
            rail.show()
            rail.set_expanded(True)
            selector.hide()
            legacy.hide()
            state_records.extend(_capture_states(window, app, output, palette))
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "method": "offscreen Qt; reconstructed previous launcher rail and comparison-only selector; no human task measurements",
                    "records": records,
                    "state_records": state_records,
                    "presentation_fingerprint": presentation_fingerprint(Path.cwd()),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        window.hide()
        window.deleteLater()
        app.processEvents()


def _capture_states(
    window: Any, app: QApplication, output: Path, palette: str
) -> list[dict[str, Any]]:
    """Exercise shared focus, hover, pressed and disabled states in each palette."""
    rail = window.workspace.activity_bar
    button = rail.widgetForAction(rail.workspace_actions["chronology"])
    records = []
    for state in ("focus", "hover", "pressed", "disabled"):
        rail.setEnabled(state != "disabled")
        button.clearFocus()
        if state == "focus":
            button.setFocus()
        if state in ("hover", "pressed"):
            QTest.mouseMove(button, button.rect().center())
        if state == "pressed":
            QTest.mousePress(button, Qt.MouseButton.LeftButton)
        for _ in range(4):
            app.processEvents()
        name = f"{palette}-{state}.png"
        window.grab().save(str(output / name))
        records.append({"file": name, "state": state, "theme": palette})
        if state == "pressed":
            QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
    rail.setEnabled(True)
    return records


def main() -> None:
    """Generate review artifacts in the requested workspace directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/krt108/rendered")
    )
    capture(parser.parse_args().output)


if __name__ == "__main__":
    main()
