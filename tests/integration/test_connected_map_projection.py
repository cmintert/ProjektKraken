"""Read-only worker delivery, generation guards and actual overlay integration."""

import json
from threading import Event

import pytest
from PySide6.QtCore import QObject, QPointF, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu

from src.app.connected_map_composition import loaded_projection_target
from src.app.coordinators.map_projection_coordinator import MapProjectionCoordinator
from src.core.map import MapLayerNode
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
    valid = snapshot().markers[0]
    valid.id, valid.object_id = "valid", "another-object"
    db_service.insert_marker(valid)
    connection = db_service.require_connection()
    connection.execute(
        "INSERT INTO moving_features (id,marker_id,t_start,t_end,trajectory) "
        "VALUES ('bad','point',0,1,?)",
        (json.dumps({"datetimes": [0], "coordinates": [[0.5]]}),),
    )
    connection.commit()
    before = list(connection.iterdump())
    frame = read_projection(db_service).frame("new", 0)
    assert frame["issues"]
    assert [point["source_id"] for point in frame["points"]] == ["valid"]
    assert list(connection.iterdump()) == before


def test_projection_target_requires_the_selected_canvas(authoring):
    widget, _, _, _, _ = authoring
    assert loaded_projection_target(widget) == "source"
    record = next(record for record in widget.maps_data if record.id == "parent")
    record.image_path += ".missing"
    widget.select_map("parent")
    assert widget.get_selected_map_id() == "parent"
    assert widget.view.pixmap_item is not None
    assert loaded_projection_target(widget) is None


def test_absolute_layer_zoom_uses_source_pixels(tmp_path):
    world_root = tmp_path / "world-assets"
    world_root.mkdir()
    db = DatabaseService(str(tmp_path / "external.kraken"), world_root=world_root)
    db.connect()
    data = snapshot()
    for record in data.maps:
        if record.id in ("old", "new"):
            size = (4000, 2000) if record.id == "old" else (1000, 500)
            record.image_path = f"{record.id}.png"
            image = QImage(*size, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.gray)
            assert image.save(str(world_root / record.image_path))
        if record.id == "old":
            record.layers = MapLayerNode(
                "Layers", children=[MapLayerNode("Point", id="object", max_zoom=0.5)]
            )
        db.insert_map(record)
    db.insert_marker(data.markers[0])
    try:
        projector = read_projection(db)
        assert projector.frame("new", 0, zoom=1)["points"]
        assert not projector.frame("new", 0, zoom=3)["points"]
    finally:
        db.close()


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
        assert json.loads(result.args[0]["snapshot"])["markers"]
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


def test_dated_geometry_reader_and_overlay_preserve_every_saved_row(authoring):
    from src.core.feature_geometry_state import FeatureGeometryState
    from tests.unit.test_map_geometry_projection import geometry_snapshot

    widget, handler, commands, db, _ = authoring
    data = geometry_snapshot()
    image = widget.maps_data[0].image_path
    for record in data.maps:
        record.image_path = image
        db.insert_map(record)
    for marker in data.markers:
        db.insert_marker(marker)
    state = FeatureGeometryState("shape", 10, data.markers[0].geometry, 0.2, 0.5)
    db.feature_geometry_repo.replace_marker_states("shape", [state])
    handler.on_maps_ready(db.get_all_maps())
    widget.select_map("new")
    before = list(db.require_connection().iterdump())
    frame = read_projection(db).frame("new", 10)
    assert frame["geometries"][0]["state_id"] == state.id
    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    overlay.display(frame)
    assert len(overlay.items) == 1
    item = overlay.items[0]
    width, height = (
        widget.view.pixmap_item.boundingRect().width(),
        widget.view.pixmap_item.boundingRect().height(),
    )
    assert item.path().contains(QPointF(0.2 * width, 0.1 * height))
    assert item.path().contains(QPointF(0.8 * width, 0.5 * height))
    assert not item.path().contains(QPointF(0.2 * width, 0.375 * height))  # Hole.
    assert not item.path().contains(QPointF(0.5 * width, 0.5 * height))  # Split gap.
    item.setSelected(True)
    item.setFocus()
    widget.view.setFocus()
    QTest.keyClick(widget.view.viewport(), Qt.Key.Key_Delete)
    assert not commands
    assert list(db.require_connection().iterdump()) == before
    pending = []
    widget.edit_transition_handler = lambda reason, continuation: pending.append(
        continuation
    )
    overlay.source_requested.connect(widget.select_map)
    item.activate()
    assert widget.get_selected_map_id() == "new" and pending
    pending[0]()
    assert widget.get_selected_map_id() == "old"
    assert list(db.require_connection().iterdump()) == before


def test_geometry_calculation_leaves_database_thread_available(
    authoring, tmp_path, qtbot, monkeypatch
):
    from src.services.map_projection import MapProjector

    widget, _, _, _, _ = authoring
    path = tmp_path / "parallel.kraken"
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

    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    coordinator = MapProjectionCoordinator(
        overlay, thread, database, lambda: str(path), lambda: "new", lambda: 0
    )
    probe = MapProjectionReader(database)
    probe.moveToThread(thread)
    thread.finished.connect(probe.deleteLater)
    requests = Requests()
    requests.run.connect(probe.run, Qt.ConnectionType.QueuedConnection)
    closer = ConnectionOwner(holder)
    closer.moveToThread(thread)
    thread.finished.connect(closer.deleteLater)
    requests.close.connect(closer.close, Qt.ConnectionType.QueuedConnection)
    entered, release = Event(), Event()
    original = MapProjector.frame

    def blocked(self, *args, **kwargs):
        assert QThread.currentThread() != thread
        entered.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MapProjector, "frame", blocked)
    thread.start()
    try:
        overlay.enabled = True
        coordinator.refresh()
        coordinator.send()
        qtbot.waitUntil(entered.is_set)
        # A second real DB request completes while the CPU stage is held.
        with qtbot.waitSignal(probe.completed) as result:
            requests.run.emit(
                {
                    "token": 20,
                    "world": str(path),
                    "revision": 1,
                    "target": "new",
                    "date": 0,
                    "zoom": 1,
                    "include_detail": False,
                }
            )
        assert result.args[0]["snapshot"]
        assert not overlay.items
        release.set()
        qtbot.waitUntil(lambda: bool(overlay.items))
    finally:
        release.set()
        coordinator.shutdown()
        with qtbot.waitSignal(closer.closed):
            requests.close.emit()
        thread.quit()
        assert thread.wait(5000)


def test_coordinator_coalesces_and_rejects_old_date_world_and_disabled_replies(
    authoring, request
):
    widget, _, _, db, _ = authoring
    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    # No thread starts: inspect serializable requests without executing them.
    thread = QThread()
    coordinator = MapProjectionCoordinator(
        overlay, thread, lambda: db, lambda: ":memory:", lambda: "new", lambda: 0
    )
    request.addfinalizer(coordinator.shutdown)
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


def test_scrubbing_sends_regular_updates_and_preserves_same_map_frame(authoring, qtbot):
    widget, _, _, db, _ = authoring
    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    overlay.enabled = True
    overlay.display(read_frame())
    date = 0
    thread = QThread()
    coordinator = MapProjectionCoordinator(
        overlay, thread, lambda: db, lambda: ":memory:", lambda: "new", lambda: date
    )
    coordinator.requested.disconnect(coordinator.reader.run)
    dates = []

    def complete(request):
        dates.append(request["date"])
        coordinator.completed({"token": request["token"], **read_frame()})

    def tick():
        nonlocal date
        date += 1
        coordinator.refresh_playhead()

    coordinator.requested.connect(complete)
    timer = QTimer()
    timer.timeout.connect(tick)
    try:
        tick()
        assert overlay.items
        timer.start(5)
        qtbot.waitUntil(lambda: len(dates) >= 2)
        assert dates[1] > dates[0]
        assert overlay.items
        coordinator.refresh()
        assert not overlay.items
    finally:
        timer.stop()
        coordinator.shutdown()
