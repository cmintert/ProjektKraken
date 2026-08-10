"""Cached playback tests for the dated geometry coordinator."""

from PySide6.QtCore import QObject, Signal

from src.app.coordinators.feature_geometry_coordinator import (
    FeatureGeometryCoordinator,
)
from src.commands.base_command import CommandResult
from src.commands.feature_geometry_commands import (
    ReplaceFeatureGeometryStatesCommand,
)


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


class _View:
    def __init__(self) -> None:
        self.feature_items = {"object": _Item()}
        self._vertex_editor = _VertexEditor()


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

    def __init__(self) -> None:
        super().__init__()
        self.map_id = "map"
        self.updates: list[tuple] = []
        self.view = _View()
        self.edit_visible = False

    def get_selected_map_id(self) -> str:
        return self.map_id

    def update_feature_geometry(self, *args) -> None:
        self.updates.append(args)

    def show_feature_geometry_edit(self, _label: str, _source: str) -> None:
        self.edit_visible = True

    def set_feature_geometry_edit_pending(self, _pending: bool) -> None:
        pass

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
