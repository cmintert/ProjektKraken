"""Tests for AnalysisPanel widget."""

import pytest

from src.core.analysis import (
    CompletenessScore,
    IssueType,
    SeverityLevel,
    ValidationIssue,
    WorldValidationReport,
)


def _make_issue(severity: SeverityLevel, issue_type: IssueType, name: str = "X") -> ValidationIssue:
    """Create a minimal ValidationIssue."""
    return ValidationIssue(
        severity=severity,
        issue_type=issue_type,
        object_id="id-1",
        object_type="entity",
        object_name=name,
        message="Test message.",
        suggestion="Test suggestion.",
    )


def _make_score(name: str, score: float = 50.0) -> CompletenessScore:
    """Create a minimal CompletenessScore."""
    return CompletenessScore(
        object_id="id-1",
        object_type="entity",
        name=name,
        has_description=True,
        description_length=60,
        has_image=False,
        has_tags=True,
        tag_count=2,
        relation_count=2,
        completeness_score=score,
    )


def _make_report(
    issues: list | None = None,
    scores: list | None = None,
    total_entities: int = 3,
    total_events: int = 2,
    avg_completeness: float = 55.0,
) -> WorldValidationReport:
    """Build a minimal WorldValidationReport for widget tests."""
    return WorldValidationReport(
        timestamp=1000.0,
        total_entities=total_entities,
        total_events=total_events,
        total_relations=1,
        total_tags=2,
        issues=issues or [],
        issues_by_severity={},
        issues_by_type={},
        completeness_scores=scores or [],
        average_completeness=avg_completeness,
        orphaned_entities_count=0,
        broken_references_count=0,
        unused_tags_count=0,
    )


@pytest.mark.unit
class TestAnalysisPanelCreation:
    """Tests for AnalysisPanel widget instantiation."""

    def test_panel_creates_without_error(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel is not None
        panel.close()

    def test_panel_has_issues_table(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel.issues_table is not None
        panel.close()

    def test_panel_has_completeness_table(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel.completeness_table is not None
        panel.close()

    def test_panel_has_header_label(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel.header_label is not None
        panel.close()


@pytest.mark.unit
class TestDisplayReport:
    """Tests for AnalysisPanel.display_report population."""

    def test_issues_table_row_count_matches_issues(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        issues = [
            _make_issue(SeverityLevel.CRITICAL, IssueType.BROKEN_REFERENCE, "A"),
            _make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY, "B"),
            _make_issue(SeverityLevel.INFO, IssueType.TAG_UNUSED, "C"),
        ]
        panel = AnalysisPanel()
        panel.display_report(_make_report(issues=issues))

        assert panel.issues_table.rowCount() == 3
        panel.close()

    def test_completeness_table_row_count_matches_scores(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        scores = [_make_score("Entity A"), _make_score("Entity B")]
        panel = AnalysisPanel()
        panel.display_report(_make_report(scores=scores))

        assert panel.completeness_table.rowCount() == 2
        panel.close()

    def test_header_label_contains_entity_count(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        panel.display_report(_make_report(total_entities=7))

        assert "7" in panel.header_label.text()
        panel.close()

    def test_header_label_contains_event_count(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        panel.display_report(_make_report(total_events=5))

        assert "5" in panel.header_label.text()
        panel.close()

    def test_header_label_contains_completeness_score(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        panel.display_report(_make_report(avg_completeness=73.0))

        assert "73" in panel.header_label.text()
        panel.close()

    def test_issues_table_has_five_columns(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel.issues_table.columnCount() == 5
        panel.close()

    def test_completeness_table_has_four_columns(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        assert panel.completeness_table.columnCount() == 4
        panel.close()

    def test_empty_report_clears_tables(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        panel = AnalysisPanel()
        panel.display_report(_make_report(issues=[_make_issue(SeverityLevel.INFO, IssueType.TAG_UNUSED)]))
        panel.display_report(_make_report(issues=[]))

        assert panel.issues_table.rowCount() == 0
        panel.close()

    def test_completeness_table_sorted_ascending_by_score(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        scores = [_make_score("High", score=90.0), _make_score("Low", score=10.0)]
        panel = AnalysisPanel()
        panel.display_report(_make_report(scores=scores))

        first_name = panel.completeness_table.item(0, 0).text()
        assert first_name == "Low"
        panel.close()

    def test_issue_severity_shown_in_first_column(self, qapp):
        from src.gui.widgets.analysis_panel import AnalysisPanel

        issues = [_make_issue(SeverityLevel.CRITICAL, IssueType.BROKEN_REFERENCE)]
        panel = AnalysisPanel()
        panel.display_report(_make_report(issues=issues))

        cell_text = panel.issues_table.item(0, 0).text()
        assert "critical" in cell_text.lower()
        panel.close()

    def test_issue_message_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis_panel import AnalysisPanel

        issues = [_make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY)]
        panel = AnalysisPanel()
        panel.display_report(_make_report(issues=issues))

        widget = panel.issues_table.cellWidget(0, 3)
        assert isinstance(widget, QTextEdit)
        assert "Test message" in widget.toPlainText()
        panel.close()

    def test_issue_suggestion_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis_panel import AnalysisPanel

        issues = [_make_issue(SeverityLevel.INFO, IssueType.TAG_UNUSED)]
        panel = AnalysisPanel()
        panel.display_report(_make_report(issues=issues))

        widget = panel.issues_table.cellWidget(0, 4)
        assert isinstance(widget, QTextEdit)
        assert "Test suggestion" in widget.toPlainText()
        panel.close()
