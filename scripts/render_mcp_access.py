"""Capture offscreen MCP settings states; these are not native/human UX evidence."""

import argparse
import json
import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.core.theme_manager import ThemeManager
from src.gui.widgets.mcp_access_widget import McpAccessWidget
from src.gui.widgets.settings_center import SettingsCenter


def main() -> None:
    """Render enabled/focused and disabled states across all maintained themes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    if os.name == "nt":
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        app.setFont(QFont("Segoe UI", 10))
    manager = ThemeManager()
    manager.apply_theme(app, Path("src/resources/main.qss").read_text(encoding="utf-8"))
    records = []
    for theme in manager.get_available_themes():
        manager.set_theme(theme, app, persist=False)
        for width, state in ((640, "Active"), (960, "Off")):
            center = SettingsCenter()
            form = McpAccessWidget(center)
            center.add_page("kraken", "Integrations", form)
            center.navigate("integrations.mcp")
            form.render_state(
                {
                    "state": state,
                    "world_name": "Northwatch",
                    "message": "",
                    "available": state == "Active",
                    "activity": [],
                }
            )
            center.resize(width, 780)
            center.show()
            form.stop_button.setFocus()
            app.processEvents()
            name = f"{theme}-{width}-{state}.png"
            center.grab().save(str(args.output / name))
            records.append(
                {
                    "file": name,
                    "theme": theme,
                    "state": state,
                    "width": width,
                    "evidence": "offscreen",
                }
            )
            center.close()
            center.deleteLater()
            app.processEvents()
    (args.output / "captures.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
