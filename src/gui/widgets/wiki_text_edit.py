"""
Wiki Text Edit Widget.
A specialized QTextEdit that supports WikiLink navigation via Ctrl+Click.
"""

import re
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QMouseEvent, QTextCursor

from src.gui.utils.wiki_highlighter import WikiSyntaxHighlighter


class WikiTextEdit(QTextEdit):
    """
    Text Editor with WikiLink support.
    - Highlights [[Links]]
    - Emits 'link_clicked' on Ctrl+Click
    """

    link_clicked = Signal(str)  # Emits the target name (e.g. "Gandalf")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighter = WikiSyntaxHighlighter(self.document())
        self._hovered_link = None

        # Enable mouse tracking for hover effects if desired
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        updates cursor shape when hovering over a link with Ctrl pressed.
        """
        # Logic to check if under mouse is a link
        # This is complex to do perfectly map pixel -> char.
        # Simple version: rely on click.
        # Enhanced version: changing cursor.

        # For now, standard behavior.
        super().mouseMoveEvent(event)

        if event.modifiers() & Qt.ControlModifier:
            link = self.get_link_at_pos(event.pos())
            if link:
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.IBeamCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Handles click events to trigger navigation.
        """
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
