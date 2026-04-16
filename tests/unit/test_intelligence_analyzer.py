"""Tests for IntelligenceAnalyzer service.

All tests inject a _FakeProvider so no real LLM is called.  Tests cover:
- Report shape and analysis_type routing
- Plot-hole parsing (severity mapping, resolution extraction, error handling)
- Relation inference parsing (yes/no, RELATION_TYPE, CONFIDENCE extraction)
- Lore generation (EVENT: block parsing, gap selection limits, missing surrounds)
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.analysis import (
    IntelligenceReport,
    LoreGapFiller,
    PlotHole,
    RelationProposal,
    SeverityLevel,
)
from src.core.entities import Entity
from src.core.events import Event
from src.services.intelligence_analyzer import IntelligenceAnalyzer

# ---------------------------------------------------------------------------
# Fake Provider
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Controllable stub for the Provider interface — no real LLM calls."""

    def __init__(
        self,
        response: str = "",
        raise_on_call: bool = False,
        model_name: str = "fake-model",
    ) -> None:
        """Configure the stub; set raise_on_call=True to simulate provider failure."""
        self._response = response
        self._raise = raise_on_call
        self._model_name = model_name
        self.call_count = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Fake generate — records prompt and returns canned response."""
        self.call_count += 1
        self.prompts.append(prompt)
        if self._raise:
            raise RuntimeError("LLM unavailable")
        return {
            "text": self._response,
            "model": self._model_name,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "finish_reason": "stop",
        }

    def metadata(self) -> dict[str, Any]:
        """Return minimal metadata."""
        return {
            "generation_model": self._model_name,
            "supports_generation": True,
            "supports_embeddings": False,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(eid: str, name: str, tags: list[str] | None = None) -> Entity:
    """Create a minimal Entity for use in tests."""
    attrs: dict[str, Any] = {}
    if tags:
        attrs["_tags"] = tags
    return Entity(
        id=eid,
        name=name,
        type="character",
        description="A test character.",
        attributes=attrs,
    )


def _make_event(eid: str, name: str, lore_date: float) -> Event:
    """Create a minimal Event for use in tests."""
    return Event(id=eid, name=name, lore_date=lore_date, description="A test event.")


_PLOT_HOLE_RESPONSE = """\
PLOT HOLE: Alice disappears for 200 years with no explanation.
SEVERITY: high
RESOLUTION: Add an event covering her whereabouts.
CONFIDENCE: 0.91
"""

_RELATION_YES_RESPONSE = """\
SHOULD_RELATE: yes
RELATION_TYPE: ally
CONFIDENCE: 0.85
REASONING: Both characters share the warrior tag and fought in the same battle.
"""

_RELATION_YES_WITH_DIRECTION_RESPONSE = """\
SHOULD_RELATE: yes
SOURCE: Bob
TARGET: Alice
RELATION_TYPE: employs
CONFIDENCE: 0.90
REASONING: Bob runs the guild and Alice works for him.
"""

_RELATION_NO_RESPONSE = """\
SHOULD_RELATE: no
"""

_LORE_RESPONSE = """\
EVENT: The Long Silence
DATE: 150
DESCRIPTION: A period of unknown political upheaval during which no records survive.

EVENT: Rise of the Eastern Clans
DATE: 180
DESCRIPTION: Tribal factions consolidated power in the eastern territories.
"""


# ---------------------------------------------------------------------------
# TestIntelligenceAnalyzerReport
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntelligenceAnalyzerReport:
    """Tests for IntelligenceAnalyzer.analyze() report shape and routing."""

    def test_analyze_returns_intelligence_report(self, db_service):
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze()
        assert isinstance(report, IntelligenceReport)

    def test_analyze_empty_db_no_plot_holes(self, db_service):
        provider = _FakeProvider()
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes == []

    def test_analyze_type_plot_holes_only_skips_others(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.relation_proposals == []
        assert report.lore_suggestions == []

    def test_analyze_type_relations_only_skips_others(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert report.plot_holes == []
        assert report.lore_suggestions == []

    def test_analyze_type_lore_only_skips_others(self, db_service):
        # Insert events to create a gap > 100
        db_service.insert_event(_make_event("ev1", "First", 0.0))
        db_service.insert_event(_make_event("ev2", "Last", 500.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        assert report.plot_holes == []
        assert report.relation_proposals == []

    def test_report_contains_model_name(self, db_service):
        provider = _FakeProvider(model_name="test-model-42")
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze()
        assert report.analysis_model == "test-model-42"

    def test_report_timestamp_is_positive(self, db_service):
        provider = _FakeProvider()
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze()
        assert report.timestamp > 0

    def test_audit_log_is_list(self, db_service):
        provider = _FakeProvider()
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze()
        assert isinstance(report.audit_log, list)


# ---------------------------------------------------------------------------
# TestDetectPlotHoles
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetectPlotHoles:
    """Tests for IntelligenceAnalyzer._detect_plot_holes parsing and limits."""

    def test_plot_holes_parsed_from_response(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert len(report.plot_holes) == 1
        assert isinstance(report.plot_holes[0], PlotHole)

    def test_plot_hole_description_extracted(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert "Alice" in report.plot_holes[0].description

    def test_plot_hole_severity_high_maps_to_critical(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes[0].severity == SeverityLevel.CRITICAL

    def test_plot_hole_severity_low_maps_to_info(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Bob"))
        response = "PLOT HOLE: Bob appears twice in one scene.\nSEVERITY: low\n"
        provider = _FakeProvider(response=response)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes[0].severity == SeverityLevel.INFO

    def test_plot_hole_severity_medium_maps_to_warning(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Carol"))
        response = "PLOT HOLE: Carol changes allegiance unexpectedly.\nSEVERITY: medium\n"
        provider = _FakeProvider(response=response)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes[0].severity == SeverityLevel.WARNING

    def test_plot_hole_resolution_extracted(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes[0].suggested_resolution is not None
        assert "event" in report.plot_holes[0].suggested_resolution.lower()

    def test_plot_hole_confidence_extracted_from_response(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert abs(report.plot_holes[0].confidence - 0.91) < 0.001

    def test_plot_hole_confidence_defaults_when_missing(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        response = (
            "PLOT HOLE: Alice disappears for 200 years with no explanation.\n"
            "SEVERITY: high\n"
            "RESOLUTION: Add an event covering her whereabouts.\n"
        )
        provider = _FakeProvider(response=response)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert abs(report.plot_holes[0].confidence - 0.75) < 0.001

    def test_provider_error_logged_in_audit(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(raise_on_call=True)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        error_entries = [e for e in report.audit_log if "error" in e]
        assert len(error_entries) >= 1

    def test_provider_error_does_not_crash_analyze(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(raise_on_call=True)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        # Must not raise
        report = analyzer.analyze(analysis_type="plot_holes")
        assert isinstance(report, IntelligenceReport)
        assert report.plot_holes == []

    def test_top_entities_capped_at_ten(self, db_service):
        """With 15 entities, no more than 10 LLM calls should be made."""
        for i in range(15):
            db_service.insert_entity(_make_entity(f"e{i}", f"Entity{i}"))
        # Give each pair of entities a shared relation so they have connection count > 0
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        analyzer.analyze(analysis_type="plot_holes")
        assert provider.call_count <= 10

    def test_entity_id_set_on_plot_hole(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="plot_holes")
        assert report.plot_holes[0].entity_id == "e1"


# ---------------------------------------------------------------------------
# TestInferRelations
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInferRelations:
    """Tests for IntelligenceAnalyzer._infer_relations parsing and filtering."""

    def test_should_relate_yes_creates_proposal(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert len(report.relation_proposals) == 1
        assert isinstance(report.relation_proposals[0], RelationProposal)

    def test_should_relate_no_returns_no_proposal(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_NO_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert report.relation_proposals == []

    def test_relation_type_extracted_from_response(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert report.relation_proposals[0].suggested_relation_type == "ally"

    def test_confidence_extracted_from_response(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert abs(report.relation_proposals[0].confidence - 0.85) < 0.001

    def test_reasoning_extracted_from_response(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="relations")
        assert "warrior" in report.relation_proposals[0].reasoning

    def test_already_related_pair_skipped(self, db_service):
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        # Create existing relation so the pair is already related
        db_service.insert_relation("e1", "e2", "ally", {})
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        analyzer.analyze(analysis_type="relations")
        # With the only shared-tag pair already related, no LLM call needed
        assert provider.call_count == 0

    def test_candidates_no_shared_tags_produces_no_call(self, db_service):
        """Entities with no shared tags are not relation candidates."""
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["mage"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        analyzer.analyze(analysis_type="relations")
        assert provider.call_count == 0

    def test_candidates_capped_at_twenty_pairs(self, db_service):
        """At most 20 candidate pairs should reach the LLM."""
        # Create 10 entities all sharing the same tag → 10*9/2 = 45 pairs
        for i in range(10):
            db_service.insert_entity(_make_entity(f"e{i}", f"Entity{i}", tags=["shared"]))
        provider = _FakeProvider(response=_RELATION_NO_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        analyzer.analyze(analysis_type="relations")
        assert provider.call_count <= 20


# ---------------------------------------------------------------------------
# TestGenerateLore
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateLore:
    """Tests for IntelligenceAnalyzer._generate_lore gap selection and parsing."""

    def test_lore_generated_for_gap(self, db_service):
        # Gap threshold is 36,500 days (100 Gregorian years); use 40,000 to exceed it.
        db_service.insert_event(_make_event("ev1", "Start", 0.0))
        db_service.insert_event(_make_event("ev2", "End", 40000.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        assert len(report.lore_suggestions) == 1
        assert isinstance(report.lore_suggestions[0], LoreGapFiller)

    def test_lore_suggestions_parsed_from_event_blocks(self, db_service):
        db_service.insert_event(_make_event("ev1", "Start", 0.0))
        db_service.insert_event(_make_event("ev2", "End", 40000.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        # _LORE_RESPONSE has 2 EVENT: blocks
        assert len(report.lore_suggestions[0].suggestions) == 2

    def test_gap_filler_contains_start_and_end_date(self, db_service):
        db_service.insert_event(_make_event("ev1", "Start", 0.0))
        db_service.insert_event(_make_event("ev2", "End", 40000.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        filler = report.lore_suggestions[0]
        assert filler.start_date == 0.0
        assert filler.end_date == 40000.0

    def test_no_lore_without_surrounding_events(self, db_service):
        """Gap at the edge with no events on one side → skipped."""
        db_service.insert_event(_make_event("ev1", "Only", 0.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        assert report.lore_suggestions == []

    def test_at_most_five_gaps_processed(self, db_service):
        """Even with many gaps, at most 5 receive lore generation."""
        # Create 8 events each separated by 40,000 days → 7 gaps, all > threshold
        for i in range(8):
            db_service.insert_event(_make_event(f"ev{i}", f"E{i}", float(i * 40000)))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        analyzer.analyze(analysis_type="lore")
        assert provider.call_count <= 5

    def test_no_lore_when_no_gaps(self, db_service):
        """If events are too close together (gap ≤ threshold), no lore generated."""
        db_service.insert_event(_make_event("ev1", "E1", 0.0))
        db_service.insert_event(_make_event("ev2", "E2", 50.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        report = analyzer.analyze(analysis_type="lore")
        assert report.lore_suggestions == []


# ---------------------------------------------------------------------------
# TestPlotHolePromptDirection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlotHolePromptDirection:
    """Tests that _build_plot_hole_prompt uses SPO notation with correct direction."""

    def _build(
        self,
        entity: Any,
        relations: list[dict[str, Any]],
        name_map: dict[str, str] | None = None,
    ) -> str:
        """Helper to call the prompt builder directly."""
        analyzer = IntelligenceAnalyzer(None, provider=None)  # type: ignore[arg-type]
        return analyzer._build_plot_hole_prompt(
            entity=entity,
            entity_relations=relations,
            event_map={},
            entity_name_map=name_map or {},
        )

    def test_outgoing_relation_shows_entity_as_source(self) -> None:
        entity = _make_entity("e1", "Alice")
        rel = {"source_id": "e1", "target_id": "e2", "rel_type": "employs"}
        prompt = self._build(entity, [rel], {"e2": "Bob"})
        assert "Alice --employs--> Bob" in prompt

    def test_incoming_relation_shows_entity_as_target(self) -> None:
        entity = _make_entity("e1", "Alice")
        rel = {"source_id": "e2", "target_id": "e1", "rel_type": "employs"}
        prompt = self._build(entity, [rel], {"e2": "Bob"})
        assert "Bob --employs--> Alice" in prompt

    def test_outgoing_and_incoming_differ_for_same_rel_type(self) -> None:
        entity = _make_entity("e1", "Alice")
        outgoing = {"source_id": "e1", "target_id": "e2", "rel_type": "allied_with"}
        incoming = {"source_id": "e3", "target_id": "e1", "rel_type": "allied_with"}
        prompt = self._build(entity, [outgoing, incoming], {"e2": "Bob", "e3": "Carol"})
        assert "Alice --allied_with--> Bob" in prompt
        assert "Carol --allied_with--> Alice" in prompt

    def test_spo_preamble_present(self) -> None:
        entity = _make_entity("e1", "Alice")
        prompt = self._build(entity, [], {})
        assert "A --relation--> B" in prompt


# ---------------------------------------------------------------------------
# TestRelationProposalDirectionSwap
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRelationProposalDirectionSwap:
    """Tests that _parse_relation_proposal honours SOURCE:/TARGET: direction."""

    def _parse(self, response: str, source: Any, target: Any) -> RelationProposal | None:
        analyzer = IntelligenceAnalyzer(None, provider=None)  # type: ignore[arg-type]
        return analyzer._parse_relation_proposal(response, source, target)

    def test_no_source_target_fields_uses_param_order(self) -> None:
        src = _make_entity("e1", "Alice")
        tgt = _make_entity("e2", "Bob")
        result = self._parse(_RELATION_YES_RESPONSE, src, tgt)
        assert result is not None
        assert result.source_id == "e1"
        assert result.target_id == "e2"

    def test_source_target_matching_param_order_unchanged(self) -> None:
        src = _make_entity("e1", "Alice")
        tgt = _make_entity("e2", "Bob")
        response = "SHOULD_RELATE: yes\nSOURCE: Alice\nTARGET: Bob\nRELATION_TYPE: ally\nCONFIDENCE: 0.9\nREASONING: x\n"
        result = self._parse(response, src, tgt)
        assert result is not None
        assert result.source_id == "e1"
        assert result.source_name == "Alice"
        assert result.target_id == "e2"
        assert result.target_name == "Bob"

    def test_source_target_reversed_swaps_ids_and_names(self) -> None:
        """LLM picks Bob as source and Alice as target → swap the pair."""
        src = _make_entity("e1", "Alice")
        tgt = _make_entity("e2", "Bob")
        result = self._parse(_RELATION_YES_WITH_DIRECTION_RESPONSE, src, tgt)
        assert result is not None
        assert result.source_id == "e2"
        assert result.source_name == "Bob"
        assert result.target_id == "e1"
        assert result.target_name == "Alice"

    def test_source_target_unrecognised_names_falls_back_to_param_order(self) -> None:
        src = _make_entity("e1", "Alice")
        tgt = _make_entity("e2", "Bob")
        response = "SHOULD_RELATE: yes\nSOURCE: Unknown\nTARGET: Entity\nRELATION_TYPE: ally\nCONFIDENCE: 0.9\nREASONING: x\n"
        result = self._parse(response, src, tgt)
        assert result is not None
        # Falls back to param order
        assert result.source_id == "e1"
        assert result.target_id == "e2"

    def test_inference_prompt_contains_source_target_fields(self) -> None:
        """New prompt format must include SOURCE: and TARGET: in expected response."""
        analyzer = IntelligenceAnalyzer(None, provider=None)  # type: ignore[arg-type]
        src = _make_entity("e1", "Alice")
        tgt = _make_entity("e2", "Bob")
        prompt = analyzer._build_relation_inference_prompt(src, tgt)
        assert "SOURCE:" in prompt
        assert "TARGET:" in prompt


# ---------------------------------------------------------------------------
# TestOnPartialCallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOnPartialCallback:
    """Tests for the on_partial streaming callback in IntelligenceAnalyzer.analyze()."""

    def test_callback_fires_for_plot_holes(self, db_service):
        """on_partial fires with result_type='holes' when plot_holes sub-analysis runs."""
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received: list[tuple[str, Any]] = []
        analyzer.analyze(analysis_type="plot_holes", on_partial=lambda t, d: received.append((t, d)))

        assert len(received) == 1
        assert received[0][0] == "holes"

    def test_callback_fires_for_relations(self, db_service):
        """on_partial fires with result_type='relations' when relation sub-analysis runs."""
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        provider = _FakeProvider(response=_RELATION_YES_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received: list[tuple[str, Any]] = []
        analyzer.analyze(analysis_type="relations", on_partial=lambda t, d: received.append((t, d)))

        assert len(received) == 1
        assert received[0][0] == "relations"

    def test_callback_fires_for_lore(self, db_service):
        """on_partial fires with result_type='lore' when lore sub-analysis runs."""
        db_service.insert_event(_make_event("ev1", "First", 0.0))
        db_service.insert_event(_make_event("ev2", "Last", 500.0))
        provider = _FakeProvider(response=_LORE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received: list[tuple[str, Any]] = []
        analyzer.analyze(analysis_type="lore", on_partial=lambda t, d: received.append((t, d)))

        assert len(received) == 1
        assert received[0][0] == "lore"

    def test_callback_fires_three_times_for_all(self, db_service):
        """on_partial fires once per sub-analysis when analysis_type='all'."""
        db_service.insert_entity(_make_entity("e1", "Alice", tags=["warrior"]))
        db_service.insert_entity(_make_entity("e2", "Bob", tags=["warrior"]))
        db_service.insert_event(_make_event("ev1", "First", 0.0))
        db_service.insert_event(_make_event("ev2", "Last", 500.0))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received_types: list[str] = []
        analyzer.analyze(on_partial=lambda t, _d: received_types.append(t))

        assert sorted(received_types) == ["holes", "lore", "relations"]

    def test_callback_not_called_when_none(self, db_service):
        """analyze() does not raise when on_partial is omitted."""
        provider = _FakeProvider()
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)
        # Should complete without error
        report = analyzer.analyze()
        assert report is not None

    def test_callback_fires_with_empty_list_on_provider_failure(self, db_service):
        """on_partial fires with an empty result when the provider raises per-entity.

        Provider failures are caught inside the sub-analyzer's per-entity loop so
        the sub-analyzer itself returns successfully (with empty lists), and the
        callback still fires — the caller can render an empty section immediately.
        """
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(raise_on_call=True)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received: list[tuple[str, Any]] = []
        analyzer.analyze(
            analysis_type="plot_holes",
            on_partial=lambda t, d: received.append((t, d)),
        )

        # Sub-analyzer returned ([], [...audit_error...]) — callback fires
        assert len(received) == 1
        assert received[0][0] == "holes"
        holes, _audit = received[0][1]
        assert holes == []

    def test_callback_receives_result_tuple(self, db_service):
        """on_partial data argument is the raw sub-analyzer result tuple."""
        db_service.insert_entity(_make_entity("e1", "Alice"))
        provider = _FakeProvider(response=_PLOT_HOLE_RESPONSE)
        analyzer = IntelligenceAnalyzer(db_service, provider=provider)

        received_data: list[Any] = []
        analyzer.analyze(
            analysis_type="plot_holes",
            on_partial=lambda _t, d: received_data.append(d),
        )

        assert len(received_data) == 1
        holes, audit = received_data[0]
        assert isinstance(holes, list)
        assert isinstance(audit, list)
