"""Tests for provider-neutral AI generation contracts."""

from src.core.ai_generation import (
    AIGenerationPreferences,
    GenerationApplyMode,
    GenerationReviewResult,
    ModelReply,
    TaskIntent,
    TaskTemplate,
    TaskTemplateSource,
    apply_reviewed_generation,
)


def test_model_reply_maps_provider_fields_without_touching_content() -> None:
    content = "  # Title\n\n[[Link]] — text\n"
    reply = ModelReply.from_provider_result(
        {
            "text": content,
            "reasoning_content": "private",
            "tool_calls": [{"id": "call-1"}],
            "finish_reason": "stop",
        }
    )

    assert reply.content == content
    assert reply.reasoning_content == "private"
    assert reply.tool_calls == [{"id": "call-1"}]


def test_apply_modes_are_explicit_and_do_not_parse_reply_text() -> None:
    replacement = GenerationReviewResult(
        GenerationApplyMode.REPLACE,
        "APPEND:This is visible model text",
    )
    appended = GenerationReviewResult(GenerationApplyMode.APPEND, "New text")
    discarded = GenerationReviewResult(GenerationApplyMode.DISCARD, "Ignored")

    assert apply_reviewed_generation("Old", replacement) == replacement.text
    assert apply_reviewed_generation("Old", appended) == "Old\n\nNew text"
    assert apply_reviewed_generation("Old", discarded) == "Old"


def test_world_preferences_round_trip() -> None:
    custom = TaskTemplate(
        template_id="29ee028a-e40e-441f-bd9d-e170c55bf998",
        name="World Task",
        description="Portable",
        intent=TaskIntent.UPDATE,
        content="Revise {description}",
        source=TaskTemplateSource.WORLD,
    )
    preferences = AIGenerationPreferences(
        persona="Chronicler",
        entity_prompt_draft="Describe {name}",
        spatial_enabled=True,
        selected_entity_template_id="revise_clarity_flow",
        custom_task_templates=(custom,),
    )

    assert AIGenerationPreferences.from_dict(preferences.to_dict()) == preferences


def test_v1_template_selection_maps_to_v2_intent_task() -> None:
    preferences = AIGenerationPreferences.from_dict(
        {
            "version": 1,
            "selected_template_id": "description_detailed",
            "entity_prompt_draft": "Existing draft",
        }
    )

    assert preferences.version == 1
    assert preferences.selected_entity_template_id == "expand_grounded_detail"
    assert preferences.selected_event_template_id == "expand_grounded_detail"
    assert preferences.entity_prompt_draft == "Existing draft"
