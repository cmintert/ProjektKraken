"""Regression contracts for the Analysis Suite trust milestone."""

from __future__ import annotations

import json

import pytest

from src.core.analysis import (
    AnalysisCoverage,
    AnalysisPreset,
    AnalysisScope,
    AnalysisScopeKind,
    AnalysisSectionStatus,
    EvidenceReference,
)
from src.core.entities import Entity
from src.core.events import Event
from src.core.temporal_window import TemporalWindowKind, resolve_temporal_window
from src.gui.dialogs.analysis_run_dialog import AnalysisRunDialog
from src.gui.widgets.analysis.main_analysis_panel import MainAnalysisPanel
from src.services.intelligence_analyzer import IntelligenceAnalyzer


@pytest.mark.unit
def test_presets_have_required_candidate_and_request_budgets() -> None:
    assert AnalysisPreset.QUICK.limits == {
        "plot_holes": 3,
        "relations": 5,
        "lore": 2,
    }
    assert sum(AnalysisPreset.BALANCED.limits.values()) == 19
    assert sum(AnalysisPreset.THOROUGH.limits.values()) == 35


@pytest.mark.unit
def test_current_item_scope_includes_one_hop_objects() -> None:
    first = Entity(id="a", name="A", type="character")
    second = Entity(id="b", name="B", type="place")
    outside = Entity(id="c", name="C", type="place")
    event = Event(id="event", name="Event", lore_date=1.0)
    relations = [
        {"id": "r1", "source_id": "a", "target_id": "b"},
        {"id": "r2", "source_id": "a", "target_id": "event"},
    ]
    entities, events, scoped_relations = IntelligenceAnalyzer(None)._apply_scope(
        AnalysisScope(kind=AnalysisScopeKind.CURRENT_ITEM, item_ids=["a"]),
        [first, second, outside],
        [event],
        relations,
    )
    assert {item.id for item in entities} == {"a", "b"}
    assert {item.id for item in events} == {"event"}
    assert {item["id"] for item in scoped_relations} == {"r1", "r2"}


@pytest.mark.unit
def test_tag_scope_matches_any_selected_tag() -> None:
    first = Entity(id="a", name="A", type="character", attributes={"_tags": ["x"]})
    second = Entity(id="b", name="B", type="place", attributes={"_tags": ["y"]})
    third = Entity(id="c", name="C", type="place", attributes={"_tags": ["z"]})
    entities, _events, _relations = IntelligenceAnalyzer(None)._apply_scope(
        AnalysisScope(kind=AnalysisScopeKind.TAGS, tags=["x", "y"]),
        [first, second, third],
        [],
        [],
    )
    assert {item.id for item in entities} == {"a", "b"}


@pytest.mark.unit
def test_date_scope_is_inclusive_and_does_not_pull_outside_events() -> None:
    start = Event(id="start", name="Start", lore_date=10.0)
    end = Event(id="end", name="End", lore_date=20.0)
    outside = Event(id="outside", name="Outside", lore_date=21.0)
    entity = Entity(id="entity", name="Entity", type="character")
    relations = [
        {"id": "r1", "source_id": "start", "target_id": "entity"},
        {"id": "r2", "source_id": "end", "target_id": "outside"},
    ]
    entities, events, scoped_relations = IntelligenceAnalyzer(None)._apply_scope(
        AnalysisScope(
            kind=AnalysisScopeKind.DATE_RANGE,
            start_date=10.0,
            end_date=20.0,
        ),
        [entity],
        [start, end, outside],
        relations,
    )
    assert {item.id for item in events} == {"start", "end"}
    assert {item.id for item in entities} == {"entity"}
    assert [item["id"] for item in scoped_relations] == ["r1"]


@pytest.mark.unit
def test_optional_json_fence_is_accepted() -> None:
    assert IntelligenceAnalyzer._decode_json_object("```json\n{\"ok\": true}\n```") == {
        "ok": True
    }


@pytest.mark.unit
def test_invented_evidence_is_rejected() -> None:
    analyzer = IntelligenceAnalyzer(None)
    entity = Entity(id="a", name="A", type="character")
    payload = {
        "has_issue": True,
        "issue_kind": "logical_conflict",
        "description": "Contradiction",
        "severity": "high",
        "suggested_resolution": None,
        "confidence": 0.5,
        "evidence_ids": ["invented"],
    }
    evidence = [
        EvidenceReference(
            evidence_id="real",
            object_type="entity",
            object_id="a",
            object_name="A",
        )
    ]
    with pytest.raises(ValueError, match="invented evidence"):
        analyzer._parse_plot_hole_json(payload, entity, evidence)


@pytest.mark.unit
def test_coverage_distinguishes_skipped_failed_and_partial() -> None:
    assert AnalysisCoverage().status == AnalysisSectionStatus.SKIPPED
    assert (
        AnalysisCoverage(eligible=2, attempted=2, failed=2).status
        == AnalysisSectionStatus.FAILED
    )
    assert (
        AnalysisCoverage(eligible=2, attempted=2, succeeded=1, failed=1).status
        == AnalysisSectionStatus.PARTIAL
    )


@pytest.mark.unit
def test_instant_and_manual_equal_bound_semantics() -> None:
    instant = resolve_temporal_window({"valid_at_event": True}, 100.0)
    assert instant.kind == TemporalWindowKind.INSTANT
    assert instant.is_active(100.0 + 1e-10)
    assert not instant.is_active(100.0 + 1e-7)
    manual = resolve_temporal_window({"valid_from": 100.0, "valid_to": 100.0})
    assert not manual.is_valid


@pytest.mark.unit
def test_dynamic_instant_follows_moved_event() -> None:
    assert resolve_temporal_window({"valid_at_event": True}, 10.0).start == 10.0
    assert resolve_temporal_window({"valid_at_event": True}, 25.0).start == 25.0


@pytest.mark.unit
def test_run_dialog_requires_explicit_valid_scope(qapp) -> None:
    dialog = AnalysisRunDialog(current_item_id=None)
    start = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
    assert not start.isEnabled()
    dialog.scope_combo.setCurrentIndex(1)
    assert start.isEnabled()


@pytest.mark.unit
def test_standard_failure_restores_controls_and_shows_relevant_tab(qapp) -> None:
    panel = MainAnalysisPanel()
    panel.on_analysis_started("Running", "validation", "job")
    panel.on_standard_analysis_failed("job", "world", "validation", "Failed")
    assert panel.validate_btn.isEnabled()
    assert panel.validation_panel.header_label.text() == "Failed"
    assert panel.tab_widget.currentIndex() == panel._TAB_VALIDATION


@pytest.mark.unit
def test_scope_serialization_round_trip() -> None:
    scope = AnalysisScope(
        kind=AnalysisScopeKind.SELECTION,
        item_ids=["a", "b"],
        tags=["tag"],
        start_date=1.0,
        end_date=2.0,
    )
    assert AnalysisScope.from_dict(json.loads(json.dumps(scope.to_dict()))) == scope
