"""
Wiki Text Edit Widget.
A specialized QTextEdit that supports WikiLink navigation via Ctrl+Click.
"""

import re
from PySide6.QtWidgets import QTextEdit, QCompleter
from PySide6.QtCore import Signal, Qt, QStringListModel
from PySide6.QtGui import QTextCursor

from src.gui.utils.wiki_highlighter import WikiSyntaxHighlighter


class WikiTextEdit(QTextEdit):
    """
    Text Editor with WikiLink support.
    - Highlights [[Links]]
    - Emits 'link_clicked' on Ctrl+Click
    - Supports Autocompletion for [[Links]]
    """

    link_clicked = Signal(str)  # Emits the target name (e.g. "Gandalf")

    def __init__(self, parent=None):
        """
        Initializes the WikiTextEdit.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.highlighter = WikiSyntaxHighlighter(self.document())
        self._hovered_link = None
        self._completer = None

        # Enable mouse tracking for hover effects if desired
        self.setMouseTracking(True)

    def set_completer(self, names: list[str]):
        """
        Initializes or updates the completer with a list of names.

        Args:
            names (list[str]): List of potential targets (Event/Entity names).
        """
        if self._completer is None:
            self._completer = QCompleter(names, self)
            self._completer.setWidget(self)
            self._completer.setCompletionMode(QCompleter.PopupCompletion)
            self._completer.setCaseSensitivity(Qt.CaseInsensitive)
            self._completer.activated.connect(self.insert_completion)
        else:
            model = QStringListModel(names, self._completer)
            self._completer.setModel(model)

    def insert_completion(self, completion: str):
        """
        Inserts the selected completion into the text.
        """
        tc = self.textCursor()
        # We want to replace the text from "[[..." to current position
        # Find the start of the token
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])

        # Append "]]" to close the link
        tc.insertText("]]")

        # Close the link bracket automatically? Maybe.
        # Let's just complete the name for now.
        # User might want to type "|Alias]]"

        # If the user just typed "[[Nam", we want "[[Name"
        # The completer prefix handles the "Nam" part.

        self.setTextCursor(tc)

    def text_under_cursor(self):
        """Returns the word under cursor (or partial word)."""
        tc = self.textCursor()
        tc.select(tc.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, event):
        """
        Handles key presses to trigger or navigate the completer.
        """
        if self._completer and self._completer.popup().isVisible():
            # Let the completer handle navigation keys
            if event.key() in (
                Qt.Key_Enter,
                Qt.Key_Return,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Backtab,
            ):
                event.ignore()
                return

        super().keyPressEvent(event)

        # Logic to trigger completer
        # Check if we are inside a [[... sequence
        # This is a bit complex. Simple heuristic:
        # Check text to the left of cursor.
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()

        # Look backwards from pos_in_block for "[["
        # And ensure no "]]" in between
        text_before = block_text[:pos_in_block]

        # Find last "[["
        last_open_idx = text_before.rfind("[[")
        last_close_idx = text_before.rfind("]]")

        if last_open_idx != -1 and last_open_idx > last_close_idx:
            # We are inside a link
            # Get the text after "[["
            prefix = text_before[last_open_idx + 2 :]

            # If prefix contains "|", we might need to stop completing or handle alias?
            # For now, simplistic: if no "|", complete the name.
            if "|" not in prefix and self._completer:
                self._completer.setCompletionPrefix(prefix)

                curr_rect = self.cursorRect()
                curr_rect.setWidth(
                    self._completer.popup().sizeHintForColumn(0)
                    + self._completer.popup().verticalScrollBar().sizeHint().width()
                )
                self._completer.complete(curr_rect)
        elif self._completer:
            self._completer.popup().hide()

    def mouseMoveEvent(self, event):
        """updates cursor shape when hovering over a link with Ctrl pressed."""
        super().mouseMoveEvent(event)

        if event.modifiers() & Qt.ControlModifier:
            link = self.get_link_at_pos(event.pos())
            if link:
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.IBeamCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)

    def mouseReleaseEvent(self, event):
        """Handles click events to trigger navigation."""
        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            link = self.get_link_at_pos(event.pos())
            if link:
                self.link_clicked.emit(link)
                return

        super().mouseReleaseEvent(event)

    def get_link_at_pos(self, pos) -> str:
        """
        Returns the link text at the given pixel position, or None.
        """
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        text = block.text()
        pos_in_block = cursor.positionInBlock()

        # Iterate matches in this block to see if cursor is inside one
        # Using the same regex as highlighter
        pattern = re.compile(r"\[\[(.*?)\]\]")

        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()

            if start <= pos_in_block <= end:
                # Extracted content
                full_match = match.group(1)
                # Handle [[Target|Label]] -> return Target
                if "|" in full_match:
                    return full_match.split("|", 1)[0].strip()
                return full_match.strip()

        return None
