"""Render six-theme switch states with isolated settings (KRT-120).

This is automated presentation evidence, not native human acceptance.
"""

import argparse
import json
import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from scripts.benchmark_theme_switch import _configure_fonts, _fixtures, _settle
from scripts.gui_probe_settings import install_probe_settings


def _workspace(widgets: list[QWidget]) -> QMainWindow:
    """Compose hydrated feature widgets in the real fixed-zone shell."""
    from src.gui.workspace import WorkspaceShell

    host = QMainWindow()
    shell = WorkspaceShell(host)
    host.setCentralWidget(shell)
    # Settings remains its own modeless window, as in the application.
    panels = [
        ("entity", "Entity", widgets[0], "center"),
        ("event", "Event", widgets[1], "center"),
        ("timeline", "Timeline", widgets[3], "bottom"),
        ("graph", "Graph", widgets[4], "right"),
        ("longform", "Longform", widgets[5], "left"),
    ]
    for identifier, title, panel, zone in panels:
        panel.hide()
        panel.setWindowFlag(Qt.WindowType.Widget)
        panel.setMinimumSize(0, 0)
        panel.setMaximumSize(16777215, 16777215)
        shell.register_panel(identifier, title, panel, zone)
    shell.activity_bar.configure_workspaces()
    shell.show_panel("entity")
    shell.horizontal_splitter.setSizes([240, 580, 300])
    shell.vertical_splitter.setSizes([500, 210])
    host.resize(1280, 900)
    host.show()
    return host


def _states(widget: QWidget) -> tuple[str, ...]:
    if hasattr(widget, "btn_inject"):
        return "normal", "focus", "hover", "disabled", "checked"
    if hasattr(widget, "apply_button"):
        return "normal", "focus", "hover", "disabled"
    return ("normal",)


def _prepare_state(widget: QWidget, state: str) -> None:
    if hasattr(widget, "btn_inject"):
        widget.summary_checkbox.setChecked(state == "checked")
        widget.btn_save.setEnabled(state != "disabled")
        target = widget.btn_inject
    elif hasattr(widget, "apply_button"):
        widget.apply_button.setEnabled(state != "disabled")
        target = widget.apply_button
    else:
        return
    target.clearFocus()
    if state == "focus":
        target.setFocus()
    QTest.mouseMove(
        target, target.rect().center() if state == "hover" else QPoint(-20, -20)
    )


def main() -> None:
    """Capture actual production widgets at normal/narrow sizes and larger fonts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--presentation", choices=("legacy", "scoped"), default="scoped"
    )
    parser.add_argument("--workspace", action="store_true")
    options = parser.parse_args()
    output = Path(options.output)
    output.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    records = []
    with tempfile.TemporaryDirectory(prefix="kraken-theme-capture-") as directory:
        install_probe_settings(directory)
        from src.core.theme_manager import ThemeManager
        from src.gui.utils.theme_presentation import install_theme_presentation

        app = QApplication([])
        if options.presentation == "scoped":
            install_theme_presentation(app)
        _configure_fonts(app)
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        widgets, graph = _fixtures(app, "loaded")
        if options.workspace:
            widgets = [_workspace(widgets), widgets[2]]
        for widget in widgets:
            widget.show()
        for size in (10, 15):
            app.setFont(QFont("Segoe UI", size))
            for theme in manager.themes:
                manager.set_theme(theme, persist=False)
                for width in (1280, 760) if options.workspace else (960, 360):
                    for index, widget in enumerate(widgets):
                        widget.setFixedSize(width, 720)
                        widget.activateWindow()
                        for state in _states(widget):
                            _prepare_state(widget, state)
                            _settle(app, graph)
                            name = f"{index}-{theme}-{width}-font{size}-{state}.png"
                            widget.grab().save(str(output / name))
                            records.append(
                                {
                                    "file": name,
                                    "theme": theme,
                                    "state": state,
                                    "requested_width": width,
                                    "width": widget.width(),
                                    "font_points": size,
                                    "effective_root_font_points": widget.font().pointSizeF(),
                                    "platform": app.platformName(),
                                    "device_pixel_ratio": widget.devicePixelRatioF(),
                                }
                            )
        graph._web_view.shutdown()
        for widget in widgets:
            widget.close()
    (output / "manifest.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
