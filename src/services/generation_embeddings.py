"""Offline embedding adapter for frozen generation preparation."""

import base64
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import numpy as np
import requests

from src.services.mcp_embedding_process import EmbeddingProcess
from src.services.search_service import EmbeddingProvider


class LoopbackSession(requests.Session):
    """Reject nonlocal endpoints, environment proxies and redirect escapes."""

    def __init__(self) -> None:
        """Use direct local connections only."""
        super().__init__()
        self.trust_env = False

    def post(
        self,
        url: str | bytes,
        data: Any = None,
        json: Any = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Send only to an explicitly loopback HTTP endpoint."""
        parsed = urlsplit(url.decode() if isinstance(url, bytes) else url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Local provider required")
        kwargs["allow_redirects"] = False
        return super().post(url, data=data, json=json, **kwargs)


class LocalGenerationEmbeddings(EmbeddingProvider):
    """Use pinned LM Studio embedding settings over a restricted session."""

    def __init__(self, settings: dict[str, Any]) -> None:
        """Construct a preparation-only provider, never an environment fallback."""
        from src.services.providers.lmstudio_provider import LMStudioProvider

        self.transport = LoopbackSession()
        self.model = settings["lm_model"] or ""
        self.provider = LMStudioProvider(
            model=self.model,
            embed_url=settings["lm_url"] or None,
            api_key=settings["lm_api_key"] or None,
            request_session=self.transport,
        )
        self.dimension = 0

    def embed(self, texts: list[str]) -> Any:
        """Preserve provider-neutral embedding values."""
        result = self.provider.embed(texts)
        self.dimension = int(result.shape[1])
        return result

    def get_dimension(self) -> int:
        """Resolve dimension lazily through the same restricted endpoint."""
        if not self.dimension:
            self.embed(["dimension"])
        return self.dimension

    def get_model_name(self) -> str:
        """Return the configured embedding model."""
        return self.model


class OfflineGenerationEmbeddings(EmbeddingProvider):
    """Use the existing cached-model helper without network downloads."""

    def __init__(
        self, model: str, cancelled: Callable[[], bool] = lambda: False
    ) -> None:
        """Capture an explicitly selected installed model."""
        self.model = model
        self.cancelled = cancelled
        self.helper = EmbeddingProcess()
        self.dimension = 0

    def embed(self, texts: list[str]) -> Any:
        """Encode in a bounded, offline helper process."""
        result = self.helper.encode(
            {"model": self.model, "texts": texts},
            self.cancelled,
            30,
        )
        vectors = np.frombuffer(
            base64.b64decode(result["vectors"]),
            dtype=np.float32,
        ).reshape(result["shape"])
        self.dimension = int(vectors.shape[1])
        return vectors

    def get_dimension(self) -> int:
        """Resolve the model dimension when requested before encoding."""
        if not self.dimension:
            self.embed(["dimension"])
        return self.dimension

    def get_model_name(self) -> str:
        """Return the pinned model identity."""
        return self.model
