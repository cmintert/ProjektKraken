"""Capture isolated Settings Center presentation without personal settings/worlds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from scripts.action_label_fixtures import SURFACES, make_surface
from src.core.theme_manager import ThemeManager


def capture(output: Path) -> None:
    """Render every page in six palettes, recording requested and actual geometry."""
    app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Segoe UI", 10))
    root = Path(__file__).resolve().parents[1]
    theme = ThemeManager(str(root / "themes.json"))
    template = (root / "src/resources/main.qss").read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    surface = next(item for item in SURFACES if item.name == "SettingsCenter")
    center = make_surface(surface, output)
    center.world_name = "Fixture world"
    center.scope.setItemText(1, "This World — Fixture world")
    records = []
    for palette in theme.get_available_themes():
        theme.set_theme(palette, persist=False)
        app.setStyleSheet(theme.format_stylesheet(template))
        for width, height in ((960, 680), (700, 600)):
            center.resize(width, height)
            center.show()
            for scope, category in center.pages:
                center.scope.setCurrentIndex(1 if scope == "world" else 0)
                for index in range(center.navigation.count()):
                    item = center.navigation.item(index)
                    if item.data(256)[1] == category:
                        center.navigation.setCurrentItem(item)
                        break
                for _ in range(3):
                    app.processEvents()
                name = f"{palette}-{width}-{scope}-{category.replace(' ', '_').replace('&', 'and')}.png"
                center.grab().save(str(output / name))
                records.append(
                    {
                        "file": name,
                        "scope": scope,
                        "category": category,
                        "requested_size": [width, height],
                        "actual_size": [center.width(), center.height()],
                        "font_points": center.font().pointSizeF(),
                        "device_pixel_ratio": center.devicePixelRatioF(),
                        "physical_capture": [
                            center.grab().width(),
                            center.grab().height(),
                        ],
                    }
                )
            center.navigate("world.auto_relations")
            center.controls["world.auto_relations"].setEnabled(False)
            center.search.setFocus()
            app.processEvents()
            center.grab().save(str(output / f"{palette}-{width}-disabled-focus.png"))
            center.controls["world.auto_relations"].setEnabled(True)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "method": "offscreen Qt captures; native Windows and human review pending",
                "records": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    center.hide()
    center.deleteLater()
    app.processEvents()


def main() -> None:
    """Run an isolated presentation capture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/krt55/rendered"))
    capture(parser.parse_args().output)


if __name__ == "__main__":
    main()
