"""Tests for MainAnalysisPanel widget."""

import pytest

from src.core.analysis import (
    IntelligenceReport,
    TemporalAnalysisReport,
    WorldValidationReport,
)

# ---------------------------------------------------------------------------
# Minimal report factories
# ---------------------------------------------------------------------------


def _make_validation_report() -> WorldValidationReport:
    """Return a minimal WorldValidationReport for widget tests."""
    return WorldValidationReport(
        timestamp=1000.0,
        total_entities=1,
        total_events=1,
        total_relations=0,
        total_tags=0,
        issues=[],
        issues_by_severity={},
        issues_by_type={},
        completeness_scores=[],
        average_completeness=50.0,
        orphaned_entities_count=0,
        broken_references_count=0,
        unused_tags_count=0,
    )


def _make_temporal_report() -> TemporalAnalysisReport:
    """Return a minimal TemporalAnalysisReport for widget tests."""
    return TemporalAnalysisReport(
        timestamp=2000.0,
        timeline_gaps=[],
        total_gap_duration=0.0,
        conflicts=[],
        character_lifespans=[],
        earliest_event_date=None,
        latest_event_date=None,
        calendar_name="Gregorian",
    )


def _make_intelligence_report() -> IntelligenceReport:
    """Return a minimal IntelligenceReport for widget tests."""
    return IntelligenceReport(
        timestamp=3000.0,
        plot_holes=[],
        relation_proposals=[],
        lore_suggestions=[],
        analysis_model="test-model",
        audit_log=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMainAnalysisPanelCreation:
    """Tests for MainAnalysisPanel widget instantiation."""

    def test_panel_creates_without_error(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert panel is not None

    def test_panel_has_tab_widget(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "tab_widget")

    def test_panel_has_three_tabs(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert panel.tab_widget.count() == 3

    def test_tab_labels(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        labels = [panel.tab_widget.tabText(i) for i in range(3)]
        assert "Validation" in labels
        assert "Timeline" in labels
        assert "Intelligence" in labels

    def test_has_validate_button(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "validate_btn")

    def test_has_temporal_button(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "temporal_btn")

    def test_has_intelligence_button(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "intelligence_btn")

    def test_has_status_label(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "status_label")

    def test_has_validation_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "validation_panel")

    def test_has_temporal_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "temporal_panel")

    def test_has_intelligence_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        assert hasattr(panel, "intelligence_panel")


@pytest.mark.unit
class TestMainAnalysisPanelSlots:
    """Tests for MainAnalysisPanel report-delivery slots."""

    def test_on_validation_complete_populates_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        report = _make_validation_report()
        panel.on_validation_complete(report)
        assert "50" in panel.validation_panel.header_label.text()

    def test_on_validation_complete_switches_to_tab_zero(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        # Switch to tab 2 first
        panel.tab_widget.setCurrentIndex(2)
        panel.on_validation_complete(_make_validation_report())
        assert panel.tab_widget.currentIndex() == 0

    def test_on_validation_complete_updates_status(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_validation_complete(_make_validation_report())
        assert panel.status_label.text() != ""

    def test_on_temporal_complete_populates_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        report = _make_temporal_report()
        panel.on_temporal_complete(report)
        assert "Gregorian" in panel.temporal_panel.header_label.text()

    def test_on_temporal_complete_switches_to_tab_one(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_temporal_complete(_make_temporal_report())
        assert panel.tab_widget.currentIndex() == 1

    def test_on_intelligence_complete_populates_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        report = _make_intelligence_report()
        panel.on_intelligence_complete(report)
        assert "test-model" in panel.intelligence_panel.header_label.text()

    def test_on_intelligence_complete_switches_to_tab_two(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_complete(_make_intelligence_report())
        assert panel.tab_widget.currentIndex() == 2

    def test_on_intelligence_complete_updates_status(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_complete(_make_intelligence_report())
        assert panel.status_label.text() != ""


# ---------------------------------------------------------------------------
# TestMainAnalysisPanelStreaming
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMainAnalysisPanelStreaming:
    """Tests for progressive streaming slots on MainAnalysisPanel."""

    def test_on_intelligence_analysis_started_switches_to_intelligence_tab(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_analysis_started()
        assert panel.tab_widget.currentIndex() == 2

    def test_on_intelligence_analysis_started_puts_placeholder_in_panel(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_analysis_started()
        # start_streaming() was called; all three tables have an "Analyzing..." row
        assert "Analyzing" in panel.intelligence_panel.plot_holes_table.item(0, 0).text()

    def test_on_intelligence_partial_holes_updates_table(self, qapp):
        from src.core.analysis import PlotHole, SeverityLevel
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_analysis_started()
        hole = PlotHole(
            issue_id="h1",
            entity_id="e1",
            entity_name="TestChar",
            description="A gap.",
            severity=SeverityLevel.WARNING,
            confidence=0.8,
        )
        panel.on_intelligence_partial("holes", ([hole], []))
        assert panel.intelligence_panel.plot_holes_table.rowCount() == 1
        assert panel.intelligence_panel.plot_holes_table.item(0, 1).text() == "TestChar"

    def test_on_intelligence_partial_unknown_type_is_no_op(self, qapp):
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_analysis_started()
        # Should not raise
        panel.on_intelligence_partial("unknown", ([], []))

    def test_on_intelligence_complete_calls_finalize_not_display_report(self, qapp):
        from src.core.analysis import PlotHole, SeverityLevel
        from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel

        panel = MainAnalysisPanel()
        panel.on_intelligence_analysis_started()
        hole = PlotHole(
            issue_id="h1",
            entity_id="e1",
            entity_name="StreamChar",
            description="A gap.",
            severity=SeverityLevel.INFO,
            confidence=0.7,
        )
        # Simulate a partial arriving first
        panel.on_intelligence_partial("holes", ([hole], []))
        # Then the full report arrives — finalize should update header
        report = _make_intelligence_report()
        panel.on_intelligence_complete(report)
        assert "test-model" in panel.intelligence_panel.header_label.text()
        assert panel.status_label.text() == "AI analysis complete."
