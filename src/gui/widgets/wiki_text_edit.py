"""
Wiki Text Edit Widget.
A specialized QTextEdit that supports WikiLink navigation via Ctrl+Click.
"""

import logging
import re
from typing import Any, List, Optional

from PySide6.QtCore import QStringListModel, Qt, Signal, Slot
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QResizeEvent,
    QTextBlock,
    QTextCursor,
    QTextFragment,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QTextEdit,
    QToolButton,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.core.wiki_ast import CursorMapper, WikiASTParser, WikiASTSerializer

logger = logging.getLogger(__name__)


class WikiTextEdit(QTextEdit):
    """
    Text Editor with WikiLink support.
    - Highlights [[Links]]
    - Emits 'link_clicked' on Ctrl+Click
    - Supports Autocompletion for [[Links]]
    """

    link_clicked = Signal(str)  # Emits the target name (e.g. "Gandalf")
    link_added = Signal(str, str)  # Emits (target_id_or_name, display_name) on creation

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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
        self._current_wiki_text = ""  # Store for re-rendering on theme change

        # Enable mouse tracking for hover effects if desired
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Connect to theme changes and apply initial theme
        tm = ThemeManager()
        tm.theme_changed.connect(self._on_theme_changed)

        # Ensure native frame doesn't interfere with CSS border-radius
        self.setFrameShape(QTextEdit.NoFrame)

        # Force viewport transparency via Palette to ensure CSS border-radius shows
        p = self.viewport().palette()
        p.setColor(self.viewport().backgroundRole(), Qt.GlobalColor.transparent)
        self.viewport().setPalette(p)

        self._apply_theme_stylesheet()
        self._apply_widget_style()

        # View Mode: 'rich' (HTML) or 'source' (Markdown)
        self._view_mode = "rich"

        # Toggle Button (floating overlay)
        self.btn_toggle_view = QToolButton(self)
        self.btn_toggle_view.setText("MD")
        self.btn_toggle_view.setToolTip("Toggle Source View")
        self.btn_toggle_view.setCursor(Qt.CursorShape.ArrowCursor)
        self.btn_toggle_view.setFixedSize(30, 24)
        # Style: subtle, semi-transparent
        self.btn_toggle_view.setStyleSheet(
            """
            QToolButton {
                background-color: rgba(50, 50, 50, 150);
                color: #E0E0E0;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: rgba(80, 80, 80, 200);
                border-color: #777;
            }
            """
        )
        self.btn_toggle_view.clicked.connect(self.toggle_view_mode)
        self.btn_toggle_view.show()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle resize to reposition the floating button.
        """
        super().resizeEvent(event)
        # Top-Right corner with padding
        padding = 5
        btn_width = self.btn_toggle_view.width()
        # btn_height = self.btn_toggle_view.height()

        # Adjust for scrollbar if visible?
        # Typically scrollbar is part of the widget or overlaid.
        # QTextEdit scrollbar is inside the frame usually.
        # We'll just place it top-right relative to widget width.

        x = self.width() - btn_width - padding - 15  # extra padding for scrollbar
        y = padding
        self.btn_toggle_view.move(x, y)

    @Slot()
    def toggle_view_mode(self) -> None:
        """
        Toggles between Rich HTML view and Markdown Source view.
        Uses AST for pixel-perfect cursor position preservation.
        """
        # Capture cursor position before switching
        old_cursor_pos = self.textCursor().position()
        old_scroll = self.verticalScrollBar().value()

        if self._view_mode == "rich":
            # Rich -> Source: Map HTML cursor to MD cursor
            md_text = self.get_wiki_text()

            # Build AST for cursor mapping
            parser = WikiASTParser()
            serializer = WikiASTSerializer()
            ast = parser.parse(md_text)
            _, ast = serializer.to_markdown(ast)
            _, ast = serializer.to_plaintext(ast)
            mapper = CursorMapper(ast)

            # Map cursor position from HTML (PlainText) to MD
            new_cursor_pos = mapper.html_to_md(old_cursor_pos)

            # Switch mode
            self._view_mode = "source"
            self.setPlainText(md_text)

            # Restore cursor (clamped to valid range)
            doc_length = self.document().characterCount()
            new_cursor_pos = min(new_cursor_pos, doc_length - 1)
            new_cursor_pos = max(0, new_cursor_pos)
            cursor = self.textCursor()
            cursor.setPosition(new_cursor_pos)
            self.setTextCursor(cursor)

            # Restore scroll position
            self.verticalScrollBar().setValue(old_scroll)

            # Update Button
            self.btn_toggle_view.setText("HTML")
            self.btn_toggle_view.setToolTip("Switch to Rendered View")

        else:
            # Source -> Rich: Map MD cursor to HTML cursor
            raw_text = self.toPlainText()

            # Build AST for cursor mapping
            parser = WikiASTParser()
            serializer = WikiASTSerializer()
            ast = parser.parse(raw_text)
            _, ast = serializer.to_markdown(ast)
            _, ast = serializer.to_plaintext(ast)
            mapper = CursorMapper(ast)

            # Map cursor position from MD to HTML (PlainText)
            new_cursor_pos = mapper.md_to_html(old_cursor_pos)

            # Switch mode
            self._view_mode = "rich"
            self._current_wiki_text = None  # Force re-render
            self.set_wiki_text(raw_text)

            # Restore cursor (clamped to valid range)
            doc_length = self.document().characterCount()
            new_cursor_pos = min(new_cursor_pos, doc_length - 1)
            new_cursor_pos = max(0, new_cursor_pos)
            cursor = self.textCursor()
            cursor.setPosition(new_cursor_pos)
            self.setTextCursor(cursor)

            # Restore scroll position
            self.verticalScrollBar().setValue(old_scroll)

            # Update Button
            self.btn_toggle_view.setText("MD")
            self.btn_toggle_view.setToolTip("Switch to Source View")

    def set_link_resolver(self, link_resolver: Any) -> None:
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
        items_or_names: Optional[List[str]] = None,
        *,
        items: list[tuple[str, str, str]] = None,
        names: list[str] = None,
    ) -> None:
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
        if items_or_names and isinstance(items_or_names, list):
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

            # Create set of lower-case names and IDs for validation
            self._valid_targets_lower = {name.lower() for name in self._completion_map}
            self._valid_ids = {item_id for item_id, _, _ in items}

        elif names is not None:
            # Legacy mode - no ID mapping
            self._completion_map = {}
            display_names = names
            self._valid_targets_lower = {name.lower() for name in names}
            self._valid_ids = set()
        else:
            return

        if self._completer is None:
            self._completer = QCompleter(display_names, self)
            self._completer.setWidget(self)
            self._completer.setCompletionMode(QCompleter.PopupCompletion)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.activated.connect(self.insert_completion)
        else:
            model = QStringListModel(display_names, self._completer)
            self._completer.setModel(model)

    def _get_theme_css(self) -> str:
        """
        Build CSS stylesheet based on current theme settings.

        Retrieves current theme settings and builds CSS for headings,
        paragraphs, and links.

        Returns:
            str: CSS stylesheet as a string.
        """
        tm = ThemeManager()
        theme = tm.get_theme()

        link_color = theme.get("accent_secondary", "#2980b9")
        text_color = theme.get("text_main", "#E0E0E0")

        # Font Sizes (fallback to hardcoded if missing in old theme files)
        fs_h1 = theme.get("font_size_h1", "18pt")
        fs_h2 = theme.get("font_size_h2", "16pt")
        fs_h3 = theme.get("font_size_h3", "14pt")
        fs_body = theme.get("font_size_body", "10pt")

        # Build CSS stylesheet for the document
        css = (
            f"a {{ color: {link_color}; "
            "text-decoration: none; } "
            f"h1 {{ font-size: {fs_h1}; font-weight: 600; "
            f"color: {text_color}; "
            "margin-top: 10px; margin-bottom: 5px; } "
            f"h2 {{ font-size: {fs_h2}; font-weight: 600; "
            f"color: {text_color}; "
            "margin-top: 8px; margin-bottom: 4px; } "
            f"h3 {{ font-size: {fs_h3}; font-weight: 600; "
            f"color: {text_color}; "
            "margin-top: 6px; margin-bottom: 3px; } "
            f"p {{ margin-bottom: 2px; color: {text_color}; "
            f"font-size: {fs_body}; }} "
            f"body {{ color: {text_color}; font-size: {fs_body}; }}"
        )
        return css

    def _apply_theme_stylesheet(self) -> None:
        """
        Apply theme-based stylesheet to the document.

        Retrieves current theme settings and applies font sizes and colors
        to headings, paragraphs, and links.
        """
        css = self._get_theme_css()
        self.document().setDefaultStyleSheet(css)

    def _apply_widget_style(self) -> None:
        """
        Apply theme-based styling to the widget (borders, scrollbars).
        """
        tm = ThemeManager()
        theme = tm.get_theme()

        scrollbar_bg = theme.get("scrollbar_bg", theme.get("app_bg", "#2B2B2B"))
        scrollbar_handle = theme.get("scrollbar_handle", theme.get("border", "#454545"))
        primary = theme.get("primary", "#FF9900")
        surface = theme.get("surface", "#323232")
        border = theme.get("border", "#454545")

        widget_qss = f"""
            QTextEdit, WikiTextEdit {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px;
            }}
            QTextEdit > QWidget {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 10px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {primary};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: {scrollbar_bg};
            }}
            QScrollBar::horizontal {{
                background: {scrollbar_bg};
                height: 10px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {scrollbar_handle};
                min-width: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {primary};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: {scrollbar_bg};
            }}
        """
        self.setStyleSheet(widget_qss)

    def set_wiki_text(self, text: Optional[str]) -> None:
        """
        Sets the content using WikiLink syntax, converting it to HTML anchors.
        Uses the 'markdown' library for rich text rendering.
        """
        import markdown

        if text is None:
            text = ""

        # Check if text is identical to avoid unnecessary reload
        # This applies to BOTH Rich and Source modes.
        if hasattr(self, "_current_wiki_text") and self._current_wiki_text == text:
            # Check if we are actually fully rendered?
            # If we just initialized, we might need to render.
            # But usually safe to skip.
            return

        # If in Source mode, just set the raw text and ignore HTML rendering
        if hasattr(self, "_view_mode") and self._view_mode == "source":
            # Block signals to prevent textChanged during programmatic update
            was_blocked = self.blockSignals(True)
            try:
                self.setPlainText(text)
            finally:
                self.blockSignals(was_blocked)

            # Update internal store so switching back works
            self._current_wiki_text = text
            return

        # Store text for re-rendering on theme change
        self._current_wiki_text = text

        # 1. Pre-process WikiLinks [[Target|Label]] -> Markdown [Label](Target)
        # Markdown library processes standard links [Label](URL) naturally.
        pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")

        def replace_link_md(match: re.Match) -> str:
            """
            Convert WikiLink syntax to Markdown link syntax.
            Checks validity of target against known items.
            """
            target = match[1].strip()
            label = match[2].strip() if match[2] else target

            # Check existence
            is_valid = False

            # Handle id: prefix for ID-based links
            # Links can be:
            #   [[Name]] -> target = "Name"
            #   [[id:UUID|Label]] -> target = "id:UUID"
            check_target = target
            if target.startswith("id:"):
                # Strip "id:" prefix for ID lookup
                check_target = target[3:]

            # Check names (case insensitive)
            if (
                hasattr(self, "_valid_targets_lower")
                and check_target.lower() in self._valid_targets_lower
            ):
                is_valid = True
            # Check IDs (exact match with stripped prefix)
            elif hasattr(self, "_valid_ids") and check_target in self._valid_ids:
                is_valid = True

            # Fallback for when completer hasn't been set yet (don't mark red)
            elif not hasattr(self, "_valid_targets_lower"):
                is_valid = True

            if not is_valid:
                pass

            if is_valid:
                return f"[{label}]({target})"
            else:
                # Render as raw HTML anchor with style for red color
                return f'<a href="{target}" style="color: red;">{label}</a>'

        md_text = pattern.sub(replace_link_md, text)

        # 2. Convert Markdown to HTML
        # extensions=['extra'] enables tables, attr_list, def_list, etc.
        html_body = markdown.markdown(md_text, extensions=["extra", "nl2br"])

        # 3. Get theme CSS and wrap content with embedded stylesheet
        # Embedding CSS directly in HTML ensures Qt applies it correctly
        css = self._get_theme_css()
        html_content = (
            f"<html><head><style>{css}</style></head><body>{html_body}</body></html>"
        )

        # Block signals to prevent textChanged during programmatic update
        was_blocked = self.blockSignals(True)
        try:
            self.setHtml(html_content)
        finally:
            self.blockSignals(was_blocked)

    def get_wiki_text(self) -> str:
        """
        Converts the editor content back to WikiLink syntax.
        If in 'source' mode, returns the raw text directly.
        """
        if hasattr(self, "_view_mode") and self._view_mode == "source":
            return self.toPlainText()

        result = []
        block = self.document().begin()
        while block.isValid():
            block_text = self._process_block(block)
            result.append(block_text)
            block = block.next()

        # Smart Join:
        # If two consecutive blocks have content, they are paragraphs -> join with \n\n
        # If one of them is empty, it's an explicit spacing -> join with \n
        output = ""
        for i, text in enumerate(result):
            output += text
            if i < len(result) - 1:
                next_text = result[i + 1]
                if text.strip() and next_text.strip():
                    # Both have content: separate paragraphs
                    output += "\n\n"
                else:
                    # One or both empty: simple line break
                    output += "\n"

        return output

    def _process_block(self, block: QTextBlock) -> str:
        """
        Process a text block to recover block-level formatting (Headings).
        Then delegates to _process_fragment for inline formatting.
        """
        iterator = block.begin()
        block_content = []

        # Check first fragment for Font Size Heuristic (Heading Detection)
        # We need the first fragment to guess the block style if it's consistent
        # But iterating fragments is safer to get all content.

        # Determine Heading Status EARLY
        # Check semantic heading level first (preferred)
        heading_level = block.blockFormat().headingLevel()

        # Fallback to font size heuristic
        if heading_level == 0 and block.length() > 1:
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            font_size = cursor.charFormat().fontPointSize()

            # Get theme font sizes for dynamic comparison
            theme = ThemeManager()
            theme_data = theme.get_theme()

            def _parse_size(val: str | int | float) -> float:
                if isinstance(val, (int, float)):
                    return float(val)
                return (
                    float(val.replace("pt", "").strip())
                    if isinstance(val, str)
                    else 10.0
                )

            h1_size = _parse_size(theme_data.get("font_size_h1", 16))
            h2_size = _parse_size(theme_data.get("font_size_h2", 14))
            h3_size = _parse_size(theme_data.get("font_size_h3", 12))

            if font_size >= h1_size - 0.5:
                heading_level = 1
            elif font_size >= h2_size - 0.5:
                heading_level = 2
            elif font_size >= h3_size - 0.5:
                heading_level = 3

        is_heading = heading_level > 0

        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                text = self._process_fragment(fragment, is_heading=is_heading)
                block_content.append(text)
            iterator += 1

        full_line_text = "".join(block_content)

        if heading_level > 0:
            prefix = "#" * heading_level
            return f"{prefix} {full_line_text}"

        return full_line_text

    def _process_fragment(
        self, fragment: QTextFragment, is_heading: bool = False
    ) -> str:
        """
        Process a text fragment to recover inline formatting (Bold, Italic, Links).
        """
        text = fragment.text()
        fmt = fragment.charFormat()

        # 1. WikiLinks (Anchor)
        if fmt.isAnchor():
            href = fmt.anchorHref()
            if href == text:
                text = f"[[{text}]]"
            elif href.startswith("id:") and text:
                text = f"[[{href}|{text}]]"
            else:
                text = f"[[{href}|{text}]]"

        # 2. Bold
        # font weight 75 is Bold, 63 is DemiBold, 50 is Normal usually (legacy)
        # Qt 6: QFont.Weight.Bold = 700, Normal = 400.
        # But internal integer values might differ.
        # If it's a heading, explicit bold wrapping is redundant/visual only.
        if not is_heading and fmt.fontWeight() > 600:  # Safe threshold for Bold (700)
            text = f"**{text}**"

        # 3. Italic
        if fmt.fontItalic():
            text = f"*{text}*"

        return text

    @Slot(str)
    def insert_completion(self, completion: str) -> None:
        """
        Inserts the selected completion as an HTML anchor.
        """
        tc = self.textCursor()
        if not self._completer:
            return
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

        # Emit signal
        self.link_added.emit(target, label)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handles key press events for wiki link completion and formatting shortcuts.

        Supports:
        - Ctrl+B: Toggle bold
        - Ctrl+I: Toggle italic

        Args:
            event: QKeyEvent from PySide6.
        """
        # Check for formatting shortcuts first
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_B:
                self._toggle_bold()
                return
            elif event.key() == Qt.Key.Key_I:
                self._toggle_italic()
                return
            elif event.key() == Qt.Key.Key_1:
                self._set_heading(1)
                return
            elif event.key() == Qt.Key.Key_2:
                self._set_heading(2)
                return
            elif event.key() == Qt.Key.Key_3:
                self._set_heading(3)
                return
            elif event.key() == Qt.Key.Key_0:
                self._set_heading(0)  # Remove heading
                return
            elif event.key() == Qt.Key.Key_4:
                self._set_heading(0)  # Revert to body text
                return

        if self._completer and (popup := self._completer.popup()) and popup.isVisible():
            if event.key() in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Escape,
                Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab,
            ):
                event.ignore()
                return

        super().keyPressEvent(event)

        # Handle formatting reset on Enter (only in Rich mode)
        # If we just created a new block from a Heading,
        # it inherits the large font size.
        # We want to reset it to Body text size.
        is_source_mode = hasattr(self, "_view_mode") and self._view_mode == "source"
        if not is_source_mode and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            cursor = self.textCursor()
            # If current font size is larger than body (roughly), reset to body
            # We could fetch exact theme values, but > 11 is a safe heuristic for now
            # since body is usually 10pt and H3 is 12pt+.
            current_size = cursor.charFormat().fontPointSize()
            # logger.info(f"Enter pressed. Current Font Size: {current_size}")
            if current_size > 11:
                # logger.info("Font size > 11, resetting heading to 0")
                self._set_heading(0)

        # Check if user just closed a wiki link with ]]
        if event.text() == "]":
            self._check_for_link_closure()

        # Helper to trigger completer
        self._check_for_completion()

    def _toggle_bold(self) -> None:
        """
        Toggle bold formatting on selected text or at cursor position.

        In Source mode: wraps/unwraps selection with **
        In Rich mode: applies/removes bold QTextCharFormat
        """
        if self._view_mode == "source":
            self._toggle_markdown_format("**")
        else:
            self._toggle_rich_format("bold")

    def _toggle_italic(self) -> None:
        """
        Toggle italic formatting on selected text or at cursor position.

        In Source mode: wraps/unwraps selection with *
        In Rich mode: applies/removes italic QTextCharFormat
        """
        if self._view_mode == "source":
            self._toggle_markdown_format("*")
        else:
            self._toggle_rich_format("italic")

    def _set_heading(self, level: int) -> None:
        """
        Set heading level on the current line.

        Args:
            level: Heading level (1-3) or 0 to remove heading.

        In Source mode: Adds/replaces/removes # prefix
        In Rich mode: Applies font size from ThemeManager
        """
        if self._view_mode == "source":
            self._set_markdown_heading(level)
        else:
            self._set_rich_heading(level)

    def _set_markdown_heading(self, level: int) -> None:
        """
        Set Markdown heading on current line.

        Args:
            level: Heading level (1-3) or 0 to remove.
        """
        cursor = self.textCursor()

        # Select entire current line
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )

        line_text = cursor.selectedText()

        # Remove existing heading prefix
        stripped = line_text.lstrip("#").lstrip()

        # Add new prefix
        new_text = ("#" * level + " " + stripped) if level > 0 else stripped

        cursor.insertText(new_text)
        self.setTextCursor(cursor)

    def _set_rich_heading(self, level: int) -> None:
        """
        Set heading style in Rich mode.

        Args:
            level: Heading level (1-3) or 0 for paragraph.
        """
        from PySide6.QtGui import QFont, QTextCharFormat

        # Apply formatting
        cursor = self.textCursor()

        # Select entire current block to apply block format
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )

        # Get font size from theme
        theme = ThemeManager()
        theme_data = theme.get_theme()

        def _parse_font_size(value: Any) -> float:
            """Parse font size, handling 'pt' suffix."""
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # Remove 'pt' suffix if present
                return float(value.replace("pt", "").strip())
            return 10.0  # fallback

        font_size_map = {
            0: _parse_font_size(theme_data.get("font_size_body", 10)),
            1: _parse_font_size(theme_data.get("font_size_h1", 18)),
            2: _parse_font_size(theme_data.get("font_size_h2", 16)),
            3: _parse_font_size(theme_data.get("font_size_h3", 14)),
        }

        font_size = font_size_map.get(level, 10.0)

        from PySide6.QtGui import QTextBlockFormat

        block_fmt = QTextBlockFormat()
        block_fmt.setHeadingLevel(level)

        # Set margins to match CSS
        # h1: top=10, bottom=5
        # h2: top=8, bottom=4
        # h3: top=6, bottom=3
        # body: top=0, bottom=0 (default)
        if level == 1:
            block_fmt.setTopMargin(10)
            block_fmt.setBottomMargin(5)
        elif level == 2:
            block_fmt.setTopMargin(8)
            block_fmt.setBottomMargin(4)
        elif level == 3:
            block_fmt.setTopMargin(6)
            block_fmt.setBottomMargin(3)
        else:
            block_fmt.setTopMargin(0)
            block_fmt.setBottomMargin(0)

        cursor.setBlockFormat(block_fmt)

        # Apply char formatting (Font Size + Weight)
        fmt = QTextCharFormat()
        fmt.setFontPointSize(font_size)

        if level > 0:
            fmt.setFontWeight(QFont.Weight.Bold)  # 700 / 600
        else:
            fmt.setFontWeight(QFont.Weight.Normal)

        cursor.mergeCharFormat(fmt)

        # Force visual update by re-rendering was problematic for cursor state.
        # Since we manually applied block and char formats that match the theme,
        # we don't need to do a full markdown round-trip.
        # This prevents cursor jumping and loss of empty lines.

    def _toggle_markdown_format(self, marker: str) -> None:
        """
        Toggle Markdown formatting markers around selection.

        Args:
            marker: The Markdown marker (e.g., "**" for bold, "*" for italic)
        """
        cursor = self.textCursor()
        selected_text = cursor.selectedText()

        if not selected_text:
            # No selection - just insert markers and position cursor between
            cursor.insertText(f"{marker}{marker}")
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.MoveAnchor,
                len(marker),
            )
            self.setTextCursor(cursor)
            return

        # Check if already formatted
        if selected_text.startswith(marker) and selected_text.endswith(marker):
            # Remove markers
            unwrapped = selected_text[len(marker) : -len(marker)]
            cursor.insertText(unwrapped)
        else:
            # Add markers
            cursor.insertText(f"{marker}{selected_text}{marker}")

        self.setTextCursor(cursor)

    def _toggle_rich_format(self, format_type: str) -> None:
        """
        Toggle rich text formatting on selection.

        Args:
            format_type: "bold" or "italic"
        """
        from PySide6.QtGui import QFont, QTextCharFormat

        cursor = self.textCursor()

        if not cursor.hasSelection():
            # No selection - toggle format at cursor for future typing
            fmt = cursor.charFormat()
            if format_type == "bold":
                new_weight = (
                    QFont.Weight.Normal
                    if fmt.fontWeight() > QFont.Weight.Normal
                    else QFont.Weight.Bold
                )
                fmt.setFontWeight(new_weight)
            elif format_type == "italic":
                fmt.setFontItalic(not fmt.fontItalic())
            cursor.setCharFormat(fmt)
            self.setTextCursor(cursor)
            return

        # Has selection - apply format to selection
        fmt = QTextCharFormat()

        if format_type == "bold":
            # Check current state
            current_fmt = cursor.charFormat()
            is_bold = current_fmt.fontWeight() > QFont.Weight.Normal
            fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        elif format_type == "italic":
            current_fmt = cursor.charFormat()
            fmt.setFontItalic(not current_fmt.fontItalic())

        cursor.mergeCharFormat(fmt)
        self.setTextCursor(cursor)

    def _check_for_link_closure(self) -> None:
        """
        Check if user just completed a wiki link with ]].
        If so, validate and style the link immediately.
        """
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()

        # Check if previous char was also ]
        if pos_in_block < 2:
            return

        text_before = block_text[:pos_in_block]
        if not text_before.endswith("]]"):
            return

        # Find matching [[
        # Look backwards from the ]] we just typed
        link_end = len(text_before)
        bracket_start = text_before.rfind("[[")

        if bracket_start == -1:
            return

        # Extract the link content between [[ and ]]
        link_content = text_before[bracket_start + 2 : link_end - 2]

        # Parse target (handle [[target|label]] format)
        # Parse target (handle [[target|label]] format)
        if "|" in link_content:
            target, label = (part.strip() for part in link_content.split("|", 1))
        else:
            target = label = link_content.strip()

        if not target:
            return

        # Validate the target
        is_valid = self._validate_link_target(target)

        # Replace the [[...]] with a styled anchor
        # Calculate absolute positions
        block_start = cursor.block().position()
        abs_start = block_start + bracket_start
        abs_end = block_start + link_end

        # Select the [[...]] text
        cursor.setPosition(abs_start)
        cursor.setPosition(abs_end, QTextCursor.KeepAnchor)

        # Build the anchor HTML
        if is_valid:
            html = f'<a href="{target}">{label}</a>'
        else:
            html = f'<a href="{target}" style="color: red;">{label}</a>'

        cursor.insertHtml(html)
        self.setTextCursor(cursor)

        # Emit Signal if valid linked
        if is_valid:
            # If we know the ID, resolve it?
            # For now just send what we have. If it's a name, receiver tries to find it.
            # If it's ID, it's already ID.
            self.link_added.emit(target, label)

    def _validate_link_target(self, target: str) -> bool:
        """
        Validate a link target against known items.

        Args:
            target: The link target (name or id:UUID format).

        Returns:
            bool: True if valid, False if broken/non-existent.
        """
        # Handle id: prefix
        check_target = target[3:] if target.startswith("id:") else target

        # Check names (case insensitive)
        if (
            hasattr(self, "_valid_targets_lower")
            and check_target.lower() in self._valid_targets_lower
        ):
            return True

        # Check IDs
        if hasattr(self, "_valid_ids") and check_target in self._valid_ids:
            return True

        # Fallback if completer not set
        return not hasattr(self, "_valid_targets_lower")

    def _check_for_completion(self) -> None:
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
            if (
                "|" not in prefix
                and self._completer
                and (popup := self._completer.popup())
            ):
                self._show_completion_popup(popup, prefix)
        elif self._completer and (popup := self._completer.popup()):
            popup.hide()

    def _show_completion_popup(self, popup: QAbstractItemView, prefix: str) -> None:
        """Helper to position and show completion popup."""
        self._completer.setCompletionPrefix(prefix)
        curr_rect = self.cursorRect()

        scroll_bar = popup.verticalScrollBar()
        sb_width = scroll_bar.sizeHint().width() if scroll_bar else 0

        curr_rect.setWidth(popup.sizeHintForColumn(0) + sb_width)
        self._completer.complete(curr_rect)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handles mouse move events to show pointer cursor over links.

        Args:
            event: QMouseEvent from PySide6.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and self.anchorAt(
            event.position().toPoint()
        ):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            return
        self.viewport().setCursor(Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handles mouse release events for Ctrl+Click navigation.

        Args:
            event: QMouseEvent from PySide6.
        """
        if (
            event.button() == Qt.MouseButton.LeftButton
            and (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            and (anchor := self.anchorAt(event.position().toPoint()))
        ):
            # Handle ID checking
            target = anchor.split("|")[0]
            if target.startswith("id:"):
                target = target[3:]
            self.link_clicked.emit(target)
            return
        super().mouseReleaseEvent(event)

    @Slot(dict)
    def _on_theme_changed(self, theme_data: dict) -> None:
        """
        Updates link color and text style when theme changes.

        Re-renders the current content to apply new font sizes and colors.

        Args:
            theme_data: Dictionary containing theme settings (unused,
                        as we fetch fresh from ThemeManager).
        """
        # Update widget styling (scrollbars, borders)
        self._apply_widget_style()

        # Block signals to prevent textChanged from triggering dirty state
        was_blocked = self.blockSignals(True)
        try:
            # Re-render with stored text to apply new stylesheet
            if self._current_wiki_text:
                self.set_wiki_text(self._current_wiki_text)
            else:
                # Just update stylesheet for empty or non-wiki content
                self._apply_theme_stylesheet()
        finally:
            self.blockSignals(was_blocked)
