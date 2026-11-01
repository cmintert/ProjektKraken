"""Native Qt gesture and rendered-state probe for KRT-128 (disposable data)."""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextBrowser

from src.app.coordinators.timeline_movement_coordinator import (
    TimelineMovementCoordinator,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.core.theme_manager import ThemeManager
from src.core.timeline_visibility import DependencyVisibility
from src.gui.widgets.timeline import TimelineWidget


def main() -> None:
    """Use native pointer dispatch, render themes, and leave no world changes."""
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("KrakenTests")
    app.setApplicationName("KRT128Probe")
    output = Path("docs/ux/evidence/krt128")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kraken-krt128-") as settings:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings
        )
        manager = ThemeManager()
        manager.apply_theme(
            app, Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
        root = Event("Source", 10.125, id="root")
        child = Event(
            "Follower",
            0,
            id="child",
            attributes=EventTimingDefinition(
                EndpointDefinition(
                    "event",
                    anchor_id="event:root",
                    offset={"unit": "days", "value": 5.25},
                )
            ).apply({}),
        )
        widget = TimelineWidget()
        widget.resize(1100, 600)
        context = TemporalResolutionContext.build([root, child], None)
        widget.view.set_temporal_context(context)
        widget.view.set_dependency_visibility(DependencyVisibility.ALL)
        submitted = []
        coordinator = TimelineMovementCoordinator(
            widget.view.movement, submitted.append, widget
        )
        widget.show()
        QTest.qWait(150)
        view = widget.view
        view._apply_zoom(1)
        item = view._event_items["child"]
        item.setY(200)
        view.centerOn(item.pos())
        start = view.mapFromScene(item.pos())
        original = item.event.to_dict()
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        end = start + QPoint(60, 0)
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(end),
            QPointF(view.viewport().mapToGlobal(end)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), event)
        deadline = time.monotonic() + 5
        while (
            item.event.lore_date == original["lore_date"]
            and time.monotonic() < deadline
        ):
            QTest.qWait(20)
        assert item.event.lore_date != original["lore_date"]
        assert context.events_json == view._temporal_context.events_json
        widget.grab().save(str(output / "native-preview.png"))
        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
        assert item.event.to_dict() == original
        assert submitted == []
        for theme in manager.themes:
            manager.set_theme(theme, app, persist=False)
            for width in (1100, 360):
                widget.resize(width, 600)
                widget.drag_mode_control.setEnabled(True)
                widget.drag_mode_control.setFocus()
                QTest.qWait(30)
                widget.grab().save(str(output / f"{theme}-{width}.png"))
        widget.resize(1100, 600)
        QTest.qWait(30)
        widget.drag_mode_control.setEnabled(False)
        widget.grab().save(str(output / "disabled-wide.png"))
        widget.resize(360, 600)
        QTest.qWait(30)
        widget.drag_mode_control.setEnabled(False)
        widget.grab().save(str(output / "disabled-narrow.png"))
        widget.drag_mode_control.setEnabled(True)
        widget.action_toolbar.overflow_menu.popup(widget.mapToGlobal(QPoint(50, 50)))
        QTest.qWait(30)
        widget.action_toolbar.overflow_menu.grab().save(
            str(output / "overflow-menu.png")
        )
        widget.action_toolbar.overflow_menu.close()
        help_view = QTextBrowser()
        help_view.resize(680, 600)
        help_view.show()
        url = QUrl.fromLocalFile(
            str(Path("docs/_build/help/timeline-and-calendars.html").resolve())
        )
        url.setFragment("move-an-event-or-its-dependency-chain")
        help_view.setSource(url)
        QTest.qWait(100)
        help_view.grab().save(str(output / "offline-help.png"))
        help_view.close()
        coordinator.shutdown()
        widget.close()
        (output / "native-probe.json").write_text(
            json.dumps(
                {
                    "platform": app.platformName(),
                    "preview": True,
                    "escape_restored": True,
                    "submitted_after_escape": len(submitted),
                    "authored_sources_unchanged": True,
                    "themes": list(manager.themes),
                    "widths": [1100, 360],
                    "evidence": "Automated native Qt widget probe; no full-app or human acceptance claim.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        logging.info("KRT-128 native probe completed: %s", output)


if __name__ == "__main__":
    main()
