"""Session-local public-fact embeddings, never the application's broader AI index."""

import base64
import threading
from collections.abc import Callable
from typing import Any

from src.core.mcp_access import McpFailure
from src.services.mcp_embedding_process import EmbeddingProcess


class McpSemanticIndex:
    """Guard ephemeral vectors and documents by generation and public revision."""

    def __init__(self) -> None:
        """Start empty without loading any model or native dependency."""
        self._lock = threading.RLock()
        self._epoch = 0
        self._embedding: EmbeddingProcess | None = None
        self.clear()

    def clear(self) -> None:
        """Discard all cached content when sharing or preparation ends."""
        with self._lock:
            self._epoch += 1
            if self._embedding is not None:
                self._embedding.close()
                self._embedding = None
            self.generation = ""
            self.revision = ""
            self.model = ""
            self.documents: list[dict[str, Any]] = []
            self.vectors: Any = None

    def ready(self, generation: str, revision: str) -> bool:
        """A changed public revision requires explicit preparation again."""
        with self._lock:
            return (
                self.vectors is not None
                and self._embedding is not None
                and self._embedding.available
                and self.generation == generation
                and self.revision == revision
            )

    def invalidate_failed_helper(self, generation: str, revision: str) -> bool:
        """Clear a dead helper only if it still belongs to this investigation."""
        with self._lock:
            if (
                self.generation != generation
                or self.revision != revision
                or self._embedding is None
                or self._embedding.available
            ):
                return False
            self.clear()
            return True

    def prepare(
        self,
        generation: str,
        revision: str,
        model: str,
        documents: list[dict[str, Any]],
        expired: Callable[[], bool],
    ) -> None:
        """Embed only the copied public projection, without persistent index writes."""
        import numpy as np

        with self._lock:
            self.clear()
            epoch = self._epoch
            embedding = self._embedding = EmbeddingProcess()
        try:
            result = embedding.encode(
                {"model": model, "texts": [doc["text"] for doc in documents]},
                expired,
                300,
            )
            vectors = np.frombuffer(
                base64.b64decode(result["vectors"], validate=True), dtype="float32"
            ).reshape(result["shape"])
            if len(vectors) != len(documents) or not np.isfinite(vectors).all():
                raise McpFailure("MODEL_UNAVAILABLE")
        except Exception:
            embedding.close()
            raise
        if expired():
            embedding.close()
            raise McpFailure("UNAVAILABLE")
        with self._lock:
            if self._epoch != epoch or expired():
                embedding.close()
                raise McpFailure("UNAVAILABLE")
            self.generation, self.revision, self.model = generation, revision, model
            self.documents, self.vectors = documents, vectors

    def query(
        self, request: dict[str, Any], revision: str, expired: Callable[[], bool]
    ) -> list[dict[str, Any]]:
        """Score current public documents; similarities never establish truth."""
        import numpy as np

        from src.services.mcp_search import excerpt
        from src.services.search_service import top_k_streaming

        with self._lock:
            if not self.ready(request["generation"], revision):
                raise McpFailure("INDEX_STALE")
            docs, matrix, model = self.documents, self.vectors, self.model
            embedding = self._embedding
        if not docs:
            return []
        args = request["arguments"]
        if embedding is None:
            raise McpFailure("MODEL_UNAVAILABLE")
        try:
            result = embedding.encode(
                {"model": model, "texts": [args["query"]]}, expired, 9
            )
            vector = np.frombuffer(
                base64.b64decode(result["vectors"], validate=True), dtype="float32"
            )
            if vector.size != matrix.shape[1] or not np.isfinite(vector).all():
                raise McpFailure("MODEL_UNAVAILABLE")
        except Exception:
            embedding.close()
            raise
        scores = matrix @ vector
        requested_tags = {tag.strip().casefold() for tag in args.get("tags") or []}
        candidates = (
            (float(scores[index]), doc)
            for index, doc in enumerate(docs)
            if (not args.get("kinds") or doc["kind"] in args["kinds"])
            and (not args.get("types") or doc["type"] in args["types"])
            and requested_tags.issubset(doc["tags"])
        )
        return [
            {
                "kind": doc["kind"],
                "id": doc["id"],
                "name": doc["name"],
                "score": score,
                **excerpt(doc["description"], args["query"]),
            }
            for score, doc in top_k_streaming(candidates, args.get("limit", 10))
        ]
