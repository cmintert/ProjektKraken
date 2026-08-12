"""Search Service Module.

Provides semantic search functionality with local embeddings and vector similarity.
Supports sentence-transformers (default, local) and LM Studio (optional remote) as
embedding providers.
"""

import hashlib
import heapq
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

import numpy as np

if TYPE_CHECKING:
    from src.core.entities import Entity
    from src.core.events import Event

from src.core.environment import env_bool

logger = logging.getLogger(__name__)

_EMBEDDING_MATRIX_DIMENSIONS = 2

_VECTOR_NORM_EPSILON = 1e-12

REBUILD_BATCH_SIZE = 32


@dataclass(frozen=True)
class IndexRebuildCounts:
    """Outcome counts for one rebuilt object type."""

    indexed: int = 0
    unchanged: int = 0
    failed: int = 0

    @property
    def processed(self) -> int:
        """Return the number of objects considered by the rebuild."""
        return self.indexed + self.unchanged + self.failed


@dataclass(frozen=True)
class IndexRebuildResult:
    """Aggregate outcome of a semantic-index rebuild."""

    per_type: Dict[str, IndexRebuildCounts]

    @property
    def indexed(self) -> int:
        """Return the number of newly indexed or updated objects."""
        return sum(counts.indexed for counts in self.per_type.values())

    @property
    def unchanged(self) -> int:
        """Return the number of objects whose existing index was current."""
        return sum(counts.unchanged for counts in self.per_type.values())

    @property
    def failed(self) -> int:
        """Return the number of objects that could not be indexed."""
        return sum(counts.failed for counts in self.per_type.values())

    @property
    def processed(self) -> int:
        """Return the total number of objects considered."""
        return sum(counts.processed for counts in self.per_type.values())


# =============================================================================
# Text Building Functions (Deterministic)
# =============================================================================


def _stable_dump(val: Any) -> str:
    """Convert a value to a stable string representation.

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
    entity: "Entity",
    tags: Optional[Sequence[Union[str, Dict[str, str]]]] = None,
    excluded_attributes: Optional[List[str]] = None,
) -> str:
    """Build a deterministic text representation of an entity for embedding.

    Includes name, type, description, tags, and all JSON attributes
    in a stable, sorted order.

    Args:
        entity: Entity object with name, type, description, attributes.
        tags: Optional list of tag names or tag dicts with "name" key.
        excluded_attributes: Optional list of attribute keys to exclude.

    Returns:
        str: A multi-line text representation of the entity.

    """
    if excluded_attributes is None:
        excluded_attributes = []

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
    for key in sorted(attrs.keys()):
        # Filter out internal tags or explicit exclusions
        if key.startswith("_") or key in excluded_attributes:
            continue
        parts.append(f"{key}: {_stable_dump(attrs[key])}")

    return "\n\n".join(parts)


def build_text_for_event(
    event: "Event",
    tags: Optional[Sequence[Union[str, Dict[str, str]]]] = None,
    excluded_attributes: Optional[List[str]] = None,
) -> str:
    """Build a deterministic text representation of an event for embedding.

    Includes name, type, date, duration, description, tags, and all JSON
    attributes in a stable, sorted order.

    Args:
        event: Event object with name, type, lore_date, lore_duration, etc.
        tags: Optional list of tag names or tag dicts with "name" key.
        excluded_attributes: Optional list of attribute keys to exclude.

    Returns:
        str: A multi-line text representation of the event.

    """
    if excluded_attributes is None:
        excluded_attributes = []

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
    for key in sorted(attrs.keys()):
        # Filter out internal tags or explicit exclusions
        if key.startswith("_") or key in excluded_attributes:
            continue
        parts.append(f"{key}: {_stable_dump(attrs[key])}")

    return "\n\n".join(parts)


def text_sha256(text: str) -> str:
    """Compute SHA-256 hash of text for change detection.

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
    """Normalize a vector to unit length.

    Args:
        v: Input vector as numpy array.

    Returns:
        np.ndarray: Unit-normalized vector as float32.

    """
    v = v.astype(np.float32)
    norm = np.linalg.norm(v)
    if norm < _VECTOR_NORM_EPSILON:
        return v  # avoid division by zero; treat as near-zero vector
    return v / norm


def serialize_vector(v: np.ndarray) -> bytes:
    """Serialize a vector to bytes for storage in SQLite BLOB.

    Args:
        v: Vector as numpy array.

    Returns:
        bytes: Serialized float32 vector.

    """
    v32: np.ndarray = v.astype(np.float32)
    return v32.tobytes()


def deserialize_vector(blob: bytes, dim: int) -> np.ndarray:
    """Deserialize a vector from SQLite BLOB bytes.

    Args:
        blob: Bytes from database BLOB.
        dim: Expected vector dimension.

    Returns:
        np.ndarray: Float32 vector.

    """
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def dot_scores(q_vec: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Compute dot product similarity scores between query and matrix of vectors.

    Assumes both query and matrix rows are already normalized.

    Args:
        q_vec: Query vector (1D array).
        V: Matrix of vectors (2D array, each row is a vector).

    Returns:
        np.ndarray: Array of similarity scores.

    """
    return V.dot(q_vec)


def top_k_streaming(
    scores_iter: Iterator[Tuple[float, Any]], k: int
) -> List[Tuple[float, Any]]:
    """Select top-k items from an iterator using a min-heap (streaming approach).

    Args:
        scores_iter: Iterator yielding (score, item) tuples.
        k: Number of top items to return.

    Returns:
        List of (score, item) tuples sorted by descending score.

    """
    heap: List[Tuple[float, int, Any]] = []
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
    """Abstract base class for embedding providers.

    All providers must implement embed() and get_dimension() methods.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of shape (len(texts), dimension).

        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimensionality of the embeddings.

        Returns:
            int: Embedding dimension.

        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name/identifier.

        Returns:
            str: Model name.

        """
        pass


class LMStudioEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for LM Studio local embedding API.

    Supports OpenAI-compatible embedding endpoints.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """Initialize LM Studio embedding provider.

        Args:
            url: API endpoint URL (default from env or
                 http://localhost:8080/v1/embeddings).
            model: Model name (default from env or required).
            api_key: Optional API key.
            timeout: Request timeout in seconds.

        """
        import requests  # type: ignore[import-untyped]

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
        self._dimension: Optional[int] = None

        # Configurable request/response shape
        self.input_key = os.getenv("LMSTUDIO_INPUT_KEY", "input")
        self.model_key = os.getenv("LMSTUDIO_MODEL_KEY", "model")
        self.embed_path = os.getenv("LMSTUDIO_EMBED_PATH", "data[].embedding")

        logger.info(f"LMStudioEmbeddingProvider initialized with URL: {self.url}")
        logger.info(f"Model: {self.model}")

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using LM Studio API.

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
                self._dimension = int(emb_array.shape[1])

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
            ) from e
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse LM Studio response: {e}")
            raise Exception(f"Invalid response from LM Studio API: {e}") from e

    def get_dimension(self) -> int:
        """Get the dimensionality of embeddings.

        Returns:
            int: Embedding dimension.

        """
        dimension = self._dimension
        if dimension is None:
            # Make a test call to determine dimension
            test_emb = self.embed(["test"])
            dimension = int(test_emb.shape[1])
            self._dimension = dimension
        return dimension

    def get_model_name(self) -> str:
        """Get the model name.

        Returns:
            str: Model identifier with 'lmstudio:' prefix.

        """
        return f"lmstudio:{self.model}"


class SentenceTransformersProvider(EmbeddingProvider):
    """Fallback embedding provider using sentence-transformers library.

    Requires sentence-transformers to be installed.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize sentence-transformers provider.

        Args:
            model: Model name (default from env or 'all-MiniLM-L6-v2').

        """
        # Prevent native-thread heap corruption on Windows.  The HuggingFace
        # tokenizer uses parallel Rust threads by default, and OpenMP / ONNX
        # Runtime spawn thread pools proportional to core count.  When the
        # model runs on a background QThread these native threads clash with
        # Qt's threading, producing STATUS_HEAP_CORRUPTION (0xc0000374).
        # Setting these *before* the first import is critical.
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("OMP_NUM_THREADS", "1")

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Semantic search requires it. "
                "Run: pip install sentence-transformers\n"
                "Or install all dependencies: pip install -r requirements.txt"
            ) from e

        self.model_name = model or os.getenv("ST_MODEL", "all-MiniLM-L6-v2")
        # Force CPU inference to avoid torch device conversion crashes on
        # Windows when semantic queries execute from the worker QThread.
        self.model = SentenceTransformer(self.model_name, device="cpu")
        self._dimension = self.model.get_sentence_embedding_dimension()

        logger.info(
            f"SentenceTransformersProvider initialized with model: {self.model_name}"
        )

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings using sentence-transformers.

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
        """Get embedding dimension.

        Returns:
            int: Embedding dimension.

        """
        return self._dimension

    def get_model_name(self) -> str:
        """Get model name.

        Returns:
            str: Model identifier with 'st:' prefix.

        """
        return f"st:{self.model_name}"


class SubprocessSentenceTransformersProvider(EmbeddingProvider):
    """Sentence-transformers provider that runs embedding in a child process.

    This isolates native crashes from torch/onnx/tokenizers away from the Qt
    process. Every embed call executes in a short-lived Python subprocess.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize subprocess-backed provider.

        Args:
            model: Model name (default from env or 'all-MiniLM-L6-v2').

        """
        self.model_name = model or os.getenv("ST_MODEL", "all-MiniLM-L6-v2")
        self.timeout_s = float(os.getenv("PK_ST_SUBPROCESS_TIMEOUT_S", "30"))
        self._dimension: Optional[int] = None

        logger.info(
            "SubprocessSentenceTransformersProvider initialized with model: "
            f"{self.model_name}"
        )

    def _run_embed_subprocess(self, texts: List[str]) -> np.ndarray:
        """Run embedding in child process and return vectors as float32 numpy."""
        payload = {
            "model": self.model_name,
            "texts": texts,
        }

        result = subprocess.run(
            [sys.executable, "-m", "src.services.embedding_subprocess"],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=self.timeout_s,
            check=False,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        parsed: Optional[Dict[str, Any]] = None
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                parsed = candidate
                break

        if result.returncode != 0:
            error_text = ""
            if parsed and isinstance(parsed.get("error"), str):
                error_text = parsed["error"]
            elif stderr:
                error_text = stderr[:300]
            raise RuntimeError(
                "Subprocess embedding failed "
                f"(code={result.returncode}): {error_text}"
            )

        if not parsed or "embeddings" not in parsed:
            raise RuntimeError("Subprocess embedding returned invalid payload")

        embeddings = np.array(parsed["embeddings"], dtype=np.float32)
        if embeddings.ndim != _EMBEDDING_MATRIX_DIMENSIONS:
            raise RuntimeError("Subprocess embedding payload had unexpected shape")
        return embeddings

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings in isolated child process."""
        if not texts:
            return np.array([])

        embeddings = self._run_embed_subprocess(texts)
        if self._dimension is None and embeddings.size > 0:
            self._dimension = int(embeddings.shape[1])
        return embeddings

    def get_dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            probe = self.embed(["dimension probe"])
            self._dimension = int(probe.shape[1])
        return self._dimension

    def get_model_name(self) -> str:
        """Get model name with provider prefix."""
        return f"st:{self.model_name}"


# =============================================================================
# Search Service
# =============================================================================


class SearchService:
    """Service for managing semantic search indexes and queries.

    Handles text extraction, embedding generation, and similarity search for entities
    and events.
    """

    def __init__(
        self, db_connection: sqlite3.Connection, provider: EmbeddingProvider
    ) -> None:
        """Initialize search service.

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
        """Get tags for an entity or event.

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

    def index_entity(
        self, entity_id: str, excluded_attributes: Optional[List[str]] = None
    ) -> None:
        """Index a single entity.

        Args:
            entity_id: Entity UUID.
            excluded_attributes: Optional list of attribute keys to exclude.

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
        text = build_text_for_entity(entity, tags, excluded_attributes)
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

    def index_event(
        self, event_id: str, excluded_attributes: Optional[List[str]] = None
    ) -> None:
        """Index a single event.

        Args:
            event_id: Event UUID.
            excluded_attributes: Optional list of attribute keys to exclude.

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
        text = build_text_for_event(event, tags, excluded_attributes)
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

    def _prepare_item_for_batch(
        self,
        obj_type: str,
        object_id: str,
        excluded_attributes: Optional[List[str]] = None,
    ) -> Optional[Tuple[str, str, str, Dict[str, str]]]:
        """Prepare a single item for batch embedding.

        Fetches the object from the database, builds text, checks hash to skip
        unchanged items.

        Args:
            obj_type: 'entity' or 'event'.
            object_id: Object UUID.
            excluded_attributes: Attribute keys to exclude.

        Returns:
            Tuple of (object_id, text, text_hash, metadata) or None if unchanged.

        """
        if obj_type == "entity":
            row = self.conn.execute(
                "SELECT * FROM entities WHERE id = ?", (object_id,)
            ).fetchone()
            if not row:
                return None
            entity_data = dict(row)
            if entity_data.get("attributes"):
                entity_data["attributes"] = json.loads(entity_data["attributes"])
            from src.core.entities import Entity
            entity = Entity.from_dict(entity_data)
            tags = self._get_tags_for_object("entity", object_id)
            text = build_text_for_entity(entity, tags, excluded_attributes)
            metadata = {"name": entity.name, "type": entity.type}
        elif obj_type == "event":
            row = self.conn.execute(
                "SELECT * FROM events WHERE id = ?", (object_id,)
            ).fetchone()
            if not row:
                return None
            event_data = dict(row)
            if event_data.get("attributes"):
                event_data["attributes"] = json.loads(event_data["attributes"])
            from src.core.events import Event
            event = Event.from_dict(event_data)
            tags = self._get_tags_for_object("event", object_id)
            text = build_text_for_event(event, tags, excluded_attributes)
            metadata = {"name": event.name, "type": event.type}
        else:
            return None

        text_hash_val = text_sha256(text)

        # Skip unchanged items
        existing = self.conn.execute(
            "SELECT text_hash FROM embeddings "
            "WHERE object_type = ? AND object_id = ? AND model = ?",
            (obj_type, object_id, self.model),
        ).fetchone()
        if existing and existing[0] == text_hash_val:
            return None

        return (object_id, text, text_hash_val, metadata)

    def _batch_upsert(
        self,
        object_type: str,
        items: List[Tuple[str, str, str, Dict[str, str]]],
    ) -> Tuple[int, int]:
        """Embed and upsert a batch of items.

        Args:
            object_type: 'entity' or 'event'.
            items: List of (object_id, text, text_hash, metadata) tuples.

        Returns:
            Tuple of (succeeded, failed) counts.

        """
        if not items:
            return (0, 0)

        texts = [item[1] for item in items]
        try:
            embeddings = self.provider.embed(texts)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return (0, len(items))

        succeeded = 0
        failed = 0
        for idx, (object_id, text, text_hash_val, metadata) in enumerate(items):
            try:
                normalized = normalize_vector(embeddings[idx])
                serialized = serialize_vector(normalized)
                embedding_id = str(uuid.uuid4())
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
                        object_type,
                        object_id,
                        self.model,
                        serialized,
                        self.dimension,
                        text,
                        text_hash_val,
                        json.dumps(metadata),
                        time.time(),
                    ),
                )
                succeeded += 1
            except Exception as e:
                logger.error(
                    f"Failed to upsert {object_type} {object_id}: {e}"
                )
                failed += 1

        self.conn.commit()
        return (succeeded, failed)

    def _load_rebuild_ids(
        self,
        object_types: List[str],
    ) -> Dict[str, List[str]]:
        """Load object IDs for each requested rebuild type."""
        ids_by_type: Dict[str, List[str]] = {}
        for obj_type in object_types:
            if obj_type not in {"entity", "event"}:
                raise ValueError(f"Unknown object type: {obj_type}")
            table = "entities" if obj_type == "entity" else "events"
            cursor = self.conn.execute(f"SELECT id FROM {table}")  # noqa: S608
            ids_by_type[obj_type] = [row[0] for row in cursor.fetchall()]
        return ids_by_type

    @staticmethod
    def _report_rebuild_progress(
        callback: Optional[Callable[[int, int], None]],
        processed: int,
        total: int,
    ) -> None:
        """Invoke a rebuild progress callback when one was supplied."""
        if callback is not None:
            callback(processed, total)

    def _rebuild_object_type(
        self,
        obj_type: str,
        ids: List[str],
        excluded_attributes: Optional[List[str]],
        processed: int,
        total: int,
        progress_callback: Optional[Callable[[int, int], None]],
    ) -> Tuple[IndexRebuildCounts, int]:
        """Rebuild one object type and return its counts and processed total."""
        indexed = 0
        unchanged = 0
        failed = 0
        batch: List[Tuple[str, str, str, Dict[str, str]]] = []

        for object_id in ids:
            try:
                prepared = self._prepare_item_for_batch(
                    obj_type,
                    object_id,
                    excluded_attributes,
                )
                if prepared is not None:
                    batch.append(prepared)
                else:
                    unchanged += 1
                    processed += 1
                    self._report_rebuild_progress(
                        progress_callback,
                        processed,
                        total,
                    )
            except Exception as e:
                logger.error(f"Failed to prepare {obj_type} {object_id}: {e}")
                failed += 1
                processed += 1
                self._report_rebuild_progress(
                    progress_callback,
                    processed,
                    total,
                )

            if len(batch) >= REBUILD_BATCH_SIZE:
                batch_size = len(batch)
                succeeded, batch_failed = self._batch_upsert(obj_type, batch)
                indexed += succeeded
                failed += batch_failed
                processed += batch_size
                self._report_rebuild_progress(
                    progress_callback,
                    processed,
                    total,
                )
                batch = []

        if batch:
            batch_size = len(batch)
            succeeded, batch_failed = self._batch_upsert(obj_type, batch)
            indexed += succeeded
            failed += batch_failed
            processed += batch_size
            self._report_rebuild_progress(
                progress_callback,
                processed,
                total,
            )

        return (
            IndexRebuildCounts(
                indexed=indexed,
                unchanged=unchanged,
                failed=failed,
            ),
            processed,
        )

    def rebuild_index(
        self,
        object_types: Optional[List[str]] = None,
        model: Optional[str] = None,
        excluded_attributes: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> IndexRebuildResult:
        """Rebuild embeddings index for specified object types.

        Uses batched embedding calls (REBUILD_BATCH_SIZE at a time) to avoid
        one-at-a-time overhead.  Unchanged items (same text_hash) are skipped
        before they enter a batch.

        Args:
            object_types: List of object types to index ('entity', 'event').
                         If None, indexes all types.
            model: Optional model filter (not currently used, for future compatibility).
            excluded_attributes: Optional list of attribute keys to exclude.
            progress_callback: Optional callback receiving ``(processed, total)``.

        Returns:
            Per-type indexed, unchanged, and failed counts.

        """
        if object_types is None:
            object_types = ["entity", "event"]

        ids_by_type = self._load_rebuild_ids(object_types)
        total = sum(len(ids) for ids in ids_by_type.values())
        processed = 0
        self._report_rebuild_progress(progress_callback, processed, total)
        counts: Dict[str, IndexRebuildCounts] = {}

        for obj_type in object_types:
            counts[obj_type], processed = self._rebuild_object_type(
                obj_type,
                ids_by_type[obj_type],
                excluded_attributes,
                processed,
                total,
                progress_callback,
            )

        logger.info(f"Rebuild complete. Indexed: {counts}")
        self._report_rebuild_progress(progress_callback, processed, total)
        return IndexRebuildResult(per_type=counts)

    def query(
        self,
        text: str,
        object_type: Optional[str] = None,
        top_k: int = 10,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query the index using semantic search.

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
            SELECT id, object_type, object_id, vector, vector_dim, metadata,
                   text_snippet
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
        def score_generator() -> Iterator[Tuple[float, Dict[str, Any]]]:
            """Generator function to compute similarity scores for query results.

            Yields similarity scores for each embedding vector in the result set.
            """
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
                    "text_content": row_dict.get("text_snippet", ""),
                }
            )

        return results

    def search_by_name(
        self, text: str, object_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return entities or events whose complete names occur in text."""
        # We need to find names.
        # Strategy: Fetch all names and check if they exist in text?
        # Or checking if text contains known names.
        # Given prompt length is small (Task), and DB might be large,
        # scanning text against all names is decent if we cache names?
        # For now, let's do a SQL LIKE query for words in the text?
        # Actually, best accuracy is: Get all names (cacheable in future) -> Check in text.
        # But for SQL-only:
        # We want entities whose name is IN the text.
        # NOT "text contains name".
        # If I have entity "Jonah", and text is "Who is Jonah?", match.

        # Fetch all names and IDs.
        # Optimize: Only fetch items.

        targets = []
        if object_type in (None, "entity"):
            targets.append(("entity", "entities"))
        if object_type in (None, "event"):
            targets.append(("event", "events"))

        found_items = []

        for type_label, table_name in targets:
            # We fetch all names. Warning: Scaling issue if 10k entities.
            # But local app 10k is fine for this loop usually.
            cursor = self.conn.execute(
                f"SELECT id, name, type, attributes FROM {table_name}"
            )
            rows = cursor.fetchall()

            for row in rows:
                obj_id, name, obj_type, attrs = row
                # Simple case-insensitive inclusion
                # Use word boundary to avoid "Jon" matching "Jonathan" if strict?
                # Let's try simple inclusion first, maybe improved later.
                if name.lower() in text.lower():
                    # Retrieve the embedding snippet if we want full context?
                    # Or construct partial result.
                    # RAGService expects 'text_content' for formatting attributes.
                    # We can fetch the text_snippet from embeddings table for this item.

                    # Fetch stored embedding data for the text snippet
                    emb_row = self.conn.execute(
                        "SELECT text_snippet, metadata FROM embeddings WHERE object_id = ? LIMIT 1",
                        (obj_id,),
                    ).fetchone()

                    text_content = ""
                    meta = {}
                    if emb_row:
                        text_content = emb_row[0]
                        if emb_row[1]:
                            meta = json.loads(emb_row[1])
                    else:
                        # Fallback if not indexed: Construct text_content from attributes
                        try:
                            attr_dict = json.loads(attrs) if attrs else {}
                        except json.JSONDecodeError:
                            attr_dict = {}

                        # Construct a basic snippet similar to indexer
                        lines = [f"Name: {name}", f"Type: {obj_type}"]
                        # Add some key attributes
                        for k, v in attr_dict.items():
                            if isinstance(v, (str, int, float, bool)):
                                lines.append(f"{k}: {v}")
                        text_content = "\n".join(lines)
                        meta = attr_dict  # Use attributes as metadata fallback

                    found_items.append(
                        {
                            "id": "lexical_" + obj_id,  # Dummy embedding ID
                            "object_type": type_label,
                            "object_id": obj_id,
                            "score": 1.0,  # Max score for direct match
                            "name": name,
                            "type": obj_type,
                            "metadata": meta,
                            "text_content": text_content,
                        }
                    )

        return found_items

    def delete_index_for_object(
        self, object_type: str, object_id: str, model: Optional[str] = None
    ) -> None:
        """Delete embeddings for a specific object.

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
# Provider Factory
# =============================================================================


def get_llm_settings_from_qsettings() -> Dict[str, Any]:
    """Load LLM settings from QSettings.

    Returns:
        Dict with keys: provider, lm_url, lm_model, lm_api_key, lm_timeout, st_model

    """
    try:
        from PySide6.QtCore import QSettings

        from src.core.settings import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
        from src.services.secret_store import get_api_key

        settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)

        raw_provider = str(
            settings.value("ai_embedding_provider", "sentence-transformers")
        )
        # Migrate old underscore variant saved by a previous dialog bug
        if raw_provider == "sentence_transformers":
            raw_provider = "sentence-transformers"
            settings.setValue("ai_embedding_provider", raw_provider)

        return {
            "provider": raw_provider,
            "lm_url": str(settings.value("ai_lmstudio_url", "")),
            "lm_model": str(settings.value("ai_lmstudio_model", "")),
            "lm_api_key": get_api_key("lmstudio"),
            "lm_timeout": cast(
                int, settings.value("ai_lmstudio_timeout", 30, type=int)
            ),
            "st_model": str(settings.value("ai_st_model", "")),
        }
    except Exception as e:
        logger.warning(f"Failed to load LLM settings from QSettings: {e}")
        return {
            "provider": "sentence-transformers",
            "lm_url": "",
            "lm_model": "",
            "lm_api_key": "",
            "lm_timeout": 30,
            "st_model": "",
        }


def create_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None,
) -> EmbeddingProvider:
    """Create an embedding provider based on configuration.

    Loads settings from QSettings, with environment variable fallbacks.

    Args:
        provider_name: 'lmstudio' or 'sentence-transformers'.
                       If None, uses QSettings then EMBED_PROVIDER env var.
        model: Model name override.
        url: LM Studio URL override.
        api_key: LM Studio API key override.
        timeout: LM Studio timeout override.

    Returns:
        EmbeddingProvider: Configured provider instance.

    Raises:
        ValueError: If provider is unknown or configuration is invalid.

    """
    # Load settings from QSettings
    qsettings = get_llm_settings_from_qsettings()

    # Determine provider (explicit > QSettings > env var)
    provider_name = (
        provider_name
        or qsettings["provider"]
        or os.getenv("EMBED_PROVIDER", "sentence-transformers")
    )

    if provider_name == "lmstudio":
        # Use explicit params > QSettings > env vars > defaults
        lm_url = url or qsettings["lm_url"] or None
        lm_model = model or qsettings["lm_model"] or None
        lm_api_key = api_key or qsettings["lm_api_key"] or None
        lm_timeout = timeout or qsettings["lm_timeout"] or 30

        return LMStudioEmbeddingProvider(
            url=lm_url if lm_url else None,
            model=lm_model if lm_model else None,
            api_key=lm_api_key if lm_api_key else None,
            timeout=lm_timeout,
        )
    elif provider_name == "sentence-transformers":
        st_model = model or qsettings["st_model"] or None
        use_subprocess_provider = env_bool(
            "PK_ST_EMBED_SUBPROCESS",
            default=sys.platform == "win32",
        )
        if use_subprocess_provider:
            return SubprocessSentenceTransformersProvider(
                model=st_model if st_model else None
            )
        return SentenceTransformersProvider(model=st_model if st_model else None)
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
    """Create a SearchService with the specified provider.

    Args:
        db_connection: SQLite database connection.
        provider_name: 'lmstudio' or 'sentence-transformers'.
        model: Model name override.

    Returns:
        SearchService: Configured service instance.

    """
    provider = create_provider(provider_name, model)
    return SearchService(db_connection, provider)
