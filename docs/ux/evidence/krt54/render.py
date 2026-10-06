"""Render KRT-54 authoring presentation with production QSS and isolated settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGridLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from src.core.calendar import (  # noqa: E402
    CalendarConfig,
    CalendarConverter,
    MonthDefinition,
    WeekDefinition,
)
from src.core.entities import Entity  # noqa: E402
from src.core.events import Event  # noqa: E402
from src.core.theme_manager import ThemeManager  # noqa: E402
from src.gui.utils.style_helper import StyleHelper  # noqa: E402
from src.gui.widgets.entity_editor import EntityEditorWidget  # noqa: E402
from src.gui.widgets.event_editor import EventEditorWidget  # noqa: E402

OUTPUT = Path(__file__).parent
RETAINED: list[QWidget] = []
TEXT = (
    "# Tribunal history\n\n"
    "[[id:ent|House Bjornaer]] witnesses [[id:evt|The Charter]]. "
    "The [[Missing treaty]] remains unresolved.\n\n"
    "Typed links identify their destinations; unresolved links have a dotted cue."
)


def render_editor(app: QApplication, kind: str, width: int, theme: str) -> None:
    """Capture both editor routes, visible states and supporting actions."""
    if kind == "entity":
        editor = EntityEditorWidget()
        with patch.object(editor.gallery, "set_owner"):
            editor.load_entity(
                Entity(
                    id="ent", name="House Bjornaer", type="Faction", description=TEXT
                )
            )
        editor.temporal_snapshot_label.setText(
            "Editing the visible state; corrections update the source shown below."
        )
        editor.temporal_snapshot_banner.show()
    else:
        editor = EventEditorWidget()
        editor.set_calendar_converter(
            CalendarConverter(
                CalendarConfig(
                    id="render",
                    name="Render calendar",
                    months=[
                        MonthDefinition(name="Spring", abbreviation="Spr", days=30)
                    ],
                    week=WeekDefinition(day_names=["Day"], day_abbreviations=["D"]),
                    year_variants=[],
                    epoch_name="Era",
                )
            )
        )
        with patch.object(editor.gallery, "set_owner"):
            editor.load_event(
                Event(
                    id="evt",
                    name="The Charter",
                    type="Political",
                    lore_date=1,
                    description=TEXT,
                )
            )
    editor.update_suggestions(
        items=[("ent", "House Bjornaer", "entity"), ("evt", "The Charter", "event")]
    )
    editor.resize(width, 1000)
    editor.show()
    editor.desc_edit.action_return_writing.setText("Back to previous")
    editor.desc_edit.set_return_available(True)
    app.processEvents()
    cursor = editor.desc_edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.desc_edit.setTextCursor(cursor)
    app.processEvents()
    assert editor.width() == width, (theme, kind, editor.width())
    assert editor.grab().save(str(OUTPUT / f"{theme}-{kind}-{width}.png"))
    editor.hide()
    RETAINED.append(editor)


def render_controls(app: QApplication, theme: str) -> None:
    """Show normal, checked, disabled and actual keyboard-focused controls."""
    panel = QWidget()
    panel.setStyleSheet(f"background: {ThemeManager().get_theme()['app_bg']};")
    grid = QGridLayout(panel)
    focus = None
    for row, role in enumerate(("primary", "secondary", "quiet", "destructive")):
        grid.addWidget(QLabel(role.title()), row, 0)
        for column, state in enumerate(
            ("Normal", "Checked", "Disabled", "Interaction"), 1
        ):
            button = QToolButton()
            button.setText(state)
            button.setMinimumSize(120, 36)
            button.setStyleSheet(StyleHelper.get_action_role_style(role))
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if state == "Checked":
                button.setCheckable(True)
                button.setChecked(True)
            button.setEnabled(state != "Disabled")
            grid.addWidget(button, row, column)
            if role == "secondary" and state == "Interaction":
                focus = button
    panel.show()
    panel.activateWindow()
    app.processEvents()
    for button in panel.findChildren(QToolButton):
        button.clearFocus()
    assert focus is not None
    QTest.mouseMove(focus, focus.rect().center())
    app.processEvents()
    assert focus.underMouse()
    assert panel.grab().save(str(OUTPUT / f"{theme}-controls.png"))
    QTest.mousePress(focus, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert focus.isDown()
    assert panel.grab().save(str(OUTPUT / f"{theme}-controls-pressed.png"))
    QTest.mouseRelease(focus, Qt.MouseButton.LeftButton)
    QTest.mouseMove(panel, panel.rect().topLeft())
    focus.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    assert focus.hasFocus()
    assert panel.grab().save(str(OUTPUT / f"{theme}-controls-focus.png"))
    panel.hide()
    RETAINED.append(panel)


def main() -> None:
    """Use disposable settings; never open or mutate a world database."""
    with TemporaryDirectory(prefix="kraken-krt54-render-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        QCoreApplication.setOrganizationName("KrakenRenderEvidence")
        QCoreApplication.setApplicationName("KRT54")
        app = QApplication([])
        for font in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf"):
            path = Path("C:/Windows/Fonts") / font
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        manager = ThemeManager(str(REPO / "themes.json"))
        manager.load_stylesheet(str(REPO / "src/resources/main.qss"))
        for theme in manager.get_available_themes():
            manager.set_theme(theme, app)
            for kind in ("entity", "event"):
                for width in (360, 650):
                    render_editor(app, kind, width, theme)
            render_controls(app, theme)


if __name__ == "__main__":
    main()
