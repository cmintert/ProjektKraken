"""Launch an isolated production shell for native KRT-94 keyboard review.

Run from the repository root with the project interpreter. No world is opened;
settings are temporary and the database worker is replaced by a test double.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def main() -> None:
    """Initialize isolated GUI dependencies in their required runtime order."""
    os.environ["QT_QPA_PLATFORM"] = "windows"
    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        tempfile.mkdtemp(prefix="krt94-native-"),
    )

    from src.core.theme_manager import ThemeManager

    theme_manager = ThemeManager()

    from src.app.main_window import MainWindow
    from src.core.entities import Entity
    from src.core.events import Event

    with (
        patch("src.app.worker_manager.DatabaseWorker"),
        patch("src.app.worker_manager.QThread"),
        patch("src.app.main_window.QTimer"),
        patch("src.app.main_window.invoke_method", return_value=True),
    ):
        window = MainWindow()
        window.backup_coordinator.restore_shutdown_complete = True
        theme_manager.apply_theme(
            app, Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
        window.setWindowTitle("KRT-94 disposable keyboard review")
        window.resize(1600, 900)
        with patch.object(window.entity_editor.gallery, "set_owner"):
            window.entity_editor.load_entity(
                Entity(
                    name="Keyboard review",
                    type="character",
                    description="First paragraph",
                )
            )
        with patch.object(window.event_editor.gallery, "set_owner"):
            window.event_editor.load_event(
                Event(name="Arrival", lore_date=1.0, description="Event paragraph")
            )
        window.show()
        window.workspace.show_panel("entity")
        window.entity_editor.desc_edit.editor.set_completer(
            items=[("alpha", "Alpha", "entity"), ("alpine", "Alpine", "entity")]
        )
        if "--source" in sys.argv:
            window.entity_editor.desc_edit.editor.toggle_view_mode()
        app.exec()


if __name__ == "__main__":
    main()
