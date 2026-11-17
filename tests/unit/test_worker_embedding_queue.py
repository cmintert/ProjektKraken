"""Asynchronous queue, batching, stale-result and failure regressions."""

from threading import Event
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.core.entities import Entity
from src.services.worker import DatabaseWorker


@pytest.fixture
def indexing(qapp, qtbot, db_service, monkeypatch):
    provider = MagicMock()
    provider.get_model_name.return_value = "test:queue"
    provider.get_dimension.return_value = 3
    provider.embed.side_effect = lambda texts: np.ones((len(texts), 3))
    create = MagicMock(return_value=provider)
    monkeypatch.setattr("src.services.semantic_index_task.create_provider", create)
    worker = DatabaseWorker(":memory:")
    worker.db_service = db_service
    errors, finished = [], []
    worker.error_occurred.connect(errors.append)
    worker.index_rebuild_finished.connect(lambda *counts: finished.append(counts))
    yield worker, db_service, provider, create, errors, finished
    worker._semantic_index.reset_database()


def count(db):
    return (
        db.require_connection().execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    )


def test_mass_queue_is_deduplicated_and_bounded(qtbot, indexing):
    worker, db, provider, create, errors, _ = indexing
    entities = [Entity(name=f"Subject {i}", type="Person") for i in range(75)]
    for entity in entities:
        db.insert_entity(entity)
    identifiers = [entity.id for entity in entities]
    worker.index_object("entity", identifiers)
    worker.index_object("entity", identifiers)
    qtbot.waitUntil(lambda: count(db) == 75, timeout=5000)
    assert [len(call.args[0]) for call in provider.embed.call_args_list] == [32, 32, 11]
    create.assert_called_once()
    assert errors == []


def test_rebuild_and_updates_share_provider_and_skip_unchanged(qtbot, indexing):
    worker, db, provider, create, errors, finished = indexing
    entity = Entity(name="Subject", type="Person")
    db.insert_entity(entity)
    worker.index_object("entity", entity.id)
    qtbot.waitUntil(lambda: count(db) == 1, timeout=5000)
    worker.rebuild_search_index("all")
    worker.rebuild_search_index("all")
    qtbot.waitUntil(lambda: bool(finished), timeout=5000)
    assert finished == [(0, 1, 0)]
    provider.embed.assert_called_once()
    create.assert_called_once()
    assert errors == []


@pytest.mark.parametrize("mode", ["automatic", "rebuild"])
def test_deleted_during_inference_is_not_recreated(qtbot, indexing, mode):
    worker, db, provider, _, errors, finished = indexing
    entity = Entity(name="Subject", type="Person")
    db.insert_entity(entity)
    entered, release = Event(), Event()

    def blocked(texts):
        entered.set()
        assert release.wait(5)
        return np.ones((len(texts), 3))

    provider.embed.side_effect = blocked
    try:
        if mode == "rebuild":
            worker.rebuild_search_index("all")
        else:
            worker.index_object("entity", entity.id)
        qtbot.waitUntil(entered.is_set, timeout=5000)
        db.require_connection().execute(
            "DELETE FROM entities WHERE id = ?", (entity.id,)
        )
        db.require_connection().commit()
    finally:
        release.set()
    task = worker._semantic_index._task
    qtbot.waitUntil(lambda: not task.busy, timeout=5000)
    if mode == "rebuild":
        qtbot.waitUntil(lambda: bool(finished), timeout=5000)
    assert count(db) == 0
    assert errors == []


@pytest.mark.parametrize("failure", ["provider", "shape", "nan"])
def test_failure_is_terminal_and_explicit_retry_works(qtbot, indexing, failure):
    worker, db, provider, _, errors, finished = indexing
    entity = Entity(name="Subject", type="Person")
    db.insert_entity(entity)
    if failure == "provider":
        provider.embed.side_effect = RuntimeError("unavailable")
    elif failure == "shape":
        provider.embed.side_effect = lambda texts: np.ones((len(texts), 2))
    else:
        provider.embed.side_effect = lambda texts: np.full((len(texts), 3), np.nan)
    worker.rebuild_search_index("all")
    qtbot.waitUntil(lambda: bool(finished), timeout=5000)
    assert len(errors) == 1
    assert finished[0][2] == 1
    assert count(db) == 0
    provider.embed.side_effect = lambda texts: np.ones((len(texts), 3))
    worker.rebuild_search_index("all")
    qtbot.waitUntil(lambda: len(finished) == 2, timeout=5000)
    assert finished[1] == (1, 0, 0)
    assert count(db) == 1


def test_reset_cancels_rebuild_and_new_session_reuses_path(qtbot, indexing):
    worker, db, provider, _, errors, _ = indexing
    entity = Entity(name="Subject", type="Person")
    db.insert_entity(entity)
    entered, release = Event(), Event()

    def blocked(texts):
        entered.set()
        assert release.wait(5)
        return np.ones((len(texts), 3))

    provider.embed.side_effect = blocked
    worker.rebuild_search_index("all")
    qtbot.waitUntil(entered.is_set, timeout=5000)
    old = worker._semantic_index._task
    states = []
    old.state_changed.connect(states.append)
    worker._semantic_index.reset_database()
    assert states[-1]["state"] == "cancelled"
    assert old.cancelled.is_set()
    release.set()
    provider.embed.side_effect = lambda texts: np.ones((len(texts), 3))
    worker.index_object("entity", entity.id)
    qtbot.waitUntil(lambda: count(db) == 1, timeout=5000)
    assert worker._semantic_index._task.session != old.session
    assert errors == []


def test_unavailable_database_does_not_start_executor(indexing):
    worker, _, _, create, errors, finished = indexing
    worker.db_service = None
    worker.index_object("entity", "missing")
    worker.rebuild_search_index("all")
    assert worker._semantic_index._task is None
    create.assert_not_called()
    assert errors == ["Database not ready for index rebuild."]
    assert finished == []


def test_failed_batch_rolls_back_all_vectors(qtbot, indexing):
    worker, db, _, _, errors, finished = indexing
    first = Entity(id="a-first", name="First", type="Person")
    second = Entity(id="b-second", name="Second", type="Person")
    db.insert_entity(first)
    db.insert_entity(second)
    connection = db.require_connection()
    connection.execute(
        "CREATE TRIGGER reject_vectors BEFORE INSERT ON embeddings "
        "WHEN NEW.metadata LIKE '%Second%' BEGIN SELECT RAISE(ABORT, 'test'); END"
    )
    connection.commit()
    worker.rebuild_search_index("entity")
    qtbot.waitUntil(lambda: bool(finished), timeout=5000)
    assert len(errors) == 1
    assert count(db) == 0
    connection.execute("DROP TRIGGER reject_vectors")
    connection.commit()
    worker.rebuild_search_index("entity")
    qtbot.waitUntil(lambda: len(finished) == 2, timeout=5000)
    assert count(db) == 2


def test_tag_changes_during_inference_retry_current_text(qtbot, indexing):
    worker, db, provider, _, errors, _ = indexing
    entity = Entity(name="Subject", type="Person")
    db.insert_entity(entity)
    entered, release = Event(), Event()

    def blocked(texts):
        entered.set()
        assert release.wait(5)
        return np.ones((len(texts), 3))

    provider.embed.side_effect = blocked
    worker.index_object("entity", entity.id)
    qtbot.waitUntil(entered.is_set, timeout=5000)
    try:
        connection = db.require_connection()
        connection.execute(
            "INSERT INTO tags (id, name, created_at) VALUES ('test-tag', 'New tag', 0.0)"
        )
        connection.execute(
            "INSERT INTO entity_tags (entity_id, tag_id, created_at) VALUES (?, 'test-tag', 0.0)",
            (entity.id,),
        )
        connection.commit()
    finally:
        release.set()
    qtbot.waitUntil(lambda: count(db) == 1, timeout=5000)
    row = (
        db.require_connection()
        .execute(
            "SELECT text_snippet FROM embeddings WHERE object_id = ?", (entity.id,)
        )
        .fetchone()
    )
    assert "New tag" in row[0]
    assert provider.embed.call_count == 2
    assert errors == []
