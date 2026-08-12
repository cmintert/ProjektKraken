"""Base Repository Module.

Provides the abstract base class for all repository implementations. Repositories handle
CRUD operations for specific domain entities.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class BaseRepository:
    """Abstract base class for repository implementations.

    Provides common functionality for database operations including
    connection management, transaction handling, and JSON serialization.

    Attributes:
        _connection: The SQLite database connection (managed by DatabaseService).

    """

    def __init__(self, connection: Optional[sqlite3.Connection] = None) -> None:
        """Initialize the repository.

        Args:
            connection: Optional SQLite connection. If None, must be set later.

        """
        self._connection = connection

    def set_connection(self, connection: sqlite3.Connection) -> None:
        """Set the database connection.

        Args:
            connection: The SQLite database connection.

        """
        self._connection = connection

    def _require_connection(self) -> sqlite3.Connection:
        """Return the active connection or fail with a stable lifecycle error.

        Returns:
            The initialized SQLite connection.

        Raises:
            RuntimeError: If the repository has not received a connection.

        """
        if self._connection is None:
            raise RuntimeError("Database connection not initialized")
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Context manager for safe transaction handling.

        Yields:
            The database connection within a transaction context.

        Raises:
            sqlite3.Error: If the transaction fails.

        """
        connection = self._require_connection()
        owns_transaction = not connection.in_transaction
        try:
            if owns_transaction:
                connection.execute("BEGIN")
            yield connection
            if owns_transaction:
                connection.commit()
        except Exception as e:
            if owns_transaction:
                connection.rollback()
            if not getattr(e, "silent_transaction_rollback", False):
                logger.error(f"Transaction rolled back due to error: {e}")
            raise

    @staticmethod
    def _serialize_json(data: dict) -> str:
        """Serialize a dictionary to JSON string.

        Args:
            data: Dictionary to serialize.

        Returns:
            JSON string representation.

        """
        return json.dumps(data)

    @staticmethod
    def _deserialize_json(json_str: str) -> dict:
        """Deserialize JSON string to dictionary.

        Args:
            json_str: JSON string to deserialize.

        Returns:
            Dictionary representation, or empty dict if parsing fails.

        """
        if not json_str:
            return {}
        try:
            result = json.loads(json_str)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse JSON: {e}. Returning empty dict.")
            return {}
