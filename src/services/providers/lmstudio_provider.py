"""
LM Studio Provider Implementation.

Provides embeddings and text generation via LM Studio's OpenAI-compatible API.
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


class LMStudioProvider(Provider):
    """
    LM Studio provider supporting embeddings and text generation.

    Implements OpenAI-compatible API endpoints with streaming support,
    retries, and circuit breaker pattern.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embed_url: Optional[str] = None,
        generate_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize LM Studio provider.

        Args:
            url: Legacy API endpoint (deprecated, use embed_url/generate_url).
            model: Model name for both embedding and generation.
            api_key: Optional API key.
            embed_url: Embeddings endpoint URL.
            generate_url: Completions endpoint URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for failed requests.

        Raises:
            ValueError: If model is not specified.
        """
        self.model = model
        if not self.model:
            raise ValueError(
                "Model name is required. Set LMSTUDIO_MODEL env variable "
                "or pass model parameter."
            )

        # Handle legacy url parameter
        if url and not embed_url:
            embed_url = url

        self.embed_url = embed_url or "http://localhost:8080/v1/embeddings"
        self.generate_url = generate_url or "http://localhost:8080/v1/completions"
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._dimension = None
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)

        logger.info(f"LMStudioProvider initialized with model: {self.model}")
        logger.info(f"Embed URL: {self.embed_url}")
        logger.info(f"Generate URL: {self.generate_url}")

    def _make_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _retry_request(self, func, *args, **kwargs):
        """
        Execute request with retry logic.

        Args:
            func: Function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            Exception: If all retries fail.
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return self.circuit_breaker.call(func, *args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
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
        Generate embeddings using LM Studio API.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of embeddings.

        Raises:
            Exception: If API request fails or response is invalid.
        """
        if not texts:
            return np.array([])

        def _embed_impl():
            """Inner implementation for retry wrapper."""
            payload = {"input": texts, "model": self.model}
            response = requests.post(
                self.embed_url,
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
            logger.error(f"LM Studio embedding request failed: {e}")
            raise Exception(
                f"Failed to connect to LM Studio at {self.embed_url}. "
                f"Ensure LM Studio is running and the embedding endpoint "
                f"is available. Error: {e}"
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse LM Studio embedding response: {e}")
            raise Exception(f"Invalid response from LM Studio API: {e}")

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
                "prompt": prompt,
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }

            if stop:
                payload["stop"] = stop

            response = requests.post(
                self.generate_url,
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

            text = choices[0].get("text", "")
            finish_reason = choices[0].get("finish_reason", "unknown")

            # Extract usage statistics
            usage = data.get("usage", {})

            return {
                "text": text,
                "model": self.model,
                "usage": usage,
                "finish_reason": finish_reason,
            }

        try:
            return self._retry_request(_generate_impl)
        except requests.exceptions.RequestException as e:
            logger.error(f"LM Studio generation request failed: {e}")
            raise Exception(
                f"Failed to generate completion from LM Studio at {self.generate_url}. "
                f"Ensure LM Studio is running and the completions endpoint "
                f"is available. Error: {e}"
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse LM Studio generation response: {e}")
            raise Exception(f"Invalid response from LM Studio API: {e}")

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
            "prompt": prompt,
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if stop:
            payload["stop"] = stop

        try:
            # Use asyncio to run blocking requests in executor
            loop = asyncio.get_event_loop()

            def _make_request():
                return requests.post(
                    self.generate_url,
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
                            delta = choice.get("text", "")
                            finish_reason = choice.get("finish_reason")

                            chunk = {"delta": delta}
                            if finish_reason:
                                chunk["finish_reason"] = finish_reason

                            yield chunk

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE chunk: {e}")
                        continue

        except requests.exceptions.RequestException as e:
            logger.error(f"LM Studio streaming request failed: {e}")
            raise Exception(
                f"Failed to stream completion from LM Studio at {self.generate_url}. "
                f"Error: {e}"
            )

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
                self.embed_url,
                json={"input": ["test"], "model": self.model},
                headers=self._make_headers(),
                timeout=5,  # Short timeout for health check
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "message": "LM Studio is responding normally",
                    "models": [self.model],
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "message": f"LM Studio returned status {response.status_code}",
                    "models": [self.model],
                }

        except requests.exceptions.Timeout:
            return {
                "status": "degraded",
                "latency_ms": 5000,
                "message": "LM Studio health check timed out",
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": f"Cannot connect to LM Studio: {e}",
            }

    def metadata(self) -> Dict[str, Any]:
        """
        Get provider metadata and capabilities.

        Returns:
            Dict containing provider information and capabilities.
        """
        return {
            "provider_id": "lmstudio",
            "name": "LM Studio",
            "supports_embeddings": True,
            "supports_generation": True,
            "supports_streaming": True,
            "embedding_dimension": self._dimension or 0,
            "embedding_model": self.model,
            "generation_model": self.model,
            "max_tokens": 4096,  # LM Studio typical limit
            "embed_url": self.embed_url,
            "generate_url": self.generate_url,
        }
