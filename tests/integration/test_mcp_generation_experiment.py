"""Exercise queued experiment preparation, frozen trials and session revocation."""

import asyncio
import json
import sqlite3
import threading
from contextlib import closing

import pytest
from PySide6.QtCore import QMetaObject, Qt, QThread

from src.app.coordinators.mcp_coordinator import McpCoordinator
from src.core.entities import Entity
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.real_qt_invoke]


def test_queued_generation_experiment(qtbot, db_service, monkeypatch, tmp_path):
    from src.integrations.mcp import discovery
    from src.services import generation_experiments

    subject = Entity(name="Example", type="Character")
    db_service.insert_entity(subject)
    db_service.set_ai_generation_preferences({"rag_enabled": False})
    path = str(tmp_path / "world.kraken")
    with closing(sqlite3.connect(path)) as connection:
        db_service.require_connection().backup(connection)
    monkeypatch.setattr(
        discovery, "discovery_directory", lambda: tmp_path / "discovery"
    )
    monkeypatch.setattr(
        generation_experiments,
        "get_provider_settings_from_qsettings",
        lambda *_: {
            "generation_model": "local-test",
            "generate_url": "http://127.0.0.1:1234/v1/chat/completions",
            "embed_url": "http://127.0.0.1:1234/v1/embeddings",
        },
    )
    thread = QThread()
    worker = DatabaseWorker(path)
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    context = {
        "world_id": "test",
        "world_name": "Test",
        "database": path,
    }
    coordinator = McpCoordinator(lambda: context, lambda: worker.db_service, thread)
    thread.start()

    def call(tool, args):
        result = {}
        caller = threading.Thread(
            target=lambda: result.update(
                asyncio.run(coordinator._session.call(tool, args))
            )
        )
        caller.start()
        qtbot.waitUntil(lambda: bool(result), timeout=8000)
        caller.join()
        return result

    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000):
            QMetaObject.invokeMethod(
                worker, "initialize_db", Qt.ConnectionType.QueuedConnection
            )
        coordinator.set_scopes(["generation"])
        coordinator.enable()
        qtbot.waitUntil(
            lambda: coordinator.snapshot()["state"] == "Active", timeout=8000
        )
        result = call(
            "prepare_generation_experiment",
            {
                "kind": "entity",
                "target_id": subject.id,
                "task": "Describe",
                "idempotency_key": "prepare",
            },
        )
        assert result["status"] == "OK", result
        identifier = result["data"]["experiment_id"]
        qtbot.waitUntil(
            lambda: coordinator._experiments.entries[identifier]["state"]
            != "preparing",
            timeout=8000,
        )
        entry = coordinator._experiments.entries[identifier]
        assert entry["state"] == "ready", entry.get("error")
        baseline = dict(entry["baseline"])
        coordinator.invalidate()
        monkeypatch.setattr(
            coordinator._experiments,
            "_generate",
            lambda *_: {"raw_text": "Candidate", "presented_text": "Candidate"},
        )
        result = call(
            "start_generation_trial",
            {"experiment_id": identifier, "idempotency_key": "trial"},
        )
        trial = result["data"]["trial_id"]
        qtbot.waitUntil(
            lambda: entry["trials"][trial]["state"] == "completed", timeout=5000
        )
        result = call(
            "get_generation_trial", {"experiment_id": identifier, "trial_id": trial}
        )
        evidence = json.loads(result["data"]["content"])
        assert evidence["prompt"] == baseline
        assert evidence["raw_text"] == "Candidate"
        assert "generation_remaining" not in coordinator.snapshot()
    finally:
        coordinator.stop()
        qtbot.waitUntil(lambda: coordinator.snapshot()["state"] == "Off", timeout=5000)
        coordinator._experiments._pool.shutdown(wait=True)
        coordinator._poll.stop()
        with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
            QMetaObject.invokeMethod(
                worker, "cleanup", Qt.ConnectionType.QueuedConnection
            )
        thread.quit()
        assert thread.wait(5000)
