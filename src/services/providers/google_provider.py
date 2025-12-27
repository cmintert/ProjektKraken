"""
Google Vertex AI Provider Implementation.

Provides embeddings and text generation via Google Vertex AI API.
Supports health checks, timeouts, retries, and circuit breaker pattern.
Note: Streaming not fully supported by all Vertex AI models yet.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import numpy as np
import requests

from src.services.llm_provider import Provider
from src.services.resilience import CircuitBreaker

logger = logging.getLogger(__name__)


class GoogleProvider(Provider):
    """
    Google Vertex AI provider supporting embeddings and text generation.

    Implements Vertex AI API with retries and circuit breaker.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        credentials_path: Optional[str] = None,
        model: str = "text-bison@001",
        embed_model: str = "textembedding-gecko@001",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize Google Vertex AI provider.

        Args:
            project_id: GCP project ID.
            location: GCP region (default us-central1).
            credentials_path: Path to service account JSON (uses ADC if None).
            model: Model name for text generation.
            embed_model: Model name for embeddings.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for failed requests.

        Raises:
            ValueError: If project_id is not provided.
            ImportError: If google-cloud-aiplatform is not installed.
        """
        try:
            from google.auth import default
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is not installed. "
                "Install it with: pip install google-cloud-aiplatform"
            )

        self.project_id = project_id
        if not self.project_id:
            raise ValueError(
                "Google Cloud project ID is required. "
                "Set GOOGLE_PROJECT_ID env variable or configure in settings."
            )

        self.location = location
        self.model = model
        self.embed_model = embed_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._dimension = None
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)

        # Initialize credentials
        if credentials_path and os.path.exists(credentials_path):
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            logger.info(f"Using service account credentials from {credentials_path}")
        else:
            # Use Application Default Credentials
            self.credentials, _ = default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            logger.info("Using Application Default Credentials")

        # Build API endpoints
        self.api_endpoint = f"https://{location}-aiplatform.googleapis.com"
        self.embed_url = (
            f"{self.api_endpoint}/v1/projects/{project_id}/"
            f"locations/{location}/publishers/google/models/{embed_model}:predict"
        )
        self.generate_url = (
            f"{self.api_endpoint}/v1/projects/{project_id}/"
            f"locations/{location}/publishers/google/models/{model}:predict"
        )

        logger.info(f"GoogleProvider initialized with model: {self.model}")
        logger.info(f"Embedding model: {self.embed_model}")
        logger.info(f"Project: {self.project_id}, Location: {self.location}")

    def _get_access_token(self) -> str:
        """
        Get fresh access token for API requests.

        Returns:
            str: OAuth2 access token.
        """
        from google.auth.transport.requests import Request

        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return self.credentials.token

    def _make_headers(self) -> Dict[str, str]:
        """Build request headers with fresh access token."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._get_access_token()}",
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
        Generate embeddings using Vertex AI API.

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
            # Vertex AI expects instances with "content" field
            payload = {"instances": [{"content": text} for text in texts]}

            response = requests.post(
                self.embed_url,
                json=payload,
                headers=self._make_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            predictions = data.get("predictions", [])

            if not predictions:
                raise ValueError("No embeddings returned from API")

            # Extract embeddings from predictions
            embeddings = []
            for pred in predictions:
                if isinstance(pred, dict):
                    # Vertex AI returns embeddings in "embeddings" field
                    emb = pred.get("embeddings", {}).get("values", [])
                    embeddings.append(emb)
                elif isinstance(pred, list):
                    embeddings.append(pred)

            if not embeddings:
                raise ValueError("No valid embeddings in response")

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
            logger.error(f"Vertex AI embedding request failed: {e}")
            raise Exception(f"Failed to connect to Vertex AI API. Error: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse Vertex AI embedding response: {e}")
            raise Exception(f"Invalid response from Vertex AI API: {e}")

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
            # Vertex AI text generation format
            payload = {
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }

            if stop:
                payload["parameters"]["stopSequences"] = stop

            response = requests.post(
                self.generate_url,
                json=payload,
                headers=self._make_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()

            # Extract completion text from predictions
            predictions = data.get("predictions", [])
            if not predictions:
                raise ValueError("No predictions returned from API")

            prediction = predictions[0]

            # Extract text based on response structure
            if isinstance(prediction, dict):
                text = prediction.get("content", "")
            elif isinstance(prediction, str):
                text = prediction
            else:
                text = str(prediction)

            # Vertex AI doesn't always provide detailed usage stats
            # Note: This is a rough estimate. For accurate token counts, consider
            # using a tokenizer library like tiktoken or the model's specific tokenizer.
            usage = {
                "prompt_tokens": len(prompt.split()),  # Rough estimate
                "completion_tokens": len(text.split()),  # Rough estimate
                "total_tokens": len(prompt.split()) + len(text.split()),
            }

            return {
                "text": text,
                "model": self.model,
                "usage": usage,
                "finish_reason": "stop",  # Vertex AI doesn't always provide this
            }

        try:
            return self._retry_request(_generate_impl)
        except requests.exceptions.RequestException as e:
            logger.error(f"Vertex AI generation request failed: {e}")
            raise Exception(
                f"Failed to generate completion from Vertex AI API. Error: {e}"
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse Vertex AI generation response: {e}")
            raise Exception(f"Invalid response from Vertex AI API: {e}")

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

        Note: Vertex AI streaming support is limited. This implementation
        falls back to non-streaming and yields the complete result.

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
        logger.warning("Vertex AI streaming not fully supported, using fallback")

        # Fall back to non-streaming and yield complete result
        try:
            result = self.generate(prompt, max_tokens, temperature, stop, metadata)
            yield {"delta": result["text"], "finish_reason": result["finish_reason"]}
        except Exception as e:
            logger.error(f"Vertex AI streaming fallback failed: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and availability.

        Returns:
            Dict containing status, latency_ms, and message.
        """
        try:
            start_time = time.time()

            # Test embeddings endpoint with minimal request
            payload = {"instances": [{"content": "test"}]}
            response = requests.post(
                self.embed_url,
                json=payload,
                headers=self._make_headers(),
                timeout=5,  # Short timeout for health check
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "message": "Vertex AI API is responding normally",
                    "models": [self.model, self.embed_model],
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": latency_ms,
                    "message": f"Vertex AI API returned status {response.status_code}",
                    "models": [self.model, self.embed_model],
                }

        except requests.exceptions.Timeout:
            return {
                "status": "degraded",
                "latency_ms": 5000,
                "message": "Vertex AI API health check timed out",
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": f"Cannot connect to Vertex AI API: {e}",
            }

    def metadata(self) -> Dict[str, Any]:
        """
        Get provider metadata and capabilities.

        Returns:
            Dict containing provider information and capabilities.
        """
        return {
            "provider_id": "google",
            "name": "Google Vertex AI",
            "supports_embeddings": True,
            "supports_generation": True,
            "supports_streaming": False,  # Limited support
            "embedding_dimension": self._dimension or 768,  # Gecko default
            "embedding_model": self.embed_model,
            "generation_model": self.model,
            "max_tokens": 1024,  # PaLM/Bison typical limit
            "project_id": self.project_id,
            "location": self.location,
        }
