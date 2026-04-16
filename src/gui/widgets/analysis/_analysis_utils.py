"""Shared utilities for Tier 1 analysis panel widgets.

Provides the :func:`make_analysis_table` factory used by all three analysis
sub-panels to avoid duplicating boilerplate table configuration.

Also provides :class:`AutoHeightTextEdit` — a read-only, frameless
:class:`QTextEdit` subclass whose row height always matches the actual
document content.  :func:`make_text_cell` and :func:`make_html_cell` wrap
this class for plain-text and rich-HTML cell content respectively.
Text reflows at the actual column width via Qt word-wrap; no hard breaks
are inserted.

Additional utilities: :func:`fmt_lore_date` for lore-date float formatting,
:func:`format_lore_suggestions_html` for lore-card HTML, and
:data:`SEVERITY_COLORS` for consistent severity colour coding.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTextEdit,
)

from src.app.constants import (
    ANALYSIS_SEVERITY_CRITICAL_COLOR,
    ANALYSIS_SEVERITY_INFO_COLOR,
    ANALYSIS_SEVERITY_WARNING_COLOR,
)
from src.core.analysis import ParsedLoreSuggestion, SeverityLevel

logger = logging.getLogger(__name__)

# Shared severity → foreground colour mapping used by all analysis panels.
SEVERITY_COLORS: dict[SeverityLevel, str] = {
    SeverityLevel.CRITICAL: ANALYSIS_SEVERITY_CRITICAL_COLOR,
    SeverityLevel.WARNING: ANALYSIS_SEVERITY_WARNING_COLOR,
    SeverityLevel.INFO: ANALYSIS_SEVERITY_INFO_COLOR,
}

# HTML divider inserted between suggestion cards in the lore column.
_HR = "<hr style='margin:6px 0;border:1px solid #888;'/>"


def _wrap_html(text: str) -> str:
    """Collapse whitespace and escape plain text for HTML rendering.

    Hard wrapping is intentionally omitted — the ``AutoHeightTextEdit``
    host widget reflows text at the actual column width via Qt's word-wrap.

    Args:
        text: Plain-text string to format.

    Returns:
        str: HTML-escaped string, or ``""`` when *text* is empty.
    """
    if not text:
        return ""
    return html.escape(" ".join(text.split()))


def fmt_lore_date(value: float | None, converter: Any | None = None) -> str:
    """Format a lore-date float as a human-readable string.

    Lore dates are stored as absolute day counts from the calendar epoch
    (Year 1, Month 1, Day 1 = 0.0).  When a :class:`CalendarConverter`
    is available it is used to recover the calendar year; otherwise the
    raw float is approximated using a 365-day year.

    Args:
        value: Absolute day-count lore date, or ``None`` if unknown.
        converter: Optional ``CalendarConverter`` instance for year lookup.

    Returns:
        str: A label such as ``"Year 1897"``, or ``"Unknown"`` when *value*
        is ``None``.
    """
    if value is None:
        return "Unknown"
    if converter is not None:
        try:
            cal_date = converter.from_float(value)
            return f"Year {cal_date.year}"
        except Exception:
            logger.debug("fmt_lore_date: converter failed for %r", value)
    approx_year = int(value // 365.0) + 1
    return f"Year {approx_year}"



class AutoHeightTextEdit(QTextEdit):
    """Read-only, frameless QTextEdit whose height tracks document content.

    Designed for use as a ``QTableWidget`` cell widget.  Unlike a
    :class:`QLabel`, this widget knows its allocated width at render time —
    Qt sends a synchronous resize event to cell widgets when they are placed
    in a table, so by the time :meth:`sizeHint` is called during
    ``resizeRowsToContents`` the document has already been reflowed.

    When the parent column is resized afterwards, the document reflows and
    the row height is updated automatically via a zero-delay
    :class:`~PySide6.QtCore.QTimer` owned by this widget.  Owning the timer
    ensures it is cancelled when the widget (and its parent table) are
    destroyed, preventing ``RuntimeError`` on stale callbacks.
    """

    def __init__(self, parent: QTableWidget | None = None) -> None:
        """Initialise the cell widget.

        Args:
            parent: Optional parent (usually set by ``setCellWidget``).
        """
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(4)
        # Blend with table row background (including alternating colours).
        self.setStyleSheet(
            "QTextEdit { background-color: transparent; border: none; }"
        )
        self.viewport().setAutoFillBackground(False)

        # Use a member timer so it is destroyed with this widget, preventing
        # callbacks from firing on already-deleted C++ objects.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(0)
        self._resize_timer.timeout.connect(self._do_row_resize)

        self.document().documentLayout().documentSizeChanged.connect(
            self._schedule_row_resize
        )

    # ------------------------------------------------------------------
    # Size hint — document is already reflowed by the time this is called
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        """Return height derived from the reflowed document content.

        Qt delivers resize events to cell widgets *synchronously* inside
        ``setCellWidget``, so the document reflows at the correct column
        width before ``resizeRowsToContents`` calls this method.

        Returns:
            QSize: Width from the base hint; height from document layout.
        """
        doc_h = int(self.document().size().height())
        return QSize(super().sizeHint().width(), max(doc_h + 8, 24))

    def minimumSizeHint(self) -> QSize:
        """Mirror :meth:`sizeHint` so the table never clips the row.

        Returns:
            QSize: Same as :meth:`sizeHint`.
        """
        return self.sizeHint()

    # ------------------------------------------------------------------
    # Dynamic resize on column-width change
    # ------------------------------------------------------------------

    def resizeEvent(self, event: Any) -> None:
        """Trigger a row-height update when the allocated column width changes.

        Args:
            event: The Qt resize event.
        """
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._schedule_row_resize()

    def _schedule_row_resize(self, _new_size: object = None) -> None:
        """Start (or restart) the deferred resize timer.

        Coalesces rapid successive signals (e.g. during column drag) into
        a single ``resizeRowsToContents`` call.

        Args:
            _new_size: Ignored (received from ``documentSizeChanged``).
        """
        self._resize_timer.start()

    def _do_row_resize(self) -> None:
        """Execute the deferred ``resizeRowsToContents`` call safely.

        Wrapped in a ``RuntimeError`` guard because the C++ table object may
        have been destroyed before this deferred callback fires (e.g. in
        tests that do not process the event loop).
        """
        try:
            table = self._find_parent_table()
            if table is not None:
                table.resizeRowsToContents()
        except RuntimeError:
            pass  # C++ object already deleted — nothing to do.

    def _find_parent_table(self) -> QTableWidget | None:
        """Traverse the parent chain to locate the owning QTableWidget.

        Cell widgets are reparented to the table's viewport by Qt, so
        the chain is ``self → viewport → QTableWidget``.

        Returns:
            QTableWidget | None: The parent table, or ``None`` if the
            widget has not yet been embedded in a table.
        """
        viewport = self.parent()
        if viewport is not None:
            table = viewport.parent()
            if isinstance(table, QTableWidget):
                return table
        return None


def make_text_cell(text: str) -> AutoHeightTextEdit:
    """Create a selectable, auto-height cell widget for plain-text content.

    Whitespace in *text* is normalized to single spaces; line reflowing is
    handled by Qt's word-wrap so no hard breaks are inserted.  Mouse and
    keyboard text selection are enabled by the read-only
    :class:`AutoHeightTextEdit` base.  Use ``QTableWidget.setCellWidget()``
    to embed the result.

    Args:
        text: Plain-text content for the cell.

    Returns:
        AutoHeightTextEdit: A configured widget ready to embed as a cell.
    """
    edit = AutoHeightTextEdit()
    edit.setPlainText(" ".join(text.split()) if text else "")
    return edit


def make_html_cell(html_content: str) -> AutoHeightTextEdit:
    """Create a selectable, auto-height cell widget for rich HTML content.

    Uses the same :class:`AutoHeightTextEdit` as :func:`make_text_cell`
    but sets HTML source directly.  Suitable for lore-suggestion cards
    rendered by :func:`format_lore_suggestions_html`.  Use
    ``QTableWidget.setCellWidget()`` to embed the result.

    Args:
        html_content: HTML string to render in the cell.

    Returns:
        AutoHeightTextEdit: A configured widget ready to embed as a cell.
    """
    edit = AutoHeightTextEdit()
    edit.setHtml(html_content)
    return edit


def format_lore_suggestions_html(suggestions: list[ParsedLoreSuggestion]) -> str:
    """Format a list of ParsedLoreSuggestion objects as structured HTML.

    Each suggestion renders as a mini-card with bold event name, italic date,
    and description text (wrapped at 75 chars), separated by horizontal
    dividers.

    Args:
        suggestions: List of parsed lore suggestions for a single gap row.

    Returns:
        str: HTML string ready for display in an :class:`AutoHeightTextEdit`
        cell.
    """
    html_parts: list[str] = []
    for i, suggestion in enumerate(suggestions):
        if i > 0:
            html_parts.append(_HR)
        html_parts.append(f"<b>{html.escape(suggestion.name)}</b><br/>")
        if suggestion.date_str:
            html_parts.append(f"<i>Date: {html.escape(suggestion.date_str)}</i><br/>")
        if suggestion.description:
            html_parts.append(_wrap_html(suggestion.description))
    return "".join(html_parts)


# Appended to the base table stylesheet to suppress hover and selection
# highlights in all analysis panels.
ANALYSIS_TABLE_NO_HIGHLIGHT: str = (
    "QTableWidget::item:hover { background-color: transparent; }"
    "QTableWidget::item:selected { background-color: transparent; color: inherit; }"
)


def configure_stretch_columns(table: QTableWidget, *col_indices: int) -> None:
    """Set the given columns to Stretch mode and disable last-section auto-stretch.

    Use this after :func:`make_analysis_table` for tables that have more than
    one text-heavy column.  Every column NOT listed keeps ``ResizeToContents``
    so short data columns (severity, confidence, dates) stay compact.

    Args:
        table: The table to reconfigure.
        *col_indices: Column indices that should stretch to share available space.
    """
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for idx in col_indices:
        header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Stretch)


def make_analysis_table(headers: list[str]) -> QTableWidget:
    """Create a standard read-only, non-interactive table with given column headers.

    Columns are sized to content except the last, which stretches to fill the
    available width.  Selection and focus are disabled so no row or cell
    highlighting appears on click or hover.

    Args:
        headers: Column header labels.

    Returns:
        QTableWidget: A configured table widget ready to add to a layout.
    """
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    table.verticalHeader().setVisible(False)

    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return table
