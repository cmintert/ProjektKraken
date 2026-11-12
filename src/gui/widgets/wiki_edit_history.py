"""Retain native Qt edit commands while descriptions change presentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSignalBlocker
from PySide6.QtGui import QTextCursor, QTextDocument

if TYPE_CHECKING:
    from src.gui.widgets.wiki_text_edit import WikiTextEditView


class WikiEditHistory(QObject):
    """Order native undo groups across the documents used by Rich/Source views.

    View conversions create a fresh projection. Each user edit keeps its owning
    document alive, so undo can return to that representation before applying
    Qt's original command. A new edit truncates the shared redo branch.
    """

    def __init__(self, view: WikiTextEditView) -> None:
        """Attach native history ownership to one description editor."""
        super().__init__(view)
        self.view = view
        self.suspended = False
        self._entries: list[tuple[QTextDocument, str]] = []
        self._position = 0
        self._documents: set[QTextDocument] = set()
        self.watch(view.document())

    def watch(self, document: QTextDocument) -> None:
        """Own a projection independently of QTextEdit's active document."""
        document.setParent(self)
        self._documents.add(document)
        document.undoCommandAdded.connect(lambda: self._added(document))

    def _added(self, document: QTextDocument) -> None:
        if self.suspended:
            return
        del self._entries[self._position :]
        self._entries.append((document, self.view._view_mode))
        self._position = len(self._entries)

    def reset(self) -> None:
        """Start a baseline after loading a different description."""
        self._entries.clear()
        self._position = 0
        self.view.document().clearUndoRedoStacks()
        self.prune()

    def prune(self) -> None:
        """Release projections that own neither visible state nor edit history."""
        retained = {document for document, _ in self._entries}
        retained.add(self.view.document())
        for document in self._documents - retained:
            document.deleteLater()
        self._documents.intersection_update(retained)

    def can_undo(self) -> bool:
        """Whether the description has a preceding user edit."""
        return self._position > 0

    def can_redo(self) -> bool:
        """Whether a reverted user edit can be restored."""
        return self._position < len(self._entries)

    def move(self, *, redo: bool) -> None:
        """Apply one user operation in its original representation."""
        if self.view.isReadOnly():
            return
        if not (self.can_redo() if redo else self.can_undo()):
            return
        index = self._position if redo else self._position - 1
        document, mode = self._entries[index]
        self.suspended = True
        try:
            with QSignalBlocker(self.view):
                self.view._adopt_document(document, mode)
                cursor = QTextCursor(document)
                if redo:
                    document.redo(cursor)
                else:
                    document.undo(cursor)
                self.view.setTextCursor(cursor)
                self._position += 1 if redo else -1
        finally:
            self.suspended = False
        self.view._update_link_colors()
        self.view.view_mode_changed.emit(mode)
        self.view.textChanged.emit()
        self.prune()
