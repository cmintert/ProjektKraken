"""Reproduce KRT-53 writing controls and entry-picker render evidence."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PySide6.QtGui import QFontDatabase, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.wiki_text_edit import WikiTextEdit  # noqa: E402

TARGET = "550e8400-e29b-41d4-a716-446655440000"


def render(app: QApplication, width: int, theme: str) -> None:
    """Capture real shared writing controls, duplicate results and local feedback."""
    ThemeManager().set_theme(theme)
    writing = WikiTextEdit()
    writing.set_adaptive_width(True)
    writing.resize(width, 420)
    writing.set_completer(
        items=[
            (TARGET, "House Bjornaer", "entity"),
            ("550e8400-e29b-41d4-a716-446655440001", "House Bjornaer", "event"),
        ]
    )
    writing.set_wiki_text(
        "# Tribunal history\n\nTasgillia studies House Bjornaer.\n\n"
        "Select the group's name, then use Link to entry…"
    )
    writing.show()
    app.processEvents()
    cursor = writing.textCursor()
    start = writing.toPlainText().index("House Bjornaer")
    cursor.setPosition(start)
    cursor.setPosition(start + 14, QTextCursor.MoveMode.KeepAnchor)
    writing.setTextCursor(cursor)
    writing.action_link_entry.trigger()
    app.processEvents()
    picker = writing.link_authoring.picker
    assert picker is not None
    picker.results.setCurrentRow(0)
    app.processEvents()
    output = Path(__file__).parent
    prefix = f"{theme}-{width}"
    assert writing.grab().save(str(output / f"{prefix}-selection.png"))
    assert picker.grab().save(str(output / f"{prefix}-picker.png"))
    assert writing.width() == width
    assert picker.screen().availableGeometry().contains(picker.geometry())
    picker.link_button.click()
    cursor = writing.textCursor()
    cursor.setPosition(start + 1)
    writing.setTextCursor(cursor)
    writing.set_return_available(True)
    app.processEvents()
    assert writing.action_open_link.isEnabled()
    assert writing.grab().save(str(output / f"{prefix}-linked.png"))
    # Focus writing hides this formatting toolbar; link controls stay visible.
    writing.toolbar.hide()
    app.processEvents()
    assert writing.link_toolbar.isVisible()
    assert writing.grab().save(str(output / f"{prefix}-writing-tools.png"))
    writing.close()
    writing.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main() -> None:
    """Render without opening worlds or changing application settings."""
    with TemporaryDirectory(prefix="kraken-krt53-render-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        QCoreApplication.setOrganizationName("KrakenRenderEvidence")
        QCoreApplication.setApplicationName("KRT53")
        app = QApplication([])
        for font in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
            path = Path("C:/Windows/Fonts") / font
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        ThemeManager(str(REPO / "themes.json"))
        for theme in ("dark_mode", "light_mode"):
            for width in (360, 650):
                render(app, width, theme)


if __name__ == "__main__":
    main()
