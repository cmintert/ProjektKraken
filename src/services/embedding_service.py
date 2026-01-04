"""
Embedding Service Module.

Provides a unified interface for embedding operations with model/dimension
validation and index management. Wraps provider implementations to ensure
compatibility with the existing embeddings database schema.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.services.llm_provider import Provider, create_provider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for managing embeddings with model/dimension validation.

    Wraps provider implementations and enforces consistency checks when
    storing and retrieving embeddings from the database.
    """

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        provider: Provider,
        index_dir: Optional[str] = None,
        world_id: Optional[str] = None,
    ) -> None:
        """
        Initialize embedding service.

        Args:
            db_connection: SQLite database connection.
            provider: Embedding provider instance.
            index_dir: Optional directory for index persistence (defaults to 'indexes/').
            world_id: Optional world ID for per-world index management.

        Raises:
            ValueError: If provider doesn't support embeddings.
        """
        self.conn = db_connection
        self.provider = provider
        self.world_id = world_id

        # Validate provider supports embeddings
        meta = provider.metadata()
        if not meta.get("supports_embeddings", False):
            raise ValueError(
                f"Provider {meta.get('name', 'Unknown')} does not support embeddings"
            )

        self.model = provider.get_model_name()
        self.dimension = provider.get_dimension()

        # Setup index directory
        if index_dir:
            self.index_dir = Path(index_dir)
        else:
            # Default to indexes/ in user data directory
            from src.core.paths import get_user_data_path

            self.index_dir = Path(get_user_data_path()) / "indexes"

        self.index_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"EmbeddingService initialized with model: {self.model}")
        logger.info(f"Embedding dimension: {self.dimension}")
        logger.info(f"Index directory: {self.index_dir}")

    def get_index_path(self, model: Optional[str] = None) -> Path:
        """
        Get the path for a specific model's index file.

        Args:
            model: Optional model name (defaults to current provider model).

        Returns:
            Path: Path to index file for the model.
        """
        model_name = model or self.model
        # Sanitize model name for filename
        safe_model_name = model_name.replace(":", "_").replace("/", "_")

        if self.world_id:
            filename = f"{self.world_id}_{safe_model_name}.index"
        else:
            filename = f"{safe_model_name}.index"

        return self.index_dir / filename

    def validate_embedding(self, embedding: np.ndarray) -> bool:
        """
        Validate that an embedding matches expected dimensions.

        Args:
            embedding: Embedding vector to validate.

        Returns:
            bool: True if valid, False otherwise.
        """
        if embedding.shape[0] != self.dimension:
            logger.warning(
                f"Embedding dimension mismatch: expected {self.dimension}, "
                f"got {embedding.shape[0]}"
            )
            return False
        return True

    def get_embeddings_by_model(
        self, model: Optional[str] = None, object_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve embeddings from database filtered by model and optionally object type.

        Args:
            model: Optional model filter (defaults to current model).
            object_type: Optional object type filter ('entity' or 'event').

        Returns:
            List of dicts containing embedding metadata and vectors.

        Raises:
            ValueError: If dimension mismatch detected.
        """
        query_model = model or self.model

        sql = """
            SELECT id, object_type, object_id, vector, vector_dim, metadata, created_at
            FROM embeddings
            WHERE model = ?
        """
        params = [query_model]

        if object_type:
            sql += " AND object_type = ?"
            params.append(object_type)

        cursor = self.conn.execute(sql, params)
        results = []

        for row in cursor.fetchall():
            row_dict = dict(row)

            # Validate dimension
            if row_dict["vector_dim"] != self.dimension:
                logger.warning(
                    f"Dimension mismatch for embedding {row_dict['id']}: "
                    f"expected {self.dimension}, got {row_dict['vector_dim']}"
                )
                # Skip mismatched embeddings
                continue

            # Parse metadata
            if row_dict.get("metadata"):
                row_dict["metadata"] = json.loads(row_dict["metadata"])

            results.append(row_dict)

        logger.debug(
            f"Retrieved {len(results)} embeddings for model {query_model} "
            f"(filtered by dimension {self.dimension})"
        )
        return results

    def count_embeddings_by_model(
        self, model: Optional[str] = None, enforce_dimension: bool = True
    ) -> int:
        """
        Count embeddings in database for a specific model.

        Args:
            model: Optional model filter (defaults to current model).
            enforce_dimension: If True, only count embeddings matching current dimension.

        Returns:
            int: Count of embeddings.
        """
        query_model = model or self.model

        if enforce_dimension:
            sql = """
                SELECT COUNT(*) FROM embeddings
                WHERE model = ? AND vector_dim = ?
            """
            params = [query_model, self.dimension]
        else:
            sql = "SELECT COUNT(*) FROM embeddings WHERE model = ?"
            params = [query_model]

        cursor = self.conn.execute(sql, params)
        count = cursor.fetchone()[0]

        logger.debug(
            f"Found {count} embeddings for model {query_model}"
            + (f" with dimension {self.dimension}" if enforce_dimension else "")
        )
        return count

    def delete_embeddings_by_model(
        self, model: Optional[str] = None, enforce_dimension: bool = True
    ) -> int:
        """
        Delete embeddings from database for a specific model.

        Args:
            model: Optional model filter (defaults to current model).
            enforce_dimension: If True, only delete embeddings matching current dimension.

        Returns:
            int: Number of embeddings deleted.
        """
        query_model = model or self.model

        if enforce_dimension:
            sql = """
                DELETE FROM embeddings
                WHERE model = ? AND vector_dim = ?
            """
            params = [query_model, self.dimension]
        else:
            sql = "DELETE FROM embeddings WHERE model = ?"
            params = [query_model]

        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        deleted_count = cursor.rowcount

        logger.info(
            f"Deleted {deleted_count} embeddings for model {query_model}"
            + (f" with dimension {self.dimension}" if enforce_dimension else "")
        )
        return deleted_count

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts using the provider.

        Args:
            texts: List of text strings to embed.

        Returns:
            np.ndarray: 2D array of embeddings.

        Raises:
            Exception: If embedding generation fails or validation fails.
        """
        if not texts:
            return np.array([])

        # Generate embeddings via provider
        embeddings = self.provider.embed(texts)

        # Validate dimensions
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Provider returned embeddings with dimension {embeddings.shape[1]}, "
                f"expected {self.dimension}"
            )

        logger.debug(f"Generated {len(embeddings)} embeddings via {self.model}")
        return embeddings

    def rebuild_index(self) -> None:
        """
        Rebuild the ANN index from database embeddings.

        Loads all embeddings matching current model and dimension,
        then persists index to disk.

        Note: This is a placeholder for future ANN index integration.
        Currently just validates embeddings exist and are accessible.
        """
        logger.info(f"Rebuilding index for model {self.model}...")

        embeddings = self.get_embeddings_by_model()

        if not embeddings:
            logger.warning("No embeddings found to index")
            return

        logger.info(f"Found {len(embeddings)} embeddings for indexing")

        # TODO: Implement actual ANN index building (e.g., FAISS, Annoy)
        # For now, just save metadata about the index
        index_path = self.get_index_path()
        index_metadata = {
            "model": self.model,
            "dimension": self.dimension,
            "count": len(embeddings),
            "world_id": self.world_id,
        }

        with open(index_path, "w") as f:
            json.dump(index_metadata, f, indent=2)

        logger.info(f"Index metadata saved to {index_path}")

    def get_index_metadata(self, model: Optional[str] = None) -> Optional[Dict]:
        """
        Load index metadata from disk.

        Args:
            model: Optional model name (defaults to current model).

        Returns:
            Dict containing index metadata, or None if not found.
        """
        index_path = self.get_index_path(model)

        if not index_path.exists():
            logger.debug(f"Index file not found: {index_path}")
            return None

        try:
            with open(index_path, "r") as f:
                metadata = json.load(f)
            logger.debug(f"Loaded index metadata from {index_path}")
            return metadata
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load index metadata: {e}")
            return None


def create_embedding_service(
    db_connection: sqlite3.Connection,
    provider_id: str = "lmstudio",
    world_id: Optional[str] = None,
    **provider_kwargs: Any,
) -> EmbeddingService:
    """
    Create an EmbeddingService with the specified provider.

    Args:
        db_connection: SQLite database connection.
        provider_id: Provider identifier ('lmstudio', 'openai', 'google').
        world_id: Optional world ID for per-world configuration.
        **provider_kwargs: Additional provider configuration overrides.

    Returns:
        EmbeddingService: Configured embedding service instance.

    Raises:
        ValueError: If provider doesn't support embeddings.
    """
    provider = create_provider(provider_id, world_id, **provider_kwargs)
    return EmbeddingService(db_connection, provider, world_id=world_id)
