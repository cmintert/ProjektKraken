"""Longform Content Widget.

Handles the rendering of the longform document content using a lightweight QTextBrowser.
"""

import contextlib
import logging
import re
from typing import Any, Dict, List, Optional

import markdown  # type: ignore[import-untyped]  # Package has no py.typed marker.
from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import (
    QDesktopServices,
    QMouseEvent,
    QTextCursor,
    QTextDocument,
    QTextTable,
)
from PySide6.QtWidgets import QTextBrowser, QWidget

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class LongformContentWidget(QTextBrowser):
    """Read-only text view for displaying the continuous longform document.

    Uses QTextBrowser for lightweight HTML rendering with Markdown support.
    """

    link_clicked = Signal(str)  # Emits target (e.g., "id:123" or "Name")
    item_selected = Signal(str, str)  # Emits table, id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the content widget."""
        super().__init__(parent)
        self.setOpenLinks(False)  # We handle links manually
        self.anchorClicked.connect(self._on_anchor_clicked)
        self._sequence: list[dict[str, Any]] = []
        self._calendar_converter = None

        # Connect to theme changes
        ThemeManager().theme_changed.connect(lambda _: self._apply_theme())

        # Apply initial theme
        self._apply_theme()

    def set_calendar_converter(self, converter: Any) -> None:
        """Set the calendar converter used for formatting event dates.

        Args:
            converter: CalendarConverter instance.

        """
        self._calendar_converter = converter
        if self._sequence:
            self.load_content(self._sequence)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Detect card clicks vs link clicks."""
        pos = event.position().toPoint()

        if self.anchorAt(pos):
            # Clicked on a real link (WikiLink or Title link)
            super().mousePressEvent(event)
            return

        # Clicked on a card background/text area that is NOT a link
        cursor = self.cursorForPosition(pos)
        if (table := cursor.currentTable()) and (
            idx := self._get_item_index_from_table(table)
        ) is not None:
            if 0 <= idx < len(self._sequence):
                item = self._sequence[idx]
                self.item_selected.emit(item["table"], item["id"])

        super().mousePressEvent(event)

    def _get_item_index_from_table(self, table: QTextTable) -> Optional[int]:
        """Maps a QTextTable to its index in self._sequence."""
        # Check first cell, first character's anchorName
        cell = table.cellAt(0, 0)
        cursor = cell.firstCursorPosition()

        # The space we inserted <a name="item-idx"> </a> should hold the anchor
        # Look at the first few characters just in case of formatting shifts
        for _ in range(5):
            names = cursor.charFormat().anchorNames()
            if names and (name := names[0]).startswith("item-"):
                with contextlib.suppress(ValueError, IndexError):
                    return int(name.split("-")[1])
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
            if cursor.atEnd():
                break

        return None

    def load_content(self, sequence: List[Dict[str, Any]]) -> None:
        """Load and display the longform sequence as continuous text.

        Args:
            sequence: Ordered list of items from build_longform_sequence.

        """
        self._sequence = sequence
        html_parts = []

        for idx, item in enumerate(sequence):
            # Pre-process wikilinks in content and title
            content_md = item.get("content", "").strip()
            title = item["meta"].get("title_override") or item["name"]

            heading_level = item["heading_level"]
            heading_html = f"<h{heading_level}>{title}</h{heading_level}>"

            # Wrap heading in a link for selection/navigation
            # We use id: scheme which navigation_coordinator already handles
            heading_link = (
                f'<a href="id:{item["id"]}" style="text-decoration: none; '
                f'color: inherit;">{heading_html}</a>'
            )

            # Build optional date subtitle (events only)
            date_html = ""
            if item.get("table") == "events" and self._calendar_converter:
                lore_date = item.get("lore_date")
                if lore_date is not None:
                    try:
                        start_str = self._calendar_converter.format_date(lore_date)
                        lore_duration = item.get("lore_duration") or 0.0
                        if lore_duration > 0:
                            end_str = self._calendar_converter.format_date(
                                lore_date + lore_duration
                            )
                            date_str = f"{start_str} \u2013 {end_str}"
                        else:
                            date_str = start_str
                        date_html = f'<p class="event-date">{date_str}</p>'
                    except Exception:
                        pass

            # Render content markdown
            content_html = (
                self._render_markdown_fragment(content_md) if content_md else ""
            )

            # Build Card HTML using Table for robust Qt rendering
            # Cellpadding matches CSS padding expectations
            table_type = item.get("table", "unknown")
            card_html = (
                f'<table class="card-table type-{table_type}" width="100%" '
                f'cellpadding="20" cellspacing="0">'
                f"<tr>"
                f'<td class="card-cell">'
                f'<a name="item-{idx}"> </a>'  # Space marker for click detection
                f"{heading_link}"
                f"{date_html}"
                f"{content_html}"
                f"</td>"
                f"</tr>"
                f"</table>"
                f"<br>"
            )
            html_parts.append(card_html)

        body_html = "\n".join(html_parts)
        final_html = self._wrap_html(body_html)
        self.setHtml(final_html)

    def scroll_to_item(self, item_index: int) -> None:
        """Scroll to a specific item in the document.

        Args:
            item_index: Index of the item in the sequence.

        """
        self.scrollToAnchor(f"item-{item_index}")

    def _render_markdown_fragment(self, md_text: str) -> str:
        """Convert a fragment of Markdown to HTML (no CSS/HTML wrapping)."""
        # 1. Process WikiLinks [[Target|Label]] -> Markdown [Label](Target)
        pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")

        def replace_link(match: re.Match) -> str:
            """Replace wiki link with markdown link.

            Args:
                match: Regex match object for wiki link.

            Returns:
                Markdown-formatted link string.
            """
            target = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else target
            # Convert to standard Markdown link
            return f"[{label}]({target})"

        md_text = pattern.sub(replace_link, md_text)

        # 2. Convert to HTML
        return markdown.markdown(md_text, extensions=["extra", "nl2br"])

    def _wrap_html(self, html_body: str) -> str:
        """Wrap HTML body with CSS and standard tags."""
        css = self._get_theme_css()
        return f"""
        <html>
        <head>
            <style>{css}</style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """

    def _render_to_html(self, md_text: str) -> str:
        """Deprecated: Convert Markdown text to HTML with WikiLinks and CSS.

        Kept for compatibility if needed, but load_content uses new pipeline.
        """
        html_fragment = self._render_markdown_fragment(md_text)
        return self._wrap_html(html_fragment)

    def _get_theme_css(self) -> str:
        """Generate CSS based on current theme."""
        tm = ThemeManager()
        theme = tm.get_theme()

        text_color = theme.get("text_main", "#E0E0E0")
        link_color = theme.get("accent_secondary", "#2980b9")
        surface_color = theme.get("surface", "#323232")
        border_color = theme.get("border", "#454545")
        primary_color = theme.get("primary", "#FF9900")
        text_dim_color = theme.get("text_dim", "#9E9E9E")
        # bg_color = theme.get("app_bg", "#2B2B2B")

        fs_h1 = theme.get("font_size_h1", "18pt")
        fs_h2 = theme.get("font_size_h2", "16pt")
        fs_h3 = theme.get("font_size_h3", "14pt")
        fs_body = theme.get("font_size_body", "10pt")

        return """
            body {{
                color: {text_color};
                font-family: "Segoe UI", sans-serif;
                font-size: {fs_body};
                line-height: 1.35;
                margin: 0;
                padding: 20px;
                background-color: transparent;
            }}

            /* Card Style (Table-based) */
            .card-table {{
                margin-bottom: 20px;
                background-color: {surface_color};
                border-style: solid;
                border: 1px solid {border_color};
            }}
            td.card-cell {{
                background-color: {surface_color};
                padding: 10px;
                color: {text_color};
            }}

            a {{
                color: {link_color};
                text-decoration: none;
                font-weight: 600;
            }}
            h1 {{
                font-size: {fs_h1};
                margin-top: 0;
                margin-bottom: 12px;
                color: {primary_color};
                border-bottom: 1px solid {border_color};
                padding-bottom: 8px;
            }}

            /* Event specific styling: Blue Headings */
            .type-events h1 {{
                color: {link_color};
            }}

            .event-date {{
                font-size: 8pt;
                color: {text_dim_color};
                margin-top: -6px;
                margin-bottom: 10px;
                font-style: italic;
            }}

            h2 {{
                font-size: {fs_h2};
                margin-top: 16px;
                margin-bottom: 10px;
                color: {text_color};
            }}
            h3 {{
                font-size: {fs_h3};
                margin-top: 12px;
                margin-bottom: 8px;
                color: {text_color};
                font-weight: 600;
            }}
            p {{
                margin-bottom: 12px;
            }}
            hr {{
                border-color: {border_color};
                border-style: solid;
                margin: 20px 0;
            }}

            /* Blockquotes */
            blockquote {{
                border-left: 4px solid {accent_color};
                margin: 10px 0;
                padding-left: 10px;
                color: {text_color};
                font-style: italic;
                background-color: transparent;
            }}

            /* Code Blocks */
            pre {{
                background-color: rgba(0,0,0,0.2);
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 10px;
                font-family: "Consolas", monospace;
                white-space: pre-wrap;
            }}
            code {{
                font-family: "Consolas", monospace;
                background-color: rgba(0,0,0,0.2);
                padding: 2px 4px;
                border-radius: 3px;
            }}

            /* Lists */
            ul, ol {{
                margin-bottom: 12px;
                padding-left: 24px;
            }}
            li {{
                margin-bottom: 4px;
            }}

            /* Tables */
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 16px;
            }}
            th {{
                background-color: rgba(0,0,0,0.1);
                color: {primary_color};
                padding: 8px;
                text-align: left;
                border-bottom: 2px solid {border_color};
            }}
            td {{
                padding: 8px;
                border-bottom: 1px solid {border_color};
            }}
        """.format(
            text_color=text_color,
            link_color=link_color,
            surface_color=surface_color,
            border_color=border_color,
            primary_color=primary_color,
            text_dim_color=text_dim_color,
            accent_color=link_color,  # Re-using accent secondary for blockquote border
            fs_h1=fs_h1,
            fs_h2=fs_h2,
            fs_h3=fs_h3,
            fs_body=fs_body,
        )

    def _apply_theme(self) -> None:
        """Apply widget-level styling (background, scrollbars)."""
        try:
            import shiboken6

            if not shiboken6.isValid(self):
                return
        except ImportError:
            pass

        try:
            tm = ThemeManager()
            theme = tm.get_theme()
            from src.gui.utils.style_helper import StyleHelper

            bg_color = theme.get("app_bg", "#1e1e1e")
            scrollbar_style = StyleHelper.get_scrollbar_style()

            # Combine specific browser style with global scrollbar style
            style = f"""
                QTextBrowser {{
                    background-color: {bg_color};
                    border: none;
                }}
                {scrollbar_style}
            """
            self.setStyleSheet(style)

            # Reload content to update CSS in <head>
            if self._sequence:
                # Preserve scroll
                scrollbar = self.verticalScrollBar()
                val = scrollbar.value()
                self.load_content(self._sequence)
                scrollbar.setValue(val)
        except Exception:
            # Prevent crashes during theme changes (especially in tests or shutdown)
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Failed to apply theme in LongformContentWidget", exc_info=True
            )

    def find_text(self, text: str, backward: bool = False) -> bool:
        """Find and highlight text.

        Args:
            text: Text to search for.
            backward: Whether to search backward.

        Returns:
            bool: True if found, False otherwise.
        """
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward

        found = self.find(text, flags)
        if not found and backward:
            # Wrap around backward (end -> start)
            # Actually QTextEdit wrap logic is tricky. Simplest is retry from end/start.
            # But standard Behavior: if not found, we might be at start.
            # Let's try to reset cursor to end/start and try again if desired,
            # or just return False.
            # For now, standard behavior:
            pass
        elif not found and not backward:
            # Wrap around forward (start -> end)?
            # Typically implemented by wrapper.
            pass

        return found

    @Slot(QUrl)
    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Handle link clicks.

        Internal links (id:..., names) are emitted.
        External links (http) are opened in browser.
        """
        target = url.toString()

        # Check for internal link schemes or simple names
        if target.startswith("http://") or target.startswith("https://"):
            QDesktopServices.openUrl(url)
        else:
            # Assume internal
            self.link_clicked.emit(target)
