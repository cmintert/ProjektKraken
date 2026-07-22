"""LM Studio endpoint normalization and model discovery."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import requests

DEFAULT_LMSTUDIO_BASE_URL = "http://localhost:1234"


@dataclass(frozen=True)
class LMStudioEndpoints:
    """OpenAI-compatible endpoints derived from a single server address."""

    base_url: str
    models_url: str
    chat_completions_url: str
    embeddings_url: str


def normalize_lmstudio_base_url(value: str) -> str:
    """Normalize a base URL and migrate previously stored endpoint URLs."""
    raw = (value or DEFAULT_LMSTUDIO_BASE_URL).strip().rstrip("/")
    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlsplit(raw)
    if not parsed.hostname:
        raise ValueError("LM Studio address must include a host")

    path = parsed.path.rstrip("/")
    for suffix in (
        "/v1/chat/completions",
        "/v1/completions",
        "/v1/embeddings",
        "/v1/models",
        "/v1",
    ):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def derive_lmstudio_endpoints(value: str) -> LMStudioEndpoints:
    """Derive all API endpoints from one canonical base URL."""
    base_url = normalize_lmstudio_base_url(value)
    return LMStudioEndpoints(
        base_url=base_url,
        models_url=f"{base_url}/v1/models",
        chat_completions_url=f"{base_url}/v1/chat/completions",
        embeddings_url=f"{base_url}/v1/embeddings",
    )


def discover_lmstudio_models(
    base_url: str,
    api_key: str = "",
    timeout: float = 5.0,
) -> list[str]:
    """Return stable model identifiers reported by ``GET /v1/models``."""
    endpoint = derive_lmstudio_endpoints(base_url).models_url
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(endpoint, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("data", [])
    identifiers = {
        str(item["id"])
        for item in models
        if isinstance(item, dict) and item.get("id")
    }
    return sorted(identifiers, key=str.casefold)
