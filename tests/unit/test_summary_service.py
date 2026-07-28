import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.entities import Entity
from src.core.summary_data import (
    calculate_summary_target_words,
    calculate_summary_word_limit,
)
from src.services.summary_service import SummaryService

LONG_DESCRIPTION = " ".join(f"source-{index}" for index in range(20))


@pytest.fixture
def mock_llm_provider():
    provider = MagicMock()
    provider.generate.return_value = {
        "text": "This is a summary.",
        "model": "test-model",
        "usage": {"total_tokens": 10},
        "finish_reason": "stop",
    }
    return provider


@pytest.fixture
def mock_db_service():
    db = MagicMock()
    return db


@pytest.fixture
def summary_service(mock_db_service, mock_llm_provider):
    # Patching create_provider to return our mock
    with patch(
        "src.services.summary_service.create_provider", return_value=mock_llm_provider
    ):
        service = SummaryService(mock_db_service)
        # Manually inject provider if constructor doesn't take it (likely uses factory)
        service._llm_provider = mock_llm_provider
        return service


def test_calculate_hash_changes_with_content(summary_service):
    entity = Entity(
        name="Test Entity", type="character", description="Original description"
    )
    hash1 = summary_service._calculate_hash(entity)

    entity.description = "New description"
    hash2 = summary_service._calculate_hash(entity)

    assert hash1 != hash2


def test_calculate_hash_ignores_irrelevant_fields(summary_service):
    entity = Entity(name="Test Entity", type="character", description="Desc")
    hash1 = summary_service._calculate_hash(entity)

    entity.modified_at = time.time()  # Should not affect content hash
    hash2 = summary_service._calculate_hash(entity)

    assert hash1 == hash2


def test_is_stale_returns_true_for_missing_summary(summary_service):
    entity = Entity(name="Test", type="char")
    assert summary_service.is_stale(entity) is True


def test_is_stale_returns_true_for_mismatched_hash(summary_service):
    entity = Entity(name="Test", type="char")
    # Manually store a summary with a fake hash
    entity.attributes["_summary_data"] = {
        "text": "Old summary",
        "hash": "old_hash",
        "timestamp": 12345.0,
        "model": "gpt-3.5",
    }
    assert summary_service.is_stale(entity) is True


def test_is_stale_returns_false_for_valid_hash(summary_service):
    entity = Entity(name="Test", type="char")
    current_hash = summary_service._calculate_hash(entity)
    entity.attributes["_summary_data"] = {
        "text": "Valid summary",
        "hash": current_hash,
        "timestamp": time.time(),
        "model": "gpt-4",
    }
    assert summary_service.is_stale(entity) is False


def test_get_summary_returns_cached_if_valid(summary_service, mock_llm_provider):
    entity = Entity(name="Test", type="char")
    current_hash = summary_service._calculate_hash(entity)
    cached_data = {
        "text": "Cached summary",
        "hash": current_hash,
        "timestamp": time.time(),
        "model": "gpt-4",
    }
    entity.attributes["_summary_data"] = cached_data

    result = summary_service.get_summary(entity)

    assert result is not None
    assert result.text == "Cached summary"
    mock_llm_provider.generate.assert_not_called()


def test_generate_summary_calls_llm_and_updates_entity(
    summary_service, mock_llm_provider, mock_db_service
):
    entity = Entity(name="Hero", type="character", description=LONG_DESCRIPTION)

    result = summary_service.generate_summary(entity)

    # Check return value
    assert result.text == "This is a summary."
    assert result.model == "test-model"

    # Check LLM called
    mock_llm_provider.generate.assert_called_once()

    # Check Entity updated in memory
    assert "_summary_data" in entity.attributes
    saved_data = entity.attributes["_summary_data"]
    assert saved_data["text"] == "This is a summary."
    assert saved_data["hash"] == summary_service._calculate_hash(entity)

    # Service should NOT persist directly; caller (editor) handles persistence
    mock_db_service.insert_entity.assert_not_called()
    mock_db_service.insert_event.assert_not_called()


def test_default_prompt_does_not_require_wiki_links(
    summary_service, mock_llm_provider
):
    # Ensure QSettings returns the default prompt (not one set by a prior test)
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove("ai_gen_summary_prompt")

    entity = Entity(
        name="Page",
        type="loc",
        description=f"Links to [[Another Page]]. {LONG_DESCRIPTION}",
    )
    summary_service.generate_summary(entity)

    call_args = mock_llm_provider.generate.call_args
    prompt = call_args[0][0]  # First arg is prompt

    assert "[[Another Page]]" in prompt
    assert "wiki link" not in prompt.lower()


def test_calculate_hash_handles_missing_optional_attributes(summary_service):
    # Entity without lore_date (default)
    entity1 = Entity(name="E1", type="T1", description="D1")
    hash1 = summary_service._calculate_hash(entity1)

    # Entity with lore_date
    entity2 = Entity(name="E1", type="T1", description="D1")
    entity2.lore_date = 100.0
    hash2 = summary_service._calculate_hash(entity2)

    assert hash1 != hash2


def test_get_summary_returns_none_for_malformed_data(summary_service):
    entity = Entity(name="Test", type="char", description=LONG_DESCRIPTION)
    # Missing 'hash' field
    entity.attributes["_summary_data"] = {
        "text": "Broken",
        "timestamp": time.time(),
        "model": "gpt-4",
    }

    result = summary_service.get_summary(entity)
    assert result is None


def test_generate_summary_handles_llm_error_gracefully(
    summary_service, mock_llm_provider
):
    entity = Entity(name="Test", type="char", description=LONG_DESCRIPTION)
    mock_llm_provider.generate.side_effect = Exception("API Error")

    with pytest.raises(Exception) as excinfo:
        summary_service.generate_summary(entity)

    assert "API Error" in str(excinfo.value)
    # Ensure no partial update happened
    assert "_summary_data" not in entity.attributes


def test_generate_summary_handles_empty_response(summary_service, mock_llm_provider):
    entity = Entity(name="Test", type="char", description=LONG_DESCRIPTION)
    mock_llm_provider.generate.return_value = {"text": ""}

    result = summary_service.generate_summary(entity)

    assert result.text == ""
    assert entity.attributes["_summary_data"]["text"] == ""


def test_is_stale_handles_corrupt_stored_hash(summary_service):
    entity = Entity(name="Test", type="char")
    # Hash is not a string
    entity.attributes["_summary_data"] = {
        "text": "Valid summary",
        "hash": 12345,  # Invalid type
        "timestamp": time.time(),
        "model": "gpt-4",
    }
    # Should be considered stale/invalid rather than crashing
    assert summary_service.is_stale(entity) is True


def test_generate_summary_uses_configured_max_tokens(
    summary_service, mock_llm_provider
):
    """Verify that generate_summary reads ai_gen_summary_max_tokens from settings."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_summary_max_tokens", 4096)

    entity = Entity(name="Hero", type="character", description=LONG_DESCRIPTION)
    summary_service.generate_summary(entity)

    call_args = mock_llm_provider.generate.call_args
    assert call_args[1]["max_tokens"] == 4096

    # Clean up
    settings.remove("ai_gen_summary_max_tokens")


def test_generate_summary_filters_reasoning_tags(summary_service, mock_llm_provider):
    """Verify that reasoning tags are removed from summaries when filter is enabled."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_filter_reasoning", True)

    # Simulate a response with <think> tags (like DeepSeek R1)
    mock_llm_provider.generate.return_value = {
        "text": (
            "<think>\nLet me analyze this entity...\n</think>\n"
            "This is the actual summary."
        ),
        "model": "deepseek-r1",
        "usage": {"total_tokens": 100},
        "finish_reason": "stop",
    }

    entity = Entity(name="Hero", type="character", description=LONG_DESCRIPTION)
    result = summary_service.generate_summary(entity)

    # The <think> block should be gone
    assert "<think>" not in result.text
    assert "Let me analyze" not in result.text
    assert "This is the actual summary." in result.text

    # Clean up
    settings.remove("ai_gen_filter_reasoning")


def test_generate_summary_uses_configured_temperature(
    summary_service, mock_llm_provider
):
    """Verify that generate_summary reads ai_gen_summary_temperature from settings."""
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_summary_temperature", 25)  # 0.25

    entity = Entity(name="Hero", type="character", description=LONG_DESCRIPTION)
    summary_service.generate_summary(entity)

    call_args = mock_llm_provider.generate.call_args
    # Temperature 25 should become 0.25
    assert call_args[1]["temperature"] == 0.25

    # Clean up
    settings.remove("ai_gen_summary_temperature")


def test_calculate_summary_word_limit_uses_ratio_and_ceiling():
    assert calculate_summary_word_limit("word " * 100) == 30
    assert calculate_summary_word_limit("word " * 1000) == 150
    assert calculate_summary_target_words("word " * 100) == 22
    assert calculate_summary_target_words("word " * 1000) == 150


def test_short_summary_limit_remains_shorter_than_source():
    assert calculate_summary_word_limit("word " * 20) == 19
    assert calculate_summary_word_limit("word " * 49) == 20
    assert calculate_summary_word_limit("word") == 0


def test_short_source_prompt_requires_one_sentence(summary_service):
    entity = Entity(
        name="Short",
        type="concept",
        description=" ".join(f"word-{index}" for index in range(20)),
    )

    prompt = summary_service._build_prompt(entity)

    assert "no more than 19 words" in prompt
    assert "exactly one sentence" in prompt


def test_too_short_source_is_rejected_before_provider(
    summary_service, mock_llm_provider
):
    entity = Entity(name="Tiny", type="concept", description="Only")

    with pytest.raises(RuntimeError, match="too short"):
        summary_service.generate_summary(entity)

    mock_llm_provider.generate.assert_not_called()


def test_overlong_response_retries_once_and_accepts_compliant_result(
    summary_service, mock_llm_provider
):
    source = " ".join(f"source-{index}" for index in range(100))
    overlong = " ".join(f"over-{index}" for index in range(31))
    compliant = " ".join(f"ok-{index}" for index in range(30))
    mock_llm_provider.generate.side_effect = [
        {"text": overlong, "model": "test-model"},
        {"text": compliant, "model": "test-model"},
    ]
    entity = Entity(name="Long", type="concept", description=source)

    result = summary_service.generate_summary(entity)

    assert result.text == compliant
    assert mock_llm_provider.generate.call_count == 2
    retry_prompt = mock_llm_provider.generate.call_args_list[1].args[0]
    assert "no more than 30 words" in retry_prompt
    assert overlong in retry_prompt
    assert "DRAFT TO COMPRESS" in retry_prompt
    assert "source-0" not in retry_prompt


def test_normal_prompt_targets_below_hard_limit(summary_service):
    entity = Entity(
        name="Long",
        type="concept",
        description=" ".join(f"source-{index}" for index in range(100)),
    )

    prompt = summary_service._build_prompt(entity)

    assert "Aim for no more than 22 words" in prompt
    assert "hard maximum is 30 words" in prompt


def test_response_between_target_and_hard_limit_is_accepted_without_retry(
    summary_service, mock_llm_provider
):
    source = " ".join(f"source-{index}" for index in range(100))
    acceptable = " ".join(f"ok-{index}" for index in range(27))
    mock_llm_provider.generate.return_value = {
        "text": acceptable,
        "model": "test-model",
    }
    entity = Entity(name="Long", type="concept", description=source)

    result = summary_service.generate_summary(entity)

    assert result.text == acceptable
    mock_llm_provider.generate.assert_called_once()


def test_two_overlong_responses_preserve_existing_summary(
    summary_service, mock_llm_provider
):
    source = " ".join(f"source-{index}" for index in range(100))
    overlong = " ".join(f"over-{index}" for index in range(31))
    existing = {
        "text": "Keep this",
        "hash": "old",
        "timestamp": 1.0,
        "model": "old-model",
    }
    mock_llm_provider.generate.return_value = {
        "text": overlong,
        "model": "test-model",
    }
    entity = Entity(
        name="Long",
        type="concept",
        description=source,
        attributes={"_summary_data": existing},
    )

    with pytest.raises(RuntimeError, match="overlong summary twice"):
        summary_service.generate_summary(entity)

    assert entity.attributes["_summary_data"] == existing
    assert mock_llm_provider.generate.call_count == 2


def test_second_overlong_response_is_trimmed_at_sentence_boundary(
    summary_service, mock_llm_provider
):
    source = " ".join(f"source-{index}" for index in range(100))
    sentences = [
        " ".join(f"sentence-{sentence}-{word}" for word in range(10)) + "."
        for sentence in range(4)
    ]
    second_overlong = " ".join(sentences)
    expected = " ".join(sentences[:3])
    mock_llm_provider.generate.side_effect = [
        {"text": second_overlong, "model": "test-model"},
        {"text": second_overlong, "model": "test-model"},
    ]
    entity = Entity(name="Long", type="concept", description=source)

    result = summary_service.generate_summary(entity)

    assert result.text == expected
    assert len(result.text.split()) == 30


def test_legacy_default_prompt_is_migrated_at_runtime(summary_service):
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    legacy_prompt = (
        "Summarize the following worldbuilding item neutrally, "
        "preserving all facts and the original tone. "
        "Crucially, PRESERVE any [[Wiki Links]] exactly as they appear.\n\n"
        "Item Data:\n"
        "Type: {type}\n"
        "Name: {name}\n"
        "Description: {description}"
    )
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("ai_gen_summary_prompt", legacy_prompt)
    try:
        entity = Entity(
            name="Legacy",
            type="concept",
            description=LONG_DESCRIPTION,
        )

        prompt = summary_service._build_prompt(entity)

        assert "preserving all facts" not in prompt
        assert "Wiki Links" not in prompt
        assert "essential facts" in prompt
    finally:
        settings.remove("ai_gen_summary_prompt")


def test_custom_prompt_still_receives_mandatory_constraint(
    summary_service, mock_llm_provider
):
    from PySide6.QtCore import QSettings

    from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue(
        "ai_gen_summary_prompt",
        "Custom: {name}\nDescription: {description}",
    )
    try:
        entity = Entity(
            name="Custom",
            type="concept",
            description=LONG_DESCRIPTION,
        )
        summary_service.generate_summary(entity)

        prompt = mock_llm_provider.generate.call_args.args[0]
        assert "Custom: Custom" in prompt
        assert "MANDATORY OUTPUT RULE" in prompt
        assert "wiki link" not in prompt.lower()
    finally:
        settings.remove("ai_gen_summary_prompt")
