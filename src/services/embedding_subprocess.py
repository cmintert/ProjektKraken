"""Subprocess embedding entrypoint for sentence-transformers.

This module is executed in a dedicated Python process so any native crash in
torch/tokenizers cannot terminate the main Qt application process.
"""

import json
import os
import sys
from typing import Any

import numpy as np


def _error_payload(message: str) -> dict[str, Any]:
    """Build a stable error payload."""
    return {"error": message}


def main() -> int:
    """Read embedding request from stdin and write JSON result to stdout."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print(json.dumps(_error_payload("empty stdin payload")))
            return 2

        payload = json.loads(raw)
        model = str(payload.get("model") or "all-MiniLM-L6-v2")
        texts = payload.get("texts") or []
        if not isinstance(texts, list):
            print(json.dumps(_error_payload("payload.texts must be a list")))
            return 2

        # Threading constraints are set before importing sentence_transformers.
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("OMP_NUM_THREADS", "1")

        from sentence_transformers import SentenceTransformer  # type: ignore

        st_model = SentenceTransformer(model, device="cpu")
        vectors = st_model.encode(texts, show_progress_bar=False)
        embeddings = np.array(vectors, dtype=np.float32)

        print(json.dumps({"embeddings": embeddings.tolist()}, ensure_ascii=False))
        return 0

    except Exception as exc:
        print(json.dumps(_error_payload(str(exc)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
