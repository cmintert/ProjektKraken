"""Queued database ownership, UI session intent and context preservation."""

import asyncio
import threading

import pytest
from PySide6.QtCore import QMetaObject, Qt, QThread
from PySide6.QtTest import QSignalSpy

from src.app.coordinators.mcp_coordinator import McpCoordinator
from src.gui.widgets.mcp_access_widget import McpAccessWidget
from src.gui.widgets.settings_center import SettingsCenter
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.real_qt_invoke]


def test_queued_reads_and_stop_do_not_touch_main_thread_database(
    qtbot, tmp_path, monkeypatch
):
    from src.integrations.mcp import discovery

    monkeypatch.setattr(
        discovery, "discovery_directory", lambda: tmp_path / "discovery"
    )
    path = str(tmp_path / "world.kraken")
    thread = QThread()
    worker = DatabaseWorker(path)
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    context = {"world_id": "a", "world_name": "Saved world", "database": path}
    coordinator = McpCoordinator(
        lambda: dict(context), lambda: worker.db_service, thread
    )
    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000):
            QMetaObject.invokeMethod(
                worker, "initialize_db", Qt.ConnectionType.QueuedConnection
            )
        assert coordinator.snapshot()["state"] == "Off"
        coordinator.enable()
        qtbot.waitUntil(
            lambda: coordinator.snapshot()["state"] == "Active", timeout=8000
        )
        session = coordinator._session
        output = {}
        additional = {}

        def client():
            output.update(asyncio.run(session.call("get_active_world", {})))
            additional["overview"] = asyncio.run(session.call("get_world_overview", {}))
            additional["batch"] = asyncio.run(
                session.call(
                    "get_objects",
                    {
                        "objects": [{"kind": "entity", "id": "missing"}],
                        "detail": "compact",
                    },
                )
            )
            additional["browse"] = asyncio.run(session.call("browse_world", {}))

        caller = threading.Thread(target=client)
        caller.start()
        qtbot.waitUntil(lambda: "browse" in additional, timeout=5000)
        caller.join()
        assert output["data"]["name"] == "Saved world"
        assert additional["overview"]["data"]["counts"]["entity"]["total"] == 0
        assert (
            additional["batch"]["data"]["content"]["results"][0]["status"]
            == "NOT_FOUND"
        )
        assert additional["browse"]["data"]["done"]
        context["world_id"] = "b"
        qtbot.waitUntil(lambda: coordinator.snapshot()["state"] == "Off", timeout=5000)
        assert not session.active
    finally:
        coordinator.stop()
        qtbot.waitUntil(lambda: coordinator.snapshot()["state"] == "Off", timeout=5000)
        coordinator._poll.stop()
        with qtbot.waitSignal(worker.cleanup_finished, timeout=5000):
            QMetaObject.invokeMethod(
                worker, "cleanup", Qt.ConnectionType.QueuedConnection
            )
        thread.quit()
        assert thread.wait(5000)
    assert coordinator.snapshot()["available"] is False
    coordinator.enable()
    assert coordinator.snapshot()["state"] == "Off"
    assert coordinator._server is None


def test_session_form_is_independent_of_settings_drafts(qtbot, init_theme_manager):
    center = SettingsCenter()
    qtbot.addWidget(center)
    before = center.collect()
    form = McpAccessWidget(center)
    center.add_page("kraken", "Integrations", form)
    form.render_state(
        {
            "state": "Off",
            "world_name": "Northwatch",
            "message": "",
            "available": True,
            "activity": [],
        }
    )
    center.navigate("integrations.mcp")
    assert center.selected_target()[:2] == ("kraken", "Integrations")
    with qtbot.waitSignal(form.enable_requested):
        form.enable_button.click()
    assert center.collect() == before
    form.render_state(
        {
            "state": "Active",
            "world_name": "Northwatch",
            "message": "",
            "available": True,
            "activity": [],
        }
    )
    assert form.stop_button.isEnabled()
    assert not form.enable_button.isEnabled()
    center.search.setText("MCP")
    assert center.navigation.count() == 1


@pytest.fixture
def semantic_coordinator(qtbot, monkeypatch):
    """Observe coordinator intent without loading a model or using user discovery."""
    from src.integrations.mcp import discovery, server

    class Server:
        def __init__(self, session, discovery, ready):
            self.ready = ready

        def start(self):
            pass

        def stop(self):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(server, "LocalMcpServer", Server)
    monkeypatch.setattr(discovery, "SessionDiscovery", lambda: None)
    thread = QThread()
    thread.start()
    context = {"world_id": "world", "world_name": "World", "database": "saved.kraken"}
    coordinator = McpCoordinator(
        lambda: dict(context),
        lambda: None,
        thread,
        local_model=lambda: "installed-model",
    )
    coordinator._prepare.disconnect(coordinator._task.preparation.prepare)
    preparations = QSignalSpy(coordinator._prepare)
    yield coordinator, preparations, context
    coordinator.stop()
    coordinator._poll.stop()
    QMetaObject.invokeMethod(
        coordinator._task, "reset", Qt.ConnectionType.BlockingQueuedConnection
    )
    thread.quit()
    assert thread.wait(5000)


@pytest.mark.parametrize("scopes", [[], ["semantic"]])
def test_semantic_opt_in_prepares_once_after_secure_start(
    semantic_coordinator, qtbot, scopes
):
    coordinator, preparations, _ = semantic_coordinator
    coordinator.set_scopes(scopes)
    coordinator.enable()
    assert coordinator.snapshot()["state"] == "Starting"
    assert preparations.count() == 0
    coordinator._server.ready({"port": 1})
    qtbot.waitUntil(lambda: coordinator.snapshot()["state"] == "Active")
    assert preparations.count() == bool(scopes)
    if scopes:
        preparation = preparations.at(0)[0]
        assert preparation["model"] == "installed-model"
        assert not coordinator._expired(preparation["request_id"])
        assert coordinator.snapshot()["semantic_state"] == "preparing"
    coordinator._on_started({"generation": coordinator._session.generation, "port": 1})
    assert preparations.count() == bool(scopes)


def test_failed_start_does_not_prepare_semantics(semantic_coordinator, qtbot):
    coordinator, preparations, _ = semantic_coordinator
    coordinator.set_scopes(["semantic"])
    coordinator.enable()
    coordinator._server.ready({"error": "Secure startup rejected"})
    qtbot.waitUntil(lambda: coordinator.snapshot()["state"] == "Off")
    assert preparations.count() == 0


def test_saved_edits_refresh_automatically_and_ignore_old_preparation(
    semantic_coordinator, qtbot
):
    coordinator, preparations, _ = semantic_coordinator
    coordinator.set_scopes(["semantic"])
    coordinator.enable()
    coordinator._server.ready({"port": 1})
    qtbot.waitUntil(lambda: preparations.count() == 1)
    original = preparations.at(0)[0]
    coordinator._semantic_changed({**original, "state": "ready"})
    for _ in range(3):
        coordinator.invalidate()
    assert coordinator._expired(original["request_id"])
    coordinator._semantic_changed({**original, "state": "ready"})
    assert coordinator.snapshot()["semantic_state"] == "stale"
    qtbot.waitUntil(lambda: preparations.count() == 2, timeout=2000)
    latest = preparations.at(1)[0]
    assert latest["request_id"] != original["request_id"]
    coordinator._semantic_changed({**original, "state": "unavailable"})
    assert coordinator.snapshot()["semantic_state"] == "preparing"
    coordinator._semantic_changed({**latest, "state": "ready"})
    assert coordinator.snapshot()["semantic_state"] == "ready"


@pytest.mark.parametrize("reason", ["stop", "world_switch"])
def test_stop_cancels_pending_automatic_refresh(semantic_coordinator, qtbot, reason):
    coordinator, preparations, context = semantic_coordinator
    coordinator.set_scopes(["semantic"])
    coordinator.enable()
    coordinator._server.ready({"port": 1})
    qtbot.waitUntil(lambda: preparations.count() == 1)
    original = preparations.at(0)[0]
    coordinator._semantic_changed({**original, "state": "ready"})
    coordinator.invalidate()
    assert coordinator._semantic_refresh.isActive()
    if reason == "stop":
        coordinator.stop()
    else:
        context["world_id"] = "replacement"
        coordinator._check()
    coordinator._semantic_changed({**original, "state": "ready"})
    coordinator.prepare_semantic()
    assert not coordinator._semantic_refresh.isActive()
    assert coordinator.snapshot()["state"] == "Off"
    assert preparations.count() == 1 and coordinator._expired(original["request_id"])


def test_model_failure_waits_for_local_retry(semantic_coordinator, qtbot):
    coordinator, preparations, _ = semantic_coordinator
    coordinator.set_scopes(["semantic"])
    coordinator.enable()
    coordinator._server.ready({"port": 1})
    qtbot.waitUntil(lambda: preparations.count() == 1)
    coordinator._semantic_changed({**preparations.at(0)[0], "state": "unavailable"})
    coordinator.invalidate()
    assert not coordinator._semantic_refresh.isActive()
    coordinator.prepare_semantic()
    assert preparations.count() == 2


@pytest.mark.parametrize("semantic_state", ["preparing", "ready", "unavailable"])
def test_semantic_recovery_is_only_shown_when_needed(
    qtbot, init_theme_manager, semantic_state
):
    form = McpAccessWidget()
    qtbot.addWidget(form)
    form.scope_details.setChecked(True)
    form.render_state(
        {
            "state": "Active",
            "world_name": "World",
            "message": "",
            "available": True,
            "activity": [],
            "scopes": ["semantic"],
            "semantic_state": semantic_state,
        }
    )
    assert form.prepare_button.isHidden() is (semantic_state != "unavailable")
    assert form.prepare_button.isEnabled() is (semantic_state == "unavailable")
    assert "automatically" in form.scope_boxes["semantic"].toolTip()
    assert form.stop_button.isEnabled()
