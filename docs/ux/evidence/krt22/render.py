"""Reproduce seeded KRT-22 inspector render evidence from the repository root."""

# ruff: noqa: I001

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSettings, Signal, Slot  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget  # noqa: E402

from src.core.calendar import CalendarConfig, CalendarConverter  # noqa: E402
from src.core.entities import Entity  # noqa: E402
from src.core.events import Event  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.widgets.entity_editor import EntityEditorWidget  # noqa: E402
from src.gui.widgets.event_editor import EventEditorWidget  # noqa: E402


class AttachmentReceiver(QObject):
    """Receive irrelevant gallery requests without opening a world database."""

    attachments_loaded = Signal(str, str, list)
    command_finished = Signal(object)

    @Slot(str, str)
    def load_attachments(self, owner_type: str, owner_id: str) -> None:
        """Leave this seeded render's media gallery empty."""


def render(app: QApplication, kind: str, width: int) -> None:
    """Capture the real connection section with production QSS and sample lore."""
    host = QMainWindow()
    host.worker = AttachmentReceiver(host)
    host.resize(width, 900)
    container = QWidget(host)
    host.setCentralWidget(container)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    editor = EntityEditorWidget(host) if kind == "entity" else EventEditorWidget(host)
    layout.addWidget(editor)
    if isinstance(editor, EntityEditorWidget):
        editor.load_entity(Entity(id="source", name="Tasgillia", type="Character"))
    else:
        editor.load_event(Event(id="source", name="Winter Council", lore_date=100))
    editor.set_relation_time_context(
        125.5, CalendarConverter(CalendarConfig.create_default())
    )
    target_name = "House Bjornaer" if kind == "entity" else "Tasgillia"
    editor._suggestion_items = [("target", target_name, "entity")]
    editor.inspector.activate_section_id("connections")
    host.show()
    app.processEvents()
    panel = editor.relation_authoring

    def save(state: str) -> None:
        app.processEvents()
        editor.tab_relations.grab().save(
            str(Path(__file__).parent / f"{kind}-{width}-{state}.png")
        )

    editor._on_add_relation()
    save("capture")
    panel.cancel()
    panel.refine(
        {
            "id": "relation",
            "source_id": "source",
            "target_id": "target",
            "target_name": target_name,
            "target_kind": "entity",
            "rel_type": "member_of" if kind == "entity" else "involved",
            "attributes": {
                "notes": "Recorded in the charter",
                "confidence": 0.6000000000000001,
            },
        }
    )
    save("refine")
    panel.timing_disclosure.setChecked(True)
    assert panel.form is not None
    panel.form.starts_now_button.click()
    if kind == "event":
        choice = panel.form._boundary_choices["end"]
        choice.setCurrentIndex(choice.findData("source_event"))
    app.processEvents()
    panel.body_scroll.verticalScrollBar().setValue(
        panel.body_scroll.verticalScrollBar().maximum()
    )
    save("timing")
    panel.advanced_disclosure.setChecked(True)
    app.processEvents()
    panel.body_scroll.verticalScrollBar().setValue(
        panel.body_scroll.verticalScrollBar().maximum()
    )
    save("advanced")
    host.close()
    host.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def main() -> None:
    """Isolate settings and use the installed UI font for offscreen rendering."""
    with TemporaryDirectory(prefix="krt22-render-") as settings_dir:
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_dir
        )
        app = QApplication([])
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        ThemeManager().apply_theme(
            app, (REPO / "src/resources/main.qss").read_text(encoding="utf-8")
        )
        for kind in ("entity", "event"):
            for width in (360, 640):
                render(app, kind, width)


if __name__ == "__main__":
    main()
