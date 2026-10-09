"""Render KRT-47 Longform controls using production QSS and isolated settings."""

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.longform.editor import LongformEditorWidget  # noqa: E402

OUTPUT = Path(__file__).parent
NARROW_WIDTH = 400
RETAINED: list[QWidget] = []


def main() -> None:
    """Capture both widths and disabled/focus/chooser/menu states in six themes."""
    with TemporaryDirectory(prefix="kraken-krt47-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication([])
        for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / font))
        manager = ThemeManager()
        manager.load_stylesheet(str(REPO / "src/resources/main.qss"))
        sequence = [
            {
                "table": "entities",
                "id": "tasgillia",
                "name": "Tasgillia",
                "content": "A member of the Rhine Tribunal.",
                "heading_level": 1,
                "meta": {"position": 100.0, "parent_id": None, "depth": 0},
            },
            {
                "table": "events",
                "id": "charter",
                "name": "Benchmark Charter 1218",
                "content": "A charter witnessed by Tasgillia.",
                "heading_level": 2,
                "meta": {"position": 200.0, "parent_id": "tasgillia", "depth": 1},
            },
        ]
        for theme in manager.themes:
            manager.set_theme(theme, app)
            for width in (NARROW_WIDTH, 1100):
                editor = LongformEditorWidget()
                RETAINED.append(editor)
                editor.resize(width, 650)
                editor.show()
                editor.activateWindow()
                app.processEvents()
                assert editor.width() == width
                editor.load_sequence([])
                app.processEvents()
                editor.grab().save(str(OUTPUT / f"{theme}-{width}-empty.png"))
                editor.load_sequence(sequence)
                editor.outline.setCurrentItem(editor.outline.topLevelItem(0).child(0))
                editor.btn_add.setFocus(Qt.FocusReason.TabFocusReason)
                app.processEvents()
                assert editor.btn_add.hasFocus()
                editor.grab().save(str(OUTPUT / f"{theme}-{width}-outline-focus.png"))
                editor._prepare_outline_actions()
                editor.outline_actions_menu.popup(
                    editor.btn_outline_actions.mapToGlobal(
                        editor.btn_outline_actions.rect().bottomLeft()
                    )
                )
                app.processEvents()
                editor.outline_actions_menu.grab().save(
                    str(OUTPUT / f"{theme}-{width}-actions.png")
                )
                editor.outline_actions_menu.hide()
                if width == NARROW_WIDTH:
                    editor.action_toolbar.overflow_menu.popup(
                        editor.action_toolbar.overflow_button.mapToGlobal(
                            editor.action_toolbar.overflow_button.rect().bottomLeft()
                        )
                    )
                    app.processEvents()
                    editor.action_toolbar.overflow_menu.grab().save(
                        str(OUTPUT / f"{theme}-{width}-overflow.png")
                    )
                    editor.action_toolbar.overflow_menu.hide()
                editor.membership.show_items(
                    [
                        ("entities", "tasgillia", "Tasgillia"),
                        ("events", "charter", "Benchmark Charter 1218"),
                    ]
                )
                editor.membership.results.setCurrentRow(1)
                QTest.mouseMove(editor.membership.add_button)
                app.processEvents()
                editor.grab().save(str(OUTPUT / f"{theme}-{width}-add.png"))
                editor.hide()


if __name__ == "__main__":
    main()
