"""Tests for LM Studio endpoint and model-discovery configuration."""

from unittest.mock import MagicMock, patch

from src.services.lmstudio_config import (
    derive_lmstudio_endpoints,
    discover_lmstudio_models,
    normalize_lmstudio_base_url,
)


def test_normalize_migrates_full_endpoint_to_base_url() -> None:
    assert (
        normalize_lmstudio_base_url(
            "http://192.168.178.67:1234/v1/chat/completions"
        )
        == "http://192.168.178.67:1234"
    )


def test_derive_all_openai_compatible_endpoints() -> None:
    endpoints = derive_lmstudio_endpoints("192.168.178.67:1234/")
    assert endpoints.models_url.endswith("/v1/models")
    assert endpoints.chat_completions_url.endswith("/v1/chat/completions")
    assert endpoints.embeddings_url.endswith("/v1/embeddings")


@patch("src.services.lmstudio_config.requests.get")
def test_model_discovery_returns_sorted_unique_ids(mock_get: MagicMock) -> None:
    response = mock_get.return_value
    response.json.return_value = {
        "data": [{"id": "zeta"}, {"id": "Alpha"}, {"id": "zeta"}]
    }

    assert discover_lmstudio_models("http://localhost:1234") == ["Alpha", "zeta"]
    response.raise_for_status.assert_called_once()
    assert mock_get.call_args.args[0] == "http://localhost:1234/v1/models"
