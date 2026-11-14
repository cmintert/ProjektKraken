"""General fixtures for mechanical generation integrity."""

import pytest

from src.core.generation_experiment import render_variant
from src.core.generation_quality import (
    assess_candidate,
    completion_status,
    output_allowance,
)
from src.core.mcp_access import McpFailure

pytestmark = pytest.mark.ci_fast


def test_repeated_links_and_aliases_are_preserved():
    source = "[[id:abc|River]] flows to [[Port]] and [[Port]]."
    assert not assess_candidate(source, source.replace("flows", "runs"), "stop")
    assert (
        assess_candidate(source, "River flows to [[Port]].", "stop")[0].code
        == "links_changed"
    )


def test_table_contents_and_alignment_are_protected():
    source = "| A | B |\n| :--- | ---: |\n| [[Port]] | **Often** |\n"
    assert not assess_candidate(source, source, "stop")
    assert any(
        f.code == "protected_blocks_changed"
        for f in assess_candidate(source, source.replace("Often", "Always"))
    )


def test_literal_link_is_not_a_semantic_reference():
    assert not any(
        f.code == "links_changed"
        for f in assess_candidate("`[[literal]]`", "`[[different]]`")
    )


def test_completion_and_append_are_distinct():
    assert completion_status("length") == "incomplete"
    assert completion_status(None) == "unknown"
    assert assess_candidate("[[Port]]", "Addition.", "stop", "append") == []
    assert assess_candidate("[[Port]]", "[[Port]]", "stop", "append")
    assert assess_candidate("", "unfinished", "length")[0].code == "truncated"


def test_budget_grows_with_source_and_expansion():
    source = "Words " * 1000
    assert output_allowance(source, "expand_grounded") > output_allowance(
        source, "revise"
    )
    assert output_allowance("short", "condense") == 1024


def test_variant_excludes_only_optional_blocks():
    baseline = {"system": "policy", "user": "[Subject] source\n\nfacts\n\n[Task] edit"}
    blocks = {"subject": "source", "task": "edit", "authoring": "facts"}
    result = render_variant(
        baseline, blocks, {"exclude": ["authoring"], "max_tokens": 1024}
    )
    assert "facts" not in result["user"]
    assert result["system"] == "policy"
    with pytest.raises(McpFailure):
        render_variant(baseline, blocks, {"exclude": ["subject"]})
    with pytest.raises(McpFailure):
        render_variant(baseline, blocks, {"max_tokens": True})


def test_dated_baseline_is_reference_not_historical_evidence():
    from src.core.authoring_context import ContextAttribute, EntityAuthoringContext
    from src.services.generation_context_policy import select_entity_evidence

    baseline = ContextAttribute("Description", "A mature capital", {"kind": "baseline"})
    context = EntityAuthoringContext(
        entity_id="city", mode="at_playhead", effective_description=baseline
    )
    selected = select_entity_evidence(context, include_undated=False)
    assert selected.effective_description is None
    assert context.effective_description == baseline
    assert (
        select_entity_evidence(context, include_undated=True).effective_description
        == baseline
    )


def test_output_only_variant_retains_exact_baseline():
    baseline = {"system": "policy", "user": "Exact headings and whitespace.\n"}
    assert (
        render_variant(baseline, {"subject": "x", "task": "edit"}, {"max_tokens": 1024})
        == baseline
    )


def test_legacy_numeric_preferences_stay_manual():
    from src.core.ai_generation import AIGenerationPreferences

    assert (
        AIGenerationPreferences.from_dict({"version": 2, "max_tokens": 512}).budget_mode
        == "manual"
    )
    assert AIGenerationPreferences.from_dict({}).budget_mode == "auto"


def test_exclusion_keeps_every_other_prompt_byte():
    baseline = {
        "system": "policy",
        "user": "[Subject]\nsource\n\n[Retrieved Context]\nreference\n\n[Task]\nedit\n",
    }
    result = render_variant(
        baseline,
        {"subject": "source", "task": "edit", "retrieved": "reference"},
        {"exclude": ["retrieved"], "max_tokens": 1024},
    )
    assert result == {
        "system": "policy",
        "user": "[Subject]\nsource\n\n\n\n[Task]\nedit\n",
    }
