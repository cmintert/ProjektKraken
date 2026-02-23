"""Unit tests for DatabaseService.get_embedding_stats."""

import pytest

from src.services.db_service import DatabaseService


@pytest.fixture
def db_service() -> DatabaseService:
    """In-memory database service with schema initialized."""
    svc = DatabaseService(":memory:")
    svc.connect()
    return svc


def test_get_embedding_stats_empty(db_service: DatabaseService) -> None:
    """Returns zero count and None timestamp when no embeddings exist."""
    stats = db_service.get_embedding_stats()

    assert stats["count"] == 0
    assert stats["last_updated"] is None


def test_get_embedding_stats_with_data(db_service: DatabaseService) -> None:
    """Returns correct count and latest timestamp when embeddings exist."""
    conn = db_service.get_connection()
    assert conn is not None

    conn.execute(
        "INSERT INTO embeddings (id, object_type, object_id, model, "
        "vector, vector_dim, text_snippet, text_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("id1", "event", "ev1", "test-model", b"vec", 128, "text", "hash1", 1000.0),
    )
    conn.execute(
        "INSERT INTO embeddings (id, object_type, object_id, model, "
        "vector, vector_dim, text_snippet, text_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("id2", "entity", "en1", "test-model", b"vec", 128, "text", "hash2", 2000.0),
    )
    conn.commit()

    stats = db_service.get_embedding_stats()

    assert stats["count"] == 2
    assert stats["last_updated"] == 2000.0


def test_get_embedding_stats_no_connection() -> None:
    """Returns defaults when the service has no active connection."""
    svc = DatabaseService(":memory:")

    stats = svc.get_embedding_stats()

    assert stats["count"] == 0
    assert stats["last_updated"] is None
