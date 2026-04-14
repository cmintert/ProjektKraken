"""Analysis Panel Widget.

Displays a :class:`~src.core.analysis.WorldValidationReport` in a read-only
tabular layout. Shows a header summary, an issue table, and a completeness
score table.
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

from src.core.analysis import WorldValidationReport
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets._analysis_utils import (
    SEVERITY_COLORS,
    make_analysis_table,
    wrap_cell_text,
)

logger = logging.getLogger(__name__)

# Column headers
_ISSUE_HEADERS = ["Severity", "Type", "Object", "Message", "Suggestion"]
_COMPLETENESS_HEADERS = ["Name", "Type", "Score", "Tags"]


class AnalysisPanel(QWidget):
    """Read-only panel displaying a world validation report.

    Provides three sections:
    - A header label summarising world health and counts.
    - An issues table listing every validation issue with severity, type,
      affected object, message, and suggestion.  Severity cells are
      color-coded (CRITICAL=red, WARNING=orange, INFO=blue).
    - A completeness table sorted ascending by score, showing each object's
      name, type, computed score, and tag count.

    Call :meth:`display_report` to populate or refresh the panel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the panel and build the UI layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._init_ui()
        self._apply_styles()
        ThemeManager().theme_changed.connect(self._apply_styles)

    def _init_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)

        # --- Header ---
        self.header_label = QLabel("No report loaded.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        # --- Issues table ---
        self._issues_label = QLabel("Validation Issues")
        layout.addWidget(self._issues_label)
        self.issues_table = make_analysis_table(_ISSUE_HEADERS)
        layout.addWidget(self.issues_table)

        # --- Completeness table ---
        self._completeness_label = QLabel("Completeness Scores")
        layout.addWidget(self._completeness_label)
        self.completeness_table = make_analysis_table(_COMPLETENESS_HEADERS)
        layout.addWidget(self.completeness_table)

    def _apply_styles(self) -> None:
        """Apply theme-aware styles to all child widgets."""
        self.header_label.setStyleSheet(StyleHelper.get_preview_label_style())
        self._issues_label.setStyleSheet(StyleHelper.get_section_header_style())
        self._completeness_label.setStyleSheet(StyleHelper.get_section_header_style())
        table_style = StyleHelper.get_table_widget_style()
        self.issues_table.setStyleSheet(table_style)
        self.completeness_table.setStyleSheet(table_style)

    def display_report(self, report: WorldValidationReport) -> None:
        """Populate the panel with data from a validation report.

        Replaces any previously displayed report. The completeness table is
        sorted ascending by score (lowest completeness first).

        Args:
            report: The :class:`~src.core.analysis.WorldValidationReport` to display.
        """
        self._update_header(report)
        self._populate_issues_table(report)
        self._populate_completeness_table(report)

    def _update_header(self, report: WorldValidationReport) -> None:
        """Update the summary header label.

        Args:
            report: The report to summarise.
        """
        self.header_label.setText(
            f"World Health: {report.average_completeness:.0f}% Complete | "
            f"{len(report.issues)} Issues | "
            f"Entities: {report.total_entities}, Events: {report.total_events}"
        )

    def _populate_issues_table(self, report: WorldValidationReport) -> None:
        """Fill the issues table from the report's issue list.

        Severity cells are color-coded: CRITICAL=red, WARNING=orange, INFO=blue.

        Args:
            report: The report whose issues are displayed.
        """
        self.issues_table.setRowCount(len(report.issues))
        for row, issue in enumerate(report.issues):
            sev_item = QTableWidgetItem(issue.severity.value)
            color = SEVERITY_COLORS.get(issue.severity)
            if color:
                sev_item.setForeground(QBrush(QColor(color)))
            self.issues_table.setItem(row, 0, sev_item)
            self.issues_table.setItem(row, 1, QTableWidgetItem(issue.issue_type.value))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.object_name))
            self.issues_table.setItem(row, 3, QTableWidgetItem(wrap_cell_text(issue.message)))
            self.issues_table.setItem(
                row, 4, QTableWidgetItem(wrap_cell_text(issue.suggestion or ""))
            )
        self.issues_table.resizeRowsToContents()

    def _populate_completeness_table(self, report: WorldValidationReport) -> None:
        """Fill the completeness table sorted ascending by score.

        Args:
            report: The report whose completeness scores are displayed.
        """
        sorted_scores = sorted(
            report.completeness_scores, key=lambda s: s.completeness_score
        )
        self.completeness_table.setRowCount(len(sorted_scores))
        for row, score in enumerate(sorted_scores):
            self.completeness_table.setItem(row, 0, QTableWidgetItem(score.name))
            self.completeness_table.setItem(
                row, 1, QTableWidgetItem(score.object_type)
            )
            self.completeness_table.setItem(
                row, 2, QTableWidgetItem(f"{score.completeness_score:.0f}%")
            )
            self.completeness_table.setItem(
                row, 3, QTableWidgetItem(str(score.tag_count))
            )
