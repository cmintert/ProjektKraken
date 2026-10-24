"""Explicit source edits and completion-safe focus traversal for writing views."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from src.gui.utils.help_context import declare_inspection

if TYPE_CHECKING:
    from src.gui.widgets.wiki_text_edit import WikiTextEditView


class WritingKeyboardController(QObject):
    """Keep plain Tab non-mutating, including QCompleter's popup event filter."""

    def __init__(self, view: WikiTextEditView) -> None:
        """Keep navigation separate from text-editing behavior."""
        super().__init__(view)
        self.view = view
        view.setTabChangesFocus(True)

    def watch_completion(self) -> None:
        """Install after QCompleter so it cannot accept a navigation key first."""
        self.view.installEventFilter(self)
        if self.view._completer is not None and (popup := self.view._completer.popup()):
            popup.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Dismiss suggestions before redelivering a navigation key."""
        if not isinstance(event, QKeyEvent) or event.type() != QEvent.Type.KeyPress:
            return False
        if event.key() not in (
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            return False
        completer = self.view._completer
        popup = completer.popup() if completer is not None else None
        if popup is None or not popup.isVisible():
            return False
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = popup.currentIndex()
            if index.isValid():
                self.view.insert_completion_index(index)
                popup.hide()
                return True
            return False
        popup.hide()
        # Redeliver after closing the popup: the window's local traversal policy
        # can now handle this event, and isolated/dialog views retain native focus.
        QApplication.sendEvent(
            self.view,
            QKeyEvent(event.type(), event.key(), event.modifiers()),
        )
        return True


class SourceEditingActions(QObject):
    """Undoable source indentation, exposed through existing writing menus."""

    def __init__(self, view: WikiTextEditView) -> None:
        """Create the three discoverable source-editing operations."""
        super().__init__(view)
        self.view = view
        self.indent = self._action("Indent", lambda: self._indent(False))
        self.outdent = self._action("Outdent", lambda: self._indent(True))
        self.insert_tab = self._action("Tab character", self._insert_tab)

    def _action(self, title: str, callback: Callable[[], None]) -> QAction:
        action = declare_inspection(
            QAction(title, self),
            "writing.source-edit|writing.edit|help-inspect-writing-source-edit",
        )
        action.triggered.connect(callback)
        return action

    def refresh(self) -> None:
        """Read current mode and permissions when opening a menu."""
        enabled = self.view._view_mode == "source" and not self.view.isReadOnly()
        for action in (self.indent, self.outdent, self.insert_tab):
            action.setEnabled(enabled)
            action.setToolTip("Edit indentation in editable Markdown source")

    def _editable(self) -> bool:
        return self.view._view_mode == "source" and not self.view.isReadOnly()

    def _insert_tab(self) -> None:
        if not self._editable():
            return
        cursor = self.view.textCursor()
        cursor.beginEditBlock()
        cursor.insertText("\t")
        cursor.endEditBlock()
        self.view.setTextCursor(cursor)
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _indent(self, outdent: bool) -> None:
        if not self._editable():
            return
        cursor = self.view.textCursor()
        anchor, position = cursor.anchor(), cursor.position()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        document = self.view.document()
        block = document.findBlock(start)
        edits: list[tuple[int, int, str]] = []
        while block.isValid() and (block.position() < end or block.contains(start)):
            text = block.text()
            remove = (
                (
                    1
                    if text.startswith("\t")
                    else min(4, len(text) - len(text.lstrip(" ")))
                )
                if outdent
                else 0
            )
            if not outdent or remove:
                edits.append((block.position(), remove, "" if outdent else "    "))
            block = block.next()
        if not edits:
            self.view.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        scroll = self.view.verticalScrollBar().value()
        cursor.beginEditBlock()
        for offset, remove, replacement in reversed(edits):
            cursor.setPosition(offset)
            cursor.setPosition(offset + remove, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(replacement)
        cursor.endEditBlock()

        def adjusted(original: int) -> int:
            delta = 0
            for offset, remove, replacement in edits:
                if original >= offset:
                    delta += len(replacement) - min(remove, original - offset)
            return original + delta

        cursor.setPosition(adjusted(anchor))
        cursor.setPosition(adjusted(position), QTextCursor.MoveMode.KeepAnchor)
        self.view.setTextCursor(cursor)
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self.view.verticalScrollBar().setValue(scroll)
