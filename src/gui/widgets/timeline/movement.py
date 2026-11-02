"""Presentation-only timeline drag sessions and explicit mode control."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import replace
from time import perf_counter
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu, QToolButton

from src.core.events import Event
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.menu_caret import PhosphorToolMenuButton
from src.gui.widgets.timeline.drag_outline import PendingDragOutline
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
    """Render pending pointer feedback and incrementally apply calculated snapshots."""

    preview_requested = Signal(dict)
    move_requested = Signal(dict)
    cancelled = Signal()
    started = Signal()

    def __init__(self, view: TimelineView) -> None:
        """Keep scene objects and accepted appearances on their owning thread."""
        super().__init__(view)
        self.view = view
        self.mode = "offset"
        self.session = 0
        self.sequence = 0
        self.applied_sequence = 0
        self.intent: dict[str, Any] | None = None
        self.snapshot: dict[str, Any] = {}
        self.originals: dict[EventItem, tuple[Event, QPointF]] = {}
        self.items: dict[str, list[EventItem]] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self.target_rows: dict[str, dict[str, Any]] = {}
        self._presentation_queue: deque[str] = deque()
        self._queued: set[str] = set()
        self._status_text = "Pending calculation"
        self.presentation_timer = QTimer(self)
        self.presentation_timer.setSingleShot(True)
        self.presentation_timer.setInterval(8)
        self.presentation_timer.timeout.connect(self._drain_rows)
        self.outline: PendingDragOutline | None = None
        self.last_target: float | None = None
        self.initial_target: float | None = None
        self.press_scene_x = 0.0
        connect_theme(self, self._refresh_outline_theme)

    def _refresh_outline_theme(self, theme: dict[str, str]) -> None:
        if self.outline is not None:
            self.outline.refresh_theme(theme)

    def begin(self, identity: str, scene_x: float | None = None) -> None:
        """Capture immutable input once and create one lightweight pending outline."""
        self.cancel()
        context = getattr(self.view, "_temporal_context", None)
        if context is None:
            return
        self.snapshot = {
            "events_json": context.events_json,
            "calendar": context.calendar_json,
        }
        self.intent = {
            "event_id": identity,
            "mode": self.mode,
            "generation": context.resolution.fingerprint,
        }
        for item in [
            *self.view._event_items.values(),
            *self.view._duplicate_event_items,
        ]:
            self.items.setdefault(item.event.id, []).append(item)
        grabber = self.view.graphics_scene.mouseGrabberItem()
        source = (
            grabber
            if isinstance(grabber, EventItem) and grabber.event.id == identity
            else self.view._event_items[identity]
        )
        self.initial_target = source.event.lore_date
        self.press_scene_x = source.x() if scene_x is None else scene_x
        self.outline = PendingDragOutline(source)
        self.outline.setPos(source.pos())
        self.outline.setVisible(False)
        self.view.graphics_scene.addItem(self.outline)
        self.view._dependency_route_timer.stop()
        self.view._dependencies.begin_preview()
        self.started.emit()

    def preview(self, identity: str, target: float) -> None:
        """Give immediate provisional feedback; calculation never owns the pointer."""
        if self.intent is None or self.intent["event_id"] != identity:
            return
        self.last_target = target
        self.sequence += 1
        if self.outline is not None:
            self.outline.setX(target * self.view.scale_factor)
            self.outline.set_status("Pending calculation")
            self.outline.setVisible(True)
        self.view.viewport().update()
        self.preview_requested.emit(
            {
                **self.intent,
                "target": target,
                "session": self.session,
                "sequence": self.sequence,
            }
        )

    def move_pointer(self, scene_x: float) -> None:
        """Translate the pointer directly; Qt's item-move machinery owns no preview."""
        if self.intent is not None and self.initial_target is not None:
            self.preview(
                self.intent["event_id"],
                self.initial_target
                + (scene_x - self.press_scene_x) / self.view.scale_factor,
            )

    def present(self, result: dict[str, Any]) -> None:
        """Accept useful intermediate results without allowing old sessions to repaint."""
        if (
            self.intent is None
            or result["session"] != self.session
            or result.get("generation") != self.intent["generation"]
            or result["sequence"] <= self.applied_sequence
            or result["sequence"] > self.sequence
        ):
            return
        self.applied_sequence = result["sequence"]
        self._status_text = (
            result.get("error")
            or result.get("caption")
            or "Calculated preview; review on release"
        )
        if "error" not in result:
            self._apply_rows(result.get("updated", {}))
        self._update_status()
        self.view.viewport().update()

    def _apply_rows(self, rows: dict[str, dict[str, Any]]) -> None:
        self.target_rows = rows
        changed = {
            key
            for key in self.rows.keys() | rows.keys()
            if self.rows.get(key) != rows.get(key)
        }
        identity = self.intent["event_id"] if self.intent else ""
        for key in sorted(
            changed - self._queued, key=lambda key: (key != identity, key)
        ):
            self._presentation_queue.append(key)
            self._queued.add(key)
        if not self.presentation_timer.isActive():
            self._drain_rows()

    def _drain_rows(self) -> None:
        """Yield after four milliseconds; newer results replace data, not queue order."""
        deadline = perf_counter() + 0.004
        changed = set()
        while self._presentation_queue and perf_counter() < deadline:
            identity = self._presentation_queue.popleft()
            self._queued.remove(identity)
            row = self.target_rows.get(identity)
            if self.rows.get(identity) == row:
                continue
            self._apply_row(identity, row)
            changed.add(identity)
            if row is None:
                self.rows.pop(identity, None)
            else:
                self.rows[identity] = row
        self._refresh_lines(changed)
        if self._presentation_queue:
            self.presentation_timer.start()
        self._update_status()

    def _apply_row(self, identity: str, row: dict[str, Any] | None) -> None:
        for item in self.items.get(identity, []):
            if item not in self.originals:
                self.originals[item] = (item.event, QPointF(item.pos()))
            original, position = self.originals[item]
            event = (
                replace(
                    original,
                    lore_date=row["lore_date"],
                    lore_duration=row["lore_duration"],
                    attributes={**original.attributes, "_temporal_v2": row["temporal"]},
                )
                if row is not None
                else original
            )
            dragging = item._is_dragging
            item._is_dragging = False
            item.set_preview_event(event)
            item.setY(position.y())
            item._is_dragging = dragging
        copies = self.items.get(identity, [])
        if copies:
            self.view._dependencies.update_preview(
                copies[0].event, EventItem._calendar_converter
            )

    def _update_status(self) -> None:
        if self.outline is not None:
            pending = (
                bool(self._presentation_queue) or self.applied_sequence != self.sequence
            )
            self.outline.set_status(
                "Pending calculation" if pending else self._status_text
            )

    def finish(self, identity: str, target: float) -> None:
        """Restore accepted appearances before full-world review and application."""
        intent, requested, initial = (
            deepcopy(self.intent),
            self.last_target,
            self.initial_target,
        )
        self.cancel()
        if intent is not None and requested is not None and requested != initial:
            self.move_requested.emit({**intent, "target": requested})

    def cancel(self) -> None:
        """Remove provisional feedback and restore only appearances actually touched."""
        self.session += 1
        self.cancelled.emit()
        self.presentation_timer.stop()
        self._presentation_queue.clear()
        self._queued.clear()
        changed = set(self.rows)
        for item, (original, position) in self.originals.items():
            item._is_dragging = False
            item.set_preview_event(original)
            item.setPos(position)
            self.view._dependencies.update_preview(
                original, EventItem._calendar_converter
            )
        self.originals.clear()
        self.items.clear()
        self.rows = {}
        self.target_rows = {}
        self.intent = None
        self.last_target = None
        self.applied_sequence = 0
        if self.outline is not None:
            self.view.graphics_scene.removeItem(self.outline)
            self.outline = None
        self.view._dependencies.end_preview()
        self._refresh_lines(changed)
        self.view.viewport().update()

    def _refresh_lines(self, identities: set[str]) -> None:
        """Update guides only for affected events; routing resumes after the session."""
        for identity in identities:
            line, item = (
                self.view._drop_lines.get(identity),
                self.view._event_items.get(identity),
            )
            if line is not None and item is not None:
                line.setLine(item.x(), -self.view.RULER_HEIGHT, item.x(), item.y())
        if self.intent is None and identities:
            self.view._schedule_dependency_routes()
