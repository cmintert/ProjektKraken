"""Capture bounded Help presentation evidence without loading a world."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget

from src.app.coordinators.help_coordinator import HelpCoordinator
from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import HelpContextRegistry
from src.services.help_bundle_service import HelpBundleService


def capture(output: Path) -> None:
    """Render six palettes at normal/narrow widths and report label geometry."""
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    theme = ThemeManager(str(root / "themes.json"))
    output.mkdir(parents=True, exist_ok=True)
    owner = QWidget()
    text = QTextEdit(owner)
    QVBoxLayout(owner).addWidget(text)
    registry = HelpContextRegistry()
    registry.register_control(text, "writing.edit")
    coordinator = HelpCoordinator(owner, registry, HelpBundleService())
    owner.show()
    records = []
    try:
        for name in theme.get_available_themes():
            theme.set_theme(name)
            coordinator.history.clear()
            coordinator.index = -1
            coordinator.open_topic("writing.edit")
            for width in (640, 360):
                coordinator.viewer.resize(width, 560)
                coordinator.viewer.buttons["Return to work"].setFocus(
                    Qt.FocusReason.OtherFocusReason
                )
                app.processEvents()
                viewer = coordinator.viewer
                geometry = {
                    label: {
                        "width": button.width(),
                        "required": button.sizeHint().width(),
                        "enabled": button.isEnabled(),
                        "visible": button.isVisible(),
                    }
                    for label, button in viewer.buttons.items()
                }
                if any(
                    item["width"] < item["required"] or not item["visible"]
                    for item in geometry.values()
                ):
                    raise ValueError(f"Clipped Help control: {name}, {width}")
                filename = f"{name.replace(' ', '-').lower()}-{width}.png"
                if not viewer.grab().save(str(output / filename)):
                    raise OSError(f"Could not save {filename}")
                records.append({"theme": name, "width": width, "controls": geometry})
        screen = owner.screen()
        metadata = coordinator.service.validate()
        report = {
            "platform": app.platformName(),
            "qt_version": qVersion(),
            "app_version": metadata.version,
            "source_revision": metadata.revision,
            "source_dirty": metadata.dirty,
            "device_pixel_ratio": owner.devicePixelRatioF(),
            "logical_dpi": screen.logicalDotsPerInch(),
            "renders": records,
        }
        (output / "presentation.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        coordinator.stop()
        owner.close()


def main() -> None:
    """Write presentation artifacts to an explicitly selected directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    capture(args.output)


if __name__ == "__main__":
    main()
