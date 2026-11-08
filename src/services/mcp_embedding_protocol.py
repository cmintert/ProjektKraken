"""Shared byte bounds for offline embedding helper frames."""

import json
from typing import Any, BinaryIO

MAX_DOCUMENTS = 50000
MAX_TEXT_BYTES = 64 * 1024 * 1024
# Each input text is already JSON. Encoding the texts array can double its bytes;
# allow quotes/separators per document plus bounded model/protocol overhead.
MAX_INPUT_BYTES = 2 * MAX_TEXT_BYTES + 4 * MAX_DOCUMENTS + 1024 * 1024


def encode_payload(payload: dict[str, Any]) -> bytes:
    """Frame one request, rejecting oversize input before writing to the helper."""
    data = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("Embedding frame exceeds its byte budget")
    return data


def read_payload(stream: BinaryIO) -> dict[str, Any] | None:
    """Read a whole bounded frame; never parse a truncated prefix as a request."""
    raw = stream.readline(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Embedding frame exceeds its byte budget")
    return json.loads(raw) if raw else None
