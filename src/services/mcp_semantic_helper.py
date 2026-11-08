"""Offline-only embedding helper with no provider settings or world access."""

import base64
import contextlib
import json
import sys


def main() -> None:
    """Use cached model files only; stdout contains only the helper protocol."""
    try:
        model = None
        model_name = ""
        while raw := sys.stdin.buffer.readline(70 * 1024 * 1024):
            payload = json.loads(raw)
            with contextlib.redirect_stdout(sys.stderr):
                import numpy as np
                from sentence_transformers import SentenceTransformer

                if model is None or model_name != payload["model"]:
                    model = SentenceTransformer(
                        payload["model"],
                        device="cpu",
                        local_files_only=True,
                        trust_remote_code=False,
                    )
                    model_name = payload["model"]
                vectors = model.encode(
                    payload["texts"],
                    batch_size=32,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                vectors = np.asarray(vectors, dtype="float32")
            result = {
                "vectors": base64.b64encode(vectors.tobytes()).decode("ascii"),
                "shape": list(vectors.shape),
            }
            sys.stdout.buffer.write(json.dumps(result).encode() + b"\n")
            sys.stdout.buffer.flush()
            if not payload.get("keep_alive"):
                break
    except Exception:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
