"""Tests for analysis_commands: ValidateWorldCommand, AnalyzeTemporalCommand, and RunIntelligenceAnalysisCommand."""

from unittest.mock import MagicMock, patch

import pytest

from src.commands.base_command import CommandResult
from src.core.analysis import (
    IntelligenceReport,
    TemporalAnalysisReport,
    WorldValidationReport,
)


@pytest.fixture
def mock_db():
    """Minimal mock database service."""
    return MagicMock()


@pytest.fixture
def sample_report():
    """A minimal WorldValidationReport for mock returns."""
    return WorldValidationReport(
        timestamp=1000.0,
        total_entities=2,
        total_events=1,
        total_relations=0,
        total_tags=0,
        issues=[],
        issues_by_severity={},
        issues_by_type={},
        completeness_scores=[],
        average_completeness=0.0,
        orphaned_entities_count=0,
        broken_references_count=0,
        unused_tags_count=0,
    )


@pytest.mark.unit
class TestValidateWorldCommand:
    def test_execute_returns_success_with_report(self, mock_db, sample_report):
        from src.commands.analysis_commands import ValidateWorldCommand

        with patch(
            "src.commands.analysis_commands.WorldValidator"
        ) as MockValidator:
            MockValidator.return_value.validate.return_value = sample_report
            cmd = ValidateWorldCommand()
            result = cmd.execute(mock_db)

        assert result.success is True
        assert "report" in result.data
        assert result.data["report"] is sample_report

    def test_execute_wraps_exception_as_failure(self, mock_db):
        from src.commands.analysis_commands import ValidateWorldCommand

        with patch(
            "src.commands.analysis_commands.WorldValidator"
        ) as MockValidator:
            MockValidator.return_value.validate.side_effect = RuntimeError("DB gone")
            cmd = ValidateWorldCommand()
            result = cmd.execute(mock_db)

        assert result.success is False
        assert "validation" in result.errors
        assert "DB gone" in result.errors["validation"]

    def test_has_history_is_false(self):
        from src.commands.analysis_commands import ValidateWorldCommand

        cmd = ValidateWorldCommand()
        assert cmd.has_history is False

    def test_undo_is_noop(self, mock_db):
        from src.commands.analysis_commands import ValidateWorldCommand

        cmd = ValidateWorldCommand()
        # Should not raise
        cmd.undo(mock_db)

    def test_to_dict_contains_command_type(self):
        from src.commands.analysis_commands import ValidateWorldCommand

        cmd = ValidateWorldCommand()
        d = cmd.to_dict()
        assert d["command_type"] == "ValidateWorldCommand"

    def test_from_dict_roundtrip(self):
        from src.commands.analysis_commands import ValidateWorldCommand

        cmd = ValidateWorldCommand()
        d = cmd.to_dict()
        restored = ValidateWorldCommand.from_dict(d)
        assert isinstance(restored, ValidateWorldCommand)

    def test_command_result_has_correct_command_name(self, mock_db, sample_report):
        from src.commands.analysis_commands import ValidateWorldCommand

        with patch(
            "src.commands.analysis_commands.WorldValidator"
        ) as MockValidator:
            MockValidator.return_value.validate.return_value = sample_report
            cmd = ValidateWorldCommand()
            result = cmd.execute(mock_db)

        assert isinstance(result, CommandResult)


@pytest.mark.unit
class TestValidateWorldCommandRegistry:
    def test_command_registered_in_registry(self):
        """ValidateWorldCommand must be discoverable by name for undo persistence."""
        from src.commands.registry import get_command_types

        types = get_command_types()
        assert "ValidateWorldCommand" in types

    def test_registry_maps_to_correct_class(self):
        from src.commands.analysis_commands import ValidateWorldCommand
        from src.commands.registry import get_command_types

        types = get_command_types()
        assert types["ValidateWorldCommand"] is ValidateWorldCommand


@pytest.fixture
def sample_temporal_report():
    """A minimal TemporalAnalysisReport for mock returns."""
    return TemporalAnalysisReport(
        timestamp=2000.0,
        timeline_gaps=[],
        total_gap_duration=0.0,
        conflicts=[],
        character_lifespans=[],
        earliest_event_date=None,
        latest_event_date=None,
        calendar_name="Test Calendar",
    )


@pytest.mark.unit
class TestAnalyzeTemporalCommand:
    """Tests for AnalyzeTemporalCommand."""

    def test_execute_returns_success_with_report(
        self, mock_db, sample_temporal_report
    ):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        with patch(
            "src.commands.analysis_commands.TemporalAnalyzer"
        ) as MockAnalyzer:
            MockAnalyzer.return_value.analyze.return_value = sample_temporal_report
            cmd = AnalyzeTemporalCommand()
            result = cmd.execute(mock_db)

        assert result.success is True
        assert "report" in result.data
        assert result.data["report"] is sample_temporal_report

    def test_execute_wraps_exception_as_failure(self, mock_db):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        with patch(
            "src.commands.analysis_commands.TemporalAnalyzer"
        ) as MockAnalyzer:
            MockAnalyzer.return_value.analyze.side_effect = RuntimeError("DB gone")
            cmd = AnalyzeTemporalCommand()
            result = cmd.execute(mock_db)

        assert result.success is False
        assert "temporal_analysis" in result.errors

    def test_has_history_is_false(self):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        assert AnalyzeTemporalCommand().has_history is False

    def test_undo_is_noop(self, mock_db):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        cmd = AnalyzeTemporalCommand()
        cmd.undo(mock_db)  # must not raise

    def test_to_dict_contains_command_type(self):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        assert AnalyzeTemporalCommand().to_dict() == {
            "command_type": "AnalyzeTemporalCommand"
        }

    def test_from_dict_roundtrip(self):
        from src.commands.analysis_commands import AnalyzeTemporalCommand

        restored = AnalyzeTemporalCommand.from_dict(
            {"command_type": "AnalyzeTemporalCommand"}
        )
        assert isinstance(restored, AnalyzeTemporalCommand)

    def test_command_registered_in_registry(self):
        from src.commands.registry import get_command_types

        assert "AnalyzeTemporalCommand" in get_command_types()

    def test_registry_maps_to_correct_class(self):
        from src.commands.analysis_commands import AnalyzeTemporalCommand
        from src.commands.registry import get_command_types

        assert get_command_types()["AnalyzeTemporalCommand"] is AnalyzeTemporalCommand


@pytest.fixture
def sample_intelligence_report():
    """A minimal IntelligenceReport for mock returns."""
    return IntelligenceReport(
        timestamp=3000.0,
        plot_holes=[],
        relation_proposals=[],
        lore_suggestions=[],
        analysis_model="test-model",
        audit_log=[],
    )


@pytest.mark.unit
class TestRunIntelligenceAnalysisCommand:
    """Tests for RunIntelligenceAnalysisCommand."""

    def test_execute_returns_success_with_report(
        self, mock_db, sample_intelligence_report
    ):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        with patch(
            "src.commands.analysis_commands.IntelligenceAnalyzer"
        ) as MockAnalyzer:
            MockAnalyzer.return_value.analyze.return_value = sample_intelligence_report
            cmd = RunIntelligenceAnalysisCommand()
            result = cmd.execute(mock_db)

        assert result.success is True
        assert "report" in result.data
        assert result.data["report"] is sample_intelligence_report

    def test_execute_wraps_exception_as_failure(self, mock_db):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        with patch(
            "src.commands.analysis_commands.IntelligenceAnalyzer"
        ) as MockAnalyzer:
            MockAnalyzer.return_value.analyze.side_effect = RuntimeError("LLM down")
            cmd = RunIntelligenceAnalysisCommand()
            result = cmd.execute(mock_db)

        assert result.success is False
        assert "intelligence_analysis" in result.errors
        assert "LLM down" in result.errors["intelligence_analysis"]

    def test_has_history_is_false(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        assert RunIntelligenceAnalysisCommand().has_history is False

    def test_undo_is_noop(self, mock_db):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        cmd = RunIntelligenceAnalysisCommand()
        cmd.undo(mock_db)  # must not raise

    def test_to_dict_contains_command_type_and_analysis_type(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        d = RunIntelligenceAnalysisCommand(analysis_type="plot_holes").to_dict()
        assert d["command_type"] == "RunIntelligenceAnalysisCommand"
        assert d["analysis_type"] == "plot_holes"

    def test_to_dict_default_analysis_type_is_all(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        d = RunIntelligenceAnalysisCommand().to_dict()
        assert d["analysis_type"] == "all"

    def test_from_dict_roundtrip_preserves_analysis_type(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        original = RunIntelligenceAnalysisCommand(analysis_type="lore")
        restored = RunIntelligenceAnalysisCommand.from_dict(original.to_dict())
        assert isinstance(restored, RunIntelligenceAnalysisCommand)
        assert restored.analysis_type == "lore"

    def test_from_dict_defaults_to_all_when_key_missing(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand

        restored = RunIntelligenceAnalysisCommand.from_dict(
            {"command_type": "RunIntelligenceAnalysisCommand"}
        )
        assert restored.analysis_type == "all"

    def test_command_registered_in_registry(self):
        from src.commands.registry import get_command_types

        assert "RunIntelligenceAnalysisCommand" in get_command_types()

    def test_registry_maps_to_correct_class(self):
        from src.commands.analysis_commands import RunIntelligenceAnalysisCommand
        from src.commands.registry import get_command_types

        assert (
            get_command_types()["RunIntelligenceAnalysisCommand"]
            is RunIntelligenceAnalysisCommand
        )
