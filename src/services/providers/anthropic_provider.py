"""
Anthropic Provider Implementation.

Provides text generation via Anthropic's Claude API.
Note: Anthropic does not provide embeddings API, so embeddings are not supported.
Supports streaming, health checks, timeouts, retries, and circuit breaker pattern.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import numpy as np
import requests

from src.services.llm_provider import Provider
from src.services.resilience import CircuitBreaker

logger = logging.getLogger(__name__)


class AnthropicProvider(Provider):
    """
    Anthropic Claude provider supporting text generation.

    Implements Anthropic API with streaming support, retries, and circuit breaker.
    Note: Does not support embeddings (Anthropic doesn't offer embedding models).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key.
            model: Model name for text generation.
            base_url: API base URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for failed requests.

        Raises:
            ValueError: If api_key is not provided.
        """
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)

        logger.info(f"AnthropicProvider initialized with model: {self.model}")

    def _make_headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def _retry_request(self, func, *args, **kwargs):
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

        raise last_exception

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings (NOT SUPPORTED by Anthropic).

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: Not implemented.

        Raises:
            NotImplementedError: Anthropic does not provide embeddings.
        """
        raise NotImplementedError(
            "Anthropic does not provide an embeddings API. "
            "Use a different provider for embeddings (e.g., OpenAI, LM Studio)."
        )

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

        def _generate_impl():
            """Inner implementation for retry wrapper."""
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if stop:
                payload["stop_sequences"] = stop

            response = requests.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=self._make_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            # Extract completion text from content blocks
            content = data.get("content", [])
            if not content:
                raise ValueError("No content blocks returned from API")

            # Combine text from all content blocks
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

            text = "".join(text_parts)
            finish_reason = data.get("stop_reason", "unknown")

            # Extract usage statistics
            usage_data = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0)
                + usage_data.get("output_tokens", 0),
            }

            return {
                "text": text,
                "model": data.get("model", self.model),
                "usage": usage,
                "finish_reason": finish_reason,
            }

        try:
            return self._retry_request(_generate_impl)
        except requests.exceptions.RequestException as e:
            logger.error(f"Anthropic generation request failed: {e}")
            raise Exception(
                f"Failed to generate completion from Anthropic API. Error: {e}"
            ) from e
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse Anthropic generation response: {e}")
            raise Exception(f"Invalid response from Anthropic API: {e}") from e

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
            payload["stop_sequences"] = stop

        try:
            # Use asyncio to run blocking requests in executor
            loop = asyncio.get_event_loop()

            def _make_request():
                return requests.post(
                    f"{self.base_url}/messages",
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

                # SSE format: "event: {type}" and "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix

                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type")

                        if event_type == "content_block_delta":
                            # Extract text delta from content block
                            delta_obj = data.get("delta", {})
                            if delta_obj.get("type") == "text_delta":
                                delta = delta_obj.get("text", "")
                                yield {"delta": delta}

                        elif event_type == "message_stop":
                            # Stream complete
                            yield {"delta": "", "finish_reason": "stop"}
                            break

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE chunk: {e}")
                        continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Anthropic streaming request failed: {e}")
            raise Exception(
                f"Failed to stream completion from Anthropic API. Error: {e}"
            ) from e

    def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and availability.

        Returns:
            Dict containing status, latency_ms, and message.
        """
        try:
            start_time = time.time()

            # Test messages endpoint with minimal request
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
            }

            response = requests.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=self._make_headers(),
                timeout=5,  # Short timeout for health check
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "message": "Anthropic API is responding normally",
                    "models": [self.model],
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "message": f"Anthropic API returned status {response.status_code}",
                    "models": [self.model],
                }

        except requests.exceptions.Timeout:
            return {
                "status": "degraded",
                "latency_ms": 5000,
                "message": "Anthropic API health check timed out",
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": f"Cannot connect to Anthropic API: {e}",
            }

    def metadata(self) -> Dict[str, Any]:
        """
        Get provider metadata and capabilities.

        Returns:
            Dict containing provider information and capabilities.
        """
        return {
            "provider_id": "anthropic",
            "name": "Anthropic Claude",
            "supports_embeddings": False,
            "supports_generation": True,
            "supports_streaming": True,
            "embedding_dimension": 0,
            "embedding_model": None,
            "generation_model": self.model,
            "max_tokens": 4096 if "haiku" in self.model else 200000,
            "base_url": self.base_url,
        }
