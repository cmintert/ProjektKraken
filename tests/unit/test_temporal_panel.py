"""Tests for TemporalPanel widget."""

import pytest

from src.core.analysis import (
    CharacterLifespan,
    SeverityLevel,
    TemporalAnalysisReport,
    TemporalConflict,
    TimelineGap,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_report(
    gaps: list | None = None,
    conflicts: list | None = None,
    lifespans: list | None = None,
    calendar_name: str = "Gregorian",
) -> TemporalAnalysisReport:
    """Build a minimal TemporalAnalysisReport for widget tests."""
    gaps = gaps or []
    conflicts = conflicts or []
    lifespans = lifespans or []
    return TemporalAnalysisReport(
        timestamp=1000.0,
        timeline_gaps=gaps,
        total_gap_duration=sum(g.gap_duration for g in gaps),
        conflicts=conflicts,
        character_lifespans=lifespans,
        earliest_event_date=None if not gaps else gaps[0].start_date,
        latest_event_date=None if not gaps else gaps[-1].end_date,
        calendar_name=calendar_name,
    )


def _make_gap(start: float, end: float) -> TimelineGap:
    """Create a minimal TimelineGap."""
    return TimelineGap(
        start_date=start,
        end_date=end,
        gap_duration=end - start,
        message=f"Gap from {start} to {end}",
    )


def _make_conflict(rel_id: str = "r1") -> TemporalConflict:
    """Create a minimal TemporalConflict."""
    return TemporalConflict(
        conflict_type="invalid_relation_window",
        entity_id=rel_id,
        entity_name=f"Relation {rel_id}",
        problem_date=200.0,
        message="valid_from (200) >= valid_to (100)",
        suggestion="Fix the date range.",
        severity=SeverityLevel.WARNING,
    )


def _make_lifespan(entity_id: str, name: str) -> CharacterLifespan:
    """Create a minimal CharacterLifespan."""
    return CharacterLifespan(
        entity_id=entity_id,
        entity_name=name,
        birth_date=100.0,
        death_date=500.0,
        life_span_years=400.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemporalPanelCreation:
    """Tests for TemporalPanel widget instantiation."""

    def test_panel_creates_without_error(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert panel is not None

    def test_panel_has_gaps_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert hasattr(panel, "gaps_table")

    def test_panel_has_conflicts_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert hasattr(panel, "conflicts_table")

    def test_panel_has_lifespans_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert hasattr(panel, "lifespans_table")

    def test_panel_has_header_label(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert hasattr(panel, "header_label")


@pytest.mark.unit
class TestTemporalPanelColumnCounts:
    """Tests for correct column counts in each table."""

    def test_gaps_table_has_four_columns(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert panel.gaps_table.columnCount() == 4

    def test_conflicts_table_has_five_columns(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert panel.conflicts_table.columnCount() == 5

    def test_lifespans_table_has_five_columns(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        assert panel.lifespans_table.columnCount() == 5


@pytest.mark.unit
class TestTemporalPanelDisplayReport:
    """Tests for TemporalPanel.display_report population."""

    def test_gaps_table_row_count_matches_gaps(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        report = _make_report(gaps=[_make_gap(0, 200), _make_gap(500, 800)])
        panel.display_report(report)
        assert panel.gaps_table.rowCount() == 2

    def test_conflicts_table_row_count_matches_conflicts(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        report = _make_report(conflicts=[_make_conflict("r1")])
        panel.display_report(report)
        assert panel.conflicts_table.rowCount() == 1

    def test_lifespans_table_row_count_matches_entities(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        report = _make_report(
            lifespans=[
                _make_lifespan("e1", "Alice"),
                _make_lifespan("e2", "Bob"),
                _make_lifespan("e3", "Carol"),
            ]
        )
        panel.display_report(report)
        assert panel.lifespans_table.rowCount() == 3

    def test_empty_report_clears_all_tables(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report())
        assert panel.gaps_table.rowCount() == 0
        assert panel.conflicts_table.rowCount() == 0
        assert panel.lifespans_table.rowCount() == 0

    def test_header_label_contains_calendar_name(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(calendar_name="Gregorian"))
        assert "Gregorian" in panel.header_label.text()

    def test_header_label_contains_gap_count(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        report = _make_report(gaps=[_make_gap(0, 200), _make_gap(500, 800)])
        panel.display_report(report)
        assert "2" in panel.header_label.text()

    def test_header_label_contains_conflict_count(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        report = _make_report(conflicts=[_make_conflict()])
        panel.display_report(report)
        assert "1" in panel.header_label.text()

    def test_gap_start_date_in_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(gaps=[_make_gap(100.0, 400.0)]))
        # fmt_lore_date formats day-count floats as "Year N".
        # 100 days ÷ 365 ≈ Year 1.
        assert "Year 1" in panel.gaps_table.item(0, 0).text()

    def test_gap_end_date_in_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(gaps=[_make_gap(100.0, 400.0)]))
        # 400 days ÷ 365 ≈ Year 2.
        assert "Year 2" in panel.gaps_table.item(0, 1).text()

    def test_gap_message_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(gaps=[_make_gap(100.0, 400.0)]))
        widget = panel.gaps_table.cellWidget(0, 3)
        assert isinstance(widget, QTextEdit)
        assert "Gap from" in widget.toPlainText()

    def test_conflict_type_in_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(conflicts=[_make_conflict()]))
        assert "invalid_relation_window" in panel.conflicts_table.item(0, 0).text()

    def test_conflict_message_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(conflicts=[_make_conflict()]))
        widget = panel.conflicts_table.cellWidget(0, 3)
        assert isinstance(widget, QTextEdit)
        assert "valid_from" in widget.toPlainText()

    def test_conflict_suggestion_cell_is_selectable_label(self, qapp):
        from PySide6.QtWidgets import QTextEdit

        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(conflicts=[_make_conflict()]))
        widget = panel.conflicts_table.cellWidget(0, 4)
        assert isinstance(widget, QTextEdit)
        assert "Fix" in widget.toPlainText()

    def test_lifespan_name_in_table(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(
            _make_report(lifespans=[_make_lifespan("e1", "Aragorn")])
        )
        assert "Aragorn" in panel.lifespans_table.item(0, 0).text()

    def test_lifespan_valid_shown_as_yes(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(
            _make_report(lifespans=[_make_lifespan("e1", "Alice")])
        )
        assert "Yes" in panel.lifespans_table.item(0, 4).text()

    def test_lifespan_invalid_shown_as_no(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        bad_lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Ghost",
            birth_date=500.0,
            death_date=100.0,  # death before birth → invalid
            life_span_years=-400.0,
        )
        panel.display_report(_make_report(lifespans=[bad_lifespan]))
        assert "No" in panel.lifespans_table.item(0, 4).text()

    def test_display_report_called_twice_replaces_data(self, qapp):
        from src.gui.widgets.analysis.temporal_panel import TemporalPanel

        panel = TemporalPanel()
        panel.display_report(_make_report(gaps=[_make_gap(0, 200), _make_gap(500, 800)]))
        panel.display_report(_make_report(gaps=[_make_gap(0, 300)]))
        assert panel.gaps_table.rowCount() == 1
