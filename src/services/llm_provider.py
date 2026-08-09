"""LLM Provider Abstraction Module.

Defines the abstract interface for LLM providers supporting both embeddings and text
generation with streaming capabilities.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, cast

import numpy as np

logger = logging.getLogger(__name__)


class Provider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement embeddings, generation, streaming, health checks, and
    metadata methods.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of shape (len(texts), dimension).

        Raises:
            Exception: If embedding generation fails.

        """
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate text completion for a prompt.

        Args:
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0-2.0).
            stop: Optional list of stop sequences.
            metadata: Optional metadata for the request (e.g., world_id).

        Returns:
            Dict containing:
                - text: Generated text string
                - model: Model identifier used
                - usage: Token usage statistics
                - finish_reason: Completion status ('stop', 'length', etc.)

        Raises:
            Exception: If generation fails.

        """
        pass

    @abstractmethod
    def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Generate text completion with streaming output.

        Args:
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0-2.0).
            stop: Optional list of stop sequences.
            metadata: Optional metadata for the request.

        Yields:
            Dict chunks containing:
                - delta: Text delta for this chunk
                - finish_reason: Optional completion status (last chunk only)

        Raises:
            Exception: If streaming fails.

        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check provider health and availability.

        Returns:
            Dict containing:
                - status: 'healthy', 'degraded', or 'unhealthy'
                - latency_ms: Response time in milliseconds
                - message: Optional status message
                - models: List of available models (if applicable)

        Raises:
            Exception: If health check fails.

        """
        pass

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Get provider metadata and capabilities.

        Returns:
            Dict containing:
                - provider_id: Unique provider identifier
                - name: Human-readable provider name
                - supports_embeddings: Boolean
                - supports_generation: Boolean
                - supports_streaming: Boolean
                - embedding_dimension: Embedding dimension (if applicable)
                - embedding_model: Embedding model name (if applicable)
                - generation_model: Generation model name (if applicable)
                - max_tokens: Maximum token limit for generation

        """
        pass

    def get_dimension(self) -> int:
        """Get the dimensionality of embeddings (convenience method).

        Returns:
            int: Embedding dimension.

        Raises:
            NotImplementedError: If provider doesn't support embeddings.

        """
        meta = self.metadata()
        if not meta.get("supports_embeddings", False):
            raise NotImplementedError(
                f"{meta.get('name', 'Provider')} does not support embeddings"
            )
        return meta.get("embedding_dimension", 0)

    def get_model_name(self) -> str:
        """Get the model name/identifier (convenience method).

        Returns:
            str: Model identifier (prioritizes generation model over embedding).

        """
        meta = self.metadata()
        return meta.get("generation_model") or meta.get("embedding_model", "unknown")


def get_provider_settings_from_qsettings(
    provider_id: str, world_id: Optional[str] = None
) -> Dict[str, Any]:
    """Load provider settings from QSettings.

    Args:
        provider_id: Provider identifier ('lmstudio', 'openai', 'google', 'anthropic').
        world_id: Optional world ID for per-world settings.

    Returns:
        Dict with provider-specific settings.

    """
    try:
        from PySide6.QtCore import QSettings

        from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        # Log identifying info for debugging
        logger.debug(
            f"Loading settings for provider: {provider_id} (World: {world_id})"
        )

        # Build settings key prefix
        prefix = f"ai_{provider_id}_"
        if world_id:
            prefix = f"ai_{provider_id}_{world_id}_"

        # Common settings
        result = {
            "enabled": settings.value(f"{prefix}enabled", True, type=bool),
            "timeout": cast(int, settings.value(f"{prefix}timeout", 30, type=int)),
        }

        # Provider-specific settings
        if provider_id == "lmstudio":
            from src.services.lmstudio_config import derive_lmstudio_endpoints
            from src.services.secret_store import get_api_key

            legacy_url = str(
                settings.value(
                    "ai_lmstudio_base_url",
                    settings.value(
                        "ai_gen_lmstudio_url",
                        settings.value(
                            "ai_lmstudio_url", "http://localhost:1234"
                        ),
                    ),
                )
            )
            endpoints = derive_lmstudio_endpoints(legacy_url)
            result.update(
                {
                    "base_url": endpoints.base_url,
                    "generation_model": str(
                        settings.value("ai_gen_lmstudio_model", "")
                    ),
                    "embedding_model": str(
                        settings.value("ai_lmstudio_model", "")
                    ),
                    "api_key": get_api_key("lmstudio"),
                    "embed_url": endpoints.embeddings_url,
                    "generate_url": endpoints.chat_completions_url,
                    "use_chat_api": settings.value(
                        f"ai_gen_{provider_id}_use_chat_api", True, type=bool
                    ),
                }
            )
        elif provider_id == "openai":
            from src.services.secret_store import get_api_key

            result.update(
                {
                    "api_key": get_api_key("openai"),
                    "model": settings.value(
                        "ai_gen_openai_model", "gpt-3.5-turbo"
                    ),
                    "embed_model": settings.value(
                        f"{prefix}embed_model", "text-embedding-ada-002"
                    ),
                    "base_url": settings.value(
                        f"{prefix}base_url", "https://api.openai.com/v1"
                    ),
                }
            )
        elif provider_id == "google":
            result.update(
                {
                    "project_id": settings.value("ai_gen_google_project_id", ""),
                    "location": settings.value(
                        "ai_gen_google_location", "us-central1"
                    ),
                    "credentials_path": settings.value(
                        "ai_gen_google_credentials_path", ""
                    ),
                    "model": settings.value(
                        "ai_gen_google_model", "text-bison@001"
                    ),
                    "embed_model": settings.value(
                        f"{prefix}embed_model", "textembedding-gecko@001"
                    ),
                }
            )
        elif provider_id == "anthropic":
            from src.services.secret_store import get_api_key

            result.update(
                {
                    "api_key": get_api_key("anthropic"),
                    "model": str(
                        settings.value(
                            "ai_gen_anthropic_model",
                            "claude-3-haiku-20240307",
                        )
                    ),
                    "base_url": str(
                        settings.value(
                            f"{prefix}base_url", "https://api.anthropic.com/v1"
                        )
                    ),
                }
            )

        return result
    except Exception as e:
        logger.warning(
            f"Failed to load {provider_id} settings from QSettings: {e}", exc_info=True
        )
        return {"enabled": False, "timeout": 30}


def create_provider(
    provider_id: str, world_id: Optional[str] = None, **overrides: Any
) -> Provider:
    """Create a provider instance based on configuration.

    Loads settings from QSettings with environment variable fallbacks,
    then applies any explicit overrides.

    Args:
        provider_id: 'lmstudio', 'openai', 'google', or 'anthropic'.
        world_id: Optional world ID for per-world provider settings.
        **overrides: Explicit parameter overrides.

    Returns:
        Provider: Configured provider instance.

    Raises:
        ValueError: If provider_id is unknown or configuration is invalid.
        ImportError: If required dependencies are not installed.

    """
    # Load settings from QSettings
    settings = get_provider_settings_from_qsettings(provider_id, world_id)

    logger.info(
        "Loaded provider settings: provider=%s enabled=%s timeout=%s",
        provider_id,
        settings.get("enabled"),
        settings.get("timeout"),
    )

    # Apply overrides
    if overrides:
        logger.info(f"Applying overrides for {provider_id}: {overrides.keys()}")
        settings.update(overrides)

    # Fallback to environment variables if not in settings
    if provider_id == "lmstudio":
        from src.services.providers.lmstudio_provider import LMStudioProvider

        capability = str(settings.pop("capability", "generation"))
        selected_model = (
            settings.get("embedding_model")
            if capability == "embedding"
            else settings.get("generation_model")
        )
        return LMStudioProvider(
            model=settings.get("model") or selected_model or os.getenv("LMSTUDIO_MODEL"),
            api_key=settings.get("api_key") or os.getenv("LMSTUDIO_API_KEY"),
            embed_url=settings.get("embed_url")
            or os.getenv("LMSTUDIO_EMBED_URL", "http://localhost:1234/v1/embeddings"),
            generate_url=settings.get("generate_url")
            or os.getenv(
                "LMSTUDIO_GENERATE_URL", "http://localhost:1234/v1/chat/completions"
            ),
            timeout=settings.get("timeout", 30),
            use_chat_api=settings.get("use_chat_api", True),
        )
    elif provider_id == "openai":
        from src.services.providers.openai_provider import OpenAIProvider

        api_key = settings.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY env variable "
                "or configure in settings."
            )

        return OpenAIProvider(
            api_key=api_key,
            model=settings.get("model", "gpt-3.5-turbo"),
            embed_model=settings.get("embed_model", "text-embedding-ada-002"),
            base_url=settings.get("base_url", "https://api.openai.com/v1"),
            timeout=settings.get("timeout", 30),
        )
    elif provider_id == "google":
        from src.services.providers.google_provider import GoogleProvider

        return GoogleProvider(
            project_id=settings.get("project_id") or os.getenv("GOOGLE_PROJECT_ID"),
            location=settings.get("location", "us-central1"),
            credentials_path=settings.get("credentials_path")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            model=settings.get("model", "text-bison@001"),
            embed_model=settings.get("embed_model", "textembedding-gecko@001"),
            timeout=settings.get("timeout", 30),
        )
    elif provider_id == "anthropic":
        from src.services.providers.anthropic_provider import AnthropicProvider

        api_key = settings.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY env variable "
                "or configure in settings."
            )

        return AnthropicProvider(
            api_key=api_key,
            model=settings.get("model", "claude-3-haiku-20240307"),
            base_url=settings.get("base_url", "https://api.anthropic.com/v1"),
            timeout=settings.get("timeout", 30),
        )
    else:
        raise ValueError(
            f"Unknown provider: {provider_id}. "
            f"Supported: 'lmstudio', 'openai', 'google', 'anthropic'"
        )
