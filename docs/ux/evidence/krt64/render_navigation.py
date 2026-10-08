"""Render the production map action across themes and narrow toolbar overflow.

Run from the repository root:
    python -m docs.ux.evidence.krt64.render_navigation
"""

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map_widget import MapWidget


def render() -> None:
    """Capture disabled, normal, hover, focus and narrow production controls."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    output = Path(__file__).parent
    root = output.resolve().parents[3]
    with tempfile.TemporaryDirectory() as scratch:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, scratch
        )
        for font in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / font))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager(str(root / "themes.json"))
        manager.apply_theme(
            app, (root / "src/resources/main.qss").read_text(encoding="utf-8")
        )
        widget = MapWidget()
        image = QPixmap(600, 400)
        image.fill(Qt.GlobalColor.gray)
        image_path = Path(scratch) / "map.png"
        image.save(str(image_path))
        widget.load_map(str(image_path))
        widget.add_marker("target", "entity", "Target", 0.5, 0.5)
        item = widget.view.find_item_by_id("target")
        assert item is not None
        widget.resize(1600, 700)
        widget.show()
        for name in manager.themes:
            manager.set_theme(name, app)
            widget.resize(1600, 700)
            app.processEvents()
            board = QPixmap(820, 140)
            board.fill(QColor(manager.get_theme()["surface"]))
            painter = QPainter(board)
            painter.setPen(QColor(manager.get_theme()["text_main"]))
            for index, state in enumerate(("Disabled", "Normal", "Hover", "Focus")):
                item.setSelected(state != "Disabled")
                widget.view.setFocus()
                QTest.mouseMove(widget.view.viewport(), QPoint(20, 20))
                if state == "Hover":
                    QTest.mouseMove(
                        widget.btn_open_inspector, widget.btn_open_inspector.rect().center()
                    )
                elif state == "Focus":
                    widget.btn_open_inspector.setFocus(Qt.FocusReason.TabFocusReason)
                app.processEvents()
                painter.drawText(index * 205 + 10, 30, state)
                painter.drawPixmap(index * 205 + 10, 45, widget.btn_open_inspector.grab())
            painter.end()
            board.save(str(output / f"{name}-states.png"))
            widget.view.setFocus()
            widget.resize(430, 700)
            app.processEvents()
            QTest.qWait(30)
            widget.toolbar.grab().save(str(output / f"{name}-narrow-toolbar.png"))
            extension = widget.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            assert extension is not None and extension.isVisible()
            menu = extension.menu()
            assert menu is not None
            assert (
                widget.btn_open_inspector.isVisible()
                or widget.open_inspector_action in menu.actions()
            )
            if widget.open_inspector_action in menu.actions():
                menu.popup(extension.mapToGlobal(extension.rect().bottomLeft()))
                app.processEvents()
                menu.grab().save(str(output / f"{name}-narrow-overflow.png"))
                menu.hide()
        widget.close()


if __name__ == "__main__":
    render()
