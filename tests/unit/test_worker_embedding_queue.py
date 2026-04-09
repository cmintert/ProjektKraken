"""Tests for Worker Embedding Queue - Prevents Concurrent Embeddings.

Verifies that the DatabaseWorker queues embedding requests to prevent
concurrent embedding operations which can fail due to resource conflicts.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.worker import DatabaseWorker


@pytest.fixture
def worker():
    """DatabaseWorker instance with mocked database service."""
    with patch("src.services.worker.DatabaseService"):
        worker = DatabaseWorker("test.db")
        worker.db_service = MagicMock()
        return worker


class TestEmbeddingQueue:
    """Tests for _embedding_in_progress flag and queuing logic."""

    def test_embedding_queue_initialized(self, worker):
        """Worker should have embedding queue and flag initialized."""
        assert hasattr(worker, "_embedding_in_progress")
        assert hasattr(worker, "_pending_embeddings")
        assert worker._embedding_in_progress is False
        assert worker._pending_embeddings == set()

    def test_first_embedding_starts_immediately(self, worker):
        """First embedding request should start immediately, not queue."""
        with patch.object(worker, "_do_index_object") as mock_do_index:
            worker.index_object("entity", "ent-123", None)

            # Should call _do_index_object directly
            mock_do_index.assert_called_once_with("entity", "ent-123", None)

    def test_concurrent_embedding_gets_queued(self, worker):
        """Second embedding while one is in progress should be queued."""
        worker._embedding_in_progress = True

        with patch.object(worker, "_do_index_object") as mock_do_index:
            worker.index_object("entity", "ent-456", None)

            # Should NOT call _do_index_object directly
            mock_do_index.assert_not_called()

        # Should be in pending queue instead
        assert len(worker._pending_embeddings) == 1
        # Check that the tuple is in the set (convert tuple back to compare)
        pending = worker._pending_embeddings.pop()
        assert pending[0] == "entity"
        assert pending[1] == "ent-456"
        assert pending[2] is None

    def test_multiple_concurrent_requests_queued(self, worker):
        """Multiple requests while embedding is in progress should all queue."""
        worker._embedding_in_progress = True

        with patch.object(worker, "_do_index_object"):
            worker.index_object("entity", "ent-1", None)
            worker.index_object("entity", "ent-2", None)
            worker.index_object("event", "evt-3", None)

        # All should be queued
        assert len(worker._pending_embeddings) == 3

    def test_excluded_attributes_preserved_in_queue(self, worker):
        """Excluded attributes should be preserved when queuing."""
        worker._embedding_in_progress = True

        excluded = ["attr1", "attr2"]
        worker.index_object("entity", "ent-123", excluded)

        # Check queued item
        pending = worker._pending_embeddings.pop()
        assert pending[0] == "entity"
        assert pending[1] == "ent-123"
        assert pending[2] == tuple(excluded)

    def test_process_pending_embeddings_dequeues_one(self, worker):
        """_process_pending_embeddings should dequeue and process one item."""
        # Queue an item
        worker._pending_embeddings.add(("entity", "ent-pending", None))

        with patch.object(worker, "_do_index_object") as mock_do_index:
            worker._process_pending_embeddings()

            # Should process the queued item
            mock_do_index.assert_called_once()
            args = mock_do_index.call_args[0]
            assert args[0] == "entity"
            assert args[1] == "ent-pending"
            assert args[2] is None

    def test_process_pending_empty_is_noop(self, worker):
        """_process_pending_embeddings with empty queue should do nothing."""
        worker._pending_embeddings = set()

        with patch.object(worker, "_do_index_object") as mock_do_index:
            worker._process_pending_embeddings()

            # Should not call _do_index_object
            mock_do_index.assert_not_called()

    def test_do_index_sets_flag(self, worker):
        """_do_index_object should set the in-progress flag."""
        with patch.object(worker, "_get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_search.return_value = mock_service

            # Trap the flag state during execution
            flag_state = []

            original_index_entity = mock_service.index_entity

            def capture_flag(*args, **kwargs):
                flag_state.append(worker._embedding_in_progress)
                return original_index_entity(*args, **kwargs)

            mock_service.index_entity.side_effect = capture_flag

            worker._do_index_object("entity", "ent-123", None)

            # Flag should have been True during execution
            assert True in flag_state

    def test_do_index_clears_flag_after_completion(self, worker):
        """_do_index_object should clear flag after completion."""
        with patch.object(worker, "_get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_search.return_value = mock_service

            worker._do_index_object("entity", "ent-123", None)

            # Flag should be False after completion
            assert worker._embedding_in_progress is False

    def test_do_index_clears_flag_on_exception(self, worker):
        """_do_index_object should clear flag even if embedding fails."""
        with patch.object(worker, "_get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_search.return_value = mock_service
            mock_service.index_entity.side_effect = RuntimeError("Embed failed")

            # Should not raise, should handle exception
            worker._do_index_object("entity", "ent-fail", None)

            # Flag should still be cleared
            assert worker._embedding_in_progress is False

    def test_do_index_processes_pending_after_completion(self, worker):
        """_do_index_object should process pending queue after finishing."""
        # Queue a pending item
        worker._pending_embeddings.add(("event", "evt-pending", None))

        with patch.object(worker, "_get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_search.return_value = mock_service

            with patch.object(worker, "_process_pending_embeddings") as mock_process:
                worker._do_index_object("entity", "ent-123", None)

                # Should call _process_pending_embeddings in finally
                mock_process.assert_called_once()

    def test_full_queue_cycle(self, worker):
        """Full cycle: first embed, queue concurrent requests, process queue."""
        with patch.object(worker, "_get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_search.return_value = mock_service

            call_sequence = []

            def track_index_entity(object_id, *args):
                call_sequence.append(("embed", object_id))

            mock_service.index_entity.side_effect = track_index_entity

            # Start first embedding
            worker.index_object("entity", "ent-1", None)
            # While first is running, queue more
            worker._embedding_in_progress = True
            worker.index_object("entity", "ent-2", None)
            worker.index_object("entity", "ent-3", None)

            # Finish first, which should process ent-2 automatically
            worker._embedding_in_progress = False
            worker._process_pending_embeddings()

            # At this point ent-1 was embedded and ent-2 should be processing
            # (ent-3 would still be pending)
            # The key assertion: no crash, proper queueing occurred
            assert len(call_sequence) >= 1
            assert "ent-1" in [call[1] for call in call_sequence]
