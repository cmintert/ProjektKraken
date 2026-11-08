"""Capture offscreen MCP settings states; these are not native/human UX evidence."""

import argparse
import json
import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QScrollArea

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
        for width, state, available in (
            (640, "Active", True),
            (960, "Off", True),
            (360, "Off", True),
            (360, "Off", False),
        ):
            center = SettingsCenter()
            form = McpAccessWidget(center)
            center.add_page("kraken", "Integrations", form)
            center.navigate("integrations.mcp")
            form.render_state(
                {
                    "state": state,
                    "world_name": "Northwatch",
                    "message": "",
                    "available": available,
                    "scopes": ["maps", "longform", "attachments", "images", "semantic"]
                    if state == "Active"
                    else [],
                    "semantic_state": "unprepared",
                    "activity": [],
                }
            )
            center.resize(width, 780)
            center.show()
            form.stop_button.setFocus()
            app.processEvents()
            name = f"{theme}-{width}-{state}-{available}.png"
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
            form.scope_details.setChecked(True)
            app.processEvents()
            for scroll in center.findChildren(QScrollArea):
                if scroll.widget() and scroll.widget().isAncestorOf(form):
                    scroll.verticalScrollBar().setValue(
                        scroll.verticalScrollBar().maximum()
                    )
            app.processEvents()
            center.grab().save(str(args.output / name.replace(".png", "-controls.png")))
            center.close()
            center.deleteLater()
            app.processEvents()
    (args.output / "captures.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
