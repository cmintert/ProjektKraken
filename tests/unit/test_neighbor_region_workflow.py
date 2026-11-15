"""Neighbor creation keeps exact borders, independent sources and recoverable drafts."""

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from src.app.coordinators.map_edit_transition_coordinator import (
    MapEditTransitionCoordinator,
)
from src.app.coordinators.neighbor_region_coordinator import (
    NeighborRegionCoordinator,
    NeighborRegionPorts,
)
from src.app.raster_controller import RasterController
from src.commands.base_command import CommandResult
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import CreateEntityCommand
from src.commands.event_commands import CreateEventCommand
from src.commands.neighbor_region_command import CreateNeighborRegionCommand
from src.commands.registry import get_command_types
from src.core.feature_geometry_state import FeatureGeometryState
from src.core.map import Map
from src.core.marker import Marker
from src.core.region_geometry import RegionPolygon
from src.core.theme_manager import ThemeManager
from src.gui.dialogs.map_object_picker_dialog import MapObjectChoice
from src.gui.widgets.map.feature_actions import FeatureContext, feature_actions
from src.gui.widgets.map_widget import MapWidget

pytestmark = pytest.mark.ci_fast


def rectangle(x0, y0, x1, y1):
    return RegionPolygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


@pytest.fixture
def neighbor(qtbot, tmp_path, monkeypatch, db_service, init_theme_manager):
    map_obj = Map(name="Neighbor map", image_path="map.png")
    db_service.insert_map(map_obj)
    polygon = rectangle(0.1, 0.1, 0.600000000000003, 0.9)
    source = Marker(
        map_id=map_obj.id,
        object_id="source",
        object_type="entity",
        label="Source",
        feature_type="region",
        geometry=polygon.to_geometry(),
        x=0.3,
        y=0.5,
    )
    db_service.insert_marker(source)
    widget = MapWidget()
    widget.view.setViewport(QWidget())
    qtbot.addWidget(widget)
    monkeypatch.setattr(widget, "get_selected_map_id", lambda: map_obj.id)
    widget.resize(720, 850)
    widget.show()
    image = tmp_path / "map.png"
    pixmap = QPixmap(400, 400)
    pixmap.fill(Qt.GlobalColor.white)
    assert pixmap.save(str(image))
    assert widget.view.load_map(str(image))
    widget.view.add_marker(
        "source",
        "entity",
        "Source",
        0.3,
        0.5,
        feature_type="region",
        geometry=source.geometry,
    )
    state = {
        "date": 100.0,
        "world": "world",
        "choice": MapObjectChoice(
            "new", object_type="entity", name="Neighbor", entity_type="Location"
        ),
    }
    submitted = []
    coordinator = NeighborRegionCoordinator(
        NeighborRegionPorts(
            view=widget.view,
            controls=widget.neighbor_region_controls,
            map_id=widget.get_selected_map_id,
            world_id=lambda: state["world"],
            date=lambda: state["date"],
            format_date=lambda d: f"day {d:g}",
            choose_object=lambda: state["choice"],
            create_entity=CreateEntityCommand,
            create_event=CreateEventCommand,
            submit=submitted.append,
            begin_drawing=widget._begin_region_drawing,
            set_date=lambda d: state.update(date=d),
            transition=widget.request_edit_transition,
        ),
        widget,
    )
    coordinator.on_markers_ready(map_obj.id, [source.to_dict()])
    coordinator.on_states_ready(map_obj.id, [])
    return SimpleNamespace(
        widget=widget,
        coordinator=coordinator,
        source=source,
        polygon=polygon,
        state=state,
        submitted=submitted,
        db=db_service,
    )


def draw(n, polygon=None):
    polygon = polygon or rectangle(0.4, 0.2, 0.9, 0.8)
    n.coordinator.start("source")
    for x, y in polygon.outer:
        n.widget.view._drawing_tool._add_drawing_vertex(QPointF(x * 400, y * 400))
    return copy.deepcopy(n.widget.view._drawing_tool.draft_points())


def accept(n):
    n.coordinator.preview()
    assert n.widget.neighbor_region_controls.ready
    n.coordinator.accept_result()


def finish(n, result):
    result.data["command_id"] = n.submitted[-1].command_id
    n.coordinator.on_command_finished(result)


def test_create_roundtrip_exact_shared_border_and_independent_undo_redo(neighbor):
    n = neighbor
    before = copy.deepcopy(n.source.to_dict())
    draw(n)
    accept(n)
    n.coordinator.save()
    command = n.submitted[0]
    assert isinstance(command, CompositeCommand)
    result = command.execute(n.db)
    assert result.success
    assert result.data["marker_map_ids"] == [n.source.map_id]
    assert len(result.data["lore_effects"]) == 1
    assert result.data["select_after_apply"] is False
    saved = [
        m for m in n.db.get_markers_for_map(n.source.map_id) if m.id != n.source.id
    ][0]
    shape = RegionPolygon.from_geometry(saved.geometry).validated()
    source = n.polygon.validated()
    assert shape.intersection(source).area == 0
    assert shape.boundary.intersection(source.boundary).length == pytest.approx(0.6)
    assert min(x for x, y in shape.exterior.coords) == 0.600000000000003
    assert n.db.get_marker(n.source.id).to_dict() == before
    created_id = saved.object_id
    finish(n, result)
    assert not n.widget.neighbor_region_controls.active
    assert not n.widget.view.is_drawing
    restored = CompositeCommand.from_dict(command.to_dict())
    restored.undo(n.db)
    assert n.db.get_entity(created_id) is None
    assert n.db.get_marker(saved.id) is None
    # Once saved, this is an independent shape; redo does not recut a new source.
    n.source.geometry = rectangle(0.1, 0.1, 0.7, 0.9).to_geometry()
    n.db.insert_marker(n.source)
    assert restored.execute(n.db).success
    assert n.db.get_marker(saved.id).geometry == saved.geometry


def test_cancel_picker_failed_save_and_unrelated_ack_preserve_draft(neighbor):
    n = neighbor
    outline = draw(n)
    accept(n)
    n.state["choice"] = None
    n.coordinator.save()
    assert not n.submitted
    assert n.widget.neighbor_region_controls.stage == "accepted"
    n.state["choice"] = MapObjectChoice(
        "existing", "already-placed", "entity", "Existing"
    )
    n.coordinator.save()
    n.coordinator.on_command_finished(
        CommandResult(True, data={"command_id": "unrelated"})
    )
    assert n.widget.neighbor_region_controls.stage == "pending"
    finish(n, CommandResult(False, "Write failed"))
    assert n.widget.neighbor_region_controls.stage == "accepted"
    assert n.widget.view._drawing_tool.draft_points() == outline
    n.coordinator.back_to_drawing()
    assert not n.widget.view._drawing_tool.paused
    assert n.widget.view._drawing_tool.draft_points() == outline


def test_source_race_rolls_back_new_object_and_retains_outline(neighbor):
    n = neighbor
    outline = draw(n)
    accept(n)
    n.coordinator.save()
    n.source.geometry = rectangle(0.1, 0.1, 0.7, 0.9).to_geometry()
    n.db.insert_marker(n.source)
    command = n.submitted[0]
    entity_id = command.commands[0].entity_id
    result = command.execute(n.db)
    assert not result.success
    assert n.db.get_entity(entity_id) is None
    assert len(n.db.get_markers_for_map(n.source.map_id)) == 1
    refreshed = []
    n.coordinator.ports.refresh_source = refreshed.append
    finish(n, result)
    assert refreshed == [n.source.map_id]
    assert n.widget.view._drawing_tool.draft_points() == outline
    n.coordinator.on_markers_ready(n.source.map_id, [n.source.to_dict()])
    assert n.widget.neighbor_region_controls.stage == "drawing"
    assert not n.widget.neighbor_region_controls.ready


@pytest.mark.parametrize(
    "outline,status",
    [
        (rectangle(0.7, 0.1, 0.9, 0.9), "unchanged"),
        (rectangle(0.2, 0.2, 0.3, 0.3), "empty"),
        (RegionPolygon(((0.2, 0.2), (0.8, 0.8), (0.8, 0.2), (0.2, 0.8))), "invalid"),
    ],
)
def test_invalid_empty_and_no_overlap_are_not_accepted(neighbor, outline, status):
    n = neighbor
    points = draw(n, outline)
    n.coordinator.preview()
    assert n.coordinator._draft.result.status == status
    assert not n.widget.neighbor_region_controls.ready
    n.coordinator.accept_result()
    n.coordinator.save()
    assert not n.submitted
    n.coordinator.back_to_drawing()
    assert n.widget.view._drawing_tool.draft_points() == points


def test_split_keeps_all_pieces_visible_and_unaccepted(neighbor):
    n = neighbor
    n.source.geometry = rectangle(0.45, 0, 0.55, 1).to_geometry()
    n.db.insert_marker(n.source)
    n.coordinator.on_markers_ready(n.source.map_id, [n.source.to_dict()])
    draw(n, rectangle(0.2, 0.2, 0.8, 0.8))
    n.coordinator.preview()
    assert n.coordinator._draft.result.status == "split"
    assert len(n.coordinator._draft.result.polygons) == 2
    assert not n.widget.neighbor_region_controls.use.isEnabled()


def test_dated_source_can_create_a_region_with_a_hole(neighbor):
    n = neighbor
    dated = rectangle(0.4, 0.4, 0.6, 0.6).to_geometry()
    state = FeatureGeometryState(n.source.id, 100, dated, 0.5, 0.5)
    n.db.feature_geometry_repo.replace_marker_states(n.source.id, [state])
    n.coordinator.on_states_ready(n.source.map_id, [state.to_dict()])
    draw(n, rectangle(0.2, 0.2, 0.8, 0.8))
    accept(n)
    n.coordinator.save()
    assert n.submitted[0].execute(n.db).success
    saved = [
        m for m in n.db.get_markers_for_map(n.source.map_id) if m.id != n.source.id
    ][0]
    assert len(RegionPolygon.from_geometry(saved.geometry).holes) == 1
    assert n.db.feature_geometry_repo.get_states(saved.id) == []


def test_source_refresh_and_nested_escape_keep_authored_points(neighbor, qtbot):
    n = neighbor
    points = draw(n)
    accept(n)
    qtbot.keyClick(n.widget.view, Qt.Key.Key_Escape)
    assert n.widget.neighbor_region_controls.stage == "drawing"
    assert n.widget.view._drawing_tool.draft_points() == points
    accept(n)
    n.coordinator.on_markers_ready(n.source.map_id, [])
    assert n.widget.neighbor_region_controls.stage == "drawing"
    assert n.widget.view._drawing_tool.draft_points() == points
    n.coordinator.preview()
    assert not n.widget.neighbor_region_controls.ready
    qtbot.keyClick(n.widget.view, Qt.Key.Key_Escape)
    assert n.coordinator.edit_status() is None


def test_transition_waits_for_atomic_creation_and_time_guard_retains_date(
    neighbor, qtbot
):
    n = neighbor
    draw(n)
    accept(n)
    guard = MapEditTransitionCoordinator(
        [n.coordinator], lambda: "world", lambda *_: "apply", lambda _: None
    )
    n.widget.edit_transition_handler = guard.request_transition
    paused = []
    n.coordinator.ports.pause_playback = lambda: paused.append(True)
    assert not n.coordinator.guard_playhead(200)
    assert paused == [True]
    assert n.state["date"] == 100
    qtbot.waitUntil(lambda: len(n.submitted) == 1)
    assert guard.is_waiting
    assert n.widget.neighbor_region_controls.stage == "pending"
    finish(n, n.submitted[0].execute(n.db))
    assert n.state["date"] == 200
    assert not guard.is_waiting


@pytest.mark.parametrize("process_inside_picker", [True, False])
def test_picker_tick_restores_raster_after_signal_fanout(
    neighbor, qtbot, process_inside_picker
):
    n = neighbor
    draw(n)
    accept(n)

    class Timeline(QObject):
        changed = Signal(float)

        def set_date(self, date):
            n.state["date"] = date
            self.changed.emit(date)

    timeline = Timeline(n.widget)
    raster = SimpleNamespace(
        _current_lore_date=100,
        _current_map_id=None,
        _raster_edit_target_by_node={},
        _map_widget=n.widget,
    )
    # Match production order: the guard's nested date restore finishes before
    # the original signal reaches the raster controller.
    timeline.changed.connect(n.coordinator.guard_playhead)
    timeline.changed.connect(
        lambda date: RasterController.on_playhead_changed(raster, date)
    )
    n.coordinator.ports.set_date = timeline.set_date
    transitions, pauses = [], []
    n.coordinator.ports.transition = lambda *args: transitions.append(args)
    n.coordinator.ports.pause_playback = lambda: pauses.append(True)

    def cancel_picker():
        timeline.set_date(200)
        assert n.state["date"] == 100
        assert raster._current_lore_date == 200
        if process_inside_picker:
            qtbot.waitUntil(lambda: raster._current_lore_date == 100)
        return None

    n.coordinator.ports.choose_object = cancel_picker
    n.coordinator.save()
    qtbot.waitUntil(lambda: raster._current_lore_date == 100)
    assert n.state["date"] == 100
    assert pauses and not transitions and not n.submitted
    assert n.widget.neighbor_region_controls.stage == "accepted"
    assert n.coordinator.edit_status()["can_apply"]


def test_feature_actions_and_persistent_command_registry():
    assert "neighbor" in {
        a.action_id for a in feature_actions(FeatureContext("region"))
    }
    assert "neighbor" not in {
        a.action_id for a in feature_actions(FeatureContext("path"))
    }
    action = next(
        a
        for a in feature_actions(FeatureContext("region", canvas_available=False))
        if a.action_id == "neighbor"
    )
    assert not action.enabled and action.reason
    assert (
        get_command_types()["CreateNeighborRegionCommand"]
        is CreateNeighborRegionCommand
    )


def test_visible_feature_menu_starts_neighbor_workflow(neighbor):
    n = neighbor
    presenter = n.widget.feature_actions
    presenter.select("source", "canvas")
    menu = QMenu(n.widget)
    presenter.populate(menu)
    action = next(a for a in menu.actions() if a.data() == "neighbor")
    assert action.isEnabled()
    action.trigger()
    assert n.widget.active_map_session_mode() == "neighbor_region"
    assert n.widget.neighbor_region_controls.preview.isVisible()
    assert n.widget.view.feature_items["source"]._geometry == n.source.geometry


def test_source_changed_while_picker_is_open_cannot_save(neighbor):
    n = neighbor
    points = draw(n)
    accept(n)

    def choose():
        n.source.geometry = rectangle(0.1, 0.1, 0.7, 0.9).to_geometry()
        n.coordinator.on_markers_ready(n.source.map_id, [n.source.to_dict()])
        return n.state["choice"]

    n.coordinator.ports.choose_object = choose
    n.coordinator.save()
    assert not n.submitted
    assert n.widget.neighbor_region_controls.stage == "drawing"
    assert n.widget.view._drawing_tool.draft_points() == points


def test_existing_object_creation_and_specialized_history_refresh(neighbor):
    n = neighbor
    assert (
        CreateEntityCommand({"id": "unplaced", "name": "Neighbor", "type": "Location"})
        .execute(n.db)
        .success
    )
    n.state["choice"] = MapObjectChoice("existing", "unplaced", "entity", "Neighbor")
    draw(n)
    accept(n)
    n.coordinator.save()
    command = n.submitted[0]
    assert isinstance(command, CreateNeighborRegionCommand)
    result = command.execute(n.db)
    assert result.success
    finish(n, result)
    restored = CreateNeighborRegionCommand.from_dict(command.to_dict())
    restored.undo(n.db)
    assert n.db.get_entity("unplaced") is not None
    refreshed = []
    n.coordinator.ports.reload_map = refreshed.append
    n.coordinator.on_command_finished(
        CommandResult(
            True,
            command_name="Undo_CreateNeighborRegionCommand",
            data={"command_state": {"data": restored.to_dict()}},
        )
    )
    assert refreshed == [n.source.map_id]
    assert restored.execute(n.db).success


def test_new_event_and_neighbor_are_one_undoable_creation(neighbor):
    n = neighbor
    n.state["choice"] = MapObjectChoice("new", object_type="event", name="Frontier")
    draw(n)
    accept(n)
    n.coordinator.save()
    command = n.submitted[0]
    result = command.execute(n.db)
    assert result.success
    assert result.data["marker_map_ids"] == [n.source.map_id]
    event_id = command.commands[0].event_id
    assert n.db.get_event(event_id).lore_date == 100
    command.undo(n.db)
    assert n.db.get_event(event_id) is None
    assert len(n.db.get_markers_for_map(n.source.map_id)) == 1


def test_duplicate_placement_never_replaces_the_source(neighbor):
    n = neighbor
    before = copy.deepcopy(n.source.to_dict())
    n.state["choice"] = MapObjectChoice("existing", "source", "entity", "Source")
    draw(n)
    accept(n)
    n.coordinator.save()
    result = n.submitted[0].execute(n.db)
    assert not result.success
    finish(n, result)
    assert n.db.get_marker(n.source.id).to_dict() == before
    assert n.widget.neighbor_region_controls.stage == "accepted"


@pytest.mark.parametrize("width", [320, 540, 900])
@pytest.mark.parametrize("theme", list(json.loads(Path("themes.json").read_text())))
def test_step_actions_fit_themes_and_narrow_widths(neighbor, qapp, theme, width):
    n = neighbor
    if os.environ.get("KRT164_EVIDENCE_DIR"):
        font = Path("C:/Windows/Fonts/segoeui.ttf")
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
            qapp.setFont(QFont("Segoe UI", 10))
    tm = ThemeManager()
    tm.apply_theme(qapp, Path("src/resources/main.qss").read_text())
    tm.set_theme(theme, qapp, persist=False)
    n.widget.setFixedWidth(width)
    n.widget.resize(width, 1050)
    points = draw(n)
    c = n.widget.neighbor_region_controls
    for stage in ("drawing", "preview", "accepted", "pending"):
        if stage == "preview":
            n.coordinator.preview()
        elif stage == "accepted":
            n.coordinator.accept_result()
        elif stage == "pending":
            n.coordinator.save()
        for _ in range(3):
            qapp.processEvents()
        for button in (c.preview, c.use, c.back, c.save, c.cancel):
            if button.isVisible():
                geometry = button.label_geometry()
                assert geometry.fits, (theme, width, stage, button.text(), geometry)
                assert c.rect().contains(button.geometry())
        assert n.widget.view._drawing_tool.draft_points() == points
        if stage == "preview":
            c.use.setFocus(Qt.FocusReason.OtherFocusReason)
            qapp.processEvents()
            assert c.use.hasFocus()
        evidence = os.environ.get("KRT164_EVIDENCE_DIR")
        if evidence and width == 320 and stage == "preview":
            target = Path(evidence)
            target.mkdir(parents=True, exist_ok=True)
            assert n.widget.grab().save(str(target / f"{theme}-320-preview.png"))
    assert not c.cancel.isEnabled()
