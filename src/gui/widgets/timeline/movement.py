"""Presentation-only timeline drag sessions and explicit mode control."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu, QToolButton, QToolTip

from src.core.events import Event
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.menu_caret import PhosphorToolMenuButton
from src.gui.widgets.timeline.event_item import EventItem

if TYPE_CHECKING:
    from src.gui.widgets.timeline.timeline_view import TimelineView

_HELP = "timeline.drag-mode-options|timeline.viewing|help-inspect-timeline-drag-mode"


class DragModeButton(PhosphorToolMenuButton):
    """Expose movement intent through ordinary and overflow menu routes."""

    mode_changed = Signal(str)

    def __init__(self, parent: Any = None) -> None:
        """Start each application session in Adjust offset mode."""
        super().__init__(parent)
        self.mode = "offset"
        self.labels = {"offset": "Adjust offset", "chain": "Move chain"}
        self.mode_menu = declare_inspection(QMenu(self), _HELP)
        self.mode_group = QActionGroup(self)
        self.actions_by_mode = {}
        for mode, label in self.labels.items():
            action = declare_inspection(self.mode_menu.addAction(label), _HELP)
            action.setData(mode)
            action.setCheckable(True)
            self.mode_group.addAction(action)
            self.actions_by_mode[mode] = action
        self.mode_group.triggered.connect(
            lambda action: self.set_mode(str(action.data()))
        )
        self.setMenu(self.mode_menu)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.set_mode("offset")
        self._apply_theme()
        connect_theme(self, self._apply_theme)

    def set_mode(self, mode: str) -> None:
        """Render and publish the explicit choice."""
        self.mode = mode
        self.actions_by_mode[mode].setChecked(True)
        label = f"Drag: {self.labels[mode]}"
        self.setText(label)
        self.setAccessibleName(label)
        self.setProperty("toolbarActionLabel", label)
        self.setToolTip(
            "Adjust offset keeps the source fixed. Move chain shifts connected "
            "Events while retaining their offsets. Authored precision and calendar "
            "units are preserved; unsupported moves are rejected."
        )
        self.mode_changed.emit(mode)

    def _apply_theme(self, _theme: dict | None = None) -> None:
        self.setStyleSheet(
            StyleHelper.get_tool_button_style() + StyleHelper.get_menu_caret_style()
        )


class TimelineMovementPresenter(QObject):
    """Render detached calculation results without authoring or mutating events."""

    preview_requested = Signal(dict)
    move_requested = Signal(dict)
    cancelled = Signal()
    started = Signal()

    def __init__(self, view: TimelineView) -> None:
        """Keep scene ownership on the GUI thread."""
        super().__init__(view)
        self.view = view
        self.mode = "offset"
        self.session = 0
        self.sequence = 0
        self.intent: dict[str, Any] | None = None
        self.snapshot: dict[str, Any] = {}
        self.originals: list[tuple[EventItem, Event, QPointF]] = []
        self.last_target: float | None = None

    def begin(self, identity: str) -> None:
        """Capture source data and all visible copies before Qt moves anything."""
        self.cancel()
        context = getattr(self.view, "_temporal_context", None)
        if context is None:
            return
        self.snapshot = {
            "world_id": "preview",
            "events": json.loads(context.events_json),
            "calendar": context.calendar_json,
            "consumers": [],
        }
        self.intent = {
            "event_id": identity,
            "mode": self.mode,
            "generation": context.resolution.fingerprint,
        }
        self.originals = [
            (item, item.event, QPointF(item.pos()))
            for item in [
                *self.view._event_items.values(),
                *self.view._duplicate_event_items,
            ]
        ]
        self.started.emit()

    def preview(self, identity: str, target: float) -> None:
        """Ask the application for a cancellable detached calculation."""
        if self.intent is None or self.intent["event_id"] != identity:
            return
        self.last_target = target
        self.sequence += 1
        self.preview_requested.emit(
            {
                "session": self.session,
                "sequence": self.sequence,
                "snapshot": self.snapshot,
                "intent": {**self.intent, "target": target},
            }
        )

    def present(self, result: dict[str, Any]) -> None:
        """Ignore obsolete results and paint only calculated candidate snapshots."""
        if (
            self.intent is None
            or result["session"] != self.session
            or result["sequence"] != self.sequence
        ):
            return
        rows = result.get("updated", {})
        for item, original, position in self.originals:
            item._is_dragging = False
            item.update_event(
                Event.from_dict(rows[original.id]) if original.id in rows else original
            )
            item.setY(position.y())
        # Qt still owns the mouse grab; programmatic preview positions never author.
        grabber = self.view.graphics_scene.mouseGrabberItem()
        if grabber is not None and hasattr(grabber, "_is_dragging"):
            grabber._is_dragging = True
        self.view._dependencies.set_display_events(
            [
                Event.from_dict(rows[event.id]) if event.id in rows else event
                for event in self.view.events
            ],
            EventItem._calendar_converter,
        )
        self._refresh_lines()
        self.view.viewport().update()
        message = result.get("error", "") or result.get("caption", "")
        if message:
            QToolTip.showText(
                self.view.mapToGlobal(self.view.rect().center()), message, self.view
            )

    def finish(self, identity: str, target: float) -> None:
        """Restore the scene before submitting one explicit reviewed movement."""
        intent = deepcopy(self.intent)
        requested = self.last_target
        original = next(
            (event for _item, event, _pos in self.originals if event.id == identity),
            None,
        )
        self.cancel()
        if (
            intent is not None
            and requested is not None
            and original is not None
            and requested != original.lore_date
        ):
            self.move_requested.emit({**intent, "target": requested})

    def cancel(self) -> None:
        """Restore every appearance without touching shared authored records."""
        self.session += 1
        self.cancelled.emit()
        for item, original, position in self.originals:
            item._is_dragging = False
            item.update_event(original)
            item.setPos(position)
        had_preview = bool(self.originals)
        self.originals = []
        self.intent = None
        self.last_target = None
        if had_preview:
            self.view._dependencies.set_display_events(
                self.view.events, EventItem._calendar_converter
            )
            self._refresh_lines()
        QToolTip.hideText()
        self.view.viewport().update()

    def _refresh_lines(self) -> None:
        """Keep date guides and dependency routes aligned with preview positions."""
        for identity, line in self.view._drop_lines.items():
            item = self.view._event_items.get(identity)
            if item is not None:
                line.setLine(item.x(), -self.view.RULER_HEIGHT, item.x(), item.y())
        self.view._schedule_dependency_routes()
