"""Session-only return locations for deliberate navigation from writing links."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import QTabWidget, QToolButton, QWidget

from src.gui.widgets.editor_presentation import DisclosureButton


@dataclass
class WritingBookmark:
    """View state only; never an unsaved draft or persistence snapshot."""

    world_id: str
    kind: str
    item_id: str
    mode: str
    anchor: int
    position: int
    text_scroll: int
    inspector_scroll: int
    focused: bool
    disclosures: list[tuple[DisclosureButton, bool]]
    tabs: list[tuple[QTabWidget, QWidget]]


class WikiLinkNavigationController(QObject):
    """Navigate through existing guards and restore the applied origin view."""

    def __init__(
        self,
        editors: dict[str, Any],
        selection: Callable[[], tuple[str | None, str | None]],
        world: Callable[[], str],
        entries: Callable[[], list[tuple[str, str, str]]],
        navigate: Callable[[str, str], None],
        peek: Callable[[str], None],
        feedback: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        """Compose narrow GUI-thread inputs without a window or database service."""
        super().__init__(parent)
        self.editors = editors
        self.selection = selection
        self.world = world
        self.entries = entries
        self.navigate = navigate
        self.peek = peek
        self.feedback = feedback
        self.bookmarks: list[WritingBookmark] = []
        self._pending: tuple[str, str, WritingBookmark, bool] | None = None
        self._restore: WritingBookmark | None = None
        self._peek_origin: WritingBookmark | None = None
        self._world_id = world()
        self._header_buttons: list[QToolButton] = []
        for editor in editors.values():
            action = editor.desc_edit.action_return_writing
            action.triggered.connect(self.return_to_writing)
            button = QToolButton(editor.header_widget)
            button.setDefaultAction(action)
            button.setMinimumHeight(32)
            editor.header_widget.layout().addWidget(button)
            self._header_buttons.append(button)
        self._update_actions()

    def _capture(self) -> WritingBookmark | None:
        kind, item_id = self.selection()
        if kind not in self.editors or item_id is None:
            return None
        editor = self.editors[kind]
        view = editor.desc_edit.editor
        cursor = view.textCursor()
        focus = getattr(editor, "_focus_controller", None)
        return WritingBookmark(
            self.world(),
            kind,
            item_id,
            view._view_mode,
            cursor.anchor(),
            cursor.position(),
            view.verticalScrollBar().value(),
            editor.scroll_area.verticalScrollBar().value(),
            focus is not None and focus.active is editor,
            [
                (button, button.isChecked())
                for button in editor.findChildren(DisclosureButton)
            ],
            [
                (tabs, tabs.currentWidget())
                for tabs in editor.inspector.findChildren(QTabWidget)
                if tabs.currentWidget() is not None
            ],
        )

    def _check_world(self) -> None:
        if self._world_id != self.world():
            self.bookmarks.clear()
            self._pending = None
            self._restore = None
            self._peek_origin = None
            self._world_id = self.world()
            self._update_actions()

    @Slot(str)
    def open_link(self, target: str) -> None:
        """Resolve a stable target, remembering only successfully opened links."""
        self._check_world()
        if self._pending is not None or self._restore is not None:
            return
        id_based = target.casefold().startswith("id:")
        normalized = target[3:] if id_based else target
        matches = [
            (kind, item_id)
            for item_id, name, kind in self.entries()
            if item_id.casefold() == normalized.casefold()
            or (not id_based and name.casefold() == normalized.casefold())
        ]
        if len(matches) != 1:
            self.peek(target)
            return
        kind, item_id = matches[0]
        if (kind, item_id) == self.selection():
            return
        bookmark = self._capture()
        if bookmark is not None:
            if self._peek_origin is not None and (bookmark.kind, bookmark.item_id) == (
                self._peek_origin.kind,
                self._peek_origin.item_id,
            ):
                bookmark.focused = self._peek_origin.focused
            self._pending = (kind, item_id, bookmark, False)
        self.navigate(kind, item_id)

    @Slot()
    def return_to_writing(self) -> None:
        """Return through the same draft guard, without restoring discarded text."""
        self._check_world()
        if not self.bookmarks or self._pending is not None or self._restore is not None:
            return
        bookmark = self.bookmarks[-1]
        if not any(
            item_id == bookmark.item_id and kind == bookmark.kind
            for item_id, _name, kind in self.entries()
        ):
            self.feedback("The writing entry no longer exists.")
            self.bookmarks.pop()
            self._update_actions()
            return
        self._pending = (bookmark.kind, bookmark.item_id, bookmark, True)
        self._update_actions()
        self.navigate(bookmark.kind, bookmark.item_id)

    @Slot(str, str, str)
    def on_navigation_result(self, kind: str, item_id: str, result: str) -> None:
        """Observe navigation outcomes, including saves that finish later."""
        self._check_world()
        pending = self._pending
        if pending is None or pending[:2] != (kind, item_id):
            if result == "selected":
                self.bookmarks.clear()
                self._restore = None
                self._pending = None
                self._peek_origin = None
                self._update_actions()
            return
        if result == "deferred":
            return
        self._pending = None
        if result == "selected":
            self._peek_origin = None
            if pending[3]:
                self._restore = pending[2]
            else:
                self.bookmarks.append(pending[2])
        self._update_actions()

    @Slot()
    def on_peek_started(self) -> None:
        """Remember focus writing before the side-pane presentation exits it."""
        self._check_world()
        self._peek_origin = self._capture()

    @Slot()
    def on_peek_closed(self) -> None:
        """Restore focus presentation without touching the still-live draft."""
        self._check_world()
        bookmark = self._peek_origin
        self._peek_origin = None
        if (
            bookmark is not None
            and bookmark.focused
            and self.selection() == (bookmark.kind, bookmark.item_id)
        ):
            editor = self.editors[bookmark.kind]
            focus = getattr(editor, "_focus_controller", None)
            if focus is not None:
                focus.enter(editor)

    @Slot(str, str)
    def on_editor_hydrated(self, kind: str, item_id: str) -> None:
        """Restore positions only after the matching origin has been applied."""
        self._check_world()
        bookmark = self._restore
        if bookmark is None or (bookmark.kind, bookmark.item_id) != (kind, item_id):
            return
        if self.selection() != (kind, item_id):
            return
        self._restore = None
        editor = self.editors[kind]
        view = editor.desc_edit.editor
        if view._view_mode != bookmark.mode:
            view.toggle_view_mode()
        for button, checked in bookmark.disclosures:
            if shiboken6.isValid(button):
                button.setChecked(checked)
        for tabs, widget in bookmark.tabs:
            if shiboken6.isValid(tabs) and shiboken6.isValid(widget):
                tabs.setCurrentWidget(widget)
        focus = getattr(editor, "_focus_controller", None)
        if bookmark.focused and focus is not None:
            focus.enter(editor)
        cursor = view.textCursor()
        limit = view.document().characterCount() - 1
        cursor.setPosition(min(bookmark.anchor, limit))
        cursor.setPosition(min(bookmark.position, limit), cursor.MoveMode.KeepAnchor)
        view.setTextCursor(cursor)
        view.verticalScrollBar().setValue(bookmark.text_scroll)
        editor.scroll_area.verticalScrollBar().setValue(bookmark.inspector_scroll)
        view.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.bookmarks and self.bookmarks[-1] is bookmark:
            self.bookmarks.pop()
        self._update_actions()

    @Slot(str, str)
    def on_editor_hydration_failed(self, kind: str, item_id: str) -> None:
        """Release return controls if an origin disappears during its load."""
        self._check_world()
        if self._restore is not None and (kind, item_id) == (
            self._restore.kind,
            self._restore.item_id,
        ):
            if self.bookmarks and self.bookmarks[-1] is self._restore:
                self.bookmarks.pop()
            self._restore = None
            self.feedback("The writing entry is no longer available.")
            self._update_actions()

    def _update_actions(self) -> None:
        available = bool(self.bookmarks)
        enabled = self._pending is None and self._restore is None
        for editor in self.editors.values():
            editor.desc_edit.set_return_available(available)
            editor.desc_edit.action_return_writing.setEnabled(enabled)
        for button in self._header_buttons:
            button.setVisible(available)
