"""Longform Content Widget.

Handles the rendering of the longform document content using a lightweight QTextBrowser.
"""

import logging
import re
from typing import Any, Dict, List, Optional

import markdown
from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QTextBrowser, QWidget

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class LongformContentWidget(QTextBrowser):
    """Read-only text view for displaying the continuous longform document.

    Uses QTextBrowser for lightweight HTML rendering with Markdown support.
    """

    link_clicked = Signal(str)  # Emits target (e.g., "id:123" or "Name")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the content widget."""
        super().__init__(parent)
        self.setOpenLinks(False)  # We handle links manually
        self.anchorClicked.connect(self._on_anchor_clicked)

        # Apply initial theme
        self._apply_theme()

        # Connect to theme changes
        ThemeManager().theme_changed.connect(lambda _: self._apply_theme())

    def load_content(self, sequence: List[Dict[str, Any]]) -> None:
        """Load and display the longform sequence as continuous text.

        Args:
            sequence: Ordered list of items from build_longform_sequence.

        """
        lines = []

        for idx, item in enumerate(sequence):
            # Add anchor for navigation (HTML anchor)
            # We use an empty span or div with id because <a name> is older HTML
            # Markdown extension 'attr_list' might be needed for IDs on headers,
            # but standard HTML injection works fine in Markdown.
            lines.append(f'<a name="item-{idx}"></a>')

            # Add heading
            heading_level = item["heading_level"]
            title = item["meta"].get("title_override") or item["name"]

            # Markdown Heading
            heading = "#" * heading_level + " " + title
            lines.append(heading)
            lines.append("")

            # Add content
            content = item.get("content", "").strip()
            if content:
                lines.append(content)
                lines.append("")

            lines.append("")
            lines.append("---")  # Horizontal rule for separation
            lines.append("")

        full_markdown = "\n".join(lines)
        html = self._render_to_html(full_markdown)
        self.setHtml(html)

    def scroll_to_item(self, item_index: int) -> None:
        """Scroll to a specific item in the document.

        Args:
            item_index: Index of the item in the sequence.

        """
        self.scrollToAnchor(f"item-{item_index}")

    def _render_to_html(self, md_text: str) -> str:
        """Convert Markdown text to HTML with WikiLinks and CSS.

        Args:
            md_text: The raw markdown text.

        Returns:
            str: Full HTML document.

        """
        # 1. Process WikiLinks [[Target|Label]] -> Markdown [Label](Target)
        # Regex: [[ (group 1: target) ( | (group 2: label) )? ]]
        pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")

        def replace_link(match: re.Match) -> str:
            target = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else target
            # Convert to standard Markdown link
            return f"[{label}]({target})"

        md_text = pattern.sub(replace_link, md_text)

        # 2. Convert to HTML
        # Extensions:
        # - extra: tables, attrib sets, etc.
        # - nl2br: newlines become <br>
        html_body = markdown.markdown(md_text, extensions=["extra", "nl2br"])

        # 3. Add CSS
        css = self._get_theme_css()

        # 4. Wrap
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

    def _get_theme_css(self) -> str:
        """Generate CSS based on current theme."""
        tm = ThemeManager()
        theme = tm.get_theme()

        text_color = theme.get("text_main", "#E0E0E0")
        link_color = theme.get("accent_secondary", "#2980b9")
        # bg_color = theme.get("app_bg", "#2B2B2B") # Fallback

        fs_h1 = theme.get("font_size_h1", "18pt")
        fs_h2 = theme.get("font_size_h2", "16pt")
        fs_h3 = theme.get("font_size_h3", "14pt")
        fs_body = theme.get("font_size_body", "10pt")

        return """
            body {{
                color: {text_color};
                font-family: "Segoe UI", sans-serif;
                font-size: {fs_body};
            }}
            a {{
                color: {link_color};
                text-decoration: none;
            }}
            h1 {{
                font-size: {fs_h1};
                margin-top: 10px;
                margin-bottom: 5px;
                color: {text_color};
            }}
            h2 {{
                font-size: {fs_h2};
                margin-top: 8px;
                margin-bottom: 4px;
                color: {text_color};
            }}
            h3 {{
                font-size: {fs_h3};
                margin-top: 6px;
                margin-bottom: 3px;
                color: {text_color};
            }}
            p {{ margin-bottom: 5px; line-height: 1.4; }}
            hr {{ border-color: #555; border-style: solid; }}
        """.format(
            text_color=text_color,
            link_color=link_color,
            fs_h1=fs_h1,
            fs_h2=fs_h2,
            fs_h3=fs_h3,
            fs_body=fs_body,
        )

    def _apply_theme(self) -> None:
        """Apply widget-level styling (background, scrollbars)."""
        tm = ThemeManager()
        theme = tm.get_theme()

        bg_color = theme.get("app_bg", "#1e1e1e")  # Dark default
        # If theme has 'input_bg', maybe use that? Or transparent?
        # QTextBrowser is usually on a dock, so app_bg or surface.
        # Let's match editor style roughly.

        self.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {bg_color};
                border: none;
            }}
        """
        )

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
