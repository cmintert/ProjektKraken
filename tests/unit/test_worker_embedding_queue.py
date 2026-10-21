"""Worker semantic queue behavior and public signal delivery."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.worker import DatabaseWorker


@pytest.fixture
def worker():
    worker = DatabaseWorker("test.db")
    worker.db_service = MagicMock()
    return worker


def test_reentrant_requests_are_queued_with_exclusions(worker):
    service = worker._semantic_index
    search = MagicMock()
    seen = []

    def index_first(object_id, exclusions):
        seen.append((object_id, exclusions, service._embedding_in_progress))
        worker.index_object("event", "queued", ["private"])
        worker.index_object("event", "queued", ["private"])
        assert len(service._pending_embeddings) == 1

    search.index_entity.side_effect = index_first
    with patch.object(service, "_get_search_service", return_value=search):
        worker.index_object("entity", "first")

    assert seen == [("first", None, True)]
    search.index_event.assert_called_once_with("queued", ["private"])
    assert service._pending_embeddings == set()
    assert service._embedding_in_progress is False


def test_failed_embedding_drains_queue_and_emits_one_error(worker):
    service = worker._semantic_index
    search = MagicMock()
    errors = []
    finished = []
    worker.error_occurred.connect(errors.append)
    worker.operation_finished.connect(finished.append)

    def fail_first(object_id, exclusions):
        worker.index_object("event", "second")
        raise RuntimeError("embedding failed")

    search.index_entity.side_effect = fail_first
    with patch.object(service, "_get_search_service", return_value=search):
        worker.index_object("entity", "first")

    assert errors == ["Failed to index entity first."]
    assert finished == ["Indexed event second."]
    search.index_event.assert_called_once_with("second", None)
    assert service._embedding_in_progress is False


def test_reset_drops_database_bound_state_but_retains_probe(worker):
    service = worker._semantic_index
    service._search_service = MagicMock()
    service._embedding_in_progress = True
    service._pending_embeddings.add(("event", "old", None))
    service._semantic_probe_ran = True
    service._semantic_probe_ok = False

    service.reset_database()

    assert service._search_service is None
    assert service._embedding_in_progress is False
    assert service._pending_embeddings == set()
    assert service._semantic_probe_ran is True
    assert service._semantic_probe_ok is False


@pytest.mark.parametrize("release", ["cleanup", "_clear_failed_initialization"])
def test_worker_release_resets_semantic_state(worker, release):
    service = worker._semantic_index
    service._search_service = MagicMock()
    service._pending_embeddings.add(("entity", "old-world", None))

    getattr(worker, release)()

    assert service._search_service is None
    assert service._pending_embeddings == set()


def test_index_without_database_emits_nothing(worker):
    worker.db_service = None
    started = []
    errors = []
    worker.operation_started.connect(started.append)
    worker.error_occurred.connect(errors.append)

    worker.index_object("entity", "unavailable")

    assert started == []
    assert errors == []


def test_unsupported_type_reports_one_failure(worker):
    errors = []
    finished = []
    worker.error_occurred.connect(errors.append)
    worker.operation_finished.connect(finished.append)

    with patch.object(
        worker._semantic_index, "_get_search_service", return_value=MagicMock()
    ):
        worker.index_object("place", "unknown")

    assert errors == ["Failed to index place unknown."]
    assert finished == []
