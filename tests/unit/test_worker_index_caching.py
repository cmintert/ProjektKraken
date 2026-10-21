"""Search model reuse and worker rebuild delivery regressions."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.search_service import IndexRebuildCounts, IndexRebuildResult
from src.services.worker import DatabaseWorker


@pytest.fixture
def worker():
    worker = DatabaseWorker("test.db")
    worker.db_service = MagicMock()
    return worker


def test_index_and_rebuild_share_one_search_service(worker):
    search = MagicMock()
    search.rebuild_index.return_value = IndexRebuildResult(
        per_type={"entity": IndexRebuildCounts(indexed=3)}
    )
    finished = []
    worker.index_rebuild_finished.connect(
        lambda indexed, unchanged, failed: finished.append((indexed, unchanged, failed))
    )

    with patch(
        "src.services.search_service.create_search_service", return_value=search
    ) as create:
        worker.index_object("entity", "one")
        worker.index_object("event", "two", ["private"])
        worker.rebuild_search_index("all")

    create.assert_called_once()
    search.index_entity.assert_called_once_with("one", None)
    search.index_event.assert_called_once_with("two", ["private"])
    assert search.rebuild_index.call_args.kwargs["object_types"] == ["entity", "event"]
    assert finished == [(3, 0, 0)]


def test_rebuild_import_error_emits_one_error_and_terminal_count(worker):
    errors = []
    finished = []
    worker.error_occurred.connect(errors.append)
    worker.index_rebuild_finished.connect(
        lambda indexed, unchanged, failed: finished.append((indexed, unchanged, failed))
    )
    with patch.object(
        worker._semantic_index,
        "_get_search_service",
        side_effect=ImportError("sentence-transformers unavailable\ninstall it"),
    ):
        worker.rebuild_search_index("all")

    assert errors == ["sentence-transformers unavailable"]
    assert finished == [(0, 0, 1)]


def test_rebuild_without_database_reports_error_without_terminal_count(worker):
    worker.db_service = None
    errors = []
    finished = []
    worker.error_occurred.connect(errors.append)
    worker.index_rebuild_finished.connect(lambda *counts: finished.append(counts))

    worker.rebuild_search_index("all")

    assert errors == ["Database not ready for index rebuild."]
    assert finished == []
