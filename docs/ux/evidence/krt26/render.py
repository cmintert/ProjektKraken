"""Render map draft decisions using production QSS and disposable settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.dialogs.map_edit_transition_dialog import (  # noqa: E402
    MapEditTransitionDialog,
)


def main() -> None:
    """Capture enabled/disabled and real keyboard focus in six palettes."""
    with TemporaryDirectory(prefix="kraken-krt26-render-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        QCoreApplication.setOrganizationName("KrakenRenderEvidence")
        QCoreApplication.setApplicationName("KRT26")
        app = QApplication([])
        for font in ("segoeui.ttf", "segoeuib.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / font))
        manager = ThemeManager(str(REPO / "themes.json"))
        manager.load_stylesheet(str(REPO / "src/resources/main.qss"))
        retained = []
        for theme in manager.get_available_themes():
            manager.set_theme(theme, app)
            for enabled in (True, False):
                dialog = MapEditTransitionDialog(
                    "open the Upper Rhine map",
                    {
                        "label": "the journey for Tasgillia",
                        "can_apply": enabled,
                        "explanation": "Finish the second location before applying.",
                    },
                )
                dialog.resize(320 if not enabled else 420, 250)
                dialog.show()
                dialog.activateWindow()
                dialog.keep_button.setFocus(Qt.FocusReason.TabFocusReason)
                app.processEvents()
                assert dialog.keep_button.hasFocus()
                assert dialog.apply_button.isEnabled() == enabled
                for button in (
                    dialog.apply_button,
                    dialog.keep_button,
                    dialog.discard_button,
                ):
                    assert dialog.rect().contains(button.geometry())
                suffix = "enabled" if enabled else "disabled-narrow"
                assert dialog.grab().save(
                    str(Path(__file__).parent / f"{theme}-{suffix}.png")
                )
                dialog.hide()
                retained.append(dialog)


if __name__ == "__main__":
    main()
