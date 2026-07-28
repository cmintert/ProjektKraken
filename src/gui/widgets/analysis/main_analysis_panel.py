"""Main Analysis Panel Widget.

Hosts all three Tier 1 analysis sub-panels (World Validation, Temporal
Analysis, Intelligence Suite) in a single tabbed interface with trigger
buttons for each analysis type.

The panel is intentionally "dumb": the buttons emit no business logic and
hold no coordinator reference.  All wiring (button → coordinator, worker
signal → slot) is done by :class:`~src.app.connection_manager.ConnectionManager`.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.analysis import (
    IntelligenceReport,
    TemporalAnalysisReport,
    WorldValidationReport,
)
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.analysis.analysis_panel import AnalysisPanel
from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel
from src.gui.widgets.analysis.temporal_panel import TemporalPanel

logger = logging.getLogger(__name__)


class MainAnalysisPanel(QWidget):
    """Unified panel combining Validation, Temporal, and Intelligence analysis.

    Provides:
    - Three trigger buttons (Validate World / Analyze Timeline / Run AI
      Analysis) plus cooperative cancellation for AI analysis.
    - A status label showing the current state (idle, running, complete,
      or error).
    - A :class:`~PySide6.QtWidgets.QTabWidget` with three tabs, one per
      sub-panel (:class:`~src.gui.widgets.analysis_panel.AnalysisPanel`,
      :class:`~src.gui.widgets.temporal_panel.TemporalPanel`,
      :class:`~src.gui.widgets.intelligence_panel.IntelligencePanel`).

    The panel automatically switches to the relevant tab when a report is
    delivered via :meth:`on_validation_complete`, :meth:`on_temporal_complete`,
    or :meth:`on_intelligence_complete`.

    Button signals and worker signals are wired externally by
    :class:`~src.app.connection_manager.ConnectionManager` to keep
    this widget free of coordinator dependencies.
    """

    _TAB_VALIDATION = 0
    _TAB_TIMELINE = 1
    _TAB_INTELLIGENCE = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the panel and build the UI layout.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._standard_analysis_running = False
        self._intelligence_running = False
        self._intelligence_cancelling = False
        self._init_ui()

    def _init_ui(self) -> None:
        """Build and wire the widget layout."""
        layout = QVBoxLayout(self)

        # --- Trigger buttons ---
        btn_layout = QHBoxLayout()
        self.validate_btn = QPushButton("Validate World")
        self.temporal_btn = QPushButton("Analyze Timeline")
        self.intelligence_btn = QPushButton("Run AI Analysis")
        self.cancel_intelligence_btn = QPushButton("Cancel AI Analysis")
        self.cancel_intelligence_btn.setEnabled(False)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(StyleHelper.get_preview_label_style())
        for btn in (
            self.validate_btn,
            self.temporal_btn,
            self.intelligence_btn,
            self.cancel_intelligence_btn,
        ):
            btn_layout.addWidget(btn)
        btn_layout.addWidget(self.status_label, stretch=1)
        layout.addLayout(btn_layout)

        # --- Tab widget ---
        self.tab_widget = QTabWidget()

        self.validation_panel = AnalysisPanel()
        self.temporal_panel = TemporalPanel()
        self.intelligence_panel = IntelligencePanel()

        self.tab_widget.addTab(self.validation_panel, "Validation")
        self.tab_widget.addTab(self.temporal_panel, "Timeline")
        self.tab_widget.addTab(self.intelligence_panel, "Intelligence")

        layout.addWidget(self.tab_widget)

    # ------------------------------------------------------------------
    # Loading-state helpers (called by ConnectionManager button wrappers)
    # ------------------------------------------------------------------

    def on_intelligence_analysis_started(self) -> None:
        """Prepare the Intelligence tab for streaming and switch to it.

        Called by the :class:`~src.app.connection_manager.ConnectionManager`
        button lambda immediately before the coordinator triggers the worker,
        so the loading placeholders appear without waiting for the first
        partial result.
        """
        self._intelligence_running = True
        self._intelligence_cancelling = False
        self.intelligence_btn.setEnabled(False)
        self.cancel_intelligence_btn.setEnabled(True)
        self._show_intelligence_status()
        self.tab_widget.setCurrentIndex(self._TAB_INTELLIGENCE)
        self.intelligence_panel.start_streaming()

    def on_analysis_started(self, message: str) -> None:
        """Disable buttons and update the status label when analysis begins.

        This method is called by the :class:`~src.app.connection_manager.\
ConnectionManager` button lambdas before invoking the coordinator, so the
        UI reflects a busy state immediately on click.

        Args:
            message: Short description to show in the status label while
                running (e.g. ``"Validating world…"``).
        """
        self._standard_analysis_running = True
        self._set_standard_buttons_enabled(False)
        if self._intelligence_running:
            self.status_label.setText(f"{message} AI analysis continues in background.")
        else:
            self.status_label.setText(message)

    def _set_standard_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable the local validation and temporal triggers.

        Args:
            enabled: ``True`` to enable; ``False`` to disable.
        """
        for btn in (self.validate_btn, self.temporal_btn):
            btn.setEnabled(enabled)

    def _finish_intelligence(self) -> None:
        """Restore the AI trigger buttons after a terminal job state."""
        self._intelligence_running = False
        self._intelligence_cancelling = False
        self.intelligence_btn.setEnabled(True)
        self.cancel_intelligence_btn.setEnabled(False)

    def _show_intelligence_status(self) -> None:
        """Show the current background AI state in the shared status label."""
        if self._intelligence_cancelling:
            self.status_label.setText("Cancelling AI analysis…")
        else:
            self.status_label.setText("Running AI analysis from world snapshot…")

    # ------------------------------------------------------------------
    # Report-delivery slots (connected by ConnectionManager)
    # ------------------------------------------------------------------

    @Slot(object)
    def on_validation_complete(self, report: WorldValidationReport) -> None:
        """Display a validation report and switch to the Validation tab.

        Re-enables the trigger buttons after the report is displayed.

        Args:
            report: The :class:`~src.core.analysis.WorldValidationReport` to display.
        """
        self.validation_panel.display_report(report)
        self.tab_widget.setCurrentIndex(self._TAB_VALIDATION)
        self._standard_analysis_running = False
        self._set_standard_buttons_enabled(True)
        if self._intelligence_running:
            self._show_intelligence_status()
        else:
            self.status_label.setText("Validation complete.")
        logger.debug("MainAnalysisPanel: validation report received")

    @Slot(object)
    def on_temporal_complete(self, report: TemporalAnalysisReport) -> None:
        """Display a temporal report and switch to the Timeline tab.

        Re-enables the trigger buttons after the report is displayed.

        Args:
            report: The :class:`~src.core.analysis.TemporalAnalysisReport` to display.
        """
        self.temporal_panel.display_report(report)
        self.tab_widget.setCurrentIndex(self._TAB_TIMELINE)
        self._standard_analysis_running = False
        self._set_standard_buttons_enabled(True)
        if self._intelligence_running:
            self._show_intelligence_status()
        else:
            self.status_label.setText("Timeline analysis complete.")
        logger.debug("MainAnalysisPanel: temporal report received")

    @Slot(str, object)
    def on_intelligence_partial(self, result_type: str, data: Any) -> None:
        """Forward a completed sub-analysis to the Intelligence panel.

        Called by the dedicated intelligence analysis manager as each of the
        three concurrent sub-analyses finishes.

        Args:
            result_type: One of ``"holes"``, ``"relations"``, or ``"lore"``.
            data: The raw result tuple returned by the sub-analyzer.
        """
        self.intelligence_panel.display_partial_result(result_type, data)

    @Slot(object)
    def on_intelligence_complete(self, report: IntelligenceReport) -> None:
        """Finalise the Intelligence panel once all sub-analyses are done.

        Updates the header label with final counts, clears any remaining
        loading placeholders, and re-enables the trigger buttons.

        Args:
            report: The :class:`~src.core.analysis.IntelligenceReport` to finalise.
        """
        self.intelligence_panel.finalize_report(report)
        self.tab_widget.setCurrentIndex(self._TAB_INTELLIGENCE)
        captured_at = report.snapshot_timestamp
        if captured_at is None:
            status = "AI analysis complete."
        else:
            captured = datetime.datetime.fromtimestamp(captured_at).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            status = f"AI analysis complete — snapshot captured {captured}."
        self.status_label.setText(status)
        self._finish_intelligence()
        logger.debug("MainAnalysisPanel: intelligence report received")

    @Slot()
    def on_intelligence_cancelling(self) -> None:
        """Show cooperative cancellation progress."""
        self._intelligence_cancelling = True
        self._show_intelligence_status()
        self.cancel_intelligence_btn.setEnabled(False)

    @Slot()
    def on_intelligence_cancelled(self) -> None:
        """Restore the panel after the active AI job is cancelled."""
        self.intelligence_panel.show_terminal_message("AI Analysis — Cancelled")
        self.status_label.setText("AI analysis cancelled.")
        self._finish_intelligence()

    @Slot(str)
    def on_intelligence_failed(self, message: str) -> None:
        """Restore the panel after snapshot or provider failure."""
        self.intelligence_panel.show_terminal_message("AI Analysis — Failed")
        self.status_label.setText(message)
        self._finish_intelligence()
