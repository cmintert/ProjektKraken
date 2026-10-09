"""Automated KA-14 component replay through visible controls and real commands.

This harness uses the shared DB fixture, not the application's worker connection.
It proves UI/command persistence integration, not an unassisted human task.
"""

import sqlite3

import pytest
from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow, QWidget

from src.app.coordinators.feature_geometry_coordinator import FeatureGeometryCoordinator
from src.commands.base_command import CommandResult
from src.commands.feature_geometry_commands import ReplaceFeatureGeometryStatesCommand
from src.core.entities import Entity
from src.core.feature_geometry_state import resolve_feature_geometry
from src.core.map import Map
from src.core.marker import Marker
from src.gui.widgets.map_widget import MapWidget
from src.services.db_service import DatabaseService
from tests.unit.test_map_feature_actions import (
    click_feature,
    menu_action,
    open_toolbar_menu,
)

pytestmark = pytest.mark.ci_fast


class Timeline(QObject):
    playhead_time_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.time = 0.0

    def get_playhead_time(self):
        return self.time

    def move_to(self, date):
        self.time = date
        self.playhead_time_changed.emit(date)


class DataHandler(QObject):
    markers_ready = Signal(str, list)
    feature_geometry_states_ready = Signal(str, list)


class WorkerSignals(QObject):
    command_finished = Signal(CommandResult)


class GeometryWindow(QMainWindow):
    command_requested = Signal(object)


def test_visible_region_revision_at_date_apply_undo_redo_reopen(
    qtbot, db_service, tmp_path, init_theme_manager
):
    window = GeometryWindow()
    qtbot.addWidget(window)
    window.timeline = Timeline()
    window.data_handler = DataHandler()
    window.worker = WorkerSignals()
    window.map_widget = MapWidget(window)
    widget = window.map_widget
    widget.view.setViewport(QWidget())
    window.setCentralWidget(widget)
    image = QPixmap(600, 400)
    image.fill(Qt.GlobalColor.gray)
    image_path = tmp_path / "map.png"
    assert image.save(str(image_path))
    world_map = Map(name="Empty-world replay", image_path=str(image_path))
    location = Entity(name="Upper Rhine", type="location")
    db_service.insert_entity(location)
    db_service.insert_map(world_map)
    base = [{"x": 0.3, "y": 0.3}, {"x": 0.7, "y": 0.3}, {"x": 0.5, "y": 0.7}]
    marker = Marker(
        map_id=world_map.id,
        object_id=location.id,
        object_type="entity",
        x=0.5,
        y=0.5,
        label=location.name,
        feature_type="region",
        geometry=base,
    )
    db_service.insert_marker(marker)
    widget.set_maps([world_map])
    widget.select_map(world_map.id)
    assert widget.load_map(str(image_path))
    widget.add_marker(
        location.id,
        "entity",
        location.name,
        0.5,
        0.5,
        feature_type="region",
        geometry=base,
    )
    window.resize(1400, 800)
    window.show()
    qtbot.waitExposed(window)
    widget.view.fit_to_view()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    window.timeline.playhead_time_changed.connect(widget.on_time_changed)
    window.data_handler.markers_ready.emit(world_map.id, [marker.to_dict()])
    window.data_handler.feature_geometry_states_ready.emit(world_map.id, [])
    commands = []
    window.command_requested.connect(commands.append)

    window.timeline.move_to(150.0)
    item = widget.view.find_item_by_id(location.id)
    click_feature(widget, item)
    menu = open_toolbar_menu(widget, qtbot)
    action = menu_action(menu, "geometry")
    QTest.mouseClick(
        menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center()
    )
    assert coordinator.is_active
    assert widget.feature_geometry_edit_source.text().startswith("New state")
    editor = widget.view._vertex_editor
    handle = editor._vertex_handles[0]
    start = widget.view.mapFromScene(handle.scenePos())
    end = widget.view.mapFromScene(QPointF(210.0, 160.0))
    QTest.mousePress(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(widget.view.viewport(), end)
    QTest.mouseRelease(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert coordinator.edit_status()["dirty"]
    QTest.mouseClick(widget.btn_confirm_map_edit, Qt.MouseButton.LeftButton)
    assert len(commands) == 1
    command = commands[0]
    assert isinstance(command, ReplaceFeatureGeometryStatesCommand)
    result = command.execute(db_service)
    assert result.success
    result.data["command_id"] = command.command_id
    # Data loading is deliberately driven by independent test snapshots.
    result.data["effects"] = []
    window.worker.command_finished.emit(result)
    qtbot.waitUntil(lambda: not coordinator.is_active)
    states = db_service.feature_geometry_repo.get_states(marker.id)
    assert len(states) == 1 and states[0].effective_date == 150.0
    revised = states[0].geometry
    assert revised != base
    assert db_service.get_marker(marker.id).geometry == base
    window.data_handler.feature_geometry_states_ready.emit(
        world_map.id, [state.to_dict() for state in states]
    )
    window.timeline.move_to(149.0)
    assert sorted((p["x"], p["y"]) for p in item._geometry) == sorted(
        (p["x"], p["y"]) for p in base
    )
    window.timeline.move_to(150.0)
    assert sorted((p["x"], p["y"]) for p in item._geometry) == sorted(
        (p["x"], p["y"]) for p in revised
    )

    # At the exact date the same state is edited, then Escape discards local work.
    click_feature(widget, item)
    menu = open_toolbar_menu(widget, qtbot)
    action = menu_action(menu, "geometry")
    QTest.mouseClick(
        menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center()
    )
    assert coordinator._session["target_type"] == "state"
    QTest.keyClick(widget.view, Qt.Key.Key_Escape)
    assert not coordinator.is_active
    assert len(commands) == 1
    assert command.undo(db_service).success
    assert db_service.feature_geometry_repo.get_states(marker.id) == []
    assert command.execute(db_service).success

    # Reopen a durable SQLite snapshot using SQLite's supported backup operation.
    replay_path = tmp_path / "reopened.kraken"
    with sqlite3.connect(replay_path) as destination:
        db_service.require_connection().backup(destination)
    reopened = DatabaseService(str(replay_path))
    reopened.connect()
    try:
        saved_marker = reopened.get_marker(marker.id)
        saved_states = reopened.feature_geometry_repo.get_states(marker.id)
        assert saved_marker.object_id == location.id
        assert (
            resolve_feature_geometry(saved_marker, saved_states, 149.0).geometry == base
        )
        assert (
            resolve_feature_geometry(saved_marker, saved_states, 150.0).geometry
            == revised
        )
    finally:
        reopened.close()
