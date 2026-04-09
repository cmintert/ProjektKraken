"""Tests for worker search-service caching in index_object / rebuild_search_index.

Regression tests for the Windows heap-corruption crash (0xc0000374) caused by
creating a new SentenceTransformer model on every autosave.  The fix reuses the
cached SearchService returned by DatabaseWorker._get_search_service() so the
underlying model is loaded at most once per worker lifetime.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from src.services.worker import DatabaseWorker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def worker():
    """Bare worker instance with no real DB."""
    w = DatabaseWorker("test.db")
    # Inject a minimal mock db_service so get_connection() is callable.
    mock_db = MagicMock()
    mock_db.get_connection.return_value = MagicMock()  # fake SQLite connection
    w.db_service = mock_db
    return w


@pytest.fixture()
def mock_search_service():
    return MagicMock()


# ---------------------------------------------------------------------------
# Caching tests (the crash fix)
# ---------------------------------------------------------------------------


class TestIndexObjectCaching:
    """index_object() must reuse _get_search_service() instead of constructing
    a fresh provider on every call."""

    def test_index_object_uses_cached_service(self, worker, mock_search_service):
        """_get_search_service is called, not create_search_service directly."""
        worker._get_search_service = MagicMock(return_value=mock_search_service)

        worker.index_object("entity", "abc-123")

        # The cached getter must have been invoked exactly once.
        worker._get_search_service.assert_called_once()
        # The underlying index_entity must have been called on the *same* object.
        mock_search_service.index_entity.assert_called_once_with("abc-123", None)

    def test_second_index_object_call_reuses_same_service(
        self, worker, mock_search_service
    ):
        """Calling index_object twice must not construct the model twice."""
        call_count = 0
        first_service = mock_search_service

        def fake_get():
            nonlocal call_count
            call_count += 1
            return first_service

        worker._get_search_service = fake_get

        worker.index_object("entity", "id-1")
        worker.index_object("entity", "id-2")

        # Both calls went through the same getter (called twice, but the real
        # _get_search_service only builds the model on the first call).
        assert call_count == 2
        # Both index_entity calls happened on the same service instance.
        assert mock_search_service.index_entity.call_count == 2

    def test_index_event_delegates_correctly(self, worker, mock_search_service):
        """index_object('event', …) calls index_event on the cached service."""
        worker._get_search_service = MagicMock(return_value=mock_search_service)

        worker.index_object("event", "evt-42", excluded_attributes=["_private"])

        mock_search_service.index_event.assert_called_once_with(
            "evt-42", ["_private"]
        )
        mock_search_service.index_entity.assert_not_called()

    def test_index_object_emits_error_when_service_unavailable(self, worker):
        """If _get_search_service returns None, error_occurred must be emitted."""
        worker._get_search_service = MagicMock(return_value=None)
        errors = []
        worker.error_occurred.connect(errors.append)

        worker.index_object("entity", "no-svc")

        assert len(errors) == 1
        assert "entity" in errors[0].lower() or "unavailable" in errors[0].lower()


class TestRebuildSearchIndexCaching:
    """rebuild_search_index() must also reuse _get_search_service()."""

    def test_rebuild_uses_cached_service(self, worker, mock_search_service):
        mock_search_service.rebuild_index.return_value = {"entity": 3, "event": 5}
        worker._get_search_service = MagicMock(return_value=mock_search_service)

        finished = []
        worker.index_rebuild_finished.connect(
            lambda total, failed: finished.append((total, failed))
        )

        worker.rebuild_search_index("all")

        worker._get_search_service.assert_called_once()
        mock_search_service.rebuild_index.assert_called_once()
        assert finished == [(8, 0)]

    def test_rebuild_handles_import_error_from_get_service(self, worker):
        """ImportError in _get_search_service is forwarded as an error signal."""

        def raise_import():
            raise ImportError("sentence-transformers is not installed.")

        worker._get_search_service = raise_import
        errors = []
        finished = []
        worker.error_occurred.connect(errors.append)
        worker.index_rebuild_finished.connect(
            lambda t, f: finished.append((t, f))
        )

        worker.rebuild_search_index("all")

        assert len(errors) == 1
        assert "sentence-transformers" in errors[0]
        assert finished == [(0, 0)]
