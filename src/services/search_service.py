"""
Search Service Module.

Provides semantic search functionality with local embeddings and vector similarity.
Supports LM Studio and optional sentence-transformers as embedding providers.
"""

import hashlib
import heapq
import json
import logging
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Text Building Functions (Deterministic)
# =============================================================================


def _stable_dump(val: Any) -> str:
    """
    Convert a value to a stable string representation.

    For dicts and lists, uses JSON serialization with sorted keys for
    deterministic output.

    Args:
        val: The value to convert to a string.

    Returns:
        str: A stable string representation of the value.
    """
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False, sort_keys=True)
    if isinstance(val, list):
        # Ensure nested dicts inside lists are dumped deterministically
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def build_text_for_entity(
    entity, tags: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """
    Build a deterministic text representation of an entity for embedding.

    Includes name, type, description, tags, and all JSON attributes
    in a stable, sorted order.

    Args:
        entity: Entity object with name, type, description, attributes.
        tags: Optional list of tag names or tag dicts with "name" key.

    Returns:
        str: A multi-line text representation of the entity.
    """
    parts = [
        f"Name: {entity.name}",
        f"Type: {entity.type}",
    ]

    if tags:
        tag_names = [t["name"] if isinstance(t, dict) else str(t) for t in tags]
        parts.append("Tags: " + ", ".join(sorted(tag_names)))

    if getattr(entity, "description", None):
        parts.append("Description: " + entity.description)

    attrs = getattr(entity, "attributes", {}) or {}
    # Filter out internal tags attribute if present
    attrs = {k: v for k, v in attrs.items() if k != "_tags"}

    for key in sorted(attrs.keys()):
        parts.append(f"{key}: {_stable_dump(attrs[key])}")

    return "\n\n".join(parts)


def build_text_for_event(
    event, tags: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """
    Build a deterministic text representation of an event for embedding.

    Includes name, type, date, duration, description, tags, and all JSON
    attributes in a stable, sorted order.

    Args:
        event: Event object with name, type, lore_date, lore_duration, etc.
        tags: Optional list of tag names or tag dicts with "name" key.

    Returns:
        str: A multi-line text representation of the event.
    """
    parts = [
        f"Name: {event.name}",
        f"Type: {event.type}",
        f"Date: {getattr(event, 'lore_date', '')}",
        f"Duration: {getattr(event, 'lore_duration', '')}",
    ]

    if tags:
        tag_names = [t["name"] if isinstance(t, dict) else str(t) for t in tags]
        parts.append("Tags: " + ", ".join(sorted(tag_names)))

    if getattr(event, "description", None):
        parts.append("Description: " + event.description)

    attrs = getattr(event, "attributes", {}) or {}
    # Filter out internal tags attribute if present
    attrs = {k: v for k, v in attrs.items() if k != "_tags"}

    for key in sorted(attrs.keys()):
        parts.append(f"{key}: {_stable_dump(attrs[key])}")

    return "\n\n".join(parts)


def text_sha256(text: str) -> str:
    """
    Compute SHA-256 hash of text for change detection.

    Args:
        text: The text to hash.

    Returns:
        str: Hexadecimal hash digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =============================================================================
# Vector Operations
# =============================================================================


def normalize_vector(v: np.ndarray) -> np.ndarray:
    """
    Normalize a vector to unit length.

    Args:
        v: Input vector as numpy array.

    Returns:
        np.ndarray: Unit-normalized vector as float32.
    """
    v = v.astype(np.float32)
    norm = np.linalg.norm(v)
    if norm < 1e-12:
        return v  # avoid division by zero; treat as near-zero vector
    return v / norm


def serialize_vector(v: np.ndarray) -> bytes:
    """
    Serialize a vector to bytes for storage in SQLite BLOB.

    Args:
        v: Vector as numpy array.

    Returns:
        bytes: Serialized float32 vector.
    """
    v32 = v.astype(np.float32)
    return v32.tobytes()


def deserialize_vector(blob: bytes, dim: int) -> np.ndarray:
    """
    Deserialize a vector from SQLite BLOB bytes.

    Args:
        blob: Bytes from database BLOB.
        dim: Expected vector dimension.

    Returns:
        np.ndarray: Float32 vector.
    """
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def dot_scores(q_vec: np.ndarray, V: np.ndarray) -> np.ndarray:
    """
    Compute dot product similarity scores between query and matrix of vectors.

    Assumes both query and matrix rows are already normalized.

    Args:
        q_vec: Query vector (1D array).
        V: Matrix of vectors (2D array, each row is a vector).

    Returns:
        np.ndarray: Array of similarity scores.
    """
    return V.dot(q_vec)


def top_k_streaming(scores_iter, k: int) -> List[Tuple[float, Any]]:
    """
    Select top-k items from an iterator using a min-heap (streaming approach).

    Args:
        scores_iter: Iterator yielding (score, item) tuples.
        k: Number of top items to return.

    Returns:
        List of (score, item) tuples sorted by descending score.
    """
    heap = []
    counter = 0  # Add counter to ensure unique comparison for ties
    for score, item in scores_iter:
        # Use (score, counter, item) to avoid comparing items when scores are equal
        if len(heap) < k:
            heapq.heappush(heap, (score, counter, item))
        else:
            if score > heap[0][0]:
                heapq.heapreplace(heap, (score, counter, item))
        counter += 1
    # Return sorted by descending score, extracting (score, item) tuples
    sorted_heap = sorted(heap, key=lambda x: x[0], reverse=True)
    return [(score, item) for score, _, item in sorted_heap]


# =============================================================================
# Embedding Provider Interface
# =============================================================================


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All providers must implement embed() and get_dimension() methods.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of shape (len(texts), dimension).
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the dimensionality of the embeddings.

        Returns:
            int: Embedding dimension.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the model name/identifier.

        Returns:
            str: Model name.
        """
        pass


class LMStudioEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider for LM Studio local embedding API.

    Supports OpenAI-compatible embedding endpoints.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize LM Studio embedding provider.

        Args:
            url: API endpoint URL (default from env or http://localhost:8080/v1/embeddings).
            model: Model name (default from env or required).
            api_key: Optional API key.
            timeout: Request timeout in seconds.
        """
        import requests

        self.requests = requests
        self.url = url or os.getenv(
            "LMSTUDIO_EMBED_URL", "http://localhost:8080/v1/embeddings"
        )
        self.model = model or os.getenv("LMSTUDIO_MODEL")
        if not self.model:
            raise ValueError(
                "Model name is required. Set LMSTUDIO_MODEL env variable "
                "or pass model parameter."
            )

        self.api_key = api_key or os.getenv("LMSTUDIO_API_KEY")
        self.timeout = timeout
        self._dimension = None

        # Configurable request/response shape
        self.input_key = os.getenv("LMSTUDIO_INPUT_KEY", "input")
        self.model_key = os.getenv("LMSTUDIO_MODEL_KEY", "model")
        self.embed_path = os.getenv("LMSTUDIO_EMBED_PATH", "data[].embedding")

        logger.info(f"LMStudioEmbeddingProvider initialized with URL: {self.url}")
        logger.info(f"Model: {self.model}")

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

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {self.input_key: texts, self.model_key: self.model}

        try:
            response = self.requests.post(
                self.url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()

            # Parse embeddings from response using configured path
            if self.embed_path == "data[].embedding":
                embeddings = [item["embedding"] for item in data.get("data", [])]
            else:
                # Support custom paths if needed in the future
                embeddings = [item["embedding"] for item in data.get("data", [])]

            if not embeddings:
                raise ValueError("No embeddings returned from API")

            # Convert to numpy array
            emb_array = np.array(embeddings, dtype=np.float32)

            # Cache dimension
            if self._dimension is None:
                self._dimension = emb_array.shape[1]

            logger.debug(
                f"Generated {len(embeddings)} embeddings "
                f"with dimension {self._dimension}"
            )
            return emb_array

        except self.requests.exceptions.RequestException as e:
            logger.error(f"LM Studio API request failed: {e}")
            raise Exception(
                f"Failed to connect to LM Studio at {self.url}. "
                f"Ensure LM Studio is running and the embedding endpoint "
                f"is available. Error: {e}"
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse LM Studio response: {e}")
            raise Exception(f"Invalid response from LM Studio API: {e}")

    def get_dimension(self) -> int:
        """
        Get the dimensionality of embeddings.

        Returns:
            int: Embedding dimension.
        """
        if self._dimension is None:
            # Make a test call to determine dimension
            test_emb = self.embed(["test"])
            self._dimension = test_emb.shape[1]
        return self._dimension

    def get_model_name(self) -> str:
        """
        Get the model name.

        Returns:
            str: Model identifier with 'lmstudio:' prefix.
        """
        return f"lmstudio:{self.model}"


class SentenceTransformersProvider(EmbeddingProvider):
    """
    Fallback embedding provider using sentence-transformers library.

    Requires sentence-transformers to be installed.
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize sentence-transformers provider.

        Args:
            model: Model name (default from env or 'all-MiniLM-L6-v2').
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            )

        self.model_name = model or os.getenv(
            "LMSTUDIO_MODEL", "all-MiniLM-L6-v2"
        )  # Reuse env var
        self.model = SentenceTransformer(self.model_name)
        self._dimension = self.model.get_sentence_embedding_dimension()

        logger.info(
            f"SentenceTransformersProvider initialized with model: {self.model_name}"
        )

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings using sentence-transformers.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of embeddings.
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(texts, show_progress_bar=False)
        return np.array(embeddings, dtype=np.float32)

    def get_dimension(self) -> int:
        """
        Get embedding dimension.

        Returns:
            int: Embedding dimension.
        """
        return self._dimension

    def get_model_name(self) -> str:
        """
        Get model name.

        Returns:
            str: Model identifier with 'st:' prefix.
        """
        return f"st:{self.model_name}"


# =============================================================================
# Search Service
# =============================================================================


class SearchService:
    """
    Service for managing semantic search indexes and queries.

    Handles text extraction, embedding generation, and similarity search
    for entities and events.
    """

    def __init__(self, db_connection: sqlite3.Connection, provider: EmbeddingProvider):
        """
        Initialize search service.

        Args:
            db_connection: SQLite database connection.
            provider: Embedding provider instance.
        """
        self.conn = db_connection
        self.provider = provider
        self.model = provider.get_model_name()
        self.dimension = provider.get_dimension()

        logger.info(f"SearchService initialized with model: {self.model}")
        logger.info(f"Embedding dimension: {self.dimension}")

    def _get_tags_for_object(
        self, object_type: str, object_id: str
    ) -> List[Dict[str, str]]:
        """
        Get tags for an entity or event.

        Args:
            object_type: 'entity' or 'event'.
            object_id: Object UUID.

        Returns:
            List of tag dicts with 'name' key.
        """
        if object_type == "entity":
            table = "entity_tags"
            id_col = "entity_id"
        elif object_type == "event":
            table = "event_tags"
            id_col = "event_id"
        else:
            return []

        sql = f"""
            SELECT t.name FROM tags t
            JOIN {table} tt ON t.id = tt.tag_id
            WHERE tt.{id_col} = ?
        """
        cursor = self.conn.execute(sql, (object_id,))
        return [{"name": row[0]} for row in cursor.fetchall()]

    def index_entity(self, entity_id: str) -> None:
        """
        Index a single entity.

        Args:
            entity_id: Entity UUID.

        Raises:
            ValueError: If entity not found.
        """
        # Fetch entity
        cursor = self.conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Entity {entity_id} not found")

        # Convert row to dict
        entity_data = dict(row)
        if entity_data.get("attributes"):
            entity_data["attributes"] = json.loads(entity_data["attributes"])

        # Create minimal entity object
        from src.core.entities import Entity

        entity = Entity.from_dict(entity_data)

        # Get tags
        tags = self._get_tags_for_object("entity", entity_id)

        # Build text
        text = build_text_for_entity(entity, tags)
        text_hash_val = text_sha256(text)

        # Check if already indexed with same text
        existing = self.conn.execute(
            """
            SELECT text_hash FROM embeddings
            WHERE object_type = ? AND object_id = ? AND model = ?
            """,
            ("entity", entity_id, self.model),
        ).fetchone()

        if existing and existing[0] == text_hash_val:
            logger.debug(f"Entity {entity_id} already indexed with same text, skipping")
            return

        # Generate embedding
        embedding = self.provider.embed([text])[0]
        normalized = normalize_vector(embedding)
        serialized = serialize_vector(normalized)

        # Upsert into database
        embedding_id = str(uuid.uuid4())
        metadata = {"name": entity.name, "type": entity.type}

        self.conn.execute(
            """
            INSERT INTO embeddings (
                id, object_type, object_id, model, vector, vector_dim,
                text_snippet, text_hash, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_type, object_id, model) DO UPDATE SET
                vector = excluded.vector,
                vector_dim = excluded.vector_dim,
                text_snippet = excluded.text_snippet,
                text_hash = excluded.text_hash,
                metadata = excluded.metadata,
                created_at = excluded.created_at
            """,
            (
                embedding_id,
                "entity",
                entity_id,
                self.model,
                serialized,
                self.dimension,
                text,
                text_hash_val,
                json.dumps(metadata),
                time.time(),
            ),
        )
        self.conn.commit()

        logger.info(f"Indexed entity {entity_id} ({entity.name})")

    def index_event(self, event_id: str) -> None:
        """
        Index a single event.

        Args:
            event_id: Event UUID.

        Raises:
            ValueError: If event not found.
        """
        # Fetch event
        cursor = self.conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Event {event_id} not found")

        # Convert row to dict
        event_data = dict(row)
        if event_data.get("attributes"):
            event_data["attributes"] = json.loads(event_data["attributes"])

        # Create minimal event object
        from src.core.events import Event

        event = Event.from_dict(event_data)

        # Get tags
        tags = self._get_tags_for_object("event", event_id)

        # Build text
        text = build_text_for_event(event, tags)
        text_hash_val = text_sha256(text)

        # Check if already indexed with same text
        existing = self.conn.execute(
            """
            SELECT text_hash FROM embeddings
            WHERE object_type = ? AND object_id = ? AND model = ?
            """,
            ("event", event_id, self.model),
        ).fetchone()

        if existing and existing[0] == text_hash_val:
            logger.debug(f"Event {event_id} already indexed with same text, skipping")
            return

        # Generate embedding
        embedding = self.provider.embed([text])[0]
        normalized = normalize_vector(embedding)
        serialized = serialize_vector(normalized)

        # Upsert into database
        embedding_id = str(uuid.uuid4())
        metadata = {"name": event.name, "type": event.type}

        self.conn.execute(
            """
            INSERT INTO embeddings (
                id, object_type, object_id, model, vector, vector_dim,
                text_snippet, text_hash, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(object_type, object_id, model) DO UPDATE SET
                vector = excluded.vector,
                vector_dim = excluded.vector_dim,
                text_snippet = excluded.text_snippet,
                text_hash = excluded.text_hash,
                metadata = excluded.metadata,
                created_at = excluded.created_at
            """,
            (
                embedding_id,
                "event",
                event_id,
                self.model,
                serialized,
                self.dimension,
                text,
                text_hash_val,
                json.dumps(metadata),
                time.time(),
            ),
        )
        self.conn.commit()

        logger.info(f"Indexed event {event_id} ({event.name})")

    def rebuild_index(
        self, object_types: Optional[List[str]] = None, model: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Rebuild embeddings index for specified object types.

        Args:
            object_types: List of object types to index ('entity', 'event').
                         If None, indexes all types.
            model: Optional model filter (not currently used, for future compatibility).

        Returns:
            Dict with counts of indexed objects per type.
        """
        if object_types is None:
            object_types = ["entity", "event"]

        counts = {}

        for obj_type in object_types:
            if obj_type == "entity":
                cursor = self.conn.execute("SELECT id FROM entities")
                ids = [row[0] for row in cursor.fetchall()]
                for entity_id in ids:
                    try:
                        self.index_entity(entity_id)
                    except Exception as e:
                        logger.error(f"Failed to index entity {entity_id}: {e}")
                counts["entity"] = len(ids)

            elif obj_type == "event":
                cursor = self.conn.execute("SELECT id FROM events")
                ids = [row[0] for row in cursor.fetchall()]
                for event_id in ids:
                    try:
                        self.index_event(event_id)
                    except Exception as e:
                        logger.error(f"Failed to index event {event_id}: {e}")
                counts["event"] = len(ids)

        logger.info(f"Rebuild complete. Indexed: {counts}")
        return counts

    def query(
        self,
        text: str,
        object_type: Optional[str] = None,
        top_k: int = 10,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the index using semantic search.

        Args:
            text: Query text.
            object_type: Optional filter for 'entity' or 'event'.
            top_k: Number of results to return.
            model: Optional model filter (defaults to current provider's model).

        Returns:
            List of result dicts with keys: id, object_type, object_id, score,
            name, type, metadata.
        """
        # Use current model if not specified
        query_model = model or self.model

        # Generate query embedding
        query_embedding = self.provider.embed([text])[0]
        query_normalized = normalize_vector(query_embedding)

        # Build SQL filter
        sql = """
            SELECT id, object_type, object_id, vector, vector_dim, metadata
            FROM embeddings
            WHERE model = ? AND vector_dim = ?
        """
        params = [query_model, self.dimension]

        if object_type:
            sql += " AND object_type = ?"
            params.append(object_type)

        # Fetch all matching embeddings
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        if not rows:
            logger.info("No embeddings found matching query criteria")
            return []

        # Compute similarities and collect results
        def score_generator():
            for row in rows:
                row_dict = dict(row)
                vector_blob = row_dict["vector"]
                vector_dim = row_dict["vector_dim"]

                # Deserialize vector
                vec = deserialize_vector(vector_blob, vector_dim)

                # Compute dot product (vectors are normalized)
                score = float(np.dot(query_normalized, vec))

                yield score, row_dict

        # Get top-k using streaming heap
        top_results = top_k_streaming(score_generator(), top_k)

        # Format results
        results = []
        for score, row_dict in top_results:
            metadata = json.loads(row_dict.get("metadata", "{}"))
            results.append(
                {
                    "id": row_dict["id"],
                    "object_type": row_dict["object_type"],
                    "object_id": row_dict["object_id"],
                    "score": score,
                    "name": metadata.get("name", ""),
                    "type": metadata.get("type", ""),
                    "metadata": metadata,
                }
            )

        logger.info(
            f"Query returned {len(results)} results (requested top {top_k})"
        )
        return results

    def delete_index_for_object(
        self, object_type: str, object_id: str, model: Optional[str] = None
    ) -> None:
        """
        Delete embeddings for a specific object.

        Args:
            object_type: 'entity' or 'event'.
            object_id: Object UUID.
            model: Optional model filter (deletes for all models if None).
        """
        if model:
            self.conn.execute(
                """
                DELETE FROM embeddings
                WHERE object_type = ? AND object_id = ? AND model = ?
                """,
                (object_type, object_id, model),
            )
        else:
            self.conn.execute(
                """
                DELETE FROM embeddings
                WHERE object_type = ? AND object_id = ?
                """,
                (object_type, object_id),
            )
        self.conn.commit()

        logger.info(f"Deleted embeddings for {object_type} {object_id}")


# =============================================================================
# Factory Functions
# =============================================================================


def create_provider(
    provider_name: Optional[str] = None, model: Optional[str] = None
) -> EmbeddingProvider:
    """
    Create an embedding provider based on configuration.

    Args:
        provider_name: 'lmstudio' or 'sentence-transformers'.
                       If None, uses EMBED_PROVIDER env var (default 'lmstudio').
        model: Model name override.

    Returns:
        EmbeddingProvider: Configured provider instance.

    Raises:
        ValueError: If provider is unknown or configuration is invalid.
    """
    provider_name = provider_name or os.getenv("EMBED_PROVIDER", "lmstudio")

    if provider_name == "lmstudio":
        return LMStudioEmbeddingProvider(model=model)
    elif provider_name == "sentence-transformers":
        return SentenceTransformersProvider(model=model)
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider_name}. "
            f"Supported: 'lmstudio', 'sentence-transformers'"
        )


def create_search_service(
    db_connection: sqlite3.Connection,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
) -> SearchService:
    """
    Create a SearchService with the specified provider.

    Args:
        db_connection: SQLite database connection.
        provider_name: 'lmstudio' or 'sentence-transformers'.
        model: Model name override.

    Returns:
        SearchService: Configured service instance.
    """
    provider = create_provider(provider_name, model)
    return SearchService(db_connection, provider)
