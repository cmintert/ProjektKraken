"""Tests for src/core/analysis.py data model dataclasses."""

import time

import pytest

from src.core.analysis import (
    CharacterLifespan,
    CompletenessScore,
    IntelligenceReport,
    IssueType,
    LoreGapFiller,
    PlotHole,
    RelationProposal,
    SeverityLevel,
    TemporalAnalysisReport,
    TemporalConflict,
    TimelineGap,
    ValidationIssue,
    WorldValidationReport,
)


@pytest.mark.unit
class TestValidationIssue:
    def test_instantiates_with_required_fields(self):
        issue = ValidationIssue(
            severity=SeverityLevel.WARNING,
            issue_type=IssueType.ORPHANED_ENTITY,
            object_id="abc",
            object_type="entity",
            object_name="Gandalf",
            message="No relations found.",
        )
        assert issue.severity == SeverityLevel.WARNING
        assert issue.object_id == "abc"
        assert issue.message == "No relations found."

    def test_related_ids_defaults_to_empty_list(self):
        issue = ValidationIssue(
            severity=SeverityLevel.INFO,
            issue_type=IssueType.INCOMPLETE_ENTITY,
            object_id="x",
            object_type="entity",
            object_name="Frodo",
            message="Short description.",
        )
        assert issue.related_ids == []

    def test_related_ids_not_shared_between_instances(self):
        a = ValidationIssue(
            severity=SeverityLevel.INFO,
            issue_type=IssueType.INCOMPLETE_ENTITY,
            object_id="a",
            object_type="entity",
            object_name="A",
            message="m",
        )
        b = ValidationIssue(
            severity=SeverityLevel.INFO,
            issue_type=IssueType.INCOMPLETE_ENTITY,
            object_id="b",
            object_type="entity",
            object_name="B",
            message="m",
        )
        a.related_ids.append("x")
        assert b.related_ids == []


@pytest.mark.unit
class TestCompletenessScore:
    def _make_score(self, **kwargs) -> CompletenessScore:
        defaults = dict(
            object_id="obj1",
            object_type="entity",
            name="Test",
            has_description=False,
            description_length=0,
            has_image=False,
            has_tags=False,
            tag_count=0,
            relation_count=0,
            completeness_score=0.0,
        )
        defaults.update(kwargs)
        return CompletenessScore(**defaults)

    def test_empty_entity_scores_zero(self):
        score = self._make_score()
        assert score.calculate_score() == 0.0

    def test_short_description_gives_partial_description_points(self):
        score = self._make_score(has_description=True, description_length=10)
        assert score.calculate_score() == 20.0

    def test_long_description_gives_full_description_points(self):
        score = self._make_score(has_description=True, description_length=51)
        assert score.calculate_score() == 40.0

    def test_tags_add_points(self):
        score = self._make_score(has_tags=True, tag_count=2)
        assert score.calculate_score() == 10.0

    def test_tags_capped_at_20(self):
        score = self._make_score(has_tags=True, tag_count=100)
        assert score.calculate_score() == 20.0

    def test_relations_add_points(self):
        score = self._make_score(relation_count=1)
        assert score.calculate_score() == 5.0

    def test_relations_capped_at_20(self):
        score = self._make_score(relation_count=100)
        assert score.calculate_score() == 20.0

    def test_image_adds_10_points(self):
        score = self._make_score(has_image=True)
        assert score.calculate_score() == 10.0

    def test_fully_saturated_entity_scores_90(self):
        # Design doc formula: desc(40) + tags(20) + relations(20) + image(10) = 90 max
        score = self._make_score(
            has_description=True,
            description_length=100,
            has_image=True,
            has_tags=True,
            tag_count=4,
            relation_count=4,
        )
        assert score.calculate_score() == 90.0

    def test_score_capped_at_100_when_overflow(self):
        # Even with enormous values, score never exceeds 100
        score = self._make_score(
            has_description=True,
            description_length=999,
            has_image=True,
            has_tags=True,
            tag_count=999,
            relation_count=999,
        )
        assert score.calculate_score() <= 100.0


@pytest.mark.unit
class TestWorldValidationReport:
    def _make_report(self, issues=None) -> WorldValidationReport:
        issues = issues or []
        return WorldValidationReport(
            timestamp=time.time(),
            total_entities=5,
            total_events=3,
            total_relations=2,
            total_tags=4,
            issues=issues,
            issues_by_severity={},
            issues_by_type={},
            completeness_scores=[],
            average_completeness=0.0,
            orphaned_entities_count=0,
            broken_references_count=0,
            unused_tags_count=0,
        )

    def _make_issue(self, severity, issue_type) -> ValidationIssue:
        return ValidationIssue(
            severity=severity,
            issue_type=issue_type,
            object_id="x",
            object_type="entity",
            object_name="X",
            message="msg",
        )

    def test_get_issues_by_severity_returns_matching(self):
        issues = [
            self._make_issue(SeverityLevel.CRITICAL, IssueType.BROKEN_REFERENCE),
            self._make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY),
            self._make_issue(SeverityLevel.CRITICAL, IssueType.BROKEN_REFERENCE),
        ]
        report = self._make_report(issues=issues)
        critical = report.get_issues_by_severity(SeverityLevel.CRITICAL)
        assert len(critical) == 2

    def test_get_issues_by_severity_empty_when_none_match(self):
        issues = [self._make_issue(SeverityLevel.INFO, IssueType.INCOMPLETE_ENTITY)]
        report = self._make_report(issues=issues)
        assert report.get_issues_by_severity(SeverityLevel.CRITICAL) == []

    def test_get_issues_by_type_returns_matching(self):
        issues = [
            self._make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY),
            self._make_issue(SeverityLevel.INFO, IssueType.TAG_UNUSED),
            self._make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY),
        ]
        report = self._make_report(issues=issues)
        orphaned = report.get_issues_by_type(IssueType.ORPHANED_ENTITY)
        assert len(orphaned) == 2

    def test_get_issues_by_type_empty_when_none_match(self):
        issues = [self._make_issue(SeverityLevel.WARNING, IssueType.ORPHANED_ENTITY)]
        report = self._make_report(issues=issues)
        assert report.get_issues_by_type(IssueType.BROKEN_REFERENCE) == []


@pytest.mark.unit
class TestCharacterLifespan:
    def test_valid_when_birth_before_death(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Frodo",
            birth_date=100.0,
            death_date=500.0,
            life_span_years=400.0,
        )
        assert lifespan.is_valid() is True

    def test_invalid_when_birth_after_death(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Ghost",
            birth_date=500.0,
            death_date=100.0,
            life_span_years=None,
        )
        assert lifespan.is_valid() is False

    def test_invalid_when_birth_equals_death(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Instant",
            birth_date=100.0,
            death_date=100.0,
            life_span_years=0.0,
        )
        assert lifespan.is_valid() is False

    def test_valid_when_no_birth_date(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Unknown",
            birth_date=None,
            death_date=500.0,
            life_span_years=None,
        )
        assert lifespan.is_valid() is True

    def test_valid_when_no_death_date(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Immortal",
            birth_date=100.0,
            death_date=None,
            life_span_years=None,
        )
        assert lifespan.is_valid() is True

    def test_valid_when_neither_date_set(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="Mystery",
            birth_date=None,
            death_date=None,
            life_span_years=None,
        )
        assert lifespan.is_valid() is True

    def test_violating_events_defaults_to_empty_list(self):
        lifespan = CharacterLifespan(
            entity_id="e1",
            entity_name="X",
            birth_date=None,
            death_date=None,
            life_span_years=None,
        )
        assert lifespan.violating_events == []


@pytest.mark.unit
class TestTemporalDataclasses:
    def test_timeline_gap_instantiates(self):
        gap = TimelineGap(
            start_date=100.0,
            end_date=500.0,
            gap_duration=400.0,
            message="Big gap",
        )
        assert gap.gap_duration == 400.0
        assert gap.affected_entity_ids == []

    def test_temporal_conflict_instantiates(self):
        conflict = TemporalConflict(
            conflict_type="invalid_relation_window",
            entity_id="r1",
            entity_name="Relation r1",
            problem_date=100.0,
            message="valid_from >= valid_to",
        )
        assert conflict.severity == SeverityLevel.WARNING

    def test_temporal_analysis_report_instantiates(self):
        report = TemporalAnalysisReport(
            timestamp=time.time(),
            timeline_gaps=[],
            total_gap_duration=0.0,
            conflicts=[],
            character_lifespans=[],
            earliest_event_date=None,
            latest_event_date=None,
            calendar_name="Gregorian",
        )
        assert report.calendar_name == "Gregorian"


@pytest.mark.unit
class TestIntelligenceDataclasses:
    def test_plot_hole_instantiates(self):
        hole = PlotHole(
            issue_id="ph1",
            entity_id="e1",
            entity_name="Gandalf",
            description="Timeline inconsistency",
            severity=SeverityLevel.WARNING,
        )
        assert hole.confidence == 0.8

    def test_relation_proposal_instantiates(self):
        proposal = RelationProposal(
            source_id="e1",
            source_name="Frodo",
            target_id="e2",
            target_name="Mordor",
            suggested_relation_type="traveled_to",
            reasoning="Story implies connection",
        )
        assert proposal.confidence == 0.7

    def test_lore_gap_filler_instantiates(self):
        filler = LoreGapFiller(
            gap_id="g1",
            start_date=100.0,
            end_date=500.0,
            suggestions=["Option A", "Option B"],
        )
        assert filler.selected_suggestion is None

    def test_intelligence_report_instantiates(self):
        report = IntelligenceReport(
            timestamp=time.time(),
            plot_holes=[],
            relation_proposals=[],
            lore_suggestions=[],
            analysis_model="claude-sonnet-4-6",
            audit_log=[],
        )
        assert report.analysis_model == "claude-sonnet-4-6"
