import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.entities import Entity
from src.services.summary_service import SummaryService


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
    entity = Entity(name="Hero", type="character", description="A brave hero.")

    result = summary_service.generate_summary(entity)

    # Check return value
    assert result.text == "This is a summary."
    assert result.model == "test-model"

    # Check LLM called
    mock_llm_provider.generate.assert_called_once()

    # Check Entity updated
    assert "_summary_data" in entity.attributes
    saved_data = entity.attributes["_summary_data"]
    assert saved_data["text"] == "This is a summary."
    assert saved_data["hash"] == summary_service._calculate_hash(entity)

    # Check DB update called
    mock_db_service.insert_entity.assert_called_with(entity)


def test_prompt_contains_wiki_link_instruction(summary_service, mock_llm_provider):
    entity = Entity(name="Page", type="loc", description="Links to [[Another Page]].")
    summary_service.generate_summary(entity)

    call_args = mock_llm_provider.generate.call_args
    prompt = call_args[0][0]  # First arg is prompt

    assert "[[Wiki Links]]" in prompt
    assert "preserve" in prompt.lower()


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
    entity = Entity(name="Test", type="char")
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
    entity = Entity(name="Test", type="char")
    mock_llm_provider.generate.side_effect = Exception("API Error")

    with pytest.raises(Exception) as excinfo:
        summary_service.generate_summary(entity)

    assert "API Error" in str(excinfo.value)
    # Ensure no partial update happened
    assert "_summary_data" not in entity.attributes


def test_generate_summary_handles_empty_response(summary_service, mock_llm_provider):
    entity = Entity(name="Test", type="char")
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
