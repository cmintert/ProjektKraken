"""Foreground commands remain available during blocked background inference."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread

import numpy as np
import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal

from src.commands.entity_commands import UpdateEntityCommand
from src.core.entities import Entity
from src.core.events import Event as LoreEvent
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.integration, pytest.mark.real_qt_invoke]


class Requests(QObject):
    index = Signal(str, object, list)
    rebuild = Signal(str, list)
    entity = Signal(str)
    event = Signal(str)
    command = Signal(object)
    cleanup = Signal()
    refresh = Signal()


class BlockingProvider:
    def __init__(self):
        self.entered = Event()
        self.release = Event()
        self.calls = []
        self.threads = []

    def get_model_name(self):
        self.threads.append(QThread.currentThread())
        return "test:blocked"

    def get_dimension(self):
        return 3

    def embed(self, texts):
        self.calls.append(texts)
        self.threads.append(QThread.currentThread())
        self.entered.set()
        assert self.release.wait(10), "test did not release inference"
        return np.ones((len(texts), 3), dtype=np.float32)


@pytest.fixture
def running_worker(qapp, qtbot, db_service, tmp_path, monkeypatch):
    entity = Entity(name="Original", type="Person")
    event = LoreEvent(name="Occurrence", lore_date=1.0)
    db_service.insert_entity(entity)
    db_service.insert_event(event)
    path = tmp_path / "index.kraken"
    with sqlite3.connect(path) as destination:
        db_service.require_connection().backup(destination)
    provider = BlockingProvider()
    monkeypatch.setattr(
        "src.services.semantic_index_task.create_provider", lambda **kwargs: provider
    )
    worker = DatabaseWorker(str(path), {"UpdateEntityCommand": UpdateEntityCommand})
    thread = QThread()
    worker.moveToThread(thread)
    requests = Requests()
    for signal, slot in (
        (requests.index, worker.index_object),
        (requests.rebuild, worker.rebuild_search_index),
        (requests.entity, worker.load_entity_details),
        (requests.event, worker.load_event_details),
        (requests.command, worker.run_command),
        (requests.cleanup, worker.cleanup),
        (requests.refresh, worker.refresh_ai_settings),
    ):
        signal.connect(slot, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(worker.initialize_db, Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(worker.deleteLater)
    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000) as initialized:
            thread.start()
        assert initialized.args == [True]
        yield worker, requests, provider, path, entity, event, thread
    finally:
        provider.release.set()
        try:
            with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
                requests.cleanup.emit()
        finally:
            thread.quit()
            assert thread.wait(5000)


@pytest.mark.parametrize("mode", ["automatic", "rebuild"])
def test_details_and_save_complete_before_inference(qapp, qtbot, running_worker, mode):
    worker, requests, provider, path, entity, event, thread = running_worker
    if mode == "automatic":
        requests.index.emit("entity", [entity.id], [])
    else:
        requests.rebuild.emit("all", [])
    qtbot.waitUntil(provider.entered.is_set, timeout=5000)
    with qtbot.waitSignal(worker.entity_details_loaded, timeout=2000) as loaded:
        requests.entity.emit(entity.id)
    assert loaded.args[0].name == "Original"
    with qtbot.waitSignal(worker.event_details_loaded, timeout=2000):
        requests.event.emit(event.id)
    command = UpdateEntityCommand(entity.id, {"name": "Edited during inference"})
    with qtbot.waitSignal(worker.command_finished, timeout=2000) as saved:
        requests.command.emit(
            {"type": "UpdateEntityCommand", "data": command.to_dict()}
        )
    assert saved.args[0].success
    assert not provider.release.is_set()
    with qtbot.waitSignal(worker.entity_details_loaded, timeout=2000) as loaded:
        requests.entity.emit(entity.id)
    assert loaded.args[0].name == "Edited during inference"
    provider.release.set()

    def latest_vector_saved():
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT text_snippet FROM embeddings WHERE object_id = ?", (entity.id,)
            ).fetchone()
            return row is not None and "Edited during inference" in row[0]

    qtbot.waitUntil(latest_vector_saved, timeout=5000)
    assert all(t != thread and t != qapp.thread() for t in provider.threads)


def test_cleanup_does_not_wait_for_inference(qtbot, running_worker, monkeypatch):
    worker, requests, provider, path, entity, _, _ = running_worker
    executors = []

    def capture_executor(**kwargs):
        executor = ThreadPoolExecutor(**kwargs)
        executors.append(executor)
        return executor

    monkeypatch.setattr(
        "src.services.semantic_index_task.ThreadPoolExecutor", capture_executor
    )
    requests.index.emit("entity", [entity.id], [])
    qtbot.waitUntil(provider.entered.is_set, timeout=5000)
    with qtbot.waitSignal(worker.cleanup_finished, timeout=2000):
        requests.cleanup.emit()
    assert not provider.release.is_set()
    provider.release.set()
    # Joining the executor also waits for the future's completion callback.
    retired = Thread(target=executors[0].shutdown, daemon=True)
    retired.start()
    qtbot.waitUntil(lambda: not retired.is_alive(), timeout=5000)
    # Round-trip through the worker after any queued result has been posted.
    with qtbot.waitSignal(worker.cleanup_finished, timeout=2000):
        requests.cleanup.emit()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
