"""Analysis Panel Widget.

Displays a :class:`~src.core.analysis.WorldValidationReport` in a read-only
tabular layout.  Shows a header summary, an issue table, and a completeness
score table.

Text-heavy columns (message, suggestion) use selectable :class:`QLabel` cell
widgets so the user can copy content directly from the table.  Lines wrap at
≤75 characters.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import ValidationIssue, WorldValidationReport
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.analysis._analysis_utils import (
    SEVERITY_COLORS,
    configure_stretch_columns,
    get_analysis_table_style,
    make_analysis_table,
    make_text_cell,
    sync_analysis_cell_styles,
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
      color-coded (CRITICAL=red, WARNING=orange, INFO=blue).  Message and
      suggestion cells are selectable QLabel widgets.
    - A completeness table sorted ascending by score, showing each object's
      name, type, computed score, and tag count.

    Call :meth:`display_report` to populate or refresh the panel.
    """

    open_source_requested = Signal(str)

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

        self.header_label = QLabel("No report loaded.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        self._issues_label = QLabel("Validation Issues")
        layout.addWidget(self._issues_label)
        self.issues_table = make_analysis_table(_ISSUE_HEADERS)
        configure_stretch_columns(self.issues_table, 3, 4)  # Message, Suggestion
        layout.addWidget(self.issues_table)

        self._completeness_label = QLabel("Documentation Completeness")
        layout.addWidget(self._completeness_label)
        self.completeness_table = make_analysis_table(_COMPLETENESS_HEADERS)
        layout.addWidget(self.completeness_table)

        self.open_source_btn = QPushButton("Open Source")
        self.open_source_btn.setEnabled(False)
        layout.addWidget(self.open_source_btn)

        for table in (self.issues_table, self.completeness_table):
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setSortingEnabled(True)
            table.itemSelectionChanged.connect(
                lambda selected_table=table: self._on_table_selection(selected_table)
            )
            table.itemDoubleClicked.connect(lambda _item: self._open_source())
        self.open_source_btn.clicked.connect(self._open_source)

    def _apply_styles(self) -> None:
        """Apply theme-aware styles to all child widgets."""
        self.header_label.setStyleSheet(StyleHelper.get_preview_label_style())
        self._issues_label.setStyleSheet(StyleHelper.get_section_header_style())
        self._completeness_label.setStyleSheet(StyleHelper.get_section_header_style())
        table_style = get_analysis_table_style()
        for table in (self.issues_table, self.completeness_table):
            table.setStyleSheet(table_style)
            sync_analysis_cell_styles(table)

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
            f"Documentation completeness: {report.average_completeness:.0f}% | "
            f"{len(report.issues)} Issues | "
            f"Entities: {report.total_entities}, Events: {report.total_events}"
        )

    def _populate_issues_table(self, report: WorldValidationReport) -> None:
        """Fill the issues table from the report's issue list.

        Severity cells are color-coded: CRITICAL=red, WARNING=orange, INFO=blue.
        Message and suggestion cells use selectable QLabel widgets with text
        wrapped at 75 characters.

        Args:
            report: The report whose issues are displayed.
        """
        self.issues_table.setRowCount(len(report.issues))
        self.issues_table.setSortingEnabled(False)
        for row, issue in enumerate(report.issues):
            sev_item = QTableWidgetItem(issue.severity.value)
            sev_item.setData(
                Qt.ItemDataRole.UserRole,
                self._issue_source_id(issue),
            )
            color = SEVERITY_COLORS.get(issue.severity)
            if color:
                sev_item.setForeground(QBrush(QColor(color)))
            self.issues_table.setItem(row, 0, sev_item)
            self.issues_table.setItem(row, 1, QTableWidgetItem(issue.issue_type.value))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.object_name))
            self.issues_table.setCellWidget(row, 3, make_text_cell(issue.message))
            self.issues_table.setCellWidget(
                row, 4, make_text_cell(issue.suggestion or "")
            )
        self.issues_table.setSortingEnabled(True)
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
        self.completeness_table.setSortingEnabled(False)
        for row, score in enumerate(sorted_scores):
            name_item = QTableWidgetItem(score.name)
            name_item.setData(Qt.ItemDataRole.UserRole, score.object_id)
            self.completeness_table.setItem(row, 0, name_item)
            self.completeness_table.setItem(
                row, 1, QTableWidgetItem(score.object_type)
            )
            self.completeness_table.setItem(
                row, 2, QTableWidgetItem(f"{score.completeness_score:.0f}%")
            )
            breakdown = "\n".join(
                f"{component.name}: {component.earned:g}/{component.maximum:g} — "
                f"{component.explanation}"
                for component in score.breakdown.components
            )
            for column in range(3):
                item = self.completeness_table.item(row, column)
                if item is not None:
                    item.setToolTip(breakdown)
            self.completeness_table.setItem(
                row, 3, QTableWidgetItem(str(score.tag_count))
            )
        self.completeness_table.setSortingEnabled(True)

    @staticmethod
    def _issue_source_id(issue: ValidationIssue) -> str:
        """Return the best navigable world object behind a validation issue."""
        object_type = issue.object_type
        object_id = issue.object_id
        if object_type in {"entity", "event"}:
            return object_id
        evidence = issue.evidence
        if evidence:
            return str(evidence[0].object_id)
        related_ids = issue.related_ids or []
        return str(related_ids[0]) if related_ids else ""

    def _selected_source_id(self) -> str:
        """Return the source ID stored on the selected issue or score row."""
        for table in (self.issues_table, self.completeness_table):
            rows = table.selectionModel().selectedRows()
            if not rows:
                continue
            item = table.item(rows[0].row(), 0)
            if item is not None:
                return str(item.data(Qt.ItemDataRole.UserRole) or "")
        return ""

    def _update_source_action(self) -> None:
        """Enable source navigation only for rows backed by a world object."""
        self.open_source_btn.setEnabled(bool(self._selected_source_id()))

    def _on_table_selection(self, selected_table: QTableWidget) -> None:
        """Keep one active row across both validation result tables."""
        if selected_table.selectionModel().hasSelection():
            for table in (self.issues_table, self.completeness_table):
                if table is selected_table:
                    continue
                table.blockSignals(True)
                table.clearSelection()
                sync_analysis_cell_styles(table)
                table.blockSignals(False)
        self._update_source_action()

    def _open_source(self) -> None:
        """Request navigation without mutating or opening an edit operation."""
        source_id = self._selected_source_id()
        if source_id:
            self.open_source_requested.emit(source_id)
