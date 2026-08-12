"""Tests for TemporalAnalyzer service."""

import time
import uuid

import pytest

from src.core.analysis import (
    SeverityLevel,
    TemporalAnalysisReport,
)
from src.core.entities import Entity
from src.core.events import Event
from src.services.temporal_analyzer import TemporalAnalyzer


@pytest.fixture
def analyzer(db_service):
    """TemporalAnalyzer wired to a fresh in-memory database."""
    return TemporalAnalyzer(db_service)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def test_id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"projektkraken-test:{label}"))


test_id.__test__ = False


def make_event(eid: str, name: str, lore_date: float) -> Event:
    """Create a minimal Event for use in tests."""
    return Event(id=test_id(eid), name=name, lore_date=lore_date)


def make_entity(eid: str, name: str, etype: str = "character") -> Entity:
    """Create a minimal Entity for use in tests."""
    return Entity(id=test_id(eid), name=name, type=etype)


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectTimelineGaps:
    def test_no_events_returns_empty_gaps(self, db_service, analyzer):
        report = analyzer.analyze()
        assert report.timeline_gaps == []

    def test_single_event_returns_no_gaps(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "Only Event", 100.0))
        report = analyzer.analyze()
        assert report.timeline_gaps == []

    def test_gap_below_threshold_not_flagged(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "Alpha", 0.0))
        db_service.insert_event(make_event("e2", "Beta", 50.0))
        report = analyzer.analyze()
        assert report.timeline_gaps == []

    def test_gap_exactly_at_threshold_not_flagged(self, db_service, analyzer):
        """A gap equal to the threshold is NOT flagged (strictly greater-than).

        The default Gregorian calendar has year_length=365; threshold = 365×100
        = 36500 days.  A gap of exactly 36500 days must not be flagged.
        """
        db_service.insert_event(make_event("e1", "Alpha", 0.0))
        db_service.insert_event(make_event("e2", "Beta", 36500.0))
        report = analyzer.analyze()
        assert report.timeline_gaps == []

    def test_gap_above_threshold_flagged(self, db_service, analyzer):
        """A gap strictly greater than threshold (36500 days) is flagged."""
        db_service.insert_event(make_event("e1", "Alpha", 0.0))
        db_service.insert_event(make_event("e2", "Beta", 40000.0))
        report = analyzer.analyze()
        assert len(report.timeline_gaps) == 1

    def test_gap_duration_correct(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "Alpha", 0.0))
        db_service.insert_event(make_event("e2", "Beta", 40000.0))
        report = analyzer.analyze()
        assert len(report.timeline_gaps) == 1
        assert report.timeline_gaps[0].gap_duration == pytest.approx(40000.0)

    def test_gap_start_and_end_dates(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "Alpha", 0.0))
        db_service.insert_event(make_event("e2", "Beta", 40000.0))
        report = analyzer.analyze()
        gap = report.timeline_gaps[0]
        assert gap.start_date == pytest.approx(0.0)
        assert gap.end_date == pytest.approx(40000.0)

    def test_multiple_gaps(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "A", 0.0))
        db_service.insert_event(make_event("e2", "B", 40000.0))
        db_service.insert_event(make_event("e3", "C", 80000.0))
        report = analyzer.analyze()
        assert len(report.timeline_gaps) == 2

    def test_gap_message_contains_event_names(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "FirstEvent", 0.0))
        db_service.insert_event(make_event("e2", "SecondEvent", 40000.0))
        report = analyzer.analyze()
        assert "FirstEvent" in report.timeline_gaps[0].message
        assert "SecondEvent" in report.timeline_gaps[0].message

    def test_events_sorted_by_lore_date(self, db_service, analyzer):
        """Gap detection sorts by lore_date, not insertion order."""
        db_service.insert_event(make_event("e2", "Later", 40000.0))
        db_service.insert_event(make_event("e1", "Earlier", 0.0))
        report = analyzer.analyze()
        assert len(report.timeline_gaps) == 1
        assert report.timeline_gaps[0].start_date == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectTemporalConflicts:
    """Tests for relation-window conflict detection."""

    @pytest.fixture(autouse=True)
    def two_entities(self, db_service):
        """Insert two entities present in every conflict test."""
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Bob"))

    def test_relation_with_no_window_no_conflict(self, db_service, analyzer):
        db_service.insert_relation(test_id("e1"), test_id("e2"), "knows", {})
        report = analyzer.analyze()
        assert report.conflicts == []

    def test_valid_relation_window_no_conflict(self, db_service, analyzer):
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 100.0, "valid_to": 200.0}
        )
        report = analyzer.analyze()
        assert report.conflicts == []

    def test_invalid_relation_window_flagged(self, db_service, analyzer):
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 200.0, "valid_to": 100.0}
        )
        report = analyzer.analyze()
        assert len(report.conflicts) == 1
        assert report.conflicts[0].conflict_type == "invalid_relation_window"

    def test_equal_window_dates_flagged(self, db_service, analyzer):
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 100.0, "valid_to": 100.0}
        )
        report = analyzer.analyze()
        assert len(report.conflicts) == 1

    def test_conflict_severity_is_warning(self, db_service, analyzer):
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 200.0, "valid_to": 100.0}
        )
        report = analyzer.analyze()
        assert report.conflicts[0].severity == SeverityLevel.WARNING

    def test_conflict_references_relation_id(self, db_service, analyzer):
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 200.0, "valid_to": 100.0}
        )
        relations = db_service.get_all_relations()
        rel_id = relations[0]["id"]
        report = analyzer.analyze()
        assert report.conflicts[0].entity_id == rel_id

    def test_multiple_invalid_windows_all_flagged(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e3", "Carol"))
        db_service.insert_relation(
            test_id("e1"), test_id("e2"), "allies",
            {"valid_from": 200.0, "valid_to": 100.0}
        )
        db_service.insert_relation(
            test_id("e2"), test_id("e3"), "rivals",
            {"valid_from": 500.0, "valid_to": 300.0}
        )
        report = analyzer.analyze()
        assert len(report.conflicts) == 2


# ---------------------------------------------------------------------------
# Character lifespan analysis
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnalyzeCharacterLifespans:
    def test_entity_with_no_relations_not_in_lifespans(self, db_service, analyzer):
        """Entities without birth/death relations are not included in lifespans."""
        db_service.insert_entity(make_entity("e1", "Alice"))
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is None

    def test_birth_date_from_relation_date_attribute(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Midwife"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 100.0}
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert lifespan.birth_date == pytest.approx(100.0)

    def test_death_date_from_relation_date_attribute(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Grave"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "death", {"date": 500.0}
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert lifespan.death_date == pytest.approx(500.0)

    def test_lifespan_years_computed_from_birth_and_death(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 100.0}
        )
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "death", {"date": 500.0}
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        # life_span_years is in years; with no active calendar the fallback
        # year_length is 365 days, so 400 days / 365 ≈ 1.0959 years.
        assert lifespan.life_span_years == pytest.approx(400.0 / 365.0)

    def test_lifespan_none_when_missing_birth_or_death(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 100.0}
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert lifespan.life_span_years is None

    def test_event_after_death_is_violating(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 100.0}
        )
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "death", {"date": 200.0}
        )
        ev = make_event("ev1", "Ghost Sighting", 300.0)
        db_service.insert_event(ev)
        db_service.insert_relation(
            test_id("ev1"), test_id("e1"), "features", {}
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert test_id("ev1") in lifespan.violating_events

    def test_unrelated_event_before_birth_is_not_violating(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 200.0}
        )
        ev = make_event("ev1", "Pre-birth Mention", 100.0)
        db_service.insert_event(ev)
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert test_id("ev1") not in lifespan.violating_events

    def test_event_within_lifespan_not_violating(self, db_service, analyzer):
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "birth", {"date": 100.0}
        )
        db_service.insert_relation(
            test_id("e2"), test_id("e1"), "death", {"date": 500.0}
        )
        ev = make_event("ev1", "Mid-life Event", 300.0)
        db_service.insert_event(ev)
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert lifespan.violating_events == []

    def test_entities_without_lifespan_relations_excluded(self, db_service, analyzer):
        """Only entities with birth or death relations appear in character_lifespans."""
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Bob"))
        db_service.insert_entity(make_entity("e3", "Carol"))
        report = analyzer.analyze()
        assert report.character_lifespans == []

    def test_birth_date_from_event_id_in_relation_attributes(
        self, db_service, analyzer
    ):
        """Birth date resolved via attributes['event_id'] → event.lore_date."""
        db_service.insert_entity(make_entity("e1", "Alice"))
        db_service.insert_entity(make_entity("e2", "Source"))
        birth_event = make_event("ev_birth", "Birth of Alice", 150.0)
        db_service.insert_event(birth_event)
        db_service.insert_relation(
            test_id("e2"),
            test_id("e1"),
            "birth",
            {"event_id": test_id("ev_birth")},
        )
        report = analyzer.analyze()
        lifespan = next(
            (
                ls
                for ls in report.character_lifespans
                if ls.entity_id == test_id("e1")
            ),
            None,
        )
        assert lifespan is not None
        assert lifespan.birth_date == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Full report structure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAnalyzeReport:
    def test_returns_temporal_analysis_report(self, db_service, analyzer):
        report = analyzer.analyze()
        assert isinstance(report, TemporalAnalysisReport)

    def test_timestamp_is_recent(self, db_service, analyzer):
        before = time.time()
        report = analyzer.analyze()
        after = time.time()
        assert before <= report.timestamp <= after

    def test_calendar_name_includes_default_when_no_calendar(self, db_service, analyzer):
        """When no active calendar exists the name notes the fallback."""
        report = analyzer.analyze()
        assert "default" in report.calendar_name.lower()

    def test_total_gap_duration_is_sum_of_gaps(self, db_service, analyzer):
        # Events must be > 36500 days apart to exceed the 100-lore-year threshold.
        db_service.insert_event(make_event("e1", "A", 0.0))
        db_service.insert_event(make_event("e2", "B", 40000.0))
        db_service.insert_event(make_event("e3", "C", 80000.0))
        report = analyzer.analyze()
        # Two gaps of 40000 days each.
        assert report.total_gap_duration == pytest.approx(80000.0)

    def test_earliest_and_latest_event_dates(self, db_service, analyzer):
        db_service.insert_event(make_event("e1", "A", 10.0))
        db_service.insert_event(make_event("e2", "B", 500.0))
        db_service.insert_event(make_event("e3", "C", 250.0))
        report = analyzer.analyze()
        assert report.earliest_event_date == pytest.approx(10.0)
        assert report.latest_event_date == pytest.approx(500.0)

    def test_earliest_latest_none_with_no_events(self, db_service, analyzer):
        report = analyzer.analyze()
        assert report.earliest_event_date is None
        assert report.latest_event_date is None

    def test_empty_db_returns_valid_empty_report(self, db_service, analyzer):
        report = analyzer.analyze()
        assert report.timeline_gaps == []
        assert report.conflicts == []
        assert report.character_lifespans == []
        assert report.total_gap_duration == pytest.approx(0.0)
