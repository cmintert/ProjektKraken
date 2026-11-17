"""Cached playback tests for the dated geometry coordinator."""

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QObject, QPointF, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from src.app.coordinators.feature_geometry_coordinator import (
    FeatureGeometryCoordinator,
)
from src.commands.base_command import CommandResult
from src.commands.feature_geometry_commands import (
    ReplaceFeatureGeometryStatesCommand,
    UpdateFeatureBaseGeometryCommand,
)
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map
from src.core.marker import Marker
from src.core.region_geometry import RegionPolygon
from src.core.theme_manager import ThemeManager
from src.gui.utils.action_label_metrics import action_label_geometry
from src.gui.widgets.map_widget import MapWidget


def _square(low, high):
    return RegionPolygon(((low, low), (high, low), (high, high), (low, high)))


@pytest.mark.ci_fast
@pytest.mark.parametrize("theme", list(json.loads(Path("themes.json").read_text())))
def test_smooth_path_previews_editable_points_and_saves_only_on_confirm(
    qtbot, tmp_path, monkeypatch, init_theme_manager, db_service, qapp, theme
):
    window = _Window()
    widget = MapWidget()
    widget.view.setViewport(QWidget())
    qtbot.addWidget(widget)
    window.map_widget = widget
    monkeypatch.setattr(widget, "get_selected_map_id", lambda: "map")
    manager = ThemeManager()
    manager.apply_theme(qapp, Path("src/resources/main.qss").read_text())
    manager.set_theme(theme, qapp, persist=False)
    widget.setFixedWidth(320)
    widget.resize(320, 700)
    widget.show()
    widget.activateWindow()
    image = tmp_path / "map.png"
    pixmap = QPixmap(400, 300)
    pixmap.fill(Qt.GlobalColor.white)
    assert pixmap.save(str(image))
    assert widget.view.load_map(str(image))

    original = [
        {"x": 0.125, "y": 0.25},
        {"x": 0.625, "y": 0.25},
        {"x": 0.625, "y": 0.75},
    ]
    expected = [
        original[0],
        {"x": 0.5, "y": 0.25},
        {"x": 0.625, "y": 0.375},
        original[-1],
    ]
    snapshot = {**_marker_snapshot(), "geometry": original, "label": "Road"}
    widget.view.add_marker(
        "object", "entity", "Road", 0.5, 0.5, feature_type="path", geometry=original
    )
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    coordinator.on_markers_ready("map", [snapshot])
    coordinator.on_states_ready("map", [])
    window.timeline.time = 1220
    db_service.insert_map(Map(id="map", name="Map", image_path=str(image)))
    db_service.insert_marker(Marker.from_dict(snapshot))
    commands = []
    window.command_requested.connect(commands.append)
    widget.feature_actions.select("object", "canvas")
    menu = QMenu(widget)
    widget.feature_actions.populate(menu)
    edit = next(a for a in menu.actions() if a.text() == "Edit path at current date")

    button = widget.btn_smooth_path
    assert not button.isVisible()
    edit.trigger()
    qapp.processEvents()
    assert button.isVisible() and button.isEnabled()
    assert action_label_geometry(button).fits
    assert widget.feature_geometry_edit_strip.rect().contains(button.geometry())
    button.setFocus()
    qtbot.waitUntil(button.hasFocus)
    qtbot.keyClick(button, Qt.Key.Key_Return)
    item = widget.view.feature_items["object"]
    assert item._geometry == expected
    assert len(widget.view._vertex_editor._vertex_handles) == 4
    assert not commands
    qtbot.keyClick(widget.view, Qt.Key.Key_Escape)
    assert item._geometry == original
    assert not button.isVisible()
    assert not commands

    edit.trigger()
    widget.set_feature_geometry_edit_pending(True)
    assert button.isVisible() and not button.isEnabled()
    widget.set_feature_geometry_edit_pending(False)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert item._geometry == expected
    widget.view.setFocus()
    qtbot.keyClick(widget.view, Qt.Key.Key_Return)
    assert len(commands) == 1
    command = commands[0]
    assert command.execute(db_service).success
    assert db_service.get_marker("marker").geometry == original
    states = db_service.feature_geometry_repo.get_states("marker")
    assert [(state.effective_date, state.geometry) for state in states] == [
        (1220, expected)
    ]
    assert command.undo(db_service).success
    assert db_service.feature_geometry_repo.get_states("marker") == []


@pytest.mark.ci_fast
@pytest.mark.parametrize("target_type", ["base", "state", "new_state"])
@pytest.mark.parametrize("theme", list(json.loads(Path("themes.json").read_text())))
@pytest.mark.parametrize("cutter_kind", ["region", "drawn"])
def test_region_cut_controls_copy_cutter_at_the_fixed_edit_date(
    qtbot,
    tmp_path,
    monkeypatch,
    init_theme_manager,
    db_service,
    target_type,
    theme,
    qapp,
    cutter_kind,
):
    window = _Window()
    widget = MapWidget()
    widget.view.setViewport(QWidget())
    qtbot.addWidget(widget)
    window.map_widget = widget
    monkeypatch.setattr(widget, "get_selected_map_id", lambda: "map")
    tm = ThemeManager()
    tm.apply_theme(qapp, Path("src/resources/main.qss").read_text())
    tm.set_theme(theme, qapp, persist=False)
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
        qapp.setFont(QFont("Segoe UI", 10))
    widget.setFixedWidth(320)
    widget.resize(320, 1050)
    widget.show()
    image = tmp_path / "map.png"
    pixmap = QPixmap(600, 600)
    pixmap.fill(Qt.GlobalColor.white)
    assert pixmap.save(str(image))
    assert widget.view.load_map(str(image))
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()

    target = _square(0.1, 0.9)
    dated_lake = _square(0.4, 0.6)
    base_lake = _square(0.3, 0.7)
    _add_test_regions(widget, coordinator, target, base_lake)
    db_service.insert_map(Map(id="map", name="Map", image_path=str(image)))
    for marker_id in ("marker", "lake-marker"):
        db_service.insert_marker(
            Marker.from_dict(coordinator.marker_snapshot("map", marker_id))
        )
    lake_states = db_service.feature_geometry_repo.replace_marker_states(
        "lake-marker",
        [FeatureGeometryState("lake-marker", 1220, dated_lake.to_geometry(), 0.5, 0.5)],
    )
    target_states = [
        FeatureGeometryState("marker", 1250, target.to_geometry(), 0.5, 0.5)
    ]
    if target_type == "state":
        target_states.append(
            FeatureGeometryState("marker", 1220, target.to_geometry(), 0.5, 0.5)
        )
    before = db_service.feature_geometry_repo.replace_marker_states(
        "marker", target_states
    )
    coordinator.on_states_ready("map", [*before, *lake_states])
    original_cutter = db_service.get_marker("lake-marker").to_dict()
    commands = []
    window.command_requested.connect(commands.append)
    window.timeline.time = 1220
    if target_type == "base":
        coordinator._start_session(
            "map",
            "marker",
            coordinator.marker_snapshot("map", "marker"),
            "base",
            {},
            before,
        )
    else:
        # Exercise the visible selected-feature route, not just the core overlay.
        widget.feature_actions.select("object", "canvas")
        widget.feature_geometry_edit_requested.emit("object")
    window.timeline.time = 1200
    coordinator.on_playhead_changed(1200)
    editor = widget.region_cut_controls
    assert editor.start.isVisible()
    assert editor.start.text() == "Cut this region"
    qtbot.keyClick(editor.start, Qt.Key.Key_Space)
    assert editor.active
    assert editor.context.text() == "Cutting Region only"
    qapp.processEvents()
    assert not editor.preview.isEnabled()
    for button in (editor.draw, editor.pick, editor.preview, editor.cancel):
        if button.isVisible():
            assert action_label_geometry(button).fits
            assert editor.rect().contains(button.geometry())
    expected_cutter = (
        (base_lake if target_type == "base" else dated_lake)
        if cutter_kind == "region"
        else _square(0.2, 0.4)
    )

    def prepare_cutter():
        button = editor.pick if cutter_kind == "region" else editor.draw
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert editor.preview.isVisible() and not editor.preview.isEnabled()
        assert action_label_geometry(editor.preview).fits
        if cutter_kind == "region":
            assert editor.regions.itemText(0) == "Lake"
            editor.regions.setCurrentIndex(0)
            assert editor.regions.currentData() == expected_cutter.to_geometry()
            assert editor.message.text() == (
                "Remove the overlap with Lake from Region. Lake stays unchanged."
            )
        else:
            assert "Draw the area to remove from Region" in editor.message.text()
            widget.view._snapping_manager.enabled = False
            for x, y in expected_cutter.outer:
                assert editor.handle_mouse_press(QPointF(x * 600, y * 600))

    prepare_cutter()
    qtbot.mouseClick(editor.preview, Qt.MouseButton.LeftButton)
    assert editor.use.isEnabled()
    cutter_name = "Lake" if cutter_kind == "region" else "the drawn area"
    assert (
        f"Region after removing the overlap with {cutter_name}" in editor.message.text()
    )
    qapp.processEvents()
    assert editor.use.hasFocus()
    for button in (editor.use, editor.cancel):
        assert action_label_geometry(button).fits
        assert editor.rect().contains(button.geometry())
    evidence = os.environ.get("KRT165_EVIDENCE_DIR")
    if evidence and target_type == "new_state":
        output = Path(evidence)
        output.mkdir(parents=True, exist_ok=True)
        assert widget.grab().save(str(output / f"{theme}-320-{cutter_kind}-cut.png"))
    assert not widget.is_active_map_session_valid()
    assert widget.view.feature_items["object"]._geometry == target.to_geometry()
    qtbot.keyClick(widget.view, Qt.Key.Key_Escape)
    assert not editor.active
    assert coordinator.is_active and not commands

    qtbot.mouseClick(editor.start, Qt.MouseButton.LeftButton)
    prepare_cutter()
    qtbot.mouseClick(editor.preview, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(editor.use, Qt.MouseButton.LeftButton)
    assert not commands
    assert len(widget.view._vertex_editor._vertex_handles) == 8
    qtbot.keyClick(widget.view, Qt.Key.Key_Return)
    assert len(commands) == 1
    command = commands[0]
    assert command.execute(db_service).success
    if target_type == "base":
        saved_geometry = db_service.get_marker("marker").geometry
    else:
        saved_geometry = next(
            state.geometry
            for state in db_service.feature_geometry_repo.get_states("marker")
            if state.effective_date == 1220
        )
    assert set(RegionPolygon.from_geometry(saved_geometry).holes[0]) == set(
        expected_cutter.outer
    )
    assert db_service.get_marker("lake-marker").to_dict() == original_cutter
    assert [
        s.to_dict() for s in db_service.feature_geometry_repo.get_states("lake-marker")
    ] == lake_states
    assert command.undo(db_service).success
    assert db_service.get_marker("marker").geometry == target.to_geometry()
    assert [
        s.to_dict() for s in db_service.feature_geometry_repo.get_states("marker")
    ] == before
    assert command.execute(db_service).success


def _add_test_regions(widget, coordinator, target, cutter):
    snapshots = []
    for marker_id, object_id, label, polygon in (
        ("marker", "object", "Region", target),
        ("lake-marker", "lake", "Lake", cutter),
    ):
        geometry = polygon.to_geometry()
        snapshots.append(
            {
                **_marker_snapshot(),
                "id": marker_id,
                "object_id": object_id,
                "label": label,
                "feature_type": "region",
                "geometry": geometry,
                "x": 0.5,
                "y": 0.5,
            }
        )
        widget.view.add_marker(
            object_id,
            "entity",
            label,
            0.5,
            0.5,
            feature_type="region",
            geometry=geometry,
        )
    coordinator.on_markers_ready("map", snapshots)


def test_trace_controls_append_a_route_and_escape_preserves_draft(
    qtbot, tmp_path, init_theme_manager
):
    widget = MapWidget()
    qtbot.addWidget(widget)
    widget.resize(650, 620)
    widget.show()
    image = tmp_path / "map.png"
    pixmap = QPixmap(400, 400)
    pixmap.fill(Qt.GlobalColor.white)
    assert pixmap.save(str(image))
    view = widget.view
    assert view.load_map(str(image))
    source = _square(0.25, 0.75)
    view.add_marker(
        "region",
        "entity",
        "Source",
        0.5,
        0.5,
        feature_type="region",
        geometry=source.to_geometry(),
    )
    view.start_drawing("region")
    controls = widget.border_trace_controls
    assert controls.start.isVisible()
    qtbot.mouseClick(controls.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.mapFromScene(QPointF(100, 100)),
    )
    qtbot.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.mapFromScene(QPointF(100, 300)),
    )
    assert controls.accept.isEnabled()
    qtbot.mouseClick(controls.switch, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(controls.accept, Qt.MouseButton.LeftButton)
    assert view._drawing_tool.draft_points() == source.outer
    qtbot.mouseClick(controls.start, Qt.MouseButton.LeftButton)
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert view.is_drawing
    assert view._drawing_tool.draft_points() == source.outer


class _Item:
    def __init__(self) -> None:
        self._geometry = [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}]

    def set_geometry(self, geometry, _anchor_x, _anchor_y) -> None:
        self._geometry = [dict(point) for point in geometry]


class _VertexEditor:
    def __init__(self) -> None:
        self.started = False

    def start_vertex_editing(self, _item, *, managed_session=False) -> None:
        self.started = managed_session

    def finish_vertex_editing(self, *, emit_geometry_change=True) -> None:
        self.started = False


class _View(QObject):
    feature_geometry_preview_changed = Signal(str, list)

    def __init__(self) -> None:
        super().__init__()
        self.pixmap_item = None
        self.feature_items = {"object": _Item()}
        self._vertex_editor = _VertexEditor()

    def set_temporal_authoring_override(self, _object_id: str, _enabled: bool) -> None:
        """Mirror the production view contract for coordinator tests."""


class _Timeline(QObject):
    playhead_time_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.time = 0.0

    def get_playhead_time(self) -> float:
        return self.time


class _Widget(QObject):
    feature_geometry_edit_requested = Signal(str)
    feature_geometry_manage_requested = Signal(str)
    feature_geometry_apply_requested = Signal()
    feature_geometry_cancel_requested = Signal()
    map_selected = Signal(str)
    marker_scene_updated = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.map_id = "map"
        self.updates: list[tuple] = []
        self.view = _View()
        self.edit_visible = False
        self.edit_pending = False

    def get_selected_map_id(self) -> str:
        return self.map_id

    def update_feature_geometry(self, *args) -> None:
        self.updates.append(args)

    def show_feature_geometry_edit(self, _label: str, _source: str) -> None:
        self.edit_visible = True

    def set_feature_geometry_edit_pending(self, pending: bool) -> None:
        self.edit_pending = pending

    def set_feature_geometry_edit_available(self, available, explanation="") -> None:
        self.apply_available = available

    def hide_feature_geometry_edit(self) -> None:
        self.edit_visible = False


class _DataHandler(QObject):
    markers_ready = Signal(str, list)
    feature_geometry_states_ready = Signal(str, list)


class _Worker(QObject):
    command_finished = Signal(CommandResult)


class _Window(QObject):
    command_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.timeline = _Timeline()
        self.map_widget = _Widget()
        self.data_handler = _DataHandler()
        self.worker = _Worker()


def _marker_snapshot() -> dict:
    return {
        "id": "marker",
        "map_id": "map",
        "object_id": "object",
        "object_type": "entity",
        "x": 0.15,
        "y": 0.15,
        "label": "Border",
        "attributes": {},
        "feature_type": "path",
        "geometry": [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}],
        "style": {},
    }


def test_states_and_markers_may_arrive_in_either_order() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    state = {
        "id": "state",
        "marker_id": "marker",
        "effective_date": 100.0,
        "geometry": [{"x": 0.5, "y": 0.5}, {"x": 0.7, "y": 0.7}],
        "anchor_x": 0.6,
        "anchor_y": 0.6,
        "created_at": 1.0,
        "modified_at": 1.0,
    }
    window.data_handler.feature_geometry_states_ready.emit("map", [state])
    assert window.map_widget.updates == []

    marker = _marker_snapshot()
    window.data_handler.markers_ready.emit("map", [marker])
    assert window.map_widget.updates[-1][1][0]["x"] == 0.1

    before = len(window.map_widget.updates)
    window.timeline.time = 100.0
    window.timeline.playhead_time_changed.emit(100.0)
    assert len(window.map_widget.updates) == before + 1
    assert window.map_widget.updates[-1][1][0]["x"] == 0.5


def test_stale_map_snapshots_do_not_render() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.on_markers_ready("old-map", [])
    assert window.map_widget.updates == []


def test_edit_between_states_creates_one_atomic_command() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    coordinator.on_markers_ready("map", [_marker_snapshot()])
    window.timeline.time = 150.0
    commands = []
    window.command_requested.connect(commands.append)

    coordinator.start_edit_at_playhead("object")
    assert window.map_widget.edit_visible
    assert window.map_widget.view._vertex_editor.started
    window.map_widget.view.feature_items["object"]._geometry = [
        {"x": 0.3, "y": 0.3},
        {"x": 0.5, "y": 0.5},
    ]
    coordinator.on_preview_changed(
        "object", window.map_widget.view.feature_items["object"]._geometry
    )
    coordinator.apply_edit()

    assert len(commands) == 1
    assert isinstance(commands[0], ReplaceFeatureGeometryStatesCommand)
    assert len(commands[0].after_states) == 1
    assert commands[0].after_states[0]["effective_date"] == 150.0


def test_cancel_discards_preview_and_restores_playhead_geometry() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    coordinator.on_markers_ready("map", [_marker_snapshot()])
    coordinator.start_edit_at_playhead("object")
    window.map_widget.view.feature_items["object"]._geometry[0]["x"] = 0.9

    coordinator.cancel_edit()

    assert not window.map_widget.edit_visible
    assert window.map_widget.updates[-1][1][0]["x"] == 0.1


def test_base_apply_updates_cache_before_future_playhead_changes() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    snapshot = _marker_snapshot()
    coordinator.on_markers_ready("map", [snapshot])
    commands = []
    window.command_requested.connect(commands.append)
    coordinator._start_session(
        "map",
        "marker",
        snapshot,
        "base",
        {
            "geometry": snapshot["geometry"],
            "anchor_x": snapshot["x"],
            "anchor_y": snapshot["y"],
        },
        [],
    )
    window.map_widget.view.feature_items["object"]._geometry = [
        {"x": 0.4, "y": 0.4},
        {"x": 0.8, "y": 0.8},
    ]

    coordinator.on_preview_changed(
        "object", window.map_widget.view.feature_items["object"]._geometry
    )
    coordinator.apply_edit()
    assert isinstance(commands[0], UpdateFeatureBaseGeometryCommand)
    window.worker.command_finished.emit(
        CommandResult(
            True,
            "saved",
            data={"command_id": commands[0].command_id},
            command_name="UpdateFeatureBaseGeometryCommand",
        )
    )
    QCoreApplication.processEvents()
    window.timeline.playhead_time_changed.emit(50.0)

    assert window.map_widget.updates[-1][1][0]["x"] == 0.4
    assert not window.map_widget.edit_visible


def test_failed_geometry_apply_keeps_session_editable() -> None:
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    coordinator.on_markers_ready("map", [_marker_snapshot()])
    commands = []
    window.command_requested.connect(commands.append)
    coordinator.start_edit_at_playhead("object")
    coordinator.apply_edit()
    assert window.map_widget.edit_pending

    window.worker.command_finished.emit(
        CommandResult(
            False,
            "save failed",
            data={"command_id": commands[0].command_id},
            command_name=commands[0].__class__.__name__,
        )
    )

    QCoreApplication.processEvents()
    assert window.map_widget.edit_visible
    assert window.map_widget.view._vertex_editor.started
    assert not window.map_widget.edit_pending
    assert coordinator._session is not None


def test_geometry_draft_survives_recreated_scene_item_and_detects_conflict():
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.bind_ui()
    snapshot = _marker_snapshot()
    coordinator.on_markers_ready("map", [snapshot])
    coordinator._start_session(
        "map",
        "marker",
        snapshot,
        "base",
        {
            "geometry": snapshot["geometry"],
            "anchor_x": snapshot["x"],
            "anchor_y": snapshot["y"],
        },
        [],
    )
    working = [{"x": 0.4, "y": 0.4}, {"x": 0.8, "y": 0.8}]
    window.map_widget.view.feature_geometry_preview_changed.emit("object", working)
    working[0]["x"] = 0.99
    window.map_widget.view.feature_items["object"] = _Item()
    window.map_widget.marker_scene_updated.emit("map")
    assert window.map_widget.view.feature_items["object"]._geometry[0]["x"] == 0.4
    assert coordinator.edit_status()["dirty"]
    changed = {**snapshot, "x": 0.2}
    coordinator.on_markers_ready("map", [changed])
    assert coordinator.edit_status()["conflicted"]
    assert not coordinator.edit_status()["can_apply"]
    assert coordinator._session["working_geometry"][0]["x"] == 0.4


def test_geometry_removal_retains_independent_working_copy():
    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    coordinator.on_markers_ready("map", [_marker_snapshot()])
    coordinator.start_edit_at_playhead("object")
    coordinator.on_preview_changed(
        "object", [{"x": 0.4, "y": 0.4}, {"x": 0.8, "y": 0.8}]
    )
    window.map_widget.view.feature_items.clear()
    coordinator.on_markers_ready("map", [])
    assert coordinator.edit_status()["conflicted"]
    assert coordinator._session["working_geometry"][0]["x"] == 0.4


@pytest.mark.parametrize("target_type", ["base", "state", "new_state"])
@pytest.mark.parametrize("decision", ["keep", "discard", "apply"])
def test_geometry_transition_resolves_each_target(target_type, decision):
    from src.app.coordinators.map_edit_transition_coordinator import (
        MapEditTransitionCoordinator,
    )
    from src.core.feature_geometry_state import FeatureGeometryState

    window = _Window()
    coordinator = FeatureGeometryCoordinator(window)
    snapshot = _marker_snapshot()
    coordinator.on_markers_ready("map", [snapshot])
    state = FeatureGeometryState(
        marker_id="marker",
        effective_date=0.0,
        geometry=snapshot["geometry"],
        anchor_x=snapshot["x"],
        anchor_y=snapshot["y"],
    ).to_dict()
    before = [state] if target_type == "state" else []
    coordinator.on_states_ready("map", before)
    target = (
        {
            "geometry": snapshot["geometry"],
            "anchor_x": snapshot["x"],
            "anchor_y": snapshot["y"],
        }
        if target_type == "base"
        else state
    )
    coordinator._start_session("map", "marker", snapshot, target_type, target, before)
    coordinator.on_preview_changed(
        "object", [{"x": 0.4, "y": 0.4}, {"x": 0.8, "y": 0.8}]
    )
    commands, actions = [], []
    window.command_requested.connect(commands.append)
    guard = MapEditTransitionCoordinator(
        [coordinator], lambda: "world", lambda *_: decision, lambda _: None
    )
    guard.request_transition("open another map", lambda: actions.append(True))
    if decision == "keep":
        assert actions == [] and commands == [] and coordinator.is_active
    elif decision == "discard":
        assert actions == [True] and commands == [] and not coordinator.is_active
    else:
        assert actions == [] and len(commands) == 1
        coordinator.on_command_finished(
            CommandResult(
                True,
                "saved",
                data={"command_id": commands[0].command_id},
                command_name=commands[0].__class__.__name__,
            )
        )
        assert actions == [True] and not coordinator.is_active
