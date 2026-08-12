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

import dataclasses
import datetime
import json
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
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
    SEVERITY_COLORS,
    configure_stretch_columns,
    fmt_lore_date,
    get_analysis_table_style,
    make_analysis_table,
    make_text_cell,
    sync_analysis_cell_styles,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.calendar import CalendarConverter

# Column headers for each table
_HOLE_HEADERS = ["Severity", "Entity", "Description", "Resolution", "Evidence"]
_PROPOSAL_HEADERS = ["Source", "Target", "Relation Type", "Evidence", "Reasoning"]
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
      date, and a compact title preview. Full text appears in the details pane.

    Call :meth:`display_report` to populate or refresh the panel.
    """

    open_source_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the panel and build the UI layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._converter: CalendarConverter | None = None
        self._current_report: IntelligenceReport | None = None
        self._previous_reports: list[IntelligenceReport] = []
        self._reports_by_type: dict[str, list[IntelligenceReport]] = {
            "plot_holes": [],
            "relations": [],
            "lore": [],
        }
        self._dismissals: dict[str, str] = {}
        self._stale = False
        self._selected_finding: Any | None = None
        self._selected_evidence_id: str | None = None
        self._init_ui()
        self._apply_styles()
        ThemeManager().theme_changed.connect(self._apply_styles)

    def _init_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)

        self.header_label = QLabel("No report loaded.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        controls = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItems(
            ["All categories", "Plot Holes", "Relation Gaps", "Lore Suggestions"]
        )
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All severities", "critical", "warning", "info"])
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "new", "unchanged", "dismissed"])
        self.show_dismissed = QCheckBox("Show dismissed")
        self.dismiss_btn = QPushButton("Dismiss")
        self.open_source_btn = QPushButton("Open Source")
        self.open_source_btn.setEnabled(False)
        self.export_scope = QComboBox()
        self.export_scope.addItems(["Visible results", "Complete report"])
        self.export_markdown_btn = QPushButton("Export Markdown")
        self.export_json_btn = QPushButton("Export JSON")
        for widget in (
            self.category_filter,
            self.severity_filter,
            self.status_filter,
            self.show_dismissed,
            self.dismiss_btn,
            self.open_source_btn,
            self.export_scope,
            self.export_markdown_btn,
            self.export_json_btn,
        ):
            controls.addWidget(widget)
        layout.addLayout(controls)

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
        self.lore_table.setWordWrap(False)
        layout.addWidget(self.lore_table)

        self._details_label = QLabel("Finding Details")
        layout.addWidget(self._details_label)
        self.details = QTextBrowser()
        self.details.setPlaceholderText("Select a finding to see its complete details.")
        layout.addWidget(self.details)
        self._sources_label = QLabel("Sources")
        layout.addWidget(self._sources_label)
        self.evidence_list = QListWidget()
        self.evidence_list.setMaximumHeight(130)
        layout.addWidget(self.evidence_list)

        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
            table.setSelectionMode(table.SelectionMode.SingleSelection)
            table.setSortingEnabled(True)
            table.itemSelectionChanged.connect(
                lambda selected_table=table: self._on_row_selected(selected_table)
            )
            table.itemDoubleClicked.connect(lambda _item: self._open_source())
        self.category_filter.currentIndexChanged.connect(self._apply_filters)
        self.severity_filter.currentIndexChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.show_dismissed.toggled.connect(self._apply_filters)
        self.dismiss_btn.clicked.connect(self._dismiss_selected)
        self.open_source_btn.clicked.connect(self._open_source)
        self.evidence_list.itemSelectionChanged.connect(self._select_evidence)
        self.evidence_list.itemDoubleClicked.connect(lambda _item: self._open_source())
        self.export_markdown_btn.clicked.connect(self._export_markdown)
        self.export_json_btn.clicked.connect(self._export_json)

    def _apply_styles(self) -> None:
        """Apply theme-aware styles to all child widgets."""
        self.header_label.setStyleSheet(StyleHelper.get_preview_label_style())
        section_style = StyleHelper.get_section_header_style()
        self._holes_label.setStyleSheet(section_style)
        self._proposals_label.setStyleSheet(section_style)
        self._lore_label.setStyleSheet(section_style)
        self._details_label.setStyleSheet(section_style)
        self._sources_label.setStyleSheet(section_style)
        table_style = get_analysis_table_style()
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            table.setStyleSheet(table_style)
            sync_analysis_cell_styles(table)

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
        self._remember_report(report)
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
        self._show_empty_section_states(report)

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

    def show_terminal_message(self, message: str) -> None:
        """Clear streaming placeholders and show a terminal job message."""
        self.header_label.setText(message)
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            table.setRowCount(0)

    def display_partial_result(self, result_type: str, data: Any) -> None:
        """Populate one table section as its sub-analysis completes.

        Called from the main thread when the dedicated intelligence analysis
        manager forwards a partial result, so it is safe to update widgets here.

        Args:
            result_type: ``"holes"``, ``"relations"``, or ``"lore"``.
            data: The raw result tuple returned by the matching sub-analyzer.
        """
        if result_type == "estimate":
            eligible = data.get("eligible", {})
            summary = ", ".join(
                f"{name.replace('_', ' ')}: {count} eligible"
                for name, count in eligible.items()
            )
            self.header_label.setText(
                f"AI Analysis — Coverage: {summary or 'no eligible candidates'} | "
                f"Estimated initial requests: {data.get('estimated_initial_requests', 0)}; "
                "one repair retry may be used per malformed response."
            )
        elif result_type == "holes":
            holes = data[0]
            self._populate_plot_holes_from_list(holes)
        elif result_type == "relations":
            proposals = data[0]
            self._populate_proposals_from_list(proposals)
        elif result_type == "lore":
            suggestions, _audit, calendar_config = data[:3]
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

        Called once the dedicated intelligence analysis manager forwards the
        full report. Sections populated via :meth:`display_partial_result` are
        re-rendered from the authoritative report data; sections that were
        skipped (because the analysis type was narrower than ``"all"``, or
        because a sub-analysis failed) are replaced with empty tables instead
        of stale placeholders.

        Args:
            report: The final :class:`~src.core.analysis.IntelligenceReport`.
        """
        self._remember_report(report)
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
        self._show_empty_section_states(report)
        self._apply_filters()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _update_header(self, report: IntelligenceReport) -> None:
        """Update the summary header label.

        Args:
            report: The report to summarise.
        """
        statuses = ", ".join(
            f"{name}: {status.value}"
            for name, status in report.section_statuses.items()
        )
        failed = sum(item.failed for item in report.coverage.values())
        comparison = self.compare_current()
        stale = " | STALE" if self._stale else ""
        self.header_label.setText(
            f"AI Analysis | Model: {report.analysis_model} | "
            f"Holes: {len(report.plot_holes)} | "
            f"Proposals: {len(report.relation_proposals)} | "
            f"Lore Fills: {len(report.lore_suggestions)} | Failed requests: {failed}"
            f" | New: {comparison['new']} | Unchanged: {comparison['unchanged']} | "
            f"Resolved: {comparison['resolved']}{stale}"
            + (f" | {statuses}" if statuses else "")
        )

    def _show_empty_section_states(self, report: IntelligenceReport) -> None:
        """Explain skipped, failed, partial, and successful empty sections."""
        sections = (
            ("plot_holes", self.plot_holes_table, len(report.plot_holes)),
            ("relations", self.proposals_table, len(report.relation_proposals)),
            ("lore", self.lore_table, len(report.lore_suggestions)),
        )
        for name, table, finding_count in sections:
            if finding_count:
                continue
            status = report.section_statuses.get(name)
            coverage = report.coverage.get(name)
            if status is None:
                continue
            if status.value == "skipped":
                message = (
                    "Skipped — no eligible candidates."
                    if coverage is not None
                    else "Not selected for this run."
                )
            elif status.value == "failed":
                errors = "; ".join((coverage.errors if coverage else [])[:3])
                message = f"Failed — {errors or 'all requests failed.'}"
            elif status.value == "partial":
                failed = coverage.failed if coverage else 0
                message = f"Partial — {failed} request(s) failed."
            elif coverage is not None and coverage.succeeded > 0:
                message = "No findings."
            else:
                message = "Finished without a successful candidate."
            table.setRowCount(1)
            item = QTableWidgetItem(message)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(0, 0, item)

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
        self.plot_holes_table.setSortingEnabled(False)
        for row, hole in enumerate(holes):
            sev_item = QTableWidgetItem(hole.severity.value)
            color = SEVERITY_COLORS.get(hole.severity)
            if color:
                sev_item.setForeground(QBrush(QColor(color)))
            self.plot_holes_table.setItem(row, 0, sev_item)
            sev_item.setData(Qt.ItemDataRole.UserRole, hole)
            self.plot_holes_table.setItem(row, 1, QTableWidgetItem(hole.entity_name))
            self.plot_holes_table.setCellWidget(
                row, 2, make_text_cell(hole.description)
            )
            self.plot_holes_table.setCellWidget(
                row, 3, make_text_cell(hole.suggested_resolution or "")
            )
            self.plot_holes_table.setItem(
                row, 4, QTableWidgetItem(hole.evidence_strength.value.title())
            )
        self.plot_holes_table.setSortingEnabled(True)
        self.plot_holes_table.resizeRowsToContents()

    def _populate_proposals_from_list(self, proposals: list[RelationProposal]) -> None:
        """Fill the proposals table from a list of :class:`~src.core.analysis.RelationProposal`.

        The reasoning cell uses a selectable QLabel widget with text wrapped
        at 75 characters.

        Args:
            proposals: Relation proposals to display.
        """
        self.proposals_table.setRowCount(len(proposals))
        self.proposals_table.setSortingEnabled(False)
        for row, proposal in enumerate(proposals):
            source_item = QTableWidgetItem(proposal.source_name)
            source_item.setData(Qt.ItemDataRole.UserRole, proposal)
            self.proposals_table.setItem(row, 0, source_item)
            self.proposals_table.setItem(
                row, 1, QTableWidgetItem(proposal.target_name)
            )
            self.proposals_table.setItem(
                row, 2, QTableWidgetItem(proposal.suggested_relation_type)
            )
            self.proposals_table.setItem(
                row, 3, QTableWidgetItem(proposal.evidence_strength.value.title())
            )
            self.proposals_table.setCellWidget(
                row, 4, make_text_cell(proposal.reasoning)
            )
        self.proposals_table.setSortingEnabled(True)
        self.proposals_table.resizeRowsToContents()

    def _populate_lore_from_list(self, suggestions: list[LoreGapFiller]) -> None:
        """Fill the lore-suggestions table from a list of :class:`~src.core.analysis.LoreGapFiller`.

        Each row stays compact and shows only the number and titles of generated
        suggestions. Selecting the row reveals full text in the details pane.

        Args:
            suggestions: Lore gap fillers to display.
        """
        self.lore_table.setRowCount(len(suggestions))
        self.lore_table.setSortingEnabled(False)
        for row, filler in enumerate(suggestions):
            start_item = QTableWidgetItem(
                fmt_lore_date(filler.start_date, self._converter)
            )
            start_item.setData(Qt.ItemDataRole.UserRole, filler)
            self.lore_table.setItem(row, 0, start_item)
            self.lore_table.setItem(
                row,
                1,
                QTableWidgetItem(fmt_lore_date(filler.end_date, self._converter)),
            )
            count = len(filler.suggestions)
            noun = "suggestion" if count == 1 else "suggestions"
            titles = "; ".join(item.name for item in filler.suggestions)
            preview = QTableWidgetItem(f"{count} {noun} — {titles}")
            preview.setToolTip("\n".join(item.name for item in filler.suggestions))
            self.lore_table.setItem(row, 2, preview)
            self.lore_table.setRowHeight(row, 32)
        self.lore_table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # Session interaction
    # ------------------------------------------------------------------

    def _remember_report(self, report: IntelligenceReport) -> None:
        """Keep current and previous reports in memory for this world only."""
        if self._current_report is report:
            return
        if (
            self._current_report is not None
            and self._current_report.world_id != report.world_id
        ):
            self.clear_session()
        if self._current_report is not None:
            self._previous_reports.append(self._current_report)
        self._current_report = report
        for category, status in report.section_statuses.items():
            if status.value != "skipped" and category in self._reports_by_type:
                self._reports_by_type[category].append(report)
        self._stale = False

    @staticmethod
    def _findings(report: IntelligenceReport | None) -> list[Any]:
        if report is None:
            return []
        return [
            *report.plot_holes,
            *report.relation_proposals,
            *report.lore_suggestions,
        ]

    def compare_current(self) -> dict[str, int]:
        """Compare stable finding fingerprints with the immediately previous run."""
        current: set[str] = set()
        previous: set[str] = set()
        for category, reports in self._reports_by_type.items():
            if not reports or reports[-1] is not self._current_report:
                continue
            current.update(
                item.fingerprint
                for item in self._category_findings(reports[-1], category)
            )
            if len(reports) > 1:
                previous.update(
                    item.fingerprint
                    for item in self._category_findings(reports[-2], category)
                )
        return {
            "new": len(current - previous),
            "unchanged": len(current & previous),
            "resolved": len(previous - current),
            "dismissed": len(current & self._dismissals.keys()),
        }

    def mark_stale(self) -> None:
        """Mark all in-memory results stale after a successful world change."""
        if self._current_report is None:
            return
        self._stale = True
        self._update_header(self._current_report)

    def clear_session(self) -> None:
        """Clear reports and dismissals when the open world changes."""
        self._current_report = None
        self._previous_reports.clear()
        for reports in self._reports_by_type.values():
            reports.clear()
        self._dismissals.clear()
        self._stale = False
        self._selected_finding = None
        self._selected_evidence_id = None
        self._details_label.setText("Finding Details")
        self.details.clear()
        self.evidence_list.clear()
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            table.setRowCount(0)
        self.header_label.setText("No report loaded.")

    def _selected_table_finding(self) -> Any | None:
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            rows = table.selectionModel().selectedRows()
            if not rows:
                continue
            item = table.item(rows[0].row(), 0)
            if item is not None:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_row_selected(self, selected_table: QTableWidget | None = None) -> None:
        """Update details and keep one active selection across result tables."""
        if (
            selected_table is not None
            and selected_table.selectionModel().hasSelection()
        ):
            for table in (
                self.plot_holes_table,
                self.proposals_table,
                self.lore_table,
            ):
                if table is selected_table:
                    continue
                table.blockSignals(True)
                table.clearSelection()
                sync_analysis_cell_styles(table)
                table.blockSignals(False)
        finding = self._selected_table_finding()
        if finding is None:
            return
        self._selected_finding = finding
        self._selected_evidence_id = None
        self._details_label.setText(
            "Suggestion Details" if isinstance(finding, LoreGapFiller) else "Finding Details"
        )
        self.evidence_list.clear()
        evidence = list(getattr(finding, "evidence", []))
        for reference in evidence:
            label = reference.object_name or reference.object_id
            item = QListWidgetItem(
                f"{reference.object_type.title()}: {label} — {reference.field}"
            )
            item.setData(Qt.ItemDataRole.UserRole, reference.evidence_id)
            self.evidence_list.addItem(item)
        self.details.setPlainText(self._finding_details(finding))
        self.open_source_btn.setEnabled(bool(self._primary_source_id(finding)))

    @staticmethod
    def _finding_details(finding: Any) -> str:
        if isinstance(finding, PlotHole):
            resolution = finding.suggested_resolution or "No resolution suggested."
            return (
                f"{finding.entity_name}\n{finding.severity.value.title()} — "
                f"{finding.evidence_strength.value.title()} evidence\n\n"
                f"{finding.description}\n\nSuggested resolution:\n{resolution}"
            )
        if isinstance(finding, RelationProposal):
            return (
                f"{finding.source_name} —{finding.suggested_relation_type}→ "
                f"{finding.target_name}\n"
                f"{finding.evidence_strength.value.title()} evidence\n\n"
                f"{finding.reasoning}"
            )
        suggestions = "\n\n".join(
            f"{item.name} ({item.date_str})\n{item.description}"
            for item in finding.suggestions
        )
        return (
            "Creative lore suggestion — not a factual finding\n"
            f"{finding.evidence_strength.value.title()} boundary evidence\n\n"
            f"{suggestions}"
        )

    def _select_evidence(self) -> None:
        selected = self.evidence_list.selectedItems()
        self._selected_evidence_id = (
            str(selected[0].data(Qt.ItemDataRole.UserRole)) if selected else None
        )
        self.open_source_btn.setEnabled(bool(self._selected_source_id()))

    @staticmethod
    def _primary_source_id(finding: Any) -> str:
        if isinstance(finding, PlotHole):
            return finding.entity_id
        if isinstance(finding, RelationProposal):
            return finding.source_id
        evidence = getattr(finding, "evidence", [])
        return evidence[0].object_id if evidence else ""

    def _selected_source_id(self) -> str:
        finding = self._selected_finding
        if finding is None:
            return ""
        if self._selected_evidence_id:
            for reference in getattr(finding, "evidence", []):
                if reference.evidence_id == self._selected_evidence_id:
                    return reference.object_id
        return self._primary_source_id(finding)

    def _open_source(self) -> None:
        source_id = self._selected_source_id()
        if source_id:
            self.open_source_requested.emit(source_id)

    def _dismiss_selected(self) -> None:
        finding = self._selected_finding
        fingerprint = str(getattr(finding, "fingerprint", ""))
        if not fingerprint:
            return
        note, accepted = QInputDialog.getText(
            self, "Dismiss finding", "Optional session note"
        )
        if not accepted:
            return
        self._dismissals[fingerprint] = note.strip()
        self._apply_filters()
        if self._current_report is not None:
            self._update_header(self._current_report)

    def _finding_status(self, finding: Any) -> str:
        fingerprint = str(getattr(finding, "fingerprint", ""))
        if fingerprint in self._dismissals:
            return "dismissed"
        category = self._finding_category(finding)
        reports = self._reports_by_type.get(category, [])
        if len(reports) > 1:
            previous = {
                item.fingerprint
                for item in self._category_findings(reports[-2], category)
            }
            if fingerprint in previous:
                return "unchanged"
        return "new"

    @staticmethod
    def _finding_category(finding: Any) -> str:
        if isinstance(finding, PlotHole):
            return "plot_holes"
        if isinstance(finding, RelationProposal):
            return "relations"
        return "lore"

    @staticmethod
    def _category_findings(
        report: IntelligenceReport, category: str
    ) -> list[Any]:
        if category == "plot_holes":
            return list(report.plot_holes)
        if category == "relations":
            return list(report.relation_proposals)
        if category == "lore":
            return list(report.lore_suggestions)
        return []

    @staticmethod
    def _coverage_line(report: IntelligenceReport, name: str) -> str:
        coverage = report.coverage.get(name)
        if coverage is None:
            return "eligible 0, attempted 0, succeeded 0, failed 0"
        return (
            f"eligible {coverage.eligible}, attempted {coverage.attempted}, "
            f"succeeded {coverage.succeeded}, failed {coverage.failed}"
        )

    def _apply_filters(self) -> None:
        category_index = self.category_filter.currentIndex()
        self._holes_label.setVisible(category_index in (0, 1))
        self.plot_holes_table.setVisible(category_index in (0, 1))
        self._proposals_label.setVisible(category_index in (0, 2))
        self.proposals_table.setVisible(category_index in (0, 2))
        self._lore_label.setVisible(category_index in (0, 3))
        self.lore_table.setVisible(category_index in (0, 3))
        severity = self.severity_filter.currentText()
        status = self.status_filter.currentText()
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                finding = item.data(Qt.ItemDataRole.UserRole) if item else None
                if finding is None:
                    continue
                finding_status = self._finding_status(finding)
                dismissed_hidden = (
                    finding_status == "dismissed" and not self.show_dismissed.isChecked()
                )
                status_hidden = status != "All statuses" and finding_status != status
                severity_hidden = (
                    severity != "All severities"
                    and isinstance(finding, PlotHole)
                    and finding.severity.value != severity
                )
                table.setRowHidden(
                    row, dismissed_hidden or status_hidden or severity_hidden
                )

    def _visible_findings(self) -> list[Any]:
        visible: list[Any] = []
        for table in (
            self.plot_holes_table,
            self.proposals_table,
            self.lore_table,
        ):
            if not table.isVisible():
                continue
            for row in range(table.rowCount()):
                if table.isRowHidden(row):
                    continue
                item = table.item(row, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
                    visible.append(item.data(Qt.ItemDataRole.UserRole))
        return visible

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: IntelligencePanel._json_safe(getattr(value, field.name))
                for field in dataclasses.fields(value)
            }
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): IntelligencePanel._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [IntelligencePanel._json_safe(item) for item in value]
        return value

    def _export_payload(self, visible_only: bool = True) -> dict[str, Any]:
        report = self._current_report
        if report is None:
            return {}
        findings = self._visible_findings() if visible_only else self._findings(report)
        return {
            "report": self._json_safe(report),
            "exported_findings": self._json_safe(findings),
            "dismissals": dict(self._dismissals),
            "stale": self._stale,
            "comparison": self.compare_current(),
        }

    def _export_json(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export AI analysis", "analysis-report.json", "JSON (*.json)"
        )
        if path:
            visible_only = self.export_scope.currentIndex() == 0
            Path(path).write_text(
                json.dumps(
                    self._export_payload(visible_only),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    def _export_markdown(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export AI analysis",
            "analysis-report.md",
            "Markdown (*.md)",
        )
        if not path or self._current_report is None:
            return
        report = self._current_report
        captured = datetime.datetime.fromtimestamp(
            report.snapshot_timestamp or report.timestamp
        ).isoformat()
        lines = [
            "# AI Analysis Report",
            "",
            f"- Report ID: `{report.report_id}`",
            f"- World ID: `{report.world_id}`",
            f"- Snapshot: {captured}",
            f"- Scope: {report.scope.kind.value}",
            f"- Preset: {report.preset.value}",
            f"- Stale: {'yes' if self._stale else 'no'}",
            "",
            "## Section status and coverage",
            "",
            *[
                f"- {name}: {status.value}; {self._coverage_line(report, name)}"
                for name, status in report.section_statuses.items()
            ],
            "",
        ]
        findings = (
            self._visible_findings()
            if self.export_scope.currentIndex() == 0
            else self._findings(report)
        )
        for finding in findings:
            lines.extend(
                [
                    f"## {type(finding).__name__}",
                    "",
                    self._finding_details(finding),
                    "",
                    f"Dismissed: {'yes' if finding.fingerprint in self._dismissals else 'no'}",
                    f"Dismissal note: {self._dismissals.get(finding.fingerprint, '')}",
                    "",
                    "Evidence:",
                    *[
                        f"- {item.object_type}: {item.object_name} "
                        f"(`{item.object_id}`) — {item.excerpt}"
                        for item in getattr(finding, "evidence", [])
                    ],
                    "",
                ]
            )
        Path(path).write_text("\n".join(lines), encoding="utf-8")
