"""Intelligence Panel Widget.

Displays a :class:`~src.core.analysis.IntelligenceReport` in a read-only
tabular layout.  Shows a header summary, a plot-holes table, a relation-
proposals table, and a lore-suggestions table.

Text-heavy columns (description, resolution, reasoning, suggestions) use
selectable :class:`~src.gui.widgets._analysis_utils.AutoHeightTextEdit` cell
widgets so the user can copy content directly from the table.  Row height
tracks document content automatically.  Lines wrap at ≤75 characters.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import (
    IntelligenceReport,
    LoreGapFiller,
    PlotHole,
    RelationProposal,
)
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.analysis._analysis_utils import (
    ANALYSIS_TABLE_NO_HIGHLIGHT,
    SEVERITY_COLORS,
    configure_stretch_columns,
    fmt_lore_date,
    format_lore_suggestions_html,
    make_analysis_table,
    make_html_cell,
    make_text_cell,
)

logger = logging.getLogger(__name__)

# Column headers for each table
_HOLE_HEADERS = ["Severity", "Entity", "Description", "Resolution", "Confidence"]
_PROPOSAL_HEADERS = ["Source", "Target", "Relation Type", "Confidence", "Reasoning"]
_LORE_HEADERS = ["Gap Start", "Gap End", "Suggestions"]


class IntelligencePanel(QWidget):
    """Read-only panel displaying an AI intelligence analysis report.

    Provides four sections:
    - A header label summarising the LLM model used and counts for each
      result category.
    - A plot-holes table listing every detected narrative inconsistency with
      severity, entity, description, resolution, and confidence.  Severity
      cells are color-coded (CRITICAL=red, WARNING=orange, INFO=blue).
      Description and resolution cells are selectable QLabel widgets.
    - A relation-proposals table listing every suggested new relation with
      source, target, type, confidence, and reasoning.  The reasoning cell
      is a selectable QLabel widget.
    - A lore-suggestions table listing every gap filler with start date, end
      date, and suggestions rendered as HTML mini-cards in a QTextBrowser.

    Call :meth:`display_report` to populate or refresh the panel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the panel and build the UI layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._converter = None
        self._init_ui()
        self._apply_styles()
        ThemeManager().theme_changed.connect(self._apply_styles)

    def _init_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)

        self.header_label = QLabel("No report loaded.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        self._holes_label = QLabel("Plot Holes")
        layout.addWidget(self._holes_label)
        self.plot_holes_table = make_analysis_table(_HOLE_HEADERS)
        configure_stretch_columns(self.plot_holes_table, 2, 3)  # Description, Resolution
        layout.addWidget(self.plot_holes_table)

        self._proposals_label = QLabel("Relation Proposals")
        layout.addWidget(self._proposals_label)
        self.proposals_table = make_analysis_table(_PROPOSAL_HEADERS)
        layout.addWidget(self.proposals_table)

        self._lore_label = QLabel("Lore Gap Suggestions")
        layout.addWidget(self._lore_label)
        self.lore_table = make_analysis_table(_LORE_HEADERS)
        layout.addWidget(self.lore_table)

    def _apply_styles(self) -> None:
        """Apply theme-aware styles to all child widgets."""
        self.header_label.setStyleSheet(StyleHelper.get_preview_label_style())
        section_style = StyleHelper.get_section_header_style()
        self._holes_label.setStyleSheet(section_style)
        self._proposals_label.setStyleSheet(section_style)
        self._lore_label.setStyleSheet(section_style)
        table_style = StyleHelper.get_table_widget_style() + ANALYSIS_TABLE_NO_HIGHLIGHT
        self.plot_holes_table.setStyleSheet(table_style)
        self.proposals_table.setStyleSheet(table_style)
        self.lore_table.setStyleSheet(table_style)

    # ------------------------------------------------------------------
    # One-shot render (non-streaming callers)
    # ------------------------------------------------------------------

    def display_report(self, report: IntelligenceReport) -> None:
        """Populate the panel with data from an intelligence analysis report.

        Replaces any previously displayed report.  For streaming callers use
        :meth:`start_streaming`, :meth:`display_partial_result`, and
        :meth:`finalize_report` instead.

        Args:
            report: The :class:`~src.core.analysis.IntelligenceReport` to display.
        """
        self._converter = None
        if report.calendar_config is not None:
            try:
                from src.core.calendar import CalendarConverter

                self._converter = CalendarConverter(report.calendar_config)
            except Exception:
                logger.debug("IntelligencePanel: could not build CalendarConverter")

        self._update_header(report)
        self._populate_plot_holes_from_list(report.plot_holes)
        self._populate_proposals_from_list(report.relation_proposals)
        self._populate_lore_from_list(report.lore_suggestions)

    # ------------------------------------------------------------------
    # Streaming API
    # ------------------------------------------------------------------

    def start_streaming(self) -> None:
        """Clear all tables and show an ``Analyzing…`` placeholder in each.

        Call this immediately when the user triggers an analysis so the UI
        reflects a busy state before any partial results arrive.
        """
        self._converter = None
        self.header_label.setText("AI Analysis — Running…")
        for table, col_count in (
            (self.plot_holes_table, len(_HOLE_HEADERS)),
            (self.proposals_table, len(_PROPOSAL_HEADERS)),
            (self.lore_table, len(_LORE_HEADERS)),
        ):
            table.setRowCount(1)
            placeholder = QTableWidgetItem("Analyzing…")
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(0, 0, placeholder)
            for col in range(1, col_count):
                table.setItem(0, col, QTableWidgetItem(""))

    def display_partial_result(self, result_type: str, data: Any) -> None:
        """Populate one table section as its sub-analysis completes.

        Called via ``QueuedConnection`` from the main thread when
        :attr:`~src.services.worker.DatabaseWorker.intelligence_partial_result`
        fires, so it is safe to update widgets here.

        Args:
            result_type: ``"holes"``, ``"relations"``, or ``"lore"``.
            data: The raw result tuple returned by the matching sub-analyzer.
        """
        if result_type == "holes":
            holes, _audit = data
            self._populate_plot_holes_from_list(holes)
        elif result_type == "relations":
            proposals, _audit = data
            self._populate_proposals_from_list(proposals)
        elif result_type == "lore":
            suggestions, _audit, calendar_config = data
            if calendar_config is not None and self._converter is None:
                try:
                    from src.core.calendar import CalendarConverter

                    self._converter = CalendarConverter(calendar_config)
                except Exception:
                    logger.debug(
                        "IntelligencePanel: could not build CalendarConverter"
                    )
            self._populate_lore_from_list(suggestions)

    def finalize_report(self, report: IntelligenceReport) -> None:
        """Update the header and clear any leftover loading placeholders.

        Called once :attr:`~src.services.worker.DatabaseWorker.\
intelligence_analysis_complete` fires with the full report.  Sections
        populated via :meth:`display_partial_result` are re-rendered from the
        authoritative report data; sections that were skipped (because the
        analysis type was narrower than ``"all"``, or because a sub-analysis
        failed) are replaced with empty tables instead of stale placeholders.

        Args:
            report: The final :class:`~src.core.analysis.IntelligenceReport`.
        """
        # Build converter from final report if not already set by a lore partial.
        if self._converter is None and report.calendar_config is not None:
            try:
                from src.core.calendar import CalendarConverter

                self._converter = CalendarConverter(report.calendar_config)
            except Exception:
                logger.debug("IntelligencePanel: could not build CalendarConverter")

        self._update_header(report)
        self._populate_plot_holes_from_list(report.plot_holes)
        self._populate_proposals_from_list(report.relation_proposals)
        self._populate_lore_from_list(report.lore_suggestions)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _update_header(self, report: IntelligenceReport) -> None:
        """Update the summary header label.

        Args:
            report: The report to summarise.
        """
        self.header_label.setText(
            f"AI Analysis | Model: {report.analysis_model} | "
            f"Holes: {len(report.plot_holes)} | "
            f"Proposals: {len(report.relation_proposals)} | "
            f"Lore Fills: {len(report.lore_suggestions)}"
        )

    # ------------------------------------------------------------------
    # Table population (accept lists so streaming and one-shot share code)
    # ------------------------------------------------------------------

    def _populate_plot_holes_from_list(self, holes: list[PlotHole]) -> None:
        """Fill the plot-holes table from a list of :class:`~src.core.analysis.PlotHole`.

        Severity cells are color-coded: CRITICAL=red, WARNING=orange, INFO=blue.
        Description and resolution cells use selectable QLabel widgets with
        text wrapped at 75 characters.

        Args:
            holes: Plot holes to display.
        """
        self.plot_holes_table.setRowCount(len(holes))
        for row, hole in enumerate(holes):
            sev_item = QTableWidgetItem(hole.severity.value)
            color = SEVERITY_COLORS.get(hole.severity)
            if color:
                sev_item.setForeground(QBrush(QColor(color)))
            self.plot_holes_table.setItem(row, 0, sev_item)
            self.plot_holes_table.setItem(row, 1, QTableWidgetItem(hole.entity_name))
            self.plot_holes_table.setCellWidget(
                row, 2, make_text_cell(hole.description)
            )
            self.plot_holes_table.setCellWidget(
                row, 3, make_text_cell(hole.suggested_resolution or "")
            )
            self.plot_holes_table.setItem(
                row, 4, QTableWidgetItem(f"{hole.confidence:.2f}")
            )
        self.plot_holes_table.resizeRowsToContents()

    def _populate_proposals_from_list(self, proposals: list[RelationProposal]) -> None:
        """Fill the proposals table from a list of :class:`~src.core.analysis.RelationProposal`.

        The reasoning cell uses a selectable QLabel widget with text wrapped
        at 75 characters.

        Args:
            proposals: Relation proposals to display.
        """
        self.proposals_table.setRowCount(len(proposals))
        for row, proposal in enumerate(proposals):
            self.proposals_table.setItem(
                row, 0, QTableWidgetItem(proposal.source_name)
            )
            self.proposals_table.setItem(
                row, 1, QTableWidgetItem(proposal.target_name)
            )
            self.proposals_table.setItem(
                row, 2, QTableWidgetItem(proposal.suggested_relation_type)
            )
            self.proposals_table.setItem(
                row, 3, QTableWidgetItem(f"{proposal.confidence:.2f}")
            )
            self.proposals_table.setCellWidget(
                row, 4, make_text_cell(proposal.reasoning)
            )
        self.proposals_table.resizeRowsToContents()

    def _populate_lore_from_list(self, suggestions: list[LoreGapFiller]) -> None:
        """Fill the lore-suggestions table from a list of :class:`~src.core.analysis.LoreGapFiller`.

        Suggestions for a single gap are rendered as structured HTML mini-cards
        in a QTextBrowser cell, with event names, dates, and descriptions
        (wrapped at 75 chars) separated by dividers.

        Args:
            suggestions: Lore gap fillers to display.
        """
        self.lore_table.setRowCount(len(suggestions))
        for row, filler in enumerate(suggestions):
            self.lore_table.setItem(
                row,
                0,
                QTableWidgetItem(fmt_lore_date(filler.start_date, self._converter)),
            )
            self.lore_table.setItem(
                row,
                1,
                QTableWidgetItem(fmt_lore_date(filler.end_date, self._converter)),
            )
            self.lore_table.setCellWidget(
                row, 2, make_html_cell(format_lore_suggestions_html(filler.suggestions))
            )
        self.lore_table.resizeRowsToContents()
