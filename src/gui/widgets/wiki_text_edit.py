"""Wiki Text Edit Widget.

A specialized QTextEdit that supports WikiLink navigation via Ctrl+Click.
"""

import logging
import re
from collections import Counter
from html import escape
from typing import Any, List, Optional, Tuple, cast

import shiboken6
from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPoint,
    QSignalBlocker,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QCursor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QStandardItem,
    QStandardItemModel,
    QTextBlock,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFragment,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.command import LoreMutationEffect
from src.core.theme_manager import ThemeManager
from src.core.wiki_ast import CursorMapper, WikiASTParser, WikiASTSerializer
from src.core.wiki_markdown_grammar import requires_source_mode
from src.gui.constants import SEMANTIC_COMPLETION_MIN_PREFIX_LEN
from src.gui.editor_typography import EditorTypography
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.suggestion_effects import apply_suggestion_effects
from src.gui.widgets.wiki_link_presentation import (
    LinkPresentation,
    WikiPresentationHighlighter,
    resolve_link_presentation,
)

logger = logging.getLogger(__name__)

_MAXIMUM_OUTLINE_HEADING_LEVEL = 3
_BOLD_WEIGHT_THRESHOLD = 600
_HEADING_LEVEL_TWO = 2
_HEADING_LEVEL_THREE = 3
_WIKI_LINK_CLOSING_TOKEN_LENGTH = 2
_MINIMUM_SPELLCHECK_TEXT_LENGTH = 15
_COMPLETION_ROW_FIELDS = 3
_PEEK_CURSOR_SIZE = 24


class SectionData(QTextBlockUserData):
    """Custom block user data to store section grouping information."""

    def __init__(self, section_id: str, heading_level: int) -> None:
        """Initialize section data.

        Args:
            section_id: Determinstic hash string of the parent heading text.
            heading_level: Level of the heading that started this section (0=body).
        """
        super().__init__()
        self.section_id = section_id
        self.heading_level = heading_level


class SectionManager:
    """Analyzes a QTextDocument to group blocks into sections."""

    def __init__(self, document: QTextDocument) -> None:
        """Initialize the section manager.

        Args:
            document: The document to analyze.
        """
        self.document = document

        # Debounce timer for analysis
        self._analyze_timer = QTimer()
        self._analyze_timer.setSingleShot(True)
        self._analyze_timer.setInterval(300)
        self._analyze_timer.timeout.connect(self._analyze_document)

        # Connect to document changes
        self.document.contentsChanged.connect(self.schedule_analysis)

    def schedule_analysis(self) -> None:
        """Schedule a background analysis of the document."""
        self._analyze_timer.start()

    def _analyze_document(self) -> None:
        """Iterate over blocks and assign hashed section IDs."""
        if not shiboken6.isValid(self.document):
            self._analyze_timer.stop()
            return
        block = self.document.firstBlock()

        current_section_id = "default"

        while block.isValid():
            fmt = block.blockFormat()
            level = fmt.headingLevel()

            if level > 0:
                # Heading starts a new section based on its text
                text = block.text().strip()
                # Empty headings get a generic ID mapped to their level + block num
                seed = text if text else f"H{level}_{block.blockNumber()}"

                import hashlib

                current_section_id = hashlib.md5(seed.encode()).hexdigest()[:8]

            # Assign data
            data = SectionData(current_section_id, level)
            block.setUserData(data)

            block = block.next()


class WikiTextEditView(QTextEdit):
    """Text Editor with WikiLink support.

    - Highlights [[Links]]
    - Emits 'link_clicked' on Ctrl+Click
    - Supports Autocompletion for [[Links]]
    """

    link_clicked = Signal(str)  # Emits the target name (e.g. "Gandalf")
    peek_requested = Signal(str)
    link_to_entry_requested = Signal()
    document_replacing = Signal()
    completion_prefix_changed = Signal(str)  # Emits prefix when >= 3 chars inside [[
    view_mode_changed = Signal(str)
    _lt_check_requested = Signal(
        int, int, str, str, str, str
    )  # (request ID, document revision, text, language, username, api key)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the WikiTextEdit.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.

        """
        super().__init__(parent)
        self._hovered_link = None
        self._completer: Optional[QCompleter] = None
        self._completion_map: dict[str, tuple[str, str]] = {}
        self._completion_rows: list[tuple[str, str, str]] = []
        self._completion_items: list[tuple[str, str, str]] = []
        self._link_presentation_cache: dict[str, LinkPresentation] = {}
        self._last_completion_prefix: str = ""
        self._link_resolver = None  # Will be set later
        self._peek_cursor: QCursor | None = None
        self._peek_cursor_color = ""
        self._section_manager = SectionManager(self.document())
        self._current_wiki_text = ""  # Store for re-rendering on theme change

        # Enable mouse tracking for hover effects if desired
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Connect to theme changes and apply initial theme
        tm = ThemeManager()
        self._typography = EditorTypography.from_theme(tm.get_theme())
        tm.theme_changed.connect(self._on_theme_changed)

        # Remove frame from view as it's handled by wrapper
        self.setFrameShape(QFrame.Shape.NoFrame)

        # The wrapper limits the viewport to the configured reading width;
        # wrap within that viewport without splitting words at an exact column.
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_option = self.document().defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        self.document().setDefaultTextOption(text_option)

        # Force viewport transparency via Palette
        p = self.viewport().palette()
        p.setColor(self.viewport().backgroundRole(), Qt.GlobalColor.transparent)
        p.setColor(p.ColorRole.Highlight, QColor(tm.get_theme()["selection_bg"]))
        p.setColor(
            p.ColorRole.HighlightedText, QColor(tm.get_theme()["selection_text"])
        )
        self.viewport().setPalette(p)

        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(StyleHelper.get_transparent_input_style())
        self._apply_theme_stylesheet()
        self._apply_widget_style()

        # View Mode: 'rich' (HTML) or 'source' (Markdown)
        self._view_mode = "rich"
        self._visual_highlighter = WikiPresentationHighlighter(
            self.document(), self.link_presentation, tm.get_theme()
        )

        # Setup Shortcuts using QActions
        self._setup_actions()

        # Spell / grammar check (LanguageTool)
        self._setup_spell_check()

    def _setup_actions(self) -> None:
        """Setup formatting actions with shortcuts."""
        from src.gui.utils.shortcut_manager import ShortcutManager

        context = Qt.ShortcutContext.WidgetWithChildrenShortcut

        # Bold
        self.action_bold = QAction(self)
        self.action_bold.setShortcut(ShortcutManager.FORMAT_BOLD.key_sequence)
        self.action_bold.setShortcutContext(context)
        self.action_bold.triggered.connect(self._toggle_bold)
        self.addAction(self.action_bold)

        # Italic
        self.action_italic = QAction(self)
        self.action_italic.setShortcut(ShortcutManager.FORMAT_ITALIC.key_sequence)
        self.action_italic.setShortcutContext(context)
        self.action_italic.triggered.connect(self._toggle_italic)
        self.addAction(self.action_italic)

        # Headings
        self.action_h1 = QAction(self)
        self.action_h1.setShortcut(ShortcutManager.FORMAT_H1.key_sequence)
        self.action_h1.setShortcutContext(context)
        self.action_h1.triggered.connect(lambda: self._set_heading(1))
        self.addAction(self.action_h1)

        self.action_h2 = QAction(self)
        self.action_h2.setShortcut(ShortcutManager.FORMAT_H2.key_sequence)
        self.action_h2.setShortcutContext(context)
        self.action_h2.triggered.connect(lambda: self._set_heading(2))
        self.addAction(self.action_h2)

        self.action_h3 = QAction(self)
        self.action_h3.setShortcut(ShortcutManager.FORMAT_H3.key_sequence)
        self.action_h3.setShortcutContext(context)
        self.action_h3.triggered.connect(lambda: self._set_heading(3))
        self.addAction(self.action_h3)

        self.action_body = QAction(self)
        self.action_body.setShortcut(ShortcutManager.FORMAT_BODY.key_sequence)
        self.action_body.setShortcutContext(context)
        self.action_body.triggered.connect(self._clear_formatting)
        self.addAction(self.action_body)

    @Slot()
    def toggle_view_mode(self) -> None:
        """Switch presentation without turning a view change into a prose edit."""
        with QSignalBlocker(self):
            self._switch_view_mode()
        self._update_link_colors()
        self.view_mode_changed.emit(self._view_mode)

    def _switch_view_mode(self) -> None:
        """Toggles between Rich HTML view and Markdown Source view.

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

            # Apply monospace font for source editing
            from PySide6.QtGui import QFont

            mono_font = QFont("Consolas")
            if not mono_font.exactMatch():
                mono_font = QFont("Courier New")
            mono_font.setPointSize(10)
            self.setFont(mono_font)

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
        else:
            # Source -> Rich: Set view mode and force re-render via set_wiki_text
            if requires_source_mode(self.toPlainText()):
                return
            self._view_mode = "rich"

            # Reset to standard theme font
            from PySide6.QtGui import QFont

            self.setFont(QFont("Segoe UI", 10))  # Will be further refined by stylesheet

            md_text = self.toPlainText()

            # Map cursor position from MD to HTML (PlainText)
            # Build AST for cursor mapping
            parser = WikiASTParser()
            serializer = WikiASTSerializer()
            ast = parser.parse(md_text)
            _, ast = serializer.to_markdown(ast)
            _, ast = serializer.to_plaintext(ast)
            mapper = CursorMapper(ast)
            new_cursor_pos = mapper.md_to_html(old_cursor_pos)

            self.set_wiki_text(md_text, force=True)

            # Restore cursor (clamped to valid range)
            doc_length = self.document().characterCount()
            new_cursor_pos = min(new_cursor_pos, doc_length - 1)
            new_cursor_pos = max(0, new_cursor_pos)
            cursor = self.textCursor()
            cursor.setPosition(new_cursor_pos)
            self.setTextCursor(cursor)

            # Restore scroll position
            self.verticalScrollBar().setValue(old_scroll)

        self._update_link_colors()
        self.view_mode_changed.emit(self._view_mode)

    def set_link_resolver(self, link_resolver: Any) -> None:
        """Sets the link resolver for checking broken links.

        Args:
            link_resolver: LinkResolver instance for ID resolution and
                broken link detection.

        """
        self._link_resolver = link_resolver
        # Highlight Logic could be added here later
        # (iterating formats to color broken links)

    def set_completer(
        self,
        items_or_names: Optional[list[Any]] = None,
        *,
        items: Optional[list[tuple[str, str, str]]] = None,
        names: Optional[list[str]] = None,
    ) -> None:
        """Initializes or updates the completer with items.

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
                items = cast(list[tuple[str, str, str]], items_or_names)
            else:
                names = cast(list[str], items_or_names)

        if items is not None:
            self._completion_items = list(items)
            self._completion_rows = list(items)
            self._completion_map = self._unique_completion_map(items)

            # Create set of lower-case names and IDs for validation
            self._valid_targets_lower = {name.lower() for _, name, _ in items}
            self._valid_ids = {item_id for item_id, _, _ in items}

        elif names is not None:
            self._completion_items = []
            self._completion_rows = [("", name, "") for name in names]
            # Legacy mode - no ID mapping
            self._completion_map = {}
            self._valid_targets_lower = {name.lower() for name in names}
            self._valid_ids = set()
        else:
            return

        self._link_presentation_cache.clear()
        if self._completer is None:
            completer = QCompleter(self)
            completer.setWidget(self)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            # PySide exposes overload selection at runtime; its stub omits it.
            completer.activated[QModelIndex].connect(  # type: ignore[index]
                self.insert_completion_index
            )
            self._completer = completer
        model = self._completer.model()
        if not isinstance(model, QStandardItemModel):
            model = QStandardItemModel(self._completer)
            self._completer.setModel(model)
        self._populate_completion_model(model)

        # Update link colors in-place to reflect new valid-target set.
        # Using _update_link_colors() avoids a full setHtml() re-render which
        # would collapse empty blocks and reset the cursor position.
        if hasattr(self, "_view_mode") and self._view_mode == "rich":
            self._update_link_colors()

    def apply_completion_effects(self, effects: list[LoreMutationEffect]) -> None:
        """Update only changed completer rows and ID/name lookup state."""
        if self._completer is None or not hasattr(self, "_completion_items"):
            return
        model = cast(QStandardItemModel, self._completer.model())
        items = self._completion_items
        for effect in effects:
            items = apply_suggestion_effects(items, [effect])
        self._link_presentation_cache.clear()
        self._completion_items = items
        self._completion_rows = list(items)
        self._completion_map = self._unique_completion_map(items)
        self._valid_targets_lower = {name.lower() for _, name, _ in items}
        self._valid_ids = {item_id for item_id, _, _ in items}
        self._populate_completion_model(model)
        if hasattr(self, "_view_mode") and self._view_mode == "rich":
            self._update_link_colors()

    def merge_completions(self, names: list[str]) -> None:
        """Append semantic suggestion names to the completer without replacing base list.

        Deduplicates against existing names. Does nothing if the completer
        has not been initialized or the input list is empty.

        Args:
            names: Additional display names to add to the completer model.

        """
        if not self._completer or not names:
            return
        model = cast(QStandardItemModel, self._completer.model())
        current = [name for _, name, _ in self._completion_rows]
        existing = set(current)
        new_names = [n for n in names if n not in existing]
        if not new_names:
            return
        self._completion_rows.extend(("", name, "") for name in new_names)
        self._populate_completion_model(model)

    @staticmethod
    def _unique_completion_map(
        items: list[tuple[str, str, str]],
    ) -> dict[str, tuple[str, str]]:
        """Expose a name lookup only when it has one stable identity."""
        counts = Counter(name for _, name, _ in items)
        return {
            name: (item_id, item_type)
            for item_id, name, item_type in items
            if counts[name] == 1
        }

    def _populate_completion_model(self, model: QStandardItemModel) -> None:
        """Keep the popup's visible rows and identity roles in sync."""
        counts = Counter(name for _, name, _ in self._completion_rows)
        model.clear()
        for item_id, name, item_type in self._completion_rows:
            label = name
            if item_id and counts[name] > 1:
                label = f"{name} — {item_type.title()} · {item_id[:8]}"
            item = QStandardItem(label)
            item.setData((item_id, name, item_type), Qt.ItemDataRole.UserRole)
            model.appendRow(item)

    def link_presentation(self, target: str) -> LinkPresentation:
        """Return typed link meaning from the current completion snapshot."""
        if target not in self._link_presentation_cache:
            self._link_presentation_cache[target] = resolve_link_presentation(
                target,
                self._completion_items,
                getattr(self, "_valid_targets_lower", None),
            )
        return self._link_presentation_cache[target]

    def _update_link_colors(self) -> None:
        """Refresh transient layout formats without adding an undo command."""
        highlighter = self._visual_highlighter
        highlighter.rich = self._view_mode == "rich"
        highlighter.theme = ThemeManager().get_theme()
        blocked = self.blockSignals(True)
        try:
            highlighter.rehighlight()
        finally:
            self.blockSignals(blocked)
        self._refresh_document_layout()

    def _update_theme_colors(self) -> None:
        """Reapply the shared presentation layer without document mutation."""
        self._update_link_colors()

    def _apply_fragment_formats(
        self,
        updates: list[tuple[int, int, QTextCharFormat]],
    ) -> None:
        """Apply snapshotted fragment formats without mutating a live iterator.

        QTextCursor formatting can split or merge document fragments. Callers
        therefore collect positions, lengths, and copied formats before this
        method changes the document.

        Args:
            updates: Character ranges and their complete replacement formats.
        """
        if not updates:
            return

        edit_cursor = QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        try:
            for position, length, character_format in updates:
                edit_cursor.setPosition(position)
                edit_cursor.setPosition(
                    position + length,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                edit_cursor.setCharFormat(character_format)
        finally:
            edit_cursor.endEditBlock()

        self._refresh_document_layout()

    def _get_theme_css(self) -> str:
        """Build CSS stylesheet based on current theme settings.

        Retrieves current theme settings and builds CSS for headings,
        paragraphs, and links.

        Returns:
            str: CSS stylesheet as a string.

        """
        typography = self._typography
        body_top, body_bottom = typography.block_margins(0)
        h1_top, h1_bottom = typography.block_margins(1)
        h2_top, h2_bottom = typography.block_margins(2)
        h3_top, h3_bottom = typography.block_margins(3)

        # Build CSS stylesheet for the document
        css = (
            f"body {{ font-family: {typography.font_family}; "
            f"color: {typography.text_color}; font-size: {typography.body_size}pt; "
            f"line-height: {typography.line_height_percent}%; }} "
            f"a {{ color: {typography.link_color}; "
            "text-decoration: none; } "
            f"a:hover {{ color: {typography.link_hover_color}; "
            "text-decoration: underline; } "
            f"h1 {{ font-size: {typography.h1_size}pt; font-weight: 600; "
            f"color: {typography.text_color}; margin-top: {h1_top}px; "
            f"margin-bottom: {h1_bottom}px; }} "
            f"h2 {{ font-size: {typography.h2_size}pt; font-weight: 600; "
            f"color: {typography.text_color}; margin-top: {h2_top}px; "
            f"margin-bottom: {h2_bottom}px; }} "
            f"h3 {{ font-size: {typography.h3_size}pt; font-weight: 600; "
            f"color: {typography.text_color}; margin-top: {h3_top}px; "
            f"margin-bottom: {h3_bottom}px; }} "
            f"p {{ margin-top: {body_top}px; margin-bottom: {body_bottom}px; "
            f"color: {typography.text_color}; "
            f"font-size: {typography.body_size}pt; }} "
        )
        return css

    def _apply_theme_stylesheet(self) -> None:
        """Apply theme-based stylesheet to the document.

        Retrieves current theme settings and applies font sizes and colors to headings,
        paragraphs, and links.
        """
        css = self._get_theme_css()
        self.document().setDefaultStyleSheet(css)
        default_font = QFont(self._typography.primary_font_family)
        default_font.setPointSizeF(self._typography.body_size)
        self.document().setDefaultFont(default_font)
        self.document().setDocumentMargin(self._typography.document_margin)

    def _apply_document_typography(self) -> None:
        """Normalize loaded blocks with the same specification used by live edits."""
        from PySide6.QtGui import QTextBlockFormat

        document = self.document()
        edit_cursor = QTextCursor(document)
        was_blocked = self.blockSignals(True)
        try:
            edit_cursor.beginEditBlock()
            block = document.begin()
            while block.isValid():
                level = block.blockFormat().headingLevel()
                top_margin, bottom_margin = self._typography.block_margins(level)
                block_format = QTextBlockFormat(block.blockFormat())
                block_format.setTopMargin(top_margin)
                block_format.setBottomMargin(bottom_margin)
                block_format.setLineHeight(
                    self._typography.line_height_percent,
                    QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
                )
                edit_cursor.setPosition(block.position())
                edit_cursor.setBlockFormat(block_format)

                if block.length() > 1:
                    edit_cursor.setPosition(block.position())
                    edit_cursor.setPosition(
                        block.position() + block.length() - 1,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    character_format = QTextCharFormat()
                    character_format.setFontFamilies(
                        [self._typography.primary_font_family]
                    )
                    character_format.setFontPointSize(
                        self._typography.point_size(level)
                    )
                    if level > 0:
                        character_format.setFontWeight(QFont.Weight.DemiBold)
                    edit_cursor.mergeCharFormat(character_format)
                block = block.next()
            edit_cursor.endEditBlock()
        finally:
            self.blockSignals(was_blocked)
        self._refresh_document_layout()

    def _refresh_document_layout(self) -> None:
        """Invalidate rich-text layout after direct block or character changes."""
        document = self.document()
        document.markContentsDirty(0, document.characterCount())
        self.viewport().update()

    def _apply_widget_style(self) -> None:
        """Apply theme-based styling to the widget (borders, scrollbars)."""
        tm = ThemeManager()
        theme = tm.get_theme()

        scrollbar_bg = theme["scrollbar_bg"]
        scrollbar_handle = theme["scrollbar_handle"]
        primary = theme["primary"]

        from src.gui.utils.style_helper import StyleHelper

        transparent_style = StyleHelper.get_transparent_input_style()

        widget_qss = f"""
            QTextEdit {{
                {transparent_style}
                selection-background-color: {theme["selection_bg"]};
                selection-color: {theme["selection_text"]};
            }}
            QTextEdit > QWidget#qt_scrollarea_viewport {{
                border: none;
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

    def set_wiki_text(self, text: Optional[str], force: bool = False) -> None:
        """Sets the content using WikiLink syntax, converting it to HTML anchors.

        Uses the 'markdown' library for rich text rendering.
        """
        import markdown  # type: ignore[import-untyped]  # Package has no typing marker

        if text is None:
            text = ""

        switched_to_source = requires_source_mode(text) and self._view_mode != "source"
        if switched_to_source:
            self._view_mode = "source"
            self.setFont(QFont("Consolas", 10))
            self.view_mode_changed.emit("source")

        # Check if text is identical to avoid unnecessary reload
        # This applies to BOTH Rich and Source modes.
        if not force and not switched_to_source and self.get_wiki_text() == text:
            self._current_wiki_text = text
            return

        self.document_replacing.emit()

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

        # Do not store the raw incoming text here; canonicalize after rendering
        # The canonical form will be set after setHtml() to preserve linebreaks and ensure reliable equality checks

        # 1. Pre-process WikiLinks [[Target|Label]] -> Markdown [Label](Target)
        # Markdown library processes standard links [Label](URL) naturally.
        pattern = re.compile(r"\[\[([^]|]+)(?:\|([^]]+))?\]\]")

        def replace_link_md(match: re.Match) -> str:
            """Convert WikiLink syntax to Markdown link syntax.

            Checks validity of target against known items.
            """
            target = match[1].strip()
            label = match[2] if match[2] else target

            href = escape(target, quote=True)
            visible_label = escape(label)
            return f'<a href="{href}">{visible_label}</a>'

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
            self._apply_document_typography()
        finally:
            self.blockSignals(was_blocked)

        # Update internal canonical wiki text after rendering so comparisons and
        # cursor mapping respect linebreaks and rendered output
        self._current_wiki_text = self.get_wiki_text()
        self._update_link_colors()

    def get_wiki_text(self) -> str:
        """Converts the editor content back to WikiLink syntax.

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

        # Preserve trailing blank lines: count trailing empty blocks and append
        trailing_empty_count = 0
        for t in reversed(result):
            if not t.strip():
                trailing_empty_count += 1
            else:
                break

        if trailing_empty_count > 0:
            output += "\n" * trailing_empty_count

        return output

    def get_headings(self) -> List[Tuple[int, str, int]]:
        """Extracts headings from the document.

        Returns:
            A list of tuples: (heading_level, text, block_position)
        """
        headings = []
        is_source = hasattr(self, "_view_mode") and self._view_mode == "source"

        if is_source:
            # Parse raw text for headings
            text = self.toPlainText()
            lines = text.split("\n")
            pos = 0
            for line in lines:
                if line.startswith("#"):
                    stripped = line.lstrip("#")
                    level = len(line) - len(stripped)
                    if (
                        1 <= level <= _MAXIMUM_OUTLINE_HEADING_LEVEL
                        and stripped.startswith(" ")
                    ):
                        headings.append((level, stripped.strip(), pos))
                pos += len(line) + 1  # +1 for newline character
            return headings

        # Rich mode: Iterate blocks
        block = self.document().begin()
        while block.isValid():
            heading_level = block.blockFormat().headingLevel()

            # Fallback to font size heuristic (same as _process_block)
            if heading_level == 0 and block.length() > 1:
                from PySide6.QtGui import QTextCursor

                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                font_size = cursor.charFormat().fontPointSize()

                h1_size = self._typography.h1_size
                h2_size = self._typography.h2_size
                h3_size = self._typography.h3_size

                if font_size >= h1_size - 0.5:
                    heading_level = 1
                elif font_size >= h2_size - 0.5:
                    heading_level = 2
                elif font_size >= h3_size - 0.5:
                    heading_level = 3

            if heading_level > 0:
                headings.append((heading_level, block.text().strip(), block.position()))

            block = block.next()

        return headings

    def _process_block(self, block: QTextBlock) -> str:
        """Process a text block to recover block-level formatting (Headings).

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

            h1_size = self._typography.h1_size
            h2_size = self._typography.h2_size
            h3_size = self._typography.h3_size

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
        """Process a text fragment to recover inline formatting (Bold, Italic,
        Links).
        """
        text = fragment.text()
        # Qt stores <br> as \u2028 (line separator) within a block.
        # Normalise back to \n so callers always receive standard newlines.
        text = text.replace("\u2028", "\n")
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
        if not is_heading and fmt.fontWeight() > _BOLD_WEIGHT_THRESHOLD:
            text = f"**{text}**"

        # 3. Italic
        if fmt.fontItalic():
            text = f"*{text}*"

        return text

    @Slot(str)
    def insert_completion(self, completion: str) -> None:
        """Insert an unambiguous legacy completion by name."""
        matches = [row for row in self._completion_rows if row[1] == completion]
        if len(matches) != 1:
            return
        item_id, label, _ = matches[0]
        self._insert_completion_target(label, item_id)

    @Slot(QModelIndex)
    def insert_completion_index(self, index: QModelIndex) -> None:
        """Resolve the activated popup row's ID rather than its display text."""
        row = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(row, (tuple, list)) or len(row) != _COMPLETION_ROW_FIELDS:
            return
        item_id, label, _ = row
        self._insert_completion_target(label, item_id)

    def _insert_completion_target(self, label: str, item_id: str) -> None:
        """Replace the typed token with a semantic anchor and clean spacing."""
        tc = self.textCursor()
        if not self._completer:
            return
        prefix_len = len(self._completer.completionPrefix())

        # We need to remove the "[[" that triggered this + prefix
        # We assume cursor is after "[[Prefix"
        # Move left prefix_len
        tc.movePosition(
            QTextCursor.MoveOperation.Left,
            QTextCursor.MoveMode.KeepAnchor,
            prefix_len,
        )
        start, end = tc.selectionStart(), tc.selectionEnd()
        probe = QTextCursor(self.document())
        probe.setPosition(max(0, start - 2))
        probe.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        if probe.selectedText() == "[[":
            start -= 2
        tc.setPosition(start)
        tc.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.insert_entry_link(tc, label, item_id, separate_following_word=True)

    def insert_entry_link(
        self,
        cursor: QTextCursor,
        label: str,
        item_id: str,
        *,
        preserve_selection: bool = False,
        separate_following_word: bool = False,
    ) -> None:
        """Insert one reversible link, preserving selected rich formatting."""
        if (
            self.isReadOnly()
            or not label
            or any(char in label for char in "\n\r\u2028\u2029[]|")
        ):
            return
        tc = QTextCursor(cursor)
        target = f"id:{item_id}" if item_id else label
        continuation = QTextCharFormat(tc.charFormat())
        continuation.setAnchor(False)
        continuation.setAnchorHref("")
        continuation.setForeground(QColor(self._typography.text_color))
        continuation.setFontUnderline(False)
        link_format = QTextCharFormat(continuation)
        link_format.setAnchor(True)
        link_format.setAnchorHref(target)
        link_format.setForeground(QColor(self._typography.link_color))
        tc.beginEditBlock()
        if self._view_mode == "source":
            tc.insertText(
                f"[[{target}|{label}]]" if item_id else f"[[{label}]]", continuation
            )
        elif preserve_selection and tc.hasSelection():
            semantic = QTextCharFormat()
            semantic.setAnchor(True)
            semantic.setAnchorHref(target)
            semantic.setForeground(QColor(self._typography.link_color))
            tc.mergeCharFormat(semantic)
            tc.setPosition(tc.selectionEnd())
        else:
            tc.insertText(label, link_format)
        if (
            separate_following_word
            and str(self.document().characterAt(tc.position())).isalnum()
        ):
            tc.insertText(" ", continuation)
        tc.setCharFormat(continuation)
        tc.endEditBlock()
        self.setTextCursor(tc)
        self.setCurrentCharFormat(continuation)
        self._refresh_document_layout()

    def link_target_at_cursor(self, cursor: QTextCursor | None = None) -> str:
        """Resolve one link at the caret or selection in either writing mode."""
        cursor = self.textCursor() if cursor is None else cursor
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        if self._view_mode == "source":
            from src.services.text_parser import WikiLinkParser

            source = self.toPlainText()
            for link in WikiLinkParser.extract_links(source):
                left = len(source[: link.span[0]].encode("utf-16-le")) // 2
                right = len(source[: link.span[1]].encode("utf-16-le")) // 2
                if left <= start < right and end <= right:
                    return f"id:{link.target_id}" if link.target_id else link.name or ""
            return ""
        targets = set()
        positions = range(start, end) if start != end else range(start, start + 1)
        for position in positions:
            probe = QTextCursor(self.document())
            probe.setPosition(position)
            probe.movePosition(
                QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
            )
            fmt = probe.charFormat()
            if not fmt.isAnchor():
                return ""
            targets.add(fmt.anchorHref())
        return targets.pop() if len(targets) == 1 else ""

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handles key press events for wiki link completion and formatting shortcuts.

        Supports:
        - Ctrl+B: Toggle bold
        - Ctrl+I: Toggle italic

        Args:
            event: QKeyEvent from PySide6.

        """
        self._refresh_modifier_cursor(event)
        # Check for formatting shortcuts first
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

        is_source_mode = hasattr(self, "_view_mode") and self._view_mode == "source"
        if not is_source_mode and event.text() and not self.textCursor().hasSelection():
            cursor = self.textCursor()
            probe = QTextCursor(cursor)
            probe.movePosition(
                QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
            )
            current = cursor.charFormat()
            if current.isAnchor() and (
                cursor.atEnd()
                or probe.charFormat().anchorHref() != current.anchorHref()
            ):
                current.setAnchor(False)
                current.setAnchorHref("")
                current.setForeground(QColor(self._typography.text_color))
                current.setFontUnderline(False)
                self.setCurrentCharFormat(current)
        is_enter = event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        )
        reset_heading_after_enter = (
            not is_source_mode
            and is_enter
            and self.textCursor().blockFormat().headingLevel() > 0
        )

        super().keyPressEvent(event)

        # A paragraph created from a heading can inherit its character format.
        # Use the semantic block property rather than a theme-dependent size
        # heuristic to decide whether the new paragraph must become body text.
        if reset_heading_after_enter:
            self._set_heading(0)

        # Check if user just closed a wiki link with ]]
        if event.text() == "]" and not is_source_mode:
            self._check_for_link_closure()

        # Helper to trigger completer
        self._check_for_completion()

    def _toggle_bold(self) -> None:
        """Toggle bold formatting on selected text or at cursor position.

        In Source mode: wraps/unwraps selection with **
        In Rich mode: applies/removes bold QTextCharFormat
        """
        if self._view_mode == "source":
            self._toggle_markdown_format("**")
        else:
            self._toggle_rich_format("bold")

    def _toggle_italic(self) -> None:
        """Toggle italic formatting on selected text or at cursor position.

        In Source mode: wraps/unwraps selection with *
        In Rich mode: applies/removes italic QTextCharFormat
        """
        if self._view_mode == "source":
            self._toggle_markdown_format("*")
        else:
            self._toggle_rich_format("italic")

    def _clear_formatting(self) -> None:
        """Removes all formatting (headings, bold, italic) from selection."""
        if self._view_mode == "source":
            self._clear_source_formatting()
        else:
            self._clear_rich_formatting()

    def _clear_source_formatting(self) -> None:
        """Removes markdown formatting markers from selection."""
        cursor = self.textCursor()
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        has_sel = cursor.hasSelection()

        # 1. Handle Headings (current line if no selection, or all lines in selection)
        # For simplicity, we clear heading on the current line first if it's
        # a simple toggle, but if there's a selection, we should probably
        # iterate lines or just do the current line.
        # Following existing _set_heading pattern: current line.
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        line_text = cursor.selectedText()
        stripped_line = line_text.lstrip("#").lstrip()
        cursor.insertText(stripped_line)

        # 2. Handle Inline Formatting (Selection only)
        if not has_sel:
            return

        # Re-select the area (adjust for heading shift if necessary)
        # If we removed '#' from the start of the line, sel_start/end might shift.
        # But we'll just use the same coordinates for now.
        cursor.setPosition(sel_start)
        cursor.setPosition(sel_end, QTextCursor.MoveMode.KeepAnchor)

        text = cursor.selectedText()
        # Remove bold/italic markers while keeping content
        # Matches: **text**, __text__, *text*, _text_
        # We use a loop to handle nested markers like ***text***
        clean_text = text
        while True:
            temp = re.sub(r"(\*\*|__|\*|_)(.*?)\1", r"\2", clean_text)
            if temp == clean_text:
                break
            clean_text = temp

        cursor.insertText(clean_text)
        self.setTextCursor(cursor)

    def _clear_rich_formatting(self) -> None:
        """Resets block and character formatting in Rich mode."""
        cursor = self.textCursor()

        # 1. Reset Block Level (Heading -> Paragraph)
        self._set_rich_heading(0)

        # 2. Reset Character Formatting (Bold/Italic/Size)
        from PySide6.QtGui import QFont, QTextCharFormat

        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setFontItalic(False)
        fmt.setFontFamilies([self._typography.primary_font_family])
        fmt.setFontPointSize(self._typography.body_size)

        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            # If no selection, set for future typing
            self.mergeCurrentCharFormat(fmt)

        self.setTextCursor(cursor)

    def _set_heading(self, level: int) -> None:
        """Set heading level on the current line.

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
        """Set Markdown heading on current line.

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
        """Set heading style in Rich mode.

        Args:
            level: Heading level (1-3) or 0 for paragraph.

        """
        original_cursor = self.textCursor()
        cursor_position = original_cursor.position()
        cursor_anchor = original_cursor.anchor()
        scroll_position = self.verticalScrollBar().value()
        previous_level = original_cursor.blockFormat().headingLevel()
        cursor = QTextCursor(original_cursor)

        # Select entire current block to apply block format
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )

        font_size = self._typography.point_size(level)

        from PySide6.QtGui import QTextBlockFormat

        block_fmt = QTextBlockFormat()
        block_fmt.setHeadingLevel(level)

        top_margin, bottom_margin = self._typography.block_margins(level)
        block_fmt.setTopMargin(top_margin)
        block_fmt.setBottomMargin(bottom_margin)
        block_fmt.setLineHeight(
            self._typography.line_height_percent,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )

        cursor.setBlockFormat(block_fmt)

        self._apply_live_heading_character_format(cursor.block(), level, font_size)

        # Qt keeps the CSS box metrics from the heading tag loaded by setHtml(),
        # even after the semantic block level and fragment formats are changed.
        # Rebuild only heading-to-heading transitions so the new selector is
        # applied without exposing the usual body-to-heading path to a rerender.
        if previous_level > 0 and level > 0 and previous_level != level:
            updated_text = self.get_wiki_text()
            self.set_wiki_text(updated_text, force=True)
            maximum_position = self.document().characterCount() - 1
            restored_cursor = self.textCursor()
            restored_cursor.setPosition(min(cursor_anchor, maximum_position))
            restored_cursor.setPosition(
                min(cursor_position, maximum_position),
                QTextCursor.MoveMode.KeepAnchor,
            )
            self.setTextCursor(restored_cursor)
            self.verticalScrollBar().setValue(scroll_position)

        # Body-to-heading changes need no round-trip: applying the semantic block
        # and character formats directly preserves empty lines and cursor state.

    def _apply_live_heading_character_format(
        self,
        block: QTextBlock,
        level: int,
        font_size: float,
    ) -> None:
        """Apply heading typography to every existing fragment in a block.

        Loaded HTML contains explicit fragment-level font properties. Updating
        each copied format ensures those properties are replaced immediately
        while anchors, emphasis, foreground colors, and other inline metadata
        remain intact.

        Args:
            block: Block receiving the body or heading typography.
            level: Semantic heading level, or zero for body text.
            font_size: Resolved editor point size for the level.
        """
        weight = QFont.Weight.DemiBold if level > 0 else QFont.Weight.Normal
        updates: list[tuple[int, int, QTextCharFormat]] = []
        iterator = block.begin()

        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                fragment_format = QTextCharFormat(fragment.charFormat())
                fragment_format.setFontFamilies([self._typography.primary_font_family])
                fragment_format.setFontPointSize(font_size)
                fragment_format.setFontWeight(weight)
                updates.append(
                    (
                        fragment.position(),
                        fragment.length(),
                        fragment_format,
                    )
                )
            iterator += 1

        if updates:
            self._apply_fragment_formats(updates)
        else:
            insertion_format = QTextCharFormat(self.currentCharFormat())
            insertion_format.setFontFamilies([self._typography.primary_font_family])
            insertion_format.setFontPointSize(font_size)
            insertion_format.setFontWeight(weight)
            self.setCurrentCharFormat(insertion_format)
            self._refresh_document_layout()

    def _toggle_markdown_format(self, marker: str) -> None:
        """Toggle Markdown formatting markers around selection.

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
        """Toggle rich text formatting on selection.

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
        """Check if user just completed a wiki link with ]].

        If so, validate and style the link immediately.
        """
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()

        # Check if previous char was also ]
        if pos_in_block < _WIKI_LINK_CLOSING_TOKEN_LENGTH:
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
            target, label = link_content.split("|", 1)
            target = target.strip()
        else:
            target = label = link_content.strip()

        if not target:
            return

        # Validate the target
        is_valid = self._validate_link_target(target)

        # Preserve the format that should continue after the link. QTextCursor
        # adopts the anchor format inserted by insertHtml(), which would make
        # all subsequently typed text part of the WikiLink unless we restore
        # the pre-link insertion format explicitly.
        continuation_format = QTextCharFormat(cursor.charFormat())
        continuation_format.setAnchor(False)
        continuation_format.setAnchorHref("")

        # Replace the [[...]] with a styled anchor
        # Calculate absolute positions
        block_start = cursor.block().position()
        abs_start = block_start + bracket_start
        abs_end = block_start + link_end

        # Select the [[...]] text
        cursor.setPosition(abs_start)
        cursor.setPosition(abs_end, QTextCursor.MoveMode.KeepAnchor)

        link_format = QTextCharFormat(continuation_format)
        link_format.setAnchor(True)
        link_format.setAnchorHref(target)
        if not is_valid:
            link_format.setForeground(QColor(self._typography.broken_link_color))
        cursor.insertText(label, link_format)
        cursor.setCharFormat(continuation_format)
        self.setTextCursor(cursor)
        self._refresh_document_layout()

    def _validate_link_target(self, target: str) -> bool:
        """Validate a link target against known items.

        Args:
            target: The link target (name or id:UUID format).

        Returns:
            bool: True if valid, False if broken/non-existent.

        """
        return self.link_presentation(target).resolved

    def paintEvent(self, event: QPaintEvent) -> None:
        """Override paintEvent to draw section color gutters.

        This queries the SectionData from each visible block and draws
        a 4px wide vertical line along its left edge.
        """
        # First let the default text editor rendering happen
        super().paintEvent(event)

        # We only draw gutters in rich mode to avoid clashes with markdown hashes
        if (
            getattr(self, "_view_mode", "rich") == "source"
            or not self._typography.show_section_gutter
        ):
            return

        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPainter

        from src.gui.utils.color_utils import get_hashed_color

        painter = QPainter(self.viewport())

        # Iterate over visible blocks
        cursor = self.cursorForPosition(QPoint(0, 0))
        block = cursor.block()

        # Get viewport rect for bounds checking
        viewport_rect = self.viewport().rect()

        while block.isValid():
            block_rect = self.document().documentLayout().blockBoundingRect(block)
            # Offset by scrollbar positions
            v_offset = self.verticalScrollBar().value()
            block_rect.translate(0, -v_offset)

            # Check if block is visible
            if block_rect.top() > viewport_rect.bottom():
                break

            if block_rect.bottom() >= viewport_rect.top():
                # Block is visible, check user data
                data = block.userData()
                if isinstance(data, SectionData) and data.section_id:
                    # Determine color
                    color = get_hashed_color(data.section_id)

                    # Draw rect
                    # Width: 4px. Height: full block height minus tiny padding
                    # X: a few pixels from the absolute left margin
                    gutter_rect = block_rect.toRect()
                    gutter_rect.setX(8)
                    gutter_rect.setWidth(4)

                    # Optional: slight vertical padding so blocks don't touch seamlessly
                    gutter_rect.setTop(gutter_rect.top() + 1)
                    gutter_rect.setBottom(gutter_rect.bottom() - 1)

                    painter.fillRect(gutter_rect, color)

            block = block.next()

    def _check_for_completion(self) -> None:
        """Checks if wiki link completion should be triggered.

        Looks backwards from cursor position for "[[" pattern and shows completion popup
        if found without a closing "]]".
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
                if (
                    len(prefix) >= SEMANTIC_COMPLETION_MIN_PREFIX_LEN
                    and prefix != self._last_completion_prefix
                ):
                    self._last_completion_prefix = prefix
                    self.completion_prefix_changed.emit(prefix)
        elif self._completer and (popup := self._completer.popup()):
            popup.hide()
            self._last_completion_prefix = ""

    def _show_completion_popup(self, popup: QAbstractItemView, prefix: str) -> None:
        """Helper to position and show completion popup."""
        completer = self._completer
        if completer is None:
            return
        completer.setCompletionPrefix(prefix)
        curr_rect = self.cursorRect()

        scroll_bar = popup.verticalScrollBar()
        sb_width = scroll_bar.sizeHint().width() if scroll_bar else 0

        curr_rect.setWidth(popup.sizeHintForColumn(0) + sb_width)
        completer.complete(curr_rect)

    def _link_target_at_point(self, point: QPoint) -> str:
        """Resolve the same link under the pointer in Rich and Source views."""
        if self._view_mode == "source":
            return self.link_target_at_cursor(self.cursorForPosition(point))
        return self.anchorAt(point)

    def _peek_link_cursor(self) -> QCursor:
        """Use the shared eye icon and supporting-action theme role for Peek."""
        color = ThemeManager().get_theme()["supporting_text"]
        if self._peek_cursor is None or color != self._peek_cursor_color:
            icon = load_icon("default_assets/icons/ui_icons/eye.svg", color=color)
            pixmap = icon.pixmap(_PEEK_CURSOR_SIZE, _PEEK_CURSOR_SIZE)
            self._peek_cursor = QCursor(
                pixmap, _PEEK_CURSOR_SIZE // 2, _PEEK_CURSOR_SIZE // 2
            )
            self._peek_cursor_color = color
        return self._peek_cursor

    def _update_link_cursor(
        self, point: QPoint, modifiers: Qt.KeyboardModifier
    ) -> None:
        """Distinguish Peek, Open and ordinary writing without moving the caret."""
        target = self._link_target_at_point(point)
        if target and modifiers & Qt.KeyboardModifier.AltModifier:
            self.viewport().setCursor(self._peek_link_cursor())
        elif target and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def _refresh_modifier_cursor(
        self, event: QKeyEvent, *, released: bool = False
    ) -> None:
        """Refresh a stationary link hover when its navigation modifier changes."""
        modifiers_by_key: dict[int, Qt.KeyboardModifier] = {
            Qt.Key.Key_Alt: Qt.KeyboardModifier.AltModifier,
            Qt.Key.Key_Control: Qt.KeyboardModifier.ControlModifier,
        }
        modifier = modifiers_by_key.get(event.key())
        if modifier is None:
            return
        point = self.viewport().mapFromGlobal(QCursor.pos())
        if not self.viewport().rect().contains(point):
            return
        modifiers = event.modifiers()
        modifiers = modifiers & ~modifier if released else modifiers | modifier
        self._update_link_cursor(point, modifiers)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """End the modifier cursor cue without consuming ordinary key release."""
        super().keyReleaseEvent(event)
        self._refresh_modifier_cursor(event, released=True)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handles mouse move events to show pointer cursor over links.

        Args:
            event: QMouseEvent from PySide6.

        """
        point = event.position().toPoint()
        target = self._link_target_at_point(point)
        self.setToolTip(self.link_presentation(target).tooltip if target else "")
        if target and event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            self._update_link_cursor(point, event.modifiers())
            return
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handles mouse release events for Ctrl+Click navigation.

        Args:
            event: QMouseEvent from PySide6.

        """
        anchor = self._link_target_at_point(event.position().toPoint())
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            and anchor
        ):
            # Handle ID checking
            target = anchor.split("|")[0]
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.peek_requested.emit(target)
            else:
                if target.startswith("id:"):
                    target = target[3:]
                self.link_clicked.emit(target)
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------ #
    #  Spell / grammar check (LanguageTool)                               #
    # ------------------------------------------------------------------ #

    def _setup_spell_check(self) -> None:
        """Configure lazy LanguageTool spell/grammar checking."""
        from PySide6.QtWidgets import QApplication

        self._lt_matches: list = []
        self._lt_matches_revision: int | None = None
        self._lt_checked_text = ""
        self._lt_request_id = 0
        self._lt_pending_text = ""
        self._lt_thread: Optional[QThread] = None
        self._lt_worker: Optional[QObject] = None
        self.document().contentsChanged.connect(self.clear_spell_check)

        self._lt_timer = QTimer(self)
        self._lt_timer.setSingleShot(True)
        self._lt_timer.setInterval(800)
        self._lt_timer.timeout.connect(self._trigger_lt_check)
        self.textChanged.connect(self._lt_timer.start)

        # Ensure the worker thread is stopped cleanly on app shutdown so Qt
        # does not abort with "QThread: Destroyed while thread is still running".
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_spell_check)

    def _ensure_spell_check_worker(self) -> None:
        """Create and start the LanguageTool worker on first use."""
        thread = self._lt_thread
        if thread is not None and thread.isRunning():
            return

        from src.services.language_tool_service import LanguageToolWorker

        thread = QThread(self)
        worker = LanguageToolWorker()
        worker.moveToThread(thread)
        worker.revision_results_ready.connect(self._on_lt_results)
        self._lt_check_requested.connect(
            worker.check_revision,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.finished.connect(worker.deleteLater)
        self._lt_thread = thread
        self._lt_worker = worker
        thread.start()

    def _shutdown_spell_check(self) -> None:
        """Stop the spell-check worker thread if still running.

        Safe to call multiple times. Invoked on QApplication.aboutToQuit and
        can be called explicitly by tests.
        """
        self._lt_timer.stop()
        thread = self._lt_thread
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        except RuntimeError:
            # Underlying C++ object already deleted — nothing to do.
            pass
        finally:
            self._lt_thread = None
            self._lt_worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop background spell-check work before the editor is destroyed."""
        self._shutdown_spell_check()
        super().closeEvent(event)

    def _lt_settings(self) -> dict:
        """Read spell check settings from QSettings."""
        from PySide6.QtCore import QSettings

        s = QSettings()
        s.beginGroup("SpellCheck")
        result = {
            "enabled": s.value("enabled", False, type=bool),
            "language": s.value("language", "auto"),
            "username": s.value("username", ""),
            "api_key": s.value("api_key", ""),
        }
        s.endGroup()
        return result

    def _trigger_lt_check(self) -> None:
        """Fire a LanguageTool check after the debounce timer fires."""
        settings = self._lt_settings()
        if not settings["enabled"]:
            return
        # IMPORTANT: send ``toPlainText()`` rather than the raw WikiLink/Markdown
        # source. Offsets returned by LanguageTool are used to position cursors
        # inside ``self.document()``; in rich mode the document contains the
        # rendered text, not the raw markdown, so offsets computed from the raw
        # source would be misaligned and underlines would land on the wrong span.
        text = self.toPlainText()
        if len(text.strip()) < _MINIMUM_SPELLCHECK_TEXT_LENGTH:
            self._lt_matches = []
            self.setExtraSelections([])
            return
        self._ensure_spell_check_worker()
        self._lt_request_id += 1
        revision = self.document().revision()
        self._lt_pending_text = text
        self._lt_check_requested.emit(
            self._lt_request_id,
            revision,
            text,
            settings["language"],
            settings.get("username", ""),
            settings.get("api_key", ""),
        )

    @Slot(int, int, list)
    def _on_lt_results(
        self, request_id: int, document_revision: int, matches: list
    ) -> None:
        """Discard delayed or reordered matches for a different document."""
        if (
            request_id != self._lt_request_id
            or document_revision != self.document().revision()
            or self._lt_pending_text != self.toPlainText()
        ):
            return
        self._apply_lt_results(matches)

    def _apply_lt_results(self, matches: list) -> None:
        """Apply LanguageTool matches as wavy underline ExtraSelections.

        Args:
            matches: List of LTMatch objects from the worker.

        """
        self._lt_matches = matches
        self._lt_matches_revision = self.document().revision()
        self._lt_checked_text = self.toPlainText()
        tm = ThemeManager()
        theme = tm.get_theme()
        error_color = theme["error"]

        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor(error_color))

        selections = []
        for m in matches:
            cursor = QTextCursor(self.document())
            cursor.setPosition(m.offset)
            cursor.setPosition(m.offset + m.length, QTextCursor.MoveMode.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            setattr(sel, "cursor", cursor)
            setattr(sel, "format", fmt)
            selections.append(sel)
        self.setExtraSelections(selections)

    def clear_spell_check(self) -> None:
        """Remove all spell check underlines and cached matches."""
        self._lt_matches = []
        self._lt_matches_revision = None
        self._lt_checked_text = ""
        self.setExtraSelections([])

    def contextMenuEvent(self, event: Any) -> None:
        """Show context menu, prepending spell check suggestions when applicable.

        Args:
            event: The context menu event.

        """
        cursor_pos = self.cursorForPosition(event.pos()).position()
        anchor = self.anchorAt(event.pos())
        if self._view_mode == "source":
            anchor = self.link_target_at_cursor(self.cursorForPosition(event.pos()))
        hit = next(
            (
                m
                for m in self._lt_matches
                if m.offset <= cursor_pos < m.offset + m.length
            ),
            None,
        )

        if not hit:
            menu = self.createStandardContextMenu()
            self._add_link_menu_actions(menu, anchor)
            self._show_context_menu(menu, event.globalPos())
            return

        # Build a new menu: spell suggestions first, then standard items.
        # Keep ``standard`` alive as a local — exec() blocks so the actions
        # owned by ``standard`` remain valid for the lifetime of the popup.
        # Do NOT reparent ``standard`` to ``menu``; a child QMenu renders
        # itself alongside its parent, causing a duplicate overlay.
        menu = QMenu(self)
        self._add_link_menu_actions(menu, anchor)
        standard = self.createStandardContextMenu()  # noqa: F841 — kept alive intentionally

        if hit.replacements:
            for suggestion in hit.replacements[:5]:
                action = menu.addAction(suggestion)
                action.triggered.connect(
                    lambda _, s=suggestion, m=hit: self._apply_lt_suggestion(s, m)
                )
            menu.addSeparator()

        ignore_action = menu.addAction(f"Ignore ({hit.rule_id})")
        ignore_action.triggered.connect(lambda _, m=hit: self._ignore_lt_match(m))
        menu.addSeparator()

        for action in standard.actions():
            menu.addAction(action)

        self._show_context_menu(menu, event.globalPos())

    def _add_link_menu_actions(self, menu: QMenu, anchor: str) -> None:
        """Share link operations between standard and spell-check menus."""
        menu.addSeparator()
        action = menu.addAction("Link to entry…", self.link_to_entry_requested.emit)
        action.setEnabled(not self.isReadOnly())
        target = anchor or self.link_target_at_cursor()
        if target:
            menu.addAction("Open link", lambda: self.link_clicked.emit(target))
            menu.addAction(
                "Peek link (Alt+Click)", lambda: self.peek_requested.emit(target)
            )

    @staticmethod
    def _show_context_menu(menu: QMenu, global_pos: Any) -> None:
        """Display a context menu.

        Kept as a small seam so widget tests can inspect menus without entering
        Qt's blocking modal event loop.
        """
        menu.exec(global_pos)

    def _apply_lt_suggestion(self, replacement: str, match: Any) -> None:
        """Replace the matched span with a chosen suggestion.

        Args:
            replacement: The replacement text to insert.
            match: The LTMatch whose span should be replaced.

        """
        if (
            match not in self._lt_matches
            or self._lt_matches_revision != self.document().revision()
            or self._lt_checked_text != self.toPlainText()
        ):
            return
        cursor = QTextCursor(self.document())
        cursor.setPosition(match.offset)
        cursor.setPosition(match.offset + match.length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        self._ignore_lt_match(match)

    def _ignore_lt_match(self, match: Any) -> None:
        """Remove a match from the active list and refresh underlines.

        Args:
            match: The LTMatch to ignore.

        """
        self._lt_matches = [m for m in self._lt_matches if m is not match]
        self._apply_lt_results(self._lt_matches)

    @Slot(dict)
    def _on_theme_changed(self, theme_data: dict) -> None:
        """Apply theme colors without rebuilding the authoring document.

        Args:
            theme_data: Dictionary containing theme settings (unused,
                        as we fetch fresh from ThemeManager).

        """
        if not shiboken6.isValid(self):
            return

        # Update widget styling (scrollbars, borders)
        palette = self.viewport().palette()
        palette.setColor(
            palette.ColorRole.Highlight, QColor(theme_data["selection_bg"])
        )
        palette.setColor(
            palette.ColorRole.HighlightedText, QColor(theme_data["selection_text"])
        )
        self.viewport().setPalette(palette)
        if self.viewport().cursor().shape() == Qt.CursorShape.BitmapCursor:
            self.viewport().setCursor(self._peek_link_cursor())
        self._typography = EditorTypography.from_theme(theme_data)
        self._apply_widget_style()

        self._apply_theme_stylesheet()
        if self._view_mode == "rich":
            self._update_theme_colors()
        self._refresh_document_layout()


class SpellCheckSettingsDialog(QDialog):
    """Settings dialog for the LanguageTool spell/grammar check feature.

    Allows the user to opt in, choose a language, and optionally provide
    premium credentials for the LanguageTool public API.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Optional parent widget.
        """
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import (
            QComboBox,
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
        )

        from src.core.theme_manager import ThemeManager
        from src.gui.utils.style_helper import StyleHelper
        from src.gui.widgets.standard_buttons import (
            PrimaryButton,
            StandardButton,
            StandardCheckbox,
        )

        super().__init__(parent)
        self.setWindowTitle("Spell & Grammar Check")
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._apply_style()
        ThemeManager().theme_changed.connect(self._apply_style)

        layout = QVBoxLayout(self)
        StyleHelper.apply_standard_list_spacing(layout)

        # Enable toggle
        self._enabled_cb = StandardCheckbox("Enable spell & grammar checking")
        layout.addWidget(self._enabled_cb)

        # Language selector
        lang_group = QGroupBox("Language")
        lang_form = QFormLayout(lang_group)
        StyleHelper.apply_standard_list_spacing(lang_form)
        self._language_combo = QComboBox()
        self._language_combo.setEditable(True)
        self._language_combo.addItems(
            ["auto", "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "pt-BR", "it-IT"]
        )
        self._language_combo.setStyleSheet(StyleHelper.get_input_field_style())
        lang_form.addRow("Language:", self._language_combo)
        layout.addWidget(lang_group)

        # Premium group
        premium_group = QGroupBox("Premium Account (optional)")
        premium_layout = QFormLayout(premium_group)
        StyleHelper.apply_standard_list_spacing(premium_layout)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("your@email.com")
        self._username_edit.setStyleSheet(StyleHelper.get_input_field_style())
        premium_layout.addRow("Username:", self._username_edit)

        self._apikey_edit = QLineEdit()
        self._apikey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apikey_edit.setPlaceholderText("API key")
        self._apikey_edit.setStyleSheet(StyleHelper.get_input_field_style())
        premium_layout.addRow("API Key:", self._apikey_edit)

        layout.addWidget(premium_group)

        # Info label
        info = QLabel(
            'Uses the <a href="https://languagetool.org">LanguageTool</a> public API. '
            "Free tier: 20 req/min, 20 KB/request."
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = StandardButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        save_btn = PrimaryButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # Load current settings
        s = QSettings()
        s.beginGroup("SpellCheck")
        self._enabled_cb.setChecked(cast(bool, s.value("enabled", False, type=bool)))
        lang = cast(str, s.value("language", "auto"))
        idx = self._language_combo.findText(lang)
        if idx >= 0:
            self._language_combo.setCurrentIndex(idx)
        else:
            self._language_combo.setCurrentText(lang)
        self._username_edit.setText(cast(str, s.value("username", "")))
        self._apikey_edit.setText(cast(str, s.value("api_key", "")))
        s.endGroup()

    def _apply_style(self) -> None:
        """Apply the current theme stylesheet to this dialog."""
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(
            StyleHelper.get_dialog_base_style() + StyleHelper.get_scrollbar_style()
        )

    def _save(self) -> None:
        """Persist settings to QSettings and close the dialog."""
        from PySide6.QtCore import QSettings

        s = QSettings()
        s.beginGroup("SpellCheck")
        s.setValue("enabled", self._enabled_cb.isChecked())
        s.setValue("language", self._language_combo.currentText())
        s.setValue("username", self._username_edit.text())
        s.setValue("api_key", self._apikey_edit.text())
        s.endGroup()
        self.accept()


class WikiTextEdit(QFrame):
    """Wrapper Frame for WikiTextEditView to ensure correct border styling.

    Composes WikiTextEditView inside a styled QFrame.
    """

    link_clicked = Signal(str)
    peek_requested = Signal(str)
    completion_prefix_changed = Signal(str)
    minimum_width_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the wiki text edit wrapper widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("WikiTextEditWrapper")  # For debugging/styling
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Layout Hierarchy
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Editor View (must be created before Toolbar to link actions)
        self.editor = WikiTextEditView(self)
        self._adaptive_width = False

        # Toolbar
        self.toolbar = QToolBar("Editor Formatting", self)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self._setup_toolbar()
        main_layout.addWidget(self.toolbar)
        self._setup_link_controls(main_layout)
        self.source_notice = QLabel(
            "Exact Markdown source. Rich view requires the supported syntax only."
        )
        self.source_notice.setWordWrap(True)
        self.source_notice.hide()
        main_layout.addWidget(self.source_notice)

        # Content Container (TOC + Editor)
        content_container = QWidget(self)
        content_layout = QHBoxLayout(content_container)
        self._content_layout = content_layout
        content_layout.setContentsMargins(1, 1, 1, 1)  # Padding for border
        content_layout.setSpacing(0)

        # TOC Widget
        from src.gui.widgets.toc_widget import TOCWidget

        self.toc_widget = TOCWidget(self)
        self.toc_widget.setFixedWidth(200)
        self.toc_widget.hide()

        # Subtle right border for TOC since it's on the left
        style = self.toc_widget.styleSheet()
        border_color = ThemeManager().get_theme()["border"]
        self.toc_widget.setStyleSheet(
            style + f"\nTOCWidget {{ border-right: 1px solid {border_color}; }}"
        )
        content_layout.addWidget(self.toc_widget)
        content_layout.addWidget(self.editor, stretch=1)

        main_layout.addWidget(content_container, stretch=1)

        # Forward signals
        self.editor.link_clicked.connect(self.link_clicked.emit)
        self.editor.peek_requested.connect(self.peek_requested.emit)
        self.editor.completion_prefix_changed.connect(
            self.completion_prefix_changed.emit
        )
        self.editor.view_mode_changed.connect(self._sync_mode_action)

        # Expose textChanged signal directly from editor
        self.textChanged = self.editor.textChanged

        # Connect TOC signals
        self.textChanged.connect(self._update_toc)
        self.toc_widget.header_clicked.connect(self._scroll_to_header)

        # Apply Style
        self._apply_style()

        # Connect to theme changes
        ThemeManager().theme_changed.connect(self._on_theme_changed)
        self._apply_editor_width_limit()

    def _apply_editor_width_limit(self) -> None:
        """Set the minimum width for the text column and visible editor chrome."""
        typography = self.editor._typography
        character_width = QFontMetricsF(
            self.editor.document().defaultFont()
        ).averageCharWidth()
        text_width = round(character_width * typography.line_length)
        document_margins = round(self.editor.document().documentMargin() * 2)
        scrollbar_width = self.editor.verticalScrollBar().sizeHint().width()
        frame_padding = 6
        toc_width = self.toc_widget.width() if not self.toc_widget.isHidden() else 0
        minimum_width = (
            text_width + document_margins + scrollbar_width + frame_padding + toc_width
        )
        if self._adaptive_width:
            minimum_width = 120
        if minimum_width != self.minimumWidth():
            self.setMinimumWidth(minimum_width)
            self.minimum_width_changed.emit(minimum_width)

    def set_adaptive_width(self, enabled: bool) -> None:
        """Allow inspector text to wrap below the preferred reading width."""
        self._adaptive_width = enabled
        self._apply_editor_width_limit()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """Stack an open contents list in narrow adaptive inspectors."""
        super().resizeEvent(event)
        if self._adaptive_width:
            from PySide6.QtWidgets import QBoxLayout

            from src.gui.widgets.editor_presentation import COMPACT_EDITOR_WIDTH

            compact = self.width() < COMPACT_EDITOR_WIDTH
            self._content_layout.setDirection(
                QBoxLayout.Direction.TopToBottom
                if compact
                else QBoxLayout.Direction.LeftToRight
            )
            self.toc_widget.setMinimumWidth(0 if compact else 200)
            self.toc_widget.setMaximumWidth(16777215 if compact else 200)
            self.toc_widget.setMaximumHeight(120 if compact else 16777215)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop the child editor's worker before closing the wrapper."""
        self.editor._shutdown_spell_check()
        super().closeEvent(event)

    def _setup_toolbar(self) -> None:
        """Configure the editor toolbar."""
        # Formatting Actions
        self.toolbar.addAction(self.editor.action_bold)
        self.editor.action_bold.setText("Bold")
        self.toolbar.addAction(self.editor.action_italic)
        self.editor.action_italic.setText("Italic")

        self.toolbar.addSeparator()

        self.toolbar.addAction(self.editor.action_h1)
        self.editor.action_h1.setText("H1")
        self.toolbar.addAction(self.editor.action_h2)
        self.editor.action_h2.setText("H2")
        self.toolbar.addAction(self.editor.action_h3)
        self.editor.action_h3.setText("H3")

        self.toolbar.addAction(self.editor.action_body)
        self.editor.action_body.setText("Body")

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Preferred
        )
        self.toolbar.addWidget(spacer)

        # Mode Toggle
        self.action_toggle_mode = self.toolbar.addAction("MD")
        self.action_toggle_mode.setToolTip(
            "Toggle between Rendered HTML and Markdown Source"
        )
        self.action_toggle_mode.triggered.connect(self._toggle_view_mode)

        # TOC Toggle
        self.action_toggle_toc = self.toolbar.addAction("TOC")
        self.action_toggle_toc.setToolTip("Toggle Table of Contents sidebar")
        self.action_toggle_toc.triggered.connect(self._toggle_toc)

        # Spell check button — always opens settings dialog; checked = currently enabled
        self.action_spell_check = self.toolbar.addAction("ABC")
        self.action_spell_check.setCheckable(True)
        self.action_spell_check.setToolTip(
            "Spell & grammar check settings (LanguageTool)"
        )
        self.action_spell_check.triggered.connect(self._open_spell_settings)

        # Sync visual state with persisted settings
        from PySide6.QtCore import QSettings

        s = QSettings()
        self.action_spell_check.setChecked(
            cast(bool, s.value("SpellCheck/enabled", False, type=bool))
        )

    def _setup_link_controls(self, layout: QVBoxLayout) -> None:
        """Keep writing actions visible when formatting is collapsed."""
        from PySide6.QtWidgets import QToolButton

        from src.gui.widgets.overflow_toolbar import OverflowToolBar
        from src.gui.widgets.wiki_link_authoring import WikiLinkAuthoring

        self.link_notice = QLabel(self)
        self.link_notice.setWordWrap(True)
        self.link_notice.hide()
        self.link_authoring = WikiLinkAuthoring(self.editor, self.link_notice)
        self.editor.link_to_entry_requested.connect(self.link_authoring.open_picker)
        self.link_toolbar = OverflowToolBar(self)
        self.link_toolbar.setStyleSheet(StyleHelper.get_action_role_style("secondary"))
        layout.addWidget(self.link_toolbar)
        layout.addWidget(self.link_notice)
        self.action_link_entry = QAction("Link to entry…", self)
        self.action_open_link = QAction("Open link", self)
        self.action_peek_link = QAction("Peek link", self)
        self.action_return_writing = QAction("Back to previous", self)
        self.action_return_writing.setVisible(False)
        self._return_button = QToolButton(self)
        for action, priority in (
            (self.action_link_entry, 3),
            (self.action_open_link, 2),
            (self.action_peek_link, 1),
            (self.action_return_writing, 4),
        ):
            button = (
                self._return_button
                if action is self.action_return_writing
                else (QToolButton(self))
            )
            button.setDefaultAction(action)
            button.setMinimumHeight(32)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
            self.link_toolbar.add_button(
                button,
                priority=priority,
                available=action is not self.action_return_writing,
            )
        self.action_link_entry.triggered.connect(self.link_authoring.open_picker)
        self.action_open_link.triggered.connect(
            lambda: self.link_clicked.emit(self.editor.link_target_at_cursor())
        )
        self.action_peek_link.triggered.connect(
            lambda: self.peek_requested.emit(self.editor.link_target_at_cursor())
        )
        self.editor.cursorPositionChanged.connect(self._update_link_actions)
        self.editor.selectionChanged.connect(self._update_link_actions)
        self.editor.textChanged.connect(self._update_link_actions)
        self._update_link_actions()

    def _update_link_actions(self) -> None:
        target = self.editor.link_target_at_cursor()
        self.action_link_entry.setEnabled(not self.editor.isReadOnly())
        self.action_open_link.setToolTip(
            "Open linked entry" if target else "Place the cursor in a link to open it."
        )
        self.action_peek_link.setToolTip(
            "Preview linked entry"
            if target
            else "Place the cursor in a link to peek at it."
        )
        self.action_open_link.setEnabled(bool(target))
        self.action_peek_link.setEnabled(bool(target))

    def set_return_available(self, available: bool) -> None:
        """Show the session's return action only while a bookmark exists."""
        self.action_return_writing.setVisible(available)
        self.link_toolbar.set_button_available(self._return_button, available)

    def set_return_destination(self, destination: str, compact: str) -> None:
        """Present a compact return route with its full accessible destination."""
        self.action_return_writing.setText(compact.replace("&", "&&"))
        self.action_return_writing.setToolTip(destination)
        self._return_button.setAccessibleName(destination)
        self.link_toolbar.refresh()

    def _open_spell_settings(self, _checked: bool = False) -> None:
        """Show the SpellCheckSettingsDialog and sync the toolbar button state on close."""
        from PySide6.QtCore import QSettings

        # Restore the button's visual state before opening — triggered() may
        # have toggled it, but the dialog owns the enabled/disabled decision.
        s = QSettings()
        self.action_spell_check.setChecked(
            cast(bool, s.value("SpellCheck/enabled", False, type=bool))
        )

        dlg = SpellCheckSettingsDialog(self)

        def _on_close() -> None:
            s2 = QSettings()
            enabled = cast(bool, s2.value("SpellCheck/enabled", False, type=bool))
            self.action_spell_check.setChecked(enabled)
            if enabled:
                self.editor._trigger_lt_check()
            else:
                self.editor.clear_spell_check()

        dlg.finished.connect(_on_close)
        dlg.show()

    def _toggle_view_mode(self) -> None:
        """Proxy to toggle view mode and update toolbar button text."""
        self.editor.toggle_view_mode()
        self._sync_mode_action(self.editor._view_mode)
        self._apply_editor_width_limit()

    def _sync_mode_action(self, mode: str) -> None:
        """Explain when source mode protects richer Markdown from conversion."""
        if mode == "rich":
            self.action_toggle_mode.setText("MD")
            self.action_toggle_mode.setToolTip("Switch to Markdown Source View")
        else:
            self.action_toggle_mode.setText("HTML")
            self.action_toggle_mode.setToolTip(
                "Exact Markdown source. Rich view is available after removing "
                "unsupported syntax."
            )
        self.source_notice.setVisible(mode == "source")

    def _apply_style(self) -> None:
        """Apply the current theme styling to the widget."""
        from src.gui.utils.style_helper import StyleHelper

        style = (
            "QFrame#WikiTextEditWrapper {\n"
            f"    {StyleHelper.get_input_field_style()}\n"
            "}\n"
            f"{StyleHelper.get_editor_toolbar_style()}"
        )
        self.setStyleSheet(style)

    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme change event by reapplying styles.

        Args:
            theme: The new theme dictionary.
        """
        self._apply_style()
        self._apply_editor_width_limit()
        self.link_toolbar.setStyleSheet(StyleHelper.get_action_role_style("secondary"))

    @Slot()
    def _toggle_toc(self) -> None:
        """Toggles the visibility of the TOC."""
        if self.toc_widget.isHidden():
            self.toc_widget.show()
            self._update_toc()
        else:
            self.toc_widget.hide()
        self._apply_editor_width_limit()

    @Slot()
    def _update_toc(self) -> None:
        """Updates the TOC with the current headings if visible."""
        if not self.toc_widget.isHidden():
            headings = self.editor.get_headings()
            self.toc_widget.update_headings(headings)

    @Slot(int)
    def _scroll_to_header(self, pos: int) -> None:
        """Scrolls the editor to the given block position and aligns it to the top."""
        cursor = self.editor.textCursor()
        cursor.setPosition(pos)
        self.editor.setTextCursor(cursor)

        # To align the header at the top, we calculate the Y offset of the cursor
        # relative to the viewport and add it to the current scrollbar value.
        rect = self.editor.cursorRect(cursor)
        scrollbar = self.editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + rect.top())

    # --- Proxy Methods ---

    def set_wiki_text(self, text: str) -> None:
        """Set the wiki-formatted text content.

        Args:
            text: Wiki-formatted text to set.
        """
        self.editor.set_wiki_text(text)

    def get_wiki_text(self) -> str:
        """Get the wiki-formatted text content.

        Returns:
            Current wiki-formatted text.
        """
        return self.editor.get_wiki_text()

    def setText(self, text: str) -> None:
        """Set the plain text content.

        Args:
            text: Plain text to set.
        """
        self.editor.setText(text)

    def toPlainText(self) -> str:
        """Get the plain text content.

        Returns:
            Current plain text.
        """
        return self.editor.toPlainText()

    def setPlainText(self, text: str) -> None:
        """Set the plain text content directly.

        Args:
            text: Plain text to set.
        """
        self.editor.setPlainText(text)

    def toHtml(self) -> str:
        """Get the HTML content.

        Returns:
            Current HTML text.
        """
        return self.editor.toHtml()

    def setHtml(self, text: str) -> None:
        """Set the HTML content directly.

        Args:
            text: HTML text to set.
        """
        self.editor.setHtml(text)

    def setReadOnly(self, ro: bool) -> None:
        """Set whether the editor is read-only.

        Args:
            ro: True to make read-only, False to make editable.
        """
        self.editor.setReadOnly(ro)
        self._update_link_actions()
        self.link_authoring.cancel_stale()

    def setPlaceholderText(self, text: str) -> None:
        """Set the placeholder text shown when editor is empty.

        Args:
            text: Placeholder text to display.
        """
        self.editor.setPlaceholderText(text)

    def document(self) -> Any:
        """Get the underlying QTextDocument.

        Returns:
            The text document.
        """
        return self.editor.document()

    def textCursor(self) -> Any:
        """Get the current text cursor.

        Returns:
            The current QTextCursor.
        """
        return self.editor.textCursor()

    def setTextCursor(self, cursor: Any) -> None:
        """Set the text cursor position.

        Args:
            cursor: The QTextCursor to set.
        """
        self.editor.setTextCursor(cursor)

    def set_completer(
        self,
        items_or_names: Optional[list[Any]] = None,
        *,
        items: Optional[list[tuple[str, str, str]]] = None,
        names: Optional[list[str]] = None,
    ) -> None:
        """Set the autocompleter for wiki links.

        Args:
            items_or_names: Legacy parameter for items or names list.
            items: List of item objects for completion.
            names: List of item names for completion.
        """
        self.editor.set_completer(items_or_names, items=items, names=names)

    def merge_completions(self, names: list[str]) -> None:
        """Merge semantic suggestion names into the completer.

        Args:
            names: Additional display names to add.

        """
        self.editor.merge_completions(names)

    def apply_completion_effects(self, effects: list[LoreMutationEffect]) -> None:
        """Forward incremental WikiLink target changes to the text view."""
        self.editor.apply_completion_effects(effects)

    def set_link_resolver(self, resolver: Any) -> None:
        """Set the link resolver for wiki links.

        Args:
            resolver: The link resolver callable.
        """
        self.editor.set_link_resolver(resolver)

    def toggle_view_mode(self) -> None:
        """Toggle between edit and view mode."""
        self.editor.toggle_view_mode()

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the inner editor view."""
        return getattr(self.editor, name)


class ResizableWikiTextEditField(QSplitter):
    """A horizontally resizable field that keeps a wiki editor's reading minimum.

    The editor occupies the left pane. A blank, expanding pane absorbs unused
    form-row width, leaving the splitter handle available for the user to widen
    the editor without resizing its parent inspector.
    """

    def __init__(
        self,
        editor: WikiTextEdit,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the field around an existing wiki editor."""
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._editor = editor
        self._spacer = QWidget(self)
        self._spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setChildrenCollapsible(False)
        self.setHandleWidth(8)
        self.addWidget(editor)
        self.addWidget(self._spacer)
        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 1)
        self._reset_to_minimum_width(editor.minimumWidth())
        editor.minimum_width_changed.connect(self._reset_to_minimum_width)

    @Slot(int)
    def _reset_to_minimum_width(self, minimum_width: int) -> None:
        """Keep the editor at least as wide as its current reading minimum."""
        current_width, spacer_width = self.sizes()
        self.setSizes([max(current_width, minimum_width), spacer_width])

    def set_fill_width(self, enabled: bool) -> None:
        """Fill a bounded parent column while retaining the splitter child API."""
        self._spacer.setVisible(not enabled)
