"""Read-only worker delivery, generation guards and actual overlay integration."""

import json

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QMenu

from src.app.coordinators.map_projection_coordinator import MapProjectionCoordinator
from src.gui.widgets.map.connected_features import ConnectedFeatures
from src.services.db_service import DatabaseService
from src.services.map_projection_reader import MapProjectionReader, read_projection
from tests.integration.test_map_hierarchy_authoring import authoring as _authoring
from tests.unit.test_map_projection import snapshot

pytestmark = pytest.mark.ci_fast
authoring = _authoring


def test_reader_never_writes_even_when_trajectory_is_invalid(db_service):
    data = snapshot()
    for record in data.maps:
        db_service.insert_map(record)
    for marker in data.markers:
        db_service.insert_marker(marker)
    connection = db_service.require_connection()
    connection.execute(
        "INSERT INTO moving_features (id,marker_id,t_start,t_end,trajectory) VALUES ('bad','point',0,1,'{}')"
    )
    connection.commit()
    before = list(connection.iterdump())
    projector = read_projection(db_service)
    assert projector.frame("new", 0)["issues"]
    assert list(connection.iterdump()) == before


class Requests(QObject):
    run = Signal(dict)
    close = Signal()


class ConnectionOwner(QObject):
    closed = Signal()

    def __init__(self, connections):
        super().__init__()
        self.connections = connections

    @Slot()
    def close(self):
        for db in self.connections:
            db.close()
        self.closed.emit()


def test_reader_executes_on_owner_thread_and_sends_only_snapshots(
    tmp_path, qtbot, db_service
):
    path = tmp_path / "world.kraken"
    # A separate connection is constructed and owned on the adapter's thread.
    seed = DatabaseService(str(path))
    seed.connect()
    data = snapshot()
    for record in data.maps:
        seed.insert_map(record)
    for marker in data.markers:
        seed.insert_marker(marker)
    seed.close()
    thread = QThread()
    holder = []

    def database():
        assert QThread.currentThread() == thread
        if not holder:
            db = DatabaseService(str(path))
            db.connect()
            holder.append(db)
        return holder[0]

    reader = MapProjectionReader(database)
    reader.moveToThread(thread)
    thread.finished.connect(reader.deleteLater)
    requests = Requests()
    closer = ConnectionOwner(holder)
    closer.moveToThread(thread)
    thread.finished.connect(closer.deleteLater)
    requests.close.connect(closer.close, Qt.ConnectionType.QueuedConnection)
    requests.run.connect(reader.run, Qt.ConnectionType.QueuedConnection)
    thread.start()
    try:
        with qtbot.waitSignal(reader.completed) as result:
            requests.run.emit(
                {
                    "token": 1,
                    "world": str(path),
                    "revision": 1,
                    "target": "new",
                    "date": 0,
                    "zoom": 1,
                    "include_detail": False,
                }
            )
        assert result.args[0]["points"]
        json.dumps(result.args[0], allow_nan=False)
    finally:
        with qtbot.waitSignal(closer.closed):
            requests.close.emit()
        thread.quit()
        assert thread.wait(5000)


def test_overlay_is_opt_in_read_only_and_does_not_touch_local_features(
    authoring, qtbot
):
    widget, _, commands, _, _ = authoring
    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    assert not overlay.enabled
    frame = read_frame()
    overlay.display(frame)
    assert len(overlay.items) == 1
    item = overlay.items[0]
    assert not item.flags() & item.GraphicsItemFlag.ItemIsMovable
    assert "source" in item.toolTip()
    sources = []
    overlay.source_requested.connect(sources.append)
    item.activate()
    assert sources == ["old"]
    local = dict(widget.view.footprint_names())
    overlay.clear()
    assert widget.view.footprint_names() == local
    assert not commands
    menu = QMenu(widget)
    overlay.populate(menu)
    actions = [a for a in menu.actions() if a.isCheckable()]
    actions[0].trigger()
    assert overlay.enabled


def read_frame():
    from src.services.map_projection import MapProjector

    return MapProjector(snapshot()).frame("new", 0)


def test_coordinator_coalesces_and_rejects_old_date_world_and_disabled_replies(
    authoring,
):
    widget, _, _, db, _ = authoring
    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    # No thread starts: inspect serializable requests without executing them.
    thread = QThread()
    coordinator = MapProjectionCoordinator(
        overlay, thread, lambda: db, lambda: ":memory:", lambda: "new", lambda: 0
    )
    coordinator.requested.disconnect(coordinator.reader.run)
    requests = []
    coordinator.requested.connect(requests.append)
    overlay.enabled = True
    coordinator.refresh()
    coordinator.send()
    assert len(requests) == 1
    old_token = coordinator.token
    coordinator.refresh()
    coordinator.send()
    assert len(requests) == 1
    coordinator.completed({"token": old_token, **read_frame()})
    assert not overlay.items
    coordinator.send()
    assert len(requests) == 2
    overlay.enabled = False
    coordinator.completed({"token": coordinator.token, **read_frame()})
    assert not overlay.items
    coordinator.timer.stop()
