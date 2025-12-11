"""
Wiki Text Edit Widget.
A specialized QTextEdit that supports WikiLink navigation via Ctrl+Click.
"""

import re
from PySide6.QtWidgets import QTextEdit, QCompleter
from PySide6.QtCore import Signal, Qt, QStringListModel
from PySide6.QtGui import QTextCursor


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
            link_resolver: LinkResolver instance for ID resolution and
                broken link detection.
        """
        self._link_resolver = link_resolver
        # Highlight Logic could be added here later
        # (iterating formats to color broken links)

    def set_completer(
        self,
        items_or_names=None,
        *,
        items: list[tuple[str, str, str]] = None,
        names: list[str] = None,
    ):
        """
        Initializes or updates the completer with items.

        Can be called with either:
        - Positional list of names for legacy compatibility:
          set_completer(["Name1", "Name2"])
        - items keyword arg: List of (id, name, type) tuples for
          ID-based completion
        - names keyword arg: List of names for legacy name-based
          completion

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
            self._completion_map = {
                name: (item_id, item_type) for item_id, name, item_type in items
            }
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

    def set_wiki_text(self, text: str):
        """
        Sets the content using WikiLink syntax, converting it to HTML anchors.
        """
        # Regex to find [[target|label]] or [[target]]
        import html

        pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")

        def replace_link(match):
            """
            Converts a WikiLink match to an HTML anchor tag.

            Args:
                match: Regex match object containing target and optional label.

            Returns:
                str: HTML anchor tag string.
            """
            target = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else target
            # Use data-target attribute safely if needed, but href is standard
            return f'<a href="{target}">{label}</a>'

        safe_text = html.escape(text)
        html_content = pattern.sub(replace_link, safe_text)
        html_content = html_content.replace("\n", "<br>")
        self.setHtml(html_content)

    def get_wiki_text(self) -> str:
        """
        Converts the editor content (HTML) back to WikiLink syntax.
        """
        result = []
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                text = fragment.text()
                fmt = fragment.charFormat()

                if fmt.isAnchor():
                    href = fmt.anchorHref()
                    if href == text:
                        result.append(f"[[{text}]]")
                    elif href.startswith("id:") and text:
                        result.append(f"[[{href}|{text}]]")
                    else:
                        # Fallback
                        result.append(f"[[{href}|{text}]]")
                else:
                    result.append(text)

                iterator += 1

            if block.next().isValid():
                result.append("\n")
            block = block.next()

        return "".join(result)

    def insert_completion(self, completion: str):
        """
        Inserts the selected completion as an HTML anchor.
        """
        tc = self.textCursor()
        prefix_len = len(self._completer.completionPrefix())

        # We need to remove the "[[" that triggered this + prefix
        # We assume cursor is after "[[Prefix"
        # Move left prefix_len
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, prefix_len)
        tc.removeSelectedText()

        # Check for "[[" to left
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 2)
        if tc.selectedText() == "[[":
            tc.removeSelectedText()
        else:
            # Logic fallback: maybe user didn't type [[ ?
            # But our trigger logic ensures it.
            # Restore position if check failed (unlikely)
            tc.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 2)

        # Resolve ID
        item_id = None
        if completion in self._completion_map:
            item_id, item_type = self._completion_map[completion]

        target = f"id:{item_id}" if item_id else completion
        label = completion

        # Insert Anchor
        tc.insertHtml(f'<a href="{target}">{label}</a>&nbsp;')
        self.setTextCursor(tc)

    def keyPressEvent(self, event):
        """
        Handles key press events for wiki link completion.

        Args:
            event: QKeyEvent from PySide6.
        """
        if self._completer and self._completer.popup().isVisible():
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

        # Helper to trigger completer
        self._check_for_completion()

    def _check_for_completion(self):
        """
        Checks if wiki link completion should be triggered.

        Looks backwards from cursor position for "[[" pattern and shows
        completion popup if found without a closing "]]".
        """
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()

        # Look backwards for "[["
        text_before = block_text[:pos_in_block]
        last_open = text_before.rfind("[[")
        last_close = text_before.rfind("]]")

        if last_open != -1 and last_open > last_close:
            prefix = text_before[last_open + 2 :]
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
        """
        Handles mouse move events to show pointer cursor over links.

        Args:
            event: QMouseEvent from PySide6.
        """
        if event.modifiers() & Qt.ControlModifier:
            anchor = self.anchorAt(event.pos())
            if anchor:
                self.viewport().setCursor(Qt.PointingHandCursor)
                return
        self.viewport().setCursor(Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release events for Ctrl+Click navigation.

        Args:
            event: QMouseEvent from PySide6.
        """
        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            anchor = self.anchorAt(event.pos())
            if anchor:
                # Handle ID checking
                if anchor.startswith("id:"):
                    target = anchor.split("|")[0][3:]
                else:
                    target = anchor.split("|")[0]
                self.link_clicked.emit(target)
                return
        super().mouseReleaseEvent(event)
