"""Main Analysis Panel Widget.

Hosts all three Tier 1 analysis sub-panels (World Validation, Temporal
Analysis, Intelligence Suite) in a single tabbed interface with trigger
buttons for each analysis type.

The panel is intentionally "dumb": the buttons emit no business logic and
hold no coordinator reference.  All wiring (button → coordinator, worker
signal → slot) is done by :class:`~src.app.connection_manager.ConnectionManager`.
"""

from __future__ import annotations

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
      Analysis).  Buttons are disabled while an analysis is running and
      re-enabled when a report is delivered.
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
        self._init_ui()

    def _init_ui(self) -> None:
        """Build and wire the widget layout."""
        layout = QVBoxLayout(self)

        # --- Trigger buttons ---
        btn_layout = QHBoxLayout()
        self.validate_btn = QPushButton("Validate World")
        self.temporal_btn = QPushButton("Analyze Timeline")
        self.intelligence_btn = QPushButton("Run AI Analysis")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(StyleHelper.get_preview_label_style())
        for btn in (self.validate_btn, self.temporal_btn, self.intelligence_btn):
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
        self._set_buttons_enabled(False)
        self.status_label.setText(message)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all three trigger buttons atomically.

        Args:
            enabled: ``True`` to enable; ``False`` to disable.
        """
        for btn in (self.validate_btn, self.temporal_btn, self.intelligence_btn):
            btn.setEnabled(enabled)

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
        self.status_label.setText("Validation complete.")
        self._set_buttons_enabled(True)
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
        self.status_label.setText("Timeline analysis complete.")
        self._set_buttons_enabled(True)
        logger.debug("MainAnalysisPanel: temporal report received")

    @Slot(str, object)
    def on_intelligence_partial(self, result_type: str, data: Any) -> None:
        """Forward a completed sub-analysis to the Intelligence panel.

        Called via :attr:`~src.services.worker.DatabaseWorker.\
intelligence_partial_result` (``QueuedConnection``) as each of the three
        concurrent sub-analyses finishes, before the full report is available.

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
        self.status_label.setText("AI analysis complete.")
        self._set_buttons_enabled(True)
        logger.debug("MainAnalysisPanel: intelligence report received")
