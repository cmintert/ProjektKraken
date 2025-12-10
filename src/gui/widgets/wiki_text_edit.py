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
        self._completion_map = {}  # Maps display names to IDs
        self._link_resolver = None  # Will be set later

        # Enable mouse tracking for hover effects if desired
        self.setMouseTracking(True)

    def set_link_resolver(self, link_resolver):
        """
        Sets the link resolver for checking broken links.
        
        Args:
            link_resolver: LinkResolver instance for ID resolution and broken link detection.
        """
        self._link_resolver = link_resolver
        self.highlighter.set_link_resolver(link_resolver)

    def set_completer(
        self, items_or_names=None, *, items: list[tuple[str, str, str]] = None, names: list[str] = None
    ):
        """
        Initializes or updates the completer with items.

        Can be called with either:
        - Positional list of names for legacy compatibility: set_completer(["Name1", "Name2"])
        - items keyword arg: List of (id, name, type) tuples for ID-based completion
        - names keyword arg: List of names for legacy name-based completion

        Args:
            items_or_names: Legacy positional parameter (list of names).
            items: List of (id, name, type) tuples for entities/events.
            names: Legacy list of names (for backward compatibility).
        """
        # Handle legacy positional argument
        if items_or_names is not None:
            if isinstance(items_or_names, list) and items_or_names:
                # Check if it's a list of tuples (new format) or strings (legacy)
                if isinstance(items_or_names[0], tuple):
                    items = items_or_names
                else:
                    names = items_or_names
        
        if items is not None:
            # Build completion map: name -> (id, type)
            self._completion_map = {name: (item_id, item_type) for item_id, name, item_type in items}
            display_names = [name for _, name, _ in items]
        elif names is not None:
            # Legacy mode - no ID mapping
            self._completion_map = {}
            display_names = names
        else:
            return

        if self._completer is None:
            self._completer = QCompleter(display_names, self)
            self._completer.setWidget(self)
            self._completer.setCompletionMode(QCompleter.PopupCompletion)
            self._completer.setCaseSensitivity(Qt.CaseInsensitive)
            self._completer.activated.connect(self.insert_completion)
        else:
            model = QStringListModel(display_names, self._completer)
            self._completer.setModel(model)

    def insert_completion(self, completion: str):
        """
        Inserts the selected completion into the text as an ID-based link.

        If ID mapping is available, inserts [[id:UUID|Name]], otherwise [[Name]].
        """
        tc = self.textCursor()
        
        # Remove the partial text typed after "[["
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])

        # If we have ID mapping, insert ID-based link
        if completion in self._completion_map:
            item_id, item_type = self._completion_map[completion]
            # Move cursor back to replace the name with ID-based format
            # Select the just-inserted completion
            tc.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveOperation.MoveAnchor, len(completion[-extra:]))
            tc.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveOperation.KeepAnchor, len(completion[-extra:]))
            # Replace with ID-based format
            tc.insertText(f"id:{item_id}|{completion}")

        # Append "]]" to close the link
        tc.insertText("]]")

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
        Returns the link target (ID or name) at the given pixel position, or None.

        For ID-based links, returns the UUID.
        For name-based links, returns the name.
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

                # Check if this is ID-based: id:UUID or id:UUID|Label
                if full_match.startswith("id:"):
                    # Extract the ID part
                    if "|" in full_match:
                        id_part = full_match.split("|", 1)[0]
                        return id_part[3:]  # Remove "id:" prefix, return UUID
                    else:
                        return full_match[3:]  # Remove "id:" prefix, return UUID

                # Legacy name-based link
                # Handle [[Target|Label]] -> return Target
                if "|" in full_match:
                    return full_match.split("|", 1)[0].strip()
                return full_match.strip()

        return None
