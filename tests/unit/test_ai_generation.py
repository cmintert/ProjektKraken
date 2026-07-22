"""Tests for provider-neutral AI generation contracts."""

from src.core.ai_generation import (
    AIGenerationPreferences,
    GenerationApplyMode,
    GenerationReviewResult,
    ModelReply,
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
    preferences = AIGenerationPreferences(
        persona="Chronicler",
        entity_prompt_draft="Describe {name}",
        spatial_enabled=True,
    )

    assert AIGenerationPreferences.from_dict(preferences.to_dict()) == preferences
