"""
Unit tests for LLM provider abstraction and implementations.

Tests the Provider interface, factory, and individual provider implementations.
"""

import os
from unittest.mock import patch

import numpy as np
import pytest
import requests

from src.services.llm_provider import create_provider
from src.services.providers.anthropic_provider import AnthropicProvider
from src.services.providers.lmstudio_provider import LMStudioProvider
from src.services.providers.openai_provider import OpenAIProvider

# =============================================================================
# Mock HTTP Responses
# =============================================================================


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(self, json_data, status_code=200, stream=False):
        self.json_data = json_data
        self.status_code = status_code
        self._stream = stream

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def iter_lines(self):
        """Mock SSE stream for streaming responses."""
        if not self._stream:
            return []

        # Simulate SSE stream
        lines = [
            b'data: {"choices": [{"text": "Hello", "finish_reason": null}]}',
            b'data: {"choices": [{"text": " world", "finish_reason": null}]}',
            b'data: {"choices": [{"text": "!", "finish_reason": "stop"}]}',
            b"data: [DONE]",
        ]
        return lines


# =============================================================================
# LMStudioProvider Tests
# =============================================================================


@pytest.fixture
def mock_requests():
    """Fixture to mock requests module."""
    with patch("src.services.providers.lmstudio_provider.requests") as mock:
        mock.exceptions.RequestException = requests.exceptions.RequestException
        mock.exceptions.Timeout = requests.exceptions.Timeout
        yield mock


def test_lmstudio_init():
    """Test LMStudioProvider initialization."""
    provider = LMStudioProvider(
        model="test-model",
        embed_url="http://localhost:8080/v1/embeddings",
        generate_url="http://localhost:8080/v1/completions",
    )

    assert provider.model == "test-model"
    assert provider.embed_url == "http://localhost:8080/v1/embeddings"
    assert provider.generate_url == "http://localhost:8080/v1/completions"


def test_lmstudio_init_no_model():
    """Test LMStudioProvider raises error without model."""
    with pytest.raises(ValueError, match="Model name is required"):
        LMStudioProvider()


def test_lmstudio_embed(mock_requests):
    """Test LMStudioProvider embedding generation."""
    # Mock API response
    mock_response = MockResponse(
        {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }
    )
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(model="test-model")
    embeddings = provider.embed(["text1", "text2"])

    assert embeddings.shape == (2, 3)
    assert np.allclose(embeddings[0], [0.1, 0.2, 0.3])
    assert np.allclose(embeddings[1], [0.4, 0.5, 0.6])

    # Verify API call
    assert mock_requests.post.called
    call_args = mock_requests.post.call_args
    assert call_args[1]["json"]["input"] == ["text1", "text2"]
    assert call_args[1]["json"]["model"] == "test-model"


def test_lmstudio_embed_empty(mock_requests):
    """Test LMStudioProvider with empty input."""
    provider = LMStudioProvider(model="test-model")
    embeddings = provider.embed([])

    assert embeddings.shape == (0,)
    assert not mock_requests.post.called


def test_lmstudio_generate(mock_requests):
    """Test LMStudioProvider text generation with default chat mode."""
    # Mock chat API response format (default mode)
    mock_response = MockResponse(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Generated text"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(model="test-model")
    result = provider.generate("Test prompt", max_tokens=100, temperature=0.7)

    assert result["text"] == "Generated text"
    assert result["model"] == "test-model"
    assert result["finish_reason"] == "stop"
    assert result["usage"]["total_tokens"] == 15

    # Verify API call uses messages format (default chat mode)
    assert mock_requests.post.called
    call_args = mock_requests.post.call_args
    payload = call_args[1]["json"]
    assert "messages" in payload
    assert payload["messages"][0]["content"] == "Test prompt"
    assert payload["max_tokens"] == 100
    assert payload["temperature"] == 0.7


def test_lmstudio_health_check(mock_requests):
    """Test LMStudioProvider health check."""
    # Mock healthy response
    mock_response = MockResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(model="test-model")
    health = provider.health_check()

    assert health["status"] == "healthy"
    assert health["latency_ms"] > 0
    assert "test-model" in health["models"]


def test_lmstudio_metadata():
    """Test LMStudioProvider metadata."""
    provider = LMStudioProvider(model="test-model")
    meta = provider.metadata()

    assert meta["provider_id"] == "lmstudio"
    assert meta["name"] == "LM Studio"
    assert meta["supports_embeddings"] is True
    assert meta["supports_generation"] is True
    assert meta["supports_streaming"] is True
    assert meta["generation_model"] == "test-model"


def test_lmstudio_init_chat_mode_default():
    """Test LMStudioProvider defaults to chat API mode."""
    provider = LMStudioProvider(model="test-model")

    assert provider.use_chat_api is True
    assert "chat/completions" in provider.generate_url


def test_lmstudio_init_legacy_mode():
    """Test LMStudioProvider can be initialized in legacy mode."""
    provider = LMStudioProvider(
        model="test-model",
        use_chat_api=False,
        generate_url="http://localhost:8080/v1/completions",
    )

    assert provider.use_chat_api is False
    assert "completions" in provider.generate_url


def test_lmstudio_generate_chat_mode_with_dict_prompt(mock_requests):
    """Test LMStudioProvider generates with structured prompt in chat mode."""
    # Mock chat API response format
    mock_response = MockResponse(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Generated text"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(model="test-model", use_chat_api=True)

    # Structured prompt with system/user separation
    prompt = {"system": "You are a fantasy writer.", "user": "Describe a castle."}
    result = provider.generate(prompt, max_tokens=100)

    assert result["text"] == "Generated text"
    assert result["finish_reason"] == "stop"

    # Verify API call uses messages format
    call_args = mock_requests.post.call_args
    payload = call_args[1]["json"]
    assert "messages" in payload
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "You are a fantasy writer."
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "Describe a castle."


def test_lmstudio_generate_chat_mode_with_string_prompt(mock_requests):
    """Test chat mode handles legacy string prompt by treating as user message."""
    mock_response = MockResponse(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Generated text"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(model="test-model", use_chat_api=True)
    result = provider.generate("Simple string prompt", max_tokens=100)

    assert result["text"] == "Generated text"

    # String prompt should become user message
    call_args = mock_requests.post.call_args
    payload = call_args[1]["json"]
    assert "messages" in payload
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "Simple string prompt"


def test_lmstudio_generate_legacy_mode(mock_requests):
    """Test LMStudioProvider legacy mode uses old completions format."""
    mock_response = MockResponse(
        {
            "choices": [{"text": "Generated text", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    mock_requests.post.return_value = mock_response

    provider = LMStudioProvider(
        model="test-model",
        use_chat_api=False,
        generate_url="http://localhost:8080/v1/completions",
    )
    result = provider.generate("Test prompt", max_tokens=100)

    assert result["text"] == "Generated text"

    # Verify uses legacy prompt format
    call_args = mock_requests.post.call_args
    payload = call_args[1]["json"]
    assert "prompt" in payload
    assert "messages" not in payload


# =============================================================================
# OpenAIProvider Tests
# =============================================================================


@pytest.fixture
def mock_openai_requests():
    """Fixture to mock requests module for OpenAI."""
    with patch("src.services.providers.openai_provider.requests") as mock:
        mock.exceptions.RequestException = requests.exceptions.RequestException
        yield mock


def test_openai_init():
    """Test OpenAIProvider initialization."""
    provider = OpenAIProvider(
        api_key="test-key", model="gpt-3.5-turbo", embed_model="text-embedding-ada-002"
    )

    assert provider.api_key == "test-key"
    assert provider.model == "gpt-3.5-turbo"
    assert provider.embed_model == "text-embedding-ada-002"


def test_openai_init_no_key():
    """Test OpenAIProvider raises error without API key."""
    with pytest.raises(ValueError, match="API key is required"):
        OpenAIProvider(api_key="")


def test_openai_embed(mock_openai_requests):
    """Test OpenAIProvider embedding generation."""
    # Mock API response
    mock_response = MockResponse(
        {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        }
    )
    mock_openai_requests.post.return_value = mock_response

    provider = OpenAIProvider(api_key="test-key")
    embeddings = provider.embed(["text1", "text2"])

    assert embeddings.shape == (2, 3)
    assert np.allclose(embeddings[0], [0.1, 0.2, 0.3])

    # Verify API call includes auth header
    call_args = mock_openai_requests.post.call_args
    assert "Authorization" in call_args[1]["headers"]
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"


def test_openai_generate(mock_openai_requests):
    """Test OpenAIProvider text generation."""
    # Mock API response
    mock_response = MockResponse(
        {
            "choices": [
                {
                    "message": {"content": "Generated text"},
                    "finish_reason": "stop",
                }
            ],
            "model": "gpt-3.5-turbo",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    mock_openai_requests.post.return_value = mock_response

    provider = OpenAIProvider(api_key="test-key")
    result = provider.generate("Test prompt", max_tokens=100)

    assert result["text"] == "Generated text"
    assert result["model"] == "gpt-3.5-turbo"
    assert result["finish_reason"] == "stop"

    # Verify API call uses chat/completions format
    call_args = mock_openai_requests.post.call_args
    assert "chat/completions" in call_args[0][0]
    assert call_args[1]["json"]["messages"][0]["content"] == "Test prompt"


def test_openai_metadata():
    """Test OpenAIProvider metadata."""
    provider = OpenAIProvider(api_key="test-key", model="gpt-4")
    meta = provider.metadata()

    assert meta["provider_id"] == "openai"
    assert meta["name"] == "OpenAI"
    assert meta["supports_embeddings"] is True
    assert meta["supports_generation"] is True
    assert meta["supports_streaming"] is True
    assert meta["generation_model"] == "gpt-4"


# =============================================================================
# AnthropicProvider Tests
# =============================================================================


@pytest.fixture
def mock_anthropic_requests():
    """Fixture to mock requests module for Anthropic."""
    with patch("src.services.providers.anthropic_provider.requests") as mock:
        mock.exceptions.RequestException = requests.exceptions.RequestException
        yield mock


def test_anthropic_init():
    """Test AnthropicProvider initialization."""
    provider = AnthropicProvider(api_key="test-key", model="claude-3-haiku-20240307")

    assert provider.api_key == "test-key"
    assert provider.model == "claude-3-haiku-20240307"


def test_anthropic_init_no_key():
    """Test AnthropicProvider raises error without API key."""
    with pytest.raises(ValueError, match="API key is required"):
        AnthropicProvider(api_key="")


def test_anthropic_embed_not_supported():
    """Test AnthropicProvider does not support embeddings."""
    provider = AnthropicProvider(api_key="test-key")

    with pytest.raises(NotImplementedError, match="does not provide an embeddings API"):
        provider.embed(["text1"])


def test_anthropic_generate(mock_anthropic_requests):
    """Test AnthropicProvider text generation."""
    # Mock API response
    mock_response = MockResponse(
        {
            "content": [{"type": "text", "text": "Generated text"}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )
    mock_anthropic_requests.post.return_value = mock_response

    provider = AnthropicProvider(api_key="test-key")
    result = provider.generate("Test prompt", max_tokens=100)

    assert result["text"] == "Generated text"
    assert result["model"] == "claude-3-haiku-20240307"
    assert result["finish_reason"] == "end_turn"

    # Verify API call uses correct headers
    call_args = mock_anthropic_requests.post.call_args
    assert call_args[1]["headers"]["x-api-key"] == "test-key"
    assert "anthropic-version" in call_args[1]["headers"]


def test_anthropic_metadata():
    """Test AnthropicProvider metadata."""
    provider = AnthropicProvider(api_key="test-key", model="claude-3-opus-20240229")
    meta = provider.metadata()

    assert meta["provider_id"] == "anthropic"
    assert meta["name"] == "Anthropic Claude"
    assert meta["supports_embeddings"] is False
    assert meta["supports_generation"] is True
    assert meta["supports_streaming"] is True
    assert meta["generation_model"] == "claude-3-opus-20240229"


# =============================================================================
# Provider Factory Tests
# =============================================================================


def test_create_provider_lmstudio():
    """Test factory creates LMStudioProvider."""
    with patch.dict(os.environ, {"LMSTUDIO_MODEL": "test-model"}):
        provider = create_provider("lmstudio")
        assert isinstance(provider, LMStudioProvider)
        assert provider.model == "test-model"


def test_create_provider_openai():
    """Test factory creates OpenAIProvider."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        provider = create_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "test-key"


def test_create_provider_anthropic():
    """Test factory creates AnthropicProvider."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        provider = create_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)
        assert provider.api_key == "test-key"


def test_create_provider_unknown():
    """Test factory raises error for unknown provider."""
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("unknown_provider")


def test_create_provider_with_overrides():
    """Test factory applies parameter overrides."""
    provider = create_provider("lmstudio", model="override-model", timeout=60)
    assert isinstance(provider, LMStudioProvider)
    assert provider.model == "override-model"
    assert provider.timeout == 60


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


def test_lmstudio_circuit_breaker(mock_requests):
    """Test circuit breaker opens after repeated failures."""
    # Mock failing responses
    mock_requests.post.side_effect = Exception("Connection failed")

    provider = LMStudioProvider(model="test-model", max_retries=2)
    provider.circuit_breaker.failure_threshold = 2

    # First attempt should fail and retry
    with pytest.raises(Exception, match="Connection failed"):
        provider.embed(["test"])

    # Second attempt should fail and open circuit
    with pytest.raises(Exception):
        provider.embed(["test"])

    # Third attempt should fail immediately due to open circuit
    with pytest.raises(Exception, match="Circuit breaker is OPEN"):
        provider.embed(["test"])


# =============================================================================
# Retry Logic Tests
# =============================================================================


def test_lmstudio_retry_success(mock_requests):
    """Test retry logic succeeds after initial failure."""
    # Mock response that fails first, then succeeds
    responses = [
        Exception("Temporary failure"),
        MockResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]}),
    ]
    mock_requests.post.side_effect = responses

    provider = LMStudioProvider(model="test-model", max_retries=3)
    embeddings = provider.embed(["test"])

    assert embeddings.shape == (1, 3)
    assert mock_requests.post.call_count == 2  # Failed once, then succeeded
