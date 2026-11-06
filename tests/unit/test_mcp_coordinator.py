"""Queued database ownership, UI session intent and context preservation."""

import asyncio
import threading

import pytest
from PySide6.QtCore import QMetaObject, Qt, QThread

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
