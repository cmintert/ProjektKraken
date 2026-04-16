"""Tests for IntelligencePanel widget."""

import pytest

from src.core.analysis import (
    IntelligenceReport,
    LoreGapFiller,
    ParsedLoreSuggestion,
    PlotHole,
    RelationProposal,
    SeverityLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(
    holes: list | None = None,
    proposals: list | None = None,
    lore: list | None = None,
    model: str = "test-model",
) -> IntelligenceReport:
    """Build a minimal IntelligenceReport for widget tests."""
    return IntelligenceReport(
        timestamp=1000.0,
        plot_holes=holes or [],
        relation_proposals=proposals or [],
        lore_suggestions=lore or [],
        analysis_model=model,
        audit_log=[],
    )


def _make_hole(entity_id: str = "e1", entity_name: str = "Alice") -> PlotHole:
    """Create a minimal PlotHole."""
    return PlotHole(
        issue_id=f"hole_{entity_id}_0",
        entity_id=entity_id,
        entity_name=entity_name,
        description="Disappears for 200 years with no explanation.",
        severity=SeverityLevel.WARNING,
        suggested_resolution="Add a bridging event.",
        confidence=0.75,
    )


def _make_proposal(source: str = "e1", target: str = "e2") -> RelationProposal:
    """Create a minimal RelationProposal."""
    return RelationProposal(
        source_id=source,
        source_name="Alice",
        target_id=target,
        target_name="Bob",
        suggested_relation_type="ally",
        reasoning="Both share warrior tag.",
        confidence=0.85,
    )


def _make_lore(start: float = 0.0, end: float = 500.0) -> LoreGapFiller:
    """Create a minimal LoreGapFiller."""
    return LoreGapFiller(
        gap_id=f"gap_{start:.0f}_{end:.0f}",
        start_date=start,
        end_date=end,
        suggestions=[
            ParsedLoreSuggestion(
                name="The Long Silence",
                date_str="Approximately Year 1200",
                description="A period of isolation and mystery.",
            ),
            ParsedLoreSuggestion(
                name="Rise of the Eastern Clans",
                date_str="Approximately Year 1350",
                description="Powerful clans emerge in the east.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntelligencePanelCreation:
    """Tests for IntelligencePanel widget instantiation."""

    def test_panel_creates_without_error(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert panel is not None

    def test_panel_has_plot_holes_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert hasattr(panel, "plot_holes_table")

    def test_panel_has_proposals_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert hasattr(panel, "proposals_table")

    def test_panel_has_lore_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert hasattr(panel, "lore_table")

    def test_panel_has_header_label(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert hasattr(panel, "header_label")


@pytest.mark.unit
class TestIntelligencePanelColumnCounts:
    """Tests for correct column counts in each table."""

    def test_plot_holes_table_has_five_columns(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert panel.plot_holes_table.columnCount() == 5

    def test_proposals_table_has_five_columns(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert panel.proposals_table.columnCount() == 5

    def test_lore_table_has_three_columns(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert panel.lore_table.columnCount() == 3


@pytest.mark.unit
class TestIntelligencePanelDisplayReport:
    """Tests for IntelligencePanel.display_report population."""

    def test_plot_holes_row_count_matches_holes(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        report = _make_report(holes=[_make_hole("e1"), _make_hole("e2")])
        panel.display_report(report)
        assert panel.plot_holes_table.rowCount() == 2

    def test_proposals_row_count_matches_proposals(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        report = _make_report(proposals=[_make_proposal()])
        panel.display_report(report)
        assert panel.proposals_table.rowCount() == 1

    def test_lore_row_count_matches_fillers(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        report = _make_report(
            lore=[_make_lore(0, 500), _make_lore(600, 1200), _make_lore(1300, 2000)]
        )
        panel.display_report(report)
        assert panel.lore_table.rowCount() == 3

    def test_empty_report_clears_all_tables(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report())
        assert panel.plot_holes_table.rowCount() == 0
        assert panel.proposals_table.rowCount() == 0
        assert panel.lore_table.rowCount() == 0

    def test_header_label_contains_model_name(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(model="gpt-turbo-42"))
        assert "gpt-turbo-42" in panel.header_label.text()

    def test_header_label_contains_hole_count(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole(), _make_hole("e2")]))
        assert "2" in panel.header_label.text()

    def test_plot_hole_severity_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole()]))
        assert SeverityLevel.WARNING.value in panel.plot_holes_table.item(0, 0).text()

    def test_plot_hole_entity_name_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole(entity_name="Gandalf")]))
        assert "Gandalf" in panel.plot_holes_table.item(0, 1).text()

    def test_plot_hole_description_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole()]))
        widget = panel.plot_holes_table.cellWidget(0, 2)
        assert isinstance(widget, QTextEdit)
        assert "Disappears" in widget.toPlainText()

    def test_plot_hole_resolution_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole()]))
        widget = panel.plot_holes_table.cellWidget(0, 3)
        assert isinstance(widget, QTextEdit)
        assert "bridging" in widget.toPlainText()

    def test_plot_hole_no_resolution_shows_empty(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        hole = PlotHole(
            issue_id="h1",
            entity_id="e1",
            entity_name="Bob",
            description="Unexplained.",
            severity=SeverityLevel.INFO,
            suggested_resolution=None,
        )
        panel.display_report(_make_report(holes=[hole]))
        widget = panel.plot_holes_table.cellWidget(0, 3)
        assert isinstance(widget, QTextEdit)
        assert widget.toPlainText() == ""

    def test_proposal_source_name_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(proposals=[_make_proposal()]))
        assert "Alice" in panel.proposals_table.item(0, 0).text()

    def test_proposal_target_name_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(proposals=[_make_proposal()]))
        assert "Bob" in panel.proposals_table.item(0, 1).text()

    def test_proposal_relation_type_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(proposals=[_make_proposal()]))
        assert "ally" in panel.proposals_table.item(0, 2).text()

    def test_proposal_reasoning_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(proposals=[_make_proposal()]))
        widget = panel.proposals_table.cellWidget(0, 4)
        assert isinstance(widget, QTextEdit)
        assert "warrior" in widget.toPlainText()

    def test_proposal_reasoning_wraps_long_text(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        long_reasoning = " ".join(["reason"] * 30)
        proposal = RelationProposal(
            source_id="e1",
            source_name="Alice",
            target_id="e2",
            target_name="Bob",
            suggested_relation_type="ally",
            reasoning=long_reasoning,
            confidence=0.85,
        )
        panel.display_report(_make_report(proposals=[proposal]))
        widget = panel.proposals_table.cellWidget(0, 4)
        assert isinstance(widget, QTextEdit)
        # Text is whitespace-normalised but not hard-wrapped; Qt reflows it.
        assert "reason" in widget.toPlainText()
        assert "\n" not in widget.toPlainText()

    def test_analysis_tables_hide_vertical_headers(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        assert panel.plot_holes_table.verticalHeader().isVisible() is False
        assert panel.proposals_table.verticalHeader().isVisible() is False
        assert panel.lore_table.verticalHeader().isVisible() is False

    def test_lore_gap_start_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(lore=[_make_lore(100.0, 800.0)]))
        # fmt_lore_date converts day-count floats to "Year N" format.
        # 100 days ÷ 365 ≈ Year 1.
        assert "Year 1" in panel.lore_table.item(0, 0).text()

    def test_lore_gap_end_in_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(lore=[_make_lore(100.0, 800.0)]))
        # 800 days ÷ 365 ≈ Year 3.
        assert "Year 3" in panel.lore_table.item(0, 1).text()

    def test_lore_suggestions_cell_is_text_browser(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(lore=[_make_lore()]))
        browser = panel.lore_table.cellWidget(0, 2)
        assert isinstance(browser, QTextEdit)
        content = browser.toHtml()
        assert "Long Silence" in content
        assert "Eastern Clans" in content

    def test_display_report_called_twice_replaces_data(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.display_report(_make_report(holes=[_make_hole(), _make_hole("e2")]))
        panel.display_report(_make_report(holes=[_make_hole()]))
        assert panel.plot_holes_table.rowCount() == 1


# ---------------------------------------------------------------------------
# TestIntelligencePanelStreaming
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntelligencePanelStreaming:
    """Tests for start_streaming, display_partial_result, and finalize_report."""

    def test_start_streaming_sets_running_header(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        assert "Running" in panel.header_label.text()

    def test_start_streaming_puts_placeholder_in_holes_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        assert panel.plot_holes_table.rowCount() == 1
        assert "Analyzing" in panel.plot_holes_table.item(0, 0).text()

    def test_start_streaming_puts_placeholder_in_proposals_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        assert panel.proposals_table.rowCount() == 1
        assert "Analyzing" in panel.proposals_table.item(0, 0).text()

    def test_start_streaming_puts_placeholder_in_lore_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        assert panel.lore_table.rowCount() == 1
        assert "Analyzing" in panel.lore_table.item(0, 0).text()

    def test_display_partial_result_holes_populates_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        hole = _make_hole()
        panel.display_partial_result("holes", ([hole], []))
        assert panel.plot_holes_table.rowCount() == 1
        assert panel.plot_holes_table.item(0, 1).text() == "Alice"

    def test_display_partial_result_holes_clears_placeholder(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        panel.display_partial_result("holes", ([], []))
        assert panel.plot_holes_table.rowCount() == 0

    def test_display_partial_result_relations_populates_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        proposal = _make_proposal()
        panel.display_partial_result("relations", ([proposal], []))
        assert panel.proposals_table.rowCount() == 1
        assert panel.proposals_table.item(0, 0).text() == "Alice"

    def test_display_partial_result_lore_populates_table(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        filler = _make_lore()
        panel.display_partial_result("lore", ([filler], [], None))
        assert panel.lore_table.rowCount() == 1

    def test_display_partial_result_unknown_type_is_no_op(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        # Should not raise
        panel.display_partial_result("unknown_type", ([], []))
        # Placeholders untouched
        assert "Analyzing" in panel.proposals_table.item(0, 0).text()

    def test_finalize_report_updates_header(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        report = _make_report(holes=[_make_hole()], model="final-model")
        panel.finalize_report(report)
        assert "final-model" in panel.header_label.text()

    def test_finalize_report_clears_placeholder_for_empty_section(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        # Only holes partial arrived; relations and lore still show placeholder
        panel.display_partial_result("holes", ([_make_hole()], []))
        # Finalize with empty relations — placeholder should be gone
        report = _make_report(holes=[_make_hole()])
        panel.finalize_report(report)
        assert panel.proposals_table.rowCount() == 0

    def test_finalize_report_preserves_partial_data(self, qapp):
        from src.gui.widgets.analysis.intelligence_panel import IntelligencePanel

        panel = IntelligencePanel()
        panel.start_streaming()
        hole = _make_hole()
        panel.display_partial_result("holes", ([hole], []))
        report = _make_report(holes=[hole])
        panel.finalize_report(report)
        assert panel.plot_holes_table.rowCount() == 1
        assert panel.plot_holes_table.item(0, 1).text() == "Alice"
