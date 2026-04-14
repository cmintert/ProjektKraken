"""Shared utilities for Tier 1 analysis panel widgets.

Provides the :func:`make_analysis_table` factory, used by all three analysis
sub-panels to avoid duplicating boilerplate table configuration.

Also provides :func:`fmt_lore_date` for converting lore-date floats
(absolute day counts from the calendar epoch) to human-readable strings,
and :data:`SEVERITY_COLORS` for consistent severity colour coding.
"""

from __future__ import annotations

import logging
import textwrap
from typing import Any

from PySide6.QtWidgets import QHeaderView, QSizePolicy, QTableWidget

from src.app.constants import (
    ANALYSIS_SEVERITY_CRITICAL_COLOR,
    ANALYSIS_SEVERITY_INFO_COLOR,
    ANALYSIS_SEVERITY_WARNING_COLOR,
)
from src.core.analysis import SeverityLevel

logger = logging.getLogger(__name__)

# Shared severity → foreground colour mapping used by all analysis panels.
SEVERITY_COLORS: dict[SeverityLevel, str] = {
    SeverityLevel.CRITICAL: ANALYSIS_SEVERITY_CRITICAL_COLOR,
    SeverityLevel.WARNING: ANALYSIS_SEVERITY_WARNING_COLOR,
    SeverityLevel.INFO: ANALYSIS_SEVERITY_INFO_COLOR,
}


def fmt_lore_date(value: float | None, converter: Any | None = None) -> str:
    """Format a lore-date float as a human-readable string.

    Lore dates are stored as absolute day counts from the calendar epoch
    (Year 1, Month 1, Day 1 = 0.0).  When a :class:`CalendarConverter`
    is available it is used to recover the calendar year; otherwise the
    raw float is shown as a fallback.

    Args:
        value: Absolute day-count lore date, or ``None`` if unknown.
        converter: Optional ``CalendarConverter`` instance for year lookup.

    Returns:
        str: A label such as ``"Year 1897"`` or ``"Unknown"`` when *value*
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
    # value is an absolute day count (epoch = Year 1, day 0).
    # Approximate the year using a 365-day Gregorian year.
    approx_year = int(value // 365.0) + 1
    return f"Year {approx_year}"


def wrap_cell_text(text: str, width: int = 75) -> str:
    """Wrap *text* to *width* characters using hard line breaks.

    Args:
        text: Input string (may be empty or None-ish).
        width: Maximum line length in characters (default 75).

    Returns:
        str: Text with ``\\n`` inserted at word boundaries.
    """
    return textwrap.fill(text, width=width) if text else text


def make_analysis_table(headers: list[str]) -> QTableWidget:
    """Create a standard read-only, row-selecting table with given column headers.

    Columns are sized to content except the last, which stretches to fill the
    available width.

    Args:
        headers: Column header labels.

    Returns:
        QTableWidget: A configured table widget ready to add to a layout.
    """
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)

    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return table
