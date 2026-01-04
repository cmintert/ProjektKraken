"""
OpenAI Provider Implementation.

Provides embeddings and text generation via OpenAI API.
Supports streaming, health checks, timeouts, retries, and circuit breaker pattern.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import numpy as np
import requests

from src.services.llm_provider import Provider
from src.services.resilience import CircuitBreaker

logger = logging.getLogger(__name__)


class OpenAIProvider(Provider):
    """
    OpenAI provider supporting embeddings and text generation.

    Implements OpenAI API with streaming support, retries, and circuit breaker.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        embed_model: str = "text-embedding-ada-002",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model name for text generation.
            embed_model: Model name for embeddings.
            base_url: API base URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for failed requests.

        Raises:
            ValueError: If api_key is not provided.
        """
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self.api_key = api_key
        self.model = model
        self.embed_model = embed_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._dimension = None
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)

        logger.info(f"OpenAIProvider initialized with model: {self.model}")
        logger.info(f"Embedding model: {self.embed_model}")

    def _make_headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _retry_request(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute request with retry logic and exponential backoff."""
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return self.circuit_breaker.call(func, *args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Request failed after {self.max_retries} attempts: {e}"
                    )

        if last_exception:
            raise last_exception
        raise Exception("Request failed with no exception captured")

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings using OpenAI API.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of embeddings.

        Raises:
            Exception: If API request fails or response is invalid.
        """
        if not texts:
            return np.array([])

        def _embed_impl() -> np.ndarray:
            """Inner implementation for retry wrapper."""
            payload = {"input": texts, "model": self.embed_model}
            response = requests.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers=self._make_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]

            if not embeddings:
                raise ValueError("No embeddings returned from API")

            emb_array = np.array(embeddings, dtype=np.float32)

            # Cache dimension
            if self._dimension is None:
                self._dimension = emb_array.shape[1]

            logger.debug(
                f"Generated {len(embeddings)} embeddings with dimension {self._dimension}"
            )
            return emb_array

        try:
            return self._retry_request(_embed_impl)
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI embedding request failed: {e}")
            raise Exception(f"Failed to connect to OpenAI API. Error: {e}") from e
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI embedding response: {e}")
            raise Exception(f"Invalid response from OpenAI API: {e}") from e

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate text completion for a prompt.

        Args:
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0-2.0).
            stop: Optional list of stop sequences.
            metadata: Optional metadata for the request.

        Returns:
            Dict containing text, model, usage, and finish_reason.

        Raises:
            Exception: If generation fails.
        """

        def _generate_impl() -> Dict[str, Any]:
            """Inner implementation for retry wrapper."""
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }

            if stop:
                payload["stop"] = stop

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._make_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            # Extract completion text
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No completion choices returned from API")

            message = choices[0].get("message", {})
            text = message.get("content", "")
            finish_reason = choices[0].get("finish_reason", "unknown")

            # Extract usage statistics
            usage = data.get("usage", {})

            return {
                "text": text,
                "model": data.get("model", self.model),
                "usage": usage,
                "finish_reason": finish_reason,
            }

        try:
            return self._retry_request(_generate_impl)
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI generation request failed: {e}")
            raise Exception(
                f"Failed to generate completion from OpenAI API. Error: {e}"
            ) from e
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI generation response: {e}")
            raise Exception(f"Invalid response from OpenAI API: {e}") from e

    async def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate text completion with streaming output.

        Note: This implementation uses blocking I/O wrapped in run_in_executor
        for the initial request, but iter_lines() still blocks the event loop.
        For production use with high concurrency, consider using an async HTTP
        client like aiohttp or httpx.

        Args:
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0-2.0).
            stop: Optional list of stop sequences.
            metadata: Optional metadata for the request.

        Yields:
            Dict chunks containing delta and optional finish_reason.

        Raises:
            Exception: If streaming fails.
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if stop:
            payload["stop"] = stop

        try:
            # Use asyncio to run blocking requests in executor
            loop = asyncio.get_event_loop()

            def _make_request() -> requests.Response:
                return requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._make_headers(),
                    timeout=self.timeout,
                    stream=True,
                )

            response = await loop.run_in_executor(None, _make_request)
            response.raise_for_status()

            # Parse SSE stream
            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode("utf-8")

                # SSE format: "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix

                    # Check for stream end marker
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])

                        if choices:
                            choice = choices[0]
                            delta_obj = choice.get("delta", {})
                            delta = delta_obj.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            chunk = {"delta": delta}
                            if finish_reason:
                                chunk["finish_reason"] = finish_reason

                            yield chunk

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE chunk: {e}")
                        continue

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI streaming request failed: {e}")
            raise Exception(
                f"Failed to stream completion from OpenAI API. Error: {e}"
            ) from e

    def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and availability.

        Returns:
            Dict containing status, latency_ms, and message.
        """
        try:
            start_time = time.time()

            # Test embeddings endpoint with minimal request
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={"input": ["test"], "model": self.embed_model},
                headers=self._make_headers(),
                timeout=5,  # Short timeout for health check
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "message": "OpenAI API is responding normally",
                    "models": [self.model, self.embed_model],
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "message": f"OpenAI API returned status {response.status_code}",
                    "models": [self.model, self.embed_model],
                }

        except requests.exceptions.Timeout:
            return {
                "status": "degraded",
                "latency_ms": 5000,
                "message": "OpenAI API health check timed out",
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": f"Cannot connect to OpenAI API: {e}",
            }

    def metadata(self) -> Dict[str, Any]:
        """
        Get provider metadata and capabilities.

        Returns:
            Dict containing provider information and capabilities.
        """
        return {
            "provider_id": "openai",
            "name": "OpenAI",
            "supports_embeddings": True,
            "supports_generation": True,
            "supports_streaming": True,
            "embedding_dimension": self._dimension or 1536,  # Ada-002 default
            "embedding_model": self.embed_model,
            "generation_model": self.model,
            "max_tokens": 4096 if "gpt-3.5" in self.model else 8192,
            "base_url": self.base_url,
        }
