"""Capture isolated, production-styled inspector components for UX review.

Run with QT_QPA_PLATFORM=offscreen. These captures do not measure human task
performance or verify the database/save path. Settings and gallery requests are
isolated from personal worlds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import tempfile
from pathlib import Path

from PySide6 import __version__ as qt_binding_version
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QSettings,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QWidget

from src.core.authoring_context import (
    ContextAttachment,
    ContextAttribute,
    ContextItem,
    EntityAuthoringContext,
    EventAuthoringContext,
)
from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.entities import Entity
from src.core.events import Event
from src.core.summary_data import SummaryData
from src.core.theme_manager import ThemeManager
from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget

Editor = EntityEditorWidget | EventEditorWidget


class _EvidenceWorker(QObject):
    """Empty gallery snapshot provider; never opens storage."""

    attachments_loaded = Signal(str, str, list)
    command_finished = Signal(object)

    @Slot(str, str)
    def load_attachments(self, owner_type: str, owner_id: str) -> None:
        self.attachments_loaded.emit(owner_type, owner_id, [])


class _EvidenceHost(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.worker = _EvidenceWorker(self)


def _settle(app: QApplication) -> None:
    for _ in range(8):
        app.processEvents()


def _make_editor(kind: str, parent: _EvidenceHost) -> Editor:
    description = "Tasgillia studies the history of the Rhine."
    attributes = {"rank": "Scholar", "strength": 12, "active": True}
    if kind == "entity":
        editor = EntityEditorWidget(parent)
        editor.load_entity(
            Entity(
                id="evidence-person",
                name="Tasgillia",
                type="Character",
                description=description,
                attributes=attributes,
            )
        )
        editor.display_temporal_state(
            "evidence-person",
            {
                "description": description,
                "attributes": attributes,
                "description_source": {"kind": "baseline"},
                "attribute_sources": {},
            },
            0.0,
        )
        return editor
    editor = EventEditorWidget(parent)
    calendar = CalendarConfig.create_default()
    calendar.id = "evidence-calendar"
    editor.set_calendar_converter(CalendarConverter(calendar))
    editor.load_event(
        Event(
            id="evidence-charter",
            name="Benchmark Charter 1218",
            description=description,
            lore_date=0.0,
            attributes=attributes,
        )
    )
    editor.date_edit.txt_date.setText("c. 1218")
    editor.date_edit._on_draft_edited("c. 1218")
    editor.date_edit.commit_draft()
    editor.set_dirty(False)
    editor.autosave_manager.stop_timer()
    return editor


def _prepare_state(editor: Editor, app: QApplication, state: str, width: int) -> None:
    """Select one explicit review scenario without altering authored values."""
    if state == "advanced" and isinstance(editor, EventEditorWidget):
        editor.date_edit.date_fields_button.setChecked(True)
    if state == "short":
        editor.resize(width, 480)
    if state in ("connections", "media", "details"):
        editor.resize(width, 720)
        editor.inspector.activate_section_id(state)
    if state == "sheet":
        editor._presentation.composition.details_views.setCurrentIndex(1)
    if state == "sheet_split":
        editor.inspector.open_auxiliary_below("sheet")
    if state == "context_embedded":
        editor.inspector.return_auxiliary("sheet")
        editor.inspector.activate_section_id("world_context")
    if state == "context_split":
        editor.inspector.activate_section_id("overview")
        editor.inspector.open_auxiliary_below("world_context")
    if state == "support":
        editor.inspector.return_auxiliary("world_context")
        editor._presentation.context_disclosure.setChecked(False)
    if state in ("summary", "ai_draft", "writing_panels"):
        editor.summary_checkbox.setChecked(state != "ai_draft")
        editor.llm_checkbox.setChecked(state != "summary")
        _settle(app)
        editor.scroll_area.ensureWidgetVisible(editor._presentation.writing_actions)
    if state in ("information", "information_more"):
        editor.summary_checkbox.setChecked(False)
        editor.llm_checkbox.setChecked(False)
        editor._presentation.history_disclosure.setChecked(True)
        editor.authoring_context.more_button.setChecked(state == "information_more")
        _settle(app)
        editor.scroll_area.verticalScrollBar().setValue(
            editor._presentation.history_disclosure.mapTo(
                editor.details_container, QPoint()
            ).y()
        )
    if state == "refinement_short":
        editor.summary_checkbox.setChecked(False)
        editor.llm_checkbox.setChecked(False)
        editor._presentation.history_disclosure.setChecked(False)
        editor.resize(width, 480)
    if state == "empty_summary":
        editor._presentation.history_disclosure.setChecked(False)
        editor.summary_widget.clear_summary()
        editor.summary_checkbox.setChecked(True)
        _settle(app)
        editor.scroll_area.ensureWidgetVisible(editor.summary_container)
    if state in ("context_embedded", "support", "refinement_short"):
        _settle(app)
        editor.scroll_area.verticalScrollBar().setValue(
            editor.scroll_area.verticalScrollBar().maximum()
        )
    _settle(app)


def capture(output: Path) -> None:
    """Render both themes and width states without connecting a database."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-inspector-settings-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        app = QApplication.instance() or QApplication([])
        assert isinstance(app, QApplication)
        QCoreApplication.setOrganizationName("KrakenInspectorEvidence")
        QCoreApplication.setApplicationName("KRT45")
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI", 10))
        manager = ThemeManager()
        manager.apply_theme(app, Path("src/resources/main.qss").read_text("utf-8"))
        records = []
        for theme in ("dark_mode", "light_mode"):
            manager.set_theme(theme, app)
            for kind in ("entity", "event"):
                for width in (331, 560, 871):
                    parent = _EvidenceHost()
                    editor = _make_editor(kind, parent)
                    editor.summary_widget.set_summary(
                        SummaryData(
                            text="Tasgillia studies Rhine history.",
                            hash="render-fixture",
                            timestamp=0,
                            model="render-fixture",
                        )
                    )
                    if isinstance(editor, EntityEditorWidget):
                        editor.authoring_context.set_entity_context(
                            EntityAuthoringContext(
                                entity_id="evidence-person",
                                attributes=(ContextAttribute("rank", "Scholar"),),
                                attachments=(
                                    ContextAttachment(
                                        "evidence-attachment", "Portrait"
                                    ),
                                ),
                                omitted_counts=(("relations", 4),),
                            )
                        )
                    else:
                        editor.authoring_context.set_context(
                            EventAuthoringContext(
                                event_id="evidence-charter",
                                context_date=editor.temporal_widget.get_start(),
                                participants=(
                                    ContextItem(
                                        "evidence-person", "entity", "Tasgillia"
                                    ),
                                ),
                                locations=(
                                    ContextItem(
                                        "evidence-region", "entity", "Upper Rhine"
                                    ),
                                ),
                                omitted_counts=(("relations", 4),),
                            ),
                            date_label="c. 1218",
                        )
                    editor.set_dirty(False)
                    editor.autosave_manager.stop_timer()
                    editor.setWindowFlag(Qt.WindowType.Window, True)
                    editor.resize(width, 720)
                    editor.show()
                    _settle(app)
                    states = ["overview", "advanced", "short"]
                    if hasattr(editor.inspector, "activate_section_id"):
                        states.extend(
                            [
                                "connections",
                                "media",
                                "details",
                                "sheet",
                                "sheet_split",
                                "context_embedded",
                                "context_split",
                                "support",
                                "summary",
                                "ai_draft",
                                "writing_panels",
                                "information",
                                "information_more",
                                "empty_summary",
                                "refinement_short",
                                "more",
                            ]
                        )
                    for state in states:
                        _prepare_state(editor, app, state, width)
                        if state == "more":
                            tabs = editor.inspector.main_tabs
                            tabs._populate_overflow()
                            name = f"{kind}-{theme}-{width}-more-menu.png"
                            assert tabs.overflow_menu.grab().save(str(output / name))
                        _settle(app)
                        name = f"{kind}-{theme}-{width}-{state}.png"
                        assert editor.grab().save(str(output / name))
                        records.append(
                            {
                                "image": name,
                                "width": editor.width(),
                                "height": editor.height(),
                                "state": state,
                                "horizontal_scroll": editor.scroll_area.horizontalScrollBar().maximum(),
                                "visible_horizontal_scrollbars": [
                                    {
                                        "widget": type(area).__name__,
                                        "maximum": area.horizontalScrollBar().maximum(),
                                    }
                                    for area in editor.findChildren(QAbstractScrollArea)
                                    if area.isVisibleTo(editor)
                                    and area.horizontalScrollBar().maximum() > 0
                                ],
                            }
                        )
                    editor.close()
                    editor.deleteLater()
                    parent.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    _settle(app)
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        (output / "captures.json").write_text(
            json.dumps(
                {
                    "base_revision": revision,
                    "source_sha256": {
                        str(path).replace("\\", "/"): hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest()
                        for path in sorted(
                            list(Path("src/gui/widgets").glob("*.py"))
                            + [
                                Path("src/gui/utils/style_helper.py"),
                                Path("src/resources/main.qss"),
                                Path("themes.json"),
                                Path(__file__).relative_to(Path.cwd()),
                            ]
                        )
                    },
                    "python": platform.python_version(),
                    "qt_binding": qt_binding_version,
                    "platform": platform.platform(),
                    "method": "isolated component rendering; no database or human metrics",
                    "captures": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def main() -> None:
    """Read the output directory and capture the inspector matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)


if __name__ == "__main__":
    main()
