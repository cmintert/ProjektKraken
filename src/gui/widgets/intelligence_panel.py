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

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import IntelligenceReport
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets._analysis_utils import (
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

    def display_report(self, report: IntelligenceReport) -> None:
        """Populate the panel with data from an intelligence analysis report.

        Replaces any previously displayed report.

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
        self._populate_plot_holes_table(report)
        self._populate_proposals_table(report)
        self._populate_lore_table(report)

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

    def _populate_plot_holes_table(self, report: IntelligenceReport) -> None:
        """Fill the plot-holes table from the report's plot_holes list.

        Severity cells are color-coded: CRITICAL=red, WARNING=orange, INFO=blue.
        Description and resolution cells use selectable QLabel widgets with
        text wrapped at 75 characters.

        Args:
            report: The report whose plot holes are displayed.
        """
        self.plot_holes_table.setRowCount(len(report.plot_holes))
        for row, hole in enumerate(report.plot_holes):
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

    def _populate_proposals_table(self, report: IntelligenceReport) -> None:
        """Fill the proposals table from the report's relation_proposals list.

        The reasoning cell uses a selectable QLabel widget with text wrapped
        at 75 characters.

        Args:
            report: The report whose relation proposals are displayed.
        """
        self.proposals_table.setRowCount(len(report.relation_proposals))
        for row, proposal in enumerate(report.relation_proposals):
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

    def _populate_lore_table(self, report: IntelligenceReport) -> None:
        """Fill the lore-suggestions table from the report's lore_suggestions list.

        Suggestions for a single gap are rendered as structured HTML mini-cards
        in a QTextBrowser cell, with event names, dates, and descriptions
        (wrapped at 75 chars) separated by dividers.

        Args:
            report: The report whose lore suggestions are displayed.
        """
        self.lore_table.setRowCount(len(report.lore_suggestions))
        for row, filler in enumerate(report.lore_suggestions):
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
