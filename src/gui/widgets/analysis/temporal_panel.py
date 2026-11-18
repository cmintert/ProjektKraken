"""Temporal Panel Widget.

Displays a :class:`~src.core.analysis.TemporalAnalysisReport` in a read-only
tabular layout.  Shows a header summary, a timeline-gaps table, a temporal-
conflicts table, and a character-lifespans table.

Text-heavy columns (message, suggestion) use selectable :class:`QLabel` cell
widgets so the user can copy content directly from the table.  Lines wrap at
≤75 characters.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import CharacterLifespan, TemporalAnalysisReport
from src.core.calendar import CalendarConverter
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.analysis._analysis_utils import (
    configure_stretch_columns,
    fmt_lore_date,
    get_analysis_table_style,
    make_analysis_table,
    make_text_cell,
    sync_analysis_cell_styles,
)
from src.gui.widgets.standard_buttons import StandardButton as QPushButton

logger = logging.getLogger(__name__)

# Column headers for each table
_GAP_HEADERS = ["Start Date", "End Date", "Duration (years)", "Message"]
_CONFLICT_HEADERS = ["Type", "Entity", "Date", "Message", "Suggestion"]
_LIFESPAN_HEADERS = ["Name", "Birth", "Death", "Age at death"]


class TemporalPanel(QWidget):
    """Read-only panel displaying a temporal analysis report.

    Provides four sections:
    - A header label summarising the calendar and high-level counts.
    - A gaps table listing every timeline gap with start, end, duration,
      and a descriptive message.  The message cell is a selectable QLabel.
    - A conflicts table listing every temporal conflict with type, entity,
      problem date, message, and suggestion.  Message and suggestion cells
      are selectable QLabel widgets.
    - A lifespans table with date evidence, age at death and source navigation.

    Call :meth:`display_report` to populate or refresh the panel.
    """

    open_source_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the panel and build the UI layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._lifespans: list[CharacterLifespan] = []
        self._init_ui()
        self._apply_styles()
        self._connect_theme_changes()

    def _init_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)

        self.header_label = QLabel("No report loaded.")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        self._gaps_label = QLabel("Timeline Gaps")
        layout.addWidget(self._gaps_label)
        self.gaps_table = make_analysis_table(_GAP_HEADERS)
        layout.addWidget(self.gaps_table)

        self._conflicts_label = QLabel("Temporal Conflicts")
        layout.addWidget(self._conflicts_label)
        self.conflicts_table = make_analysis_table(_CONFLICT_HEADERS)
        configure_stretch_columns(self.conflicts_table, 3, 4)  # Message, Suggestion
        layout.addWidget(self.conflicts_table)
        self.open_conflict_source_btn = declare_inspection(
            QPushButton("Open Source"),
            "src-gui-widgets-analysis-temporal-panel-temporalpanel-init-ui-self-open-conflict-source-btn|analysis.review|help-inspect-src-gui-widgets-analysis-temporal-panel-temporalpanel-init-ui-self-open-conflict-source-btn",
        )
        self.open_conflict_source_btn.setEnabled(False)
        layout.addWidget(self.open_conflict_source_btn)
        self.conflicts_table.itemSelectionChanged.connect(
            self._update_conflict_navigation
        )
        self.conflicts_table.itemDoubleClicked.connect(
            lambda _item: self._open_conflict_source()
        )
        self.open_conflict_source_btn.clicked.connect(self._open_conflict_source)
        self._init_lifespan_section(layout)

    def _init_lifespan_section(self, layout: QVBoxLayout) -> None:
        self._lifespans_label = QLabel("Character Lifespans")
        layout.addWidget(self._lifespans_label)
        self._lifespans_hint = QLabel(
            "Link birth and death Events from a Character's Timeline."
        )
        self._lifespans_hint.setWordWrap(True)
        layout.addWidget(self._lifespans_hint)
        self.lifespans_table = make_analysis_table(_LIFESPAN_HEADERS)
        self.lifespans_table.setAccessibleName("Character Lifespans")
        self.lifespans_table.setTabKeyNavigation(False)
        layout.addWidget(self.lifespans_table)
        self._lifespan_details = QLabel()
        self._lifespan_details.setTextFormat(Qt.TextFormat.PlainText)
        self._lifespan_details.setWordWrap(True)
        layout.addWidget(self._lifespan_details)
        self.open_birth_source_btn = QPushButton("Open Birth Event")
        self.open_death_source_btn = QPushButton("Open Death Event")
        layout.addWidget(
            self.open_birth_source_btn, alignment=Qt.AlignmentFlag.AlignLeft
        )
        layout.addWidget(
            self.open_death_source_btn, alignment=Qt.AlignmentFlag.AlignLeft
        )
        self.setTabOrder(self.lifespans_table, self.open_birth_source_btn)
        self.setTabOrder(self.open_birth_source_btn, self.open_death_source_btn)
        self.open_birth_source_btn.clicked.connect(
            lambda: self._open_lifespan_source(birth=True)
        )
        self.open_death_source_btn.clicked.connect(
            lambda: self._open_lifespan_source(birth=False)
        )
        self.lifespans_table.itemSelectionChanged.connect(self._update_lifespan_details)
        self._update_lifespan_details()

    def _apply_styles(self) -> None:
        """Apply theme-aware styles to all child widgets."""
        self.header_label.setStyleSheet(StyleHelper.get_preview_label_style())
        section_style = StyleHelper.get_section_header_style()
        self._gaps_label.setStyleSheet(section_style)
        self._conflicts_label.setStyleSheet(section_style)
        self._lifespans_label.setStyleSheet(section_style)
        self._lifespans_hint.setStyleSheet(StyleHelper.get_preview_label_style())
        self._lifespan_details.setStyleSheet(StyleHelper.get_preview_label_style())
        source_style = StyleHelper.get_action_role_style("secondary")
        for button in (
            self.open_conflict_source_btn,
            self.open_birth_source_btn,
            self.open_death_source_btn,
        ):
            button.setStyleSheet(source_style)
        table_style = get_analysis_table_style()
        for table in (self.gaps_table, self.conflicts_table, self.lifespans_table):
            table.setStyleSheet(table_style)
            sync_analysis_cell_styles(table)

    def _connect_theme_changes(self) -> None:
        """Subscribe to theme-change notifications for live style updates."""
        try:
            connect_theme(self, self._apply_styles)
        except Exception as exc:
            logger.error("Failed to connect theme changes: %s", exc)

    def display_report(self, report: TemporalAnalysisReport) -> None:
        """Populate the panel with data from a temporal analysis report.

        Replaces any previously displayed report.

        Args:
            report: The :class:`~src.core.analysis.TemporalAnalysisReport`
                to display.
        """
        converter = None
        if report.calendar_config is not None:
            try:
                from src.core.calendar import CalendarConverter

                converter = CalendarConverter(report.calendar_config)
            except Exception:
                logger.debug("TemporalPanel: could not build CalendarConverter")

        self._update_header(report)
        self._populate_gaps_table(report, converter)
        self._populate_conflicts_table(report, converter)
        self._populate_lifespans_table(report, converter)

    def _update_header(self, report: TemporalAnalysisReport) -> None:
        """Update the summary header label.

        Args:
            report: The report to summarise.
        """
        self.header_label.setText(
            f"Temporal Analysis | Calendar: {report.calendar_name} | "
            f"Gaps: {len(report.timeline_gaps)} | "
            f"Conflicts: {len(report.conflicts)}"
        )

    def _populate_gaps_table(
        self, report: TemporalAnalysisReport, converter: CalendarConverter | None
    ) -> None:
        """Fill the gaps table from the report's timeline_gaps list.

        The message column uses a selectable QLabel widget with text wrapped
        at 75 characters.

        Args:
            report: The report whose gaps are displayed.
            converter: Optional ``CalendarConverter`` for date formatting.
        """
        self.gaps_table.setRowCount(len(report.timeline_gaps))
        for row, gap in enumerate(report.timeline_gaps):
            self.gaps_table.setItem(
                row, 0, QTableWidgetItem(fmt_lore_date(gap.start_date, converter))
            )
            self.gaps_table.setItem(
                row, 1, QTableWidgetItem(fmt_lore_date(gap.end_date, converter))
            )
            if converter is not None:
                try:
                    year_len = converter._config.get_year_length(1)
                    dur_str = f"{gap.gap_duration / year_len:.0f}"
                except Exception:
                    dur_str = f"{gap.gap_duration:.0f}"
            else:
                dur_str = f"{gap.gap_duration / 365.0:.0f}"
            self.gaps_table.setItem(row, 2, QTableWidgetItem(dur_str))
            self.gaps_table.setCellWidget(row, 3, make_text_cell(gap.message))
        self.gaps_table.resizeRowsToContents()

    def _populate_conflicts_table(
        self, report: TemporalAnalysisReport, converter: CalendarConverter | None
    ) -> None:
        """Fill the conflicts table from the report's conflicts list.

        Message and suggestion columns use selectable QLabel widgets with text
        wrapped at 75 characters.

        Args:
            report: The report whose conflicts are displayed.
            converter: Optional ``CalendarConverter`` for date formatting.
        """
        self.conflicts_table.setRowCount(len(report.conflicts))
        for row, conflict in enumerate(report.conflicts):
            type_item = QTableWidgetItem(conflict.conflict_type)
            type_item.setData(Qt.ItemDataRole.UserRole, conflict.entity_id)
            evidence_text = "\n".join(
                f"{item.object_name}: {item.excerpt or item.field}"
                for item in conflict.evidence
            )
            if evidence_text:
                type_item.setToolTip(evidence_text)
            self.conflicts_table.setItem(row, 0, type_item)
            self.conflicts_table.setItem(row, 1, QTableWidgetItem(conflict.entity_name))
            self.conflicts_table.setItem(
                row,
                2,
                QTableWidgetItem(fmt_lore_date(conflict.problem_date, converter)),
            )
            self.conflicts_table.setCellWidget(row, 3, make_text_cell(conflict.message))
            self.conflicts_table.setCellWidget(
                row, 4, make_text_cell(conflict.suggestion or "")
            )
        self.conflicts_table.resizeRowsToContents()

    def _selected_conflict_source(self) -> str:
        rows = self.conflicts_table.selectionModel().selectedRows()
        if not rows:
            return ""
        item = self.conflicts_table.item(rows[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _update_conflict_navigation(self) -> None:
        self.open_conflict_source_btn.setEnabled(bool(self._selected_conflict_source()))

    def _open_conflict_source(self) -> None:
        source_id = self._selected_conflict_source()
        if source_id:
            self.open_source_requested.emit(source_id)

    def _populate_lifespans_table(
        self, report: TemporalAnalysisReport, converter: CalendarConverter | None
    ) -> None:
        """Fill the lifespans table from the report's character_lifespans list.

        Args:
            report: The report whose character lifespans are displayed.
            converter: Optional ``CalendarConverter`` for date formatting.
        """
        self.lifespans_table.clearSelection()
        self._lifespans = report.character_lifespans
        self.lifespans_table.setRowCount(len(self._lifespans))
        for row, lifespan in enumerate(self._lifespans):
            values = (
                lifespan.entity_name,
                lifespan.birth_source.caption
                if lifespan.birth_source
                else fmt_lore_date(lifespan.birth_date, converter),
                lifespan.death_source.caption
                if lifespan.death_source
                else fmt_lore_date(lifespan.death_date, converter),
                self._age_caption(lifespan),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.lifespans_table.setItem(row, column, item)
        self._update_lifespan_details()

    @staticmethod
    def _age_caption(lifespan: CharacterLifespan) -> str:
        result = lifespan.age_at_death
        if result is None:
            if lifespan.life_span_years is not None and lifespan.is_valid():
                return f"About {lifespan.life_span_years:.0f} years"
            return "Age unavailable"
        if not result.intervals:
            return "Age unavailable"
        values = " or ".join(
            f"{int(interval.lower)}"
            if interval.lower == interval.upper
            else f"{int(interval.lower)}–{int(interval.upper)}"
            for interval in result.intervals
            if interval.lower is not None and interval.upper is not None
        )
        prefix = {"estimate": "About ", "outer_bound": "Within "}.get(result.kind, "")
        unit = "year" if values == "1" else "years"
        return f"{prefix}{values} {unit}"

    def _selected_lifespan(self) -> CharacterLifespan | None:
        rows = self.lifespans_table.selectionModel().selectedRows()
        return self._lifespans[rows[0].row()] if rows else None

    def _update_lifespan_details(self) -> None:
        rows = self.lifespans_table.selectionModel().selectedRows()
        details = "Select a character to review the dates used for their age."
        if rows:
            row = rows[0].row()
            lifespan = self._lifespans[row]
            result = lifespan.age_at_death
            lines = []
            for label, column in (("Birth", 1), ("Death", 2), ("Age at death", 3)):
                if item := self.lifespans_table.item(row, column):
                    lines.append(f"{label}: {item.text()}")
            if result is not None and result.reason:
                lines.append(result.reason)
            details = "\n".join(lines)
        self._lifespan_details.setText(details)
        self.open_birth_source_btn.setEnabled(
            self._lifespan_source_id(birth=True) is not None
        )
        self.open_death_source_btn.setEnabled(
            self._lifespan_source_id(birth=False) is not None
        )

    def _lifespan_source_id(self, *, birth: bool) -> str | None:
        lifespan = self._selected_lifespan()
        if lifespan is None:
            return None
        source = lifespan.birth_source if birth else lifespan.death_source
        return source.event_id if source else None

    def _open_lifespan_source(self, *, birth: bool) -> None:
        if source_id := self._lifespan_source_id(birth=birth):
            self.open_source_requested.emit(source_id)
