"""Pointer movement previews never mutate accepted Event records."""

from copy import deepcopy

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QGraphicsItem

from src.app.coordinators.timeline_movement_coordinator import (
    TimelineMovementCoordinator,
)
from src.core.event_timing.definitions import EndpointDefinition, EventTimingDefinition
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext
from src.gui.widgets.timeline import TimelineWidget

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def moving_timeline(qtbot):
    root = Event("Source", 10.125, id="root")
    child = Event(
        "Follower",
        0,
        id="child",
        attributes=EventTimingDefinition(
            EndpointDefinition(
                "event", anchor_id="event:root", offset={"unit": "days", "value": 5.25}
            )
        ).apply({}),
    )
    widget = TimelineWidget()
    qtbot.addWidget(widget)
    widget.resize(1000, 600)
    widget.view.set_temporal_context(
        TemporalResolutionContext.build([root, child], None)
    )
    widget.show()
    widget.view._apply_zoom(1)
    item = widget.view._event_items[child.id]
    item.setY(200)
    widget.view.centerOn(item.pos())
    submitted = []
    coordinator = TimelineMovementCoordinator(
        widget.view.movement, submitted.append, widget
    )
    yield widget, item, submitted, coordinator
    widget.view.movement.cancel()
    coordinator.shutdown()


def pointer_move(view, position):
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(position),
        QPointF(view.viewport().mapToGlobal(position)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), event)


def test_dependent_pointer_drag_previews_then_submits_detached_intent(
    moving_timeline, qtbot
):
    widget, item, submitted, _coordinator = moving_timeline
    view = widget.view
    original = deepcopy(item.event.to_dict())
    original_sources = view._temporal_context.events_json
    start = view.mapFromScene(item.pos())
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert view.graphics_scene.mouseGrabberItem() is item
    pointer_move(view, start + QPoint(60, 20))
    qtbot.waitUntil(lambda: item.event.lore_date != original["lore_date"])
    assert view._temporal_context.events_json == original_sources
    assert item.y() == 200
    assert "offset:" in item.toolTip() or view.movement.intent is not None
    qtbot.mouseRelease(
        view.viewport(), Qt.MouseButton.LeftButton, pos=start + QPoint(60, 20)
    )
    assert item.event.to_dict() == original
    assert len(submitted) == 1
    assert submitted[0].intent["mode"] == "offset"
    assert submitted[0].intent["target"] > original["lore_date"]


def test_escape_restores_preview_and_release_does_not_submit(moving_timeline, qtbot):
    widget, item, submitted, _coordinator = moving_timeline
    view = widget.view
    original = deepcopy(item.event.to_dict())
    start = view.mapFromScene(item.pos())
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    pointer_move(view, start + QPoint(60, 0))
    qtbot.waitUntil(lambda: item.event.lore_date != original["lore_date"])
    qtbot.keyClick(view, Qt.Key.Key_Escape)
    assert item.event.to_dict() == original
    qtbot.mouseRelease(
        view.viewport(), Qt.MouseButton.LeftButton, pos=start + QPoint(60, 0)
    )
    assert submitted == []


def test_click_and_obsolete_preview_do_not_change_dates(moving_timeline, qtbot):
    widget, item, submitted, _coordinator = moving_timeline
    view = widget.view
    original = deepcopy(item.event.to_dict())
    start = view.mapFromScene(item.pos())
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert submitted == []
    view.movement.present({"session": -1, "sequence": -1, "updated": {}})
    assert item.event.to_dict() == original


def test_visible_mode_menu_has_keyboard_and_overflow_route(moving_timeline, qtbot):
    widget, _item, submitted, _coordinator = moving_timeline
    control = widget.drag_mode_control
    assert control.mode == "offset"
    control.mode_menu.popup(control.mapToGlobal(QPoint(0, 0)))
    control.mode_menu.setActiveAction(control.actions_by_mode["chain"])
    qtbot.keyClick(control.mode_menu, Qt.Key.Key_Return)
    assert widget.view.movement.mode == "chain"
    assert control.text() == "Drag: Move chain"
    widget.resize(340, 600)
    QApplication.processEvents()
    assert control.menu() is control.mode_menu
    assert control in widget.action_toolbar.overflowed_buttons()
    overflow_action = next(
        action
        for action in widget.action_toolbar.overflow_menu.actions()
        if action.menu() is control.mode_menu
    )
    assert overflow_action.isVisible()
    assert overflow_action.text() == "Drag: Move chain"
    assert control.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert submitted == []


def test_world_switch_during_drag_submits_nothing(moving_timeline):
    widget, item, submitted, coordinator = moving_timeline
    world = ["first.kraken"]
    coordinator.world = lambda: world[0]
    widget.view.movement.begin(item.event.id)
    widget.view.movement.preview(item.event.id, 30)
    world[0] = "second.kraken"
    widget.view.movement.finish(item.event.id, 30)
    assert submitted == []


def test_continuous_motion_is_not_starved_and_has_one_pending_target(
    moving_timeline, qtbot, monkeypatch
):
    import time

    from src.services.event_timing.preview import MovementPreviewSession

    widget, item, _, coordinator = moving_timeline
    calculated = MovementPreviewSession.calculate

    def slow(self, request, cancel=None):
        time.sleep(0.04)
        return calculated(self, request, cancel)

    monkeypatch.setattr(MovementPreviewSession, "calculate", slow)
    results = []
    coordinator.worker.completed.connect(lambda value: results.append(value))
    presenter = widget.view.movement
    presenter.begin(item.event.id)
    thread = coordinator.preview_thread
    for sequence in range(40):
        presenter.preview(item.event.id, 20 + sequence / 10)
        qtbot.wait(8)
        assert (
            coordinator.pending is None
            or coordinator.pending["sequence"] == presenter.sequence
        )
        assert coordinator.preview_thread is thread
    assert results, "Continuous motion must calculate before the pointer pauses"
    assert presenter.applied_sequence > 0
    qtbot.waitUntil(lambda: presenter.applied_sequence == presenter.sequence)
    assert coordinator.pending is None


def test_outline_moves_before_solver_and_only_changed_items_refresh(
    moving_timeline, monkeypatch
):
    widget, item, _, coordinator = moving_timeline
    presenter = widget.view.movement
    presenter.begin(item.event.id)
    original = item.event.to_dict()
    root = widget.view._event_items["root"]
    monkeypatch.setattr(
        root, "set_preview_event", lambda _: pytest.fail("Unrelated item refreshed")
    )
    presenter.preview(item.event.id, 20)
    assert presenter.outline.x() == 20 * widget.view.scale_factor
    assert presenter.outline.label.text() == "Pending calculation"
    assert item.event.to_dict() == original
    assert not coordinator.busy
    row = {
        "lore_date": 20,
        "lore_duration": 0,
        "temporal": original["attributes"]["_temporal_v2"],
    }
    presenter.present(
        {
            "session": presenter.session,
            "sequence": presenter.sequence,
            "generation": presenter.intent["generation"],
            "updated": {item.event.id: row},
        }
    )
    assert item.event.lore_date == 20
    presenter.cancel()
    assert item.event.to_dict() == original
    assert presenter.outline is None


@pytest.mark.parametrize("change", ["zoom", "calendar", "grouping"])
def test_geometry_context_changes_cancel_pending_outline(moving_timeline, change):
    widget, item, submitted, _ = moving_timeline
    presenter = widget.view.movement
    presenter.begin(item.event.id)
    presenter.preview(item.event.id, 20)
    if change == "zoom":
        widget.view._apply_zoom(2)
    elif change == "calendar":
        widget.view.set_ruler_calendar(None)
    else:
        widget.view.set_grouping_config([])
    assert presenter.intent is None
    assert presenter.outline is None
    assert not submitted


def test_no_obstacle_routing_runs_during_drag(moving_timeline, qtbot, monkeypatch):
    import src.gui.widgets.timeline.dependency_layer as module
    from src.core.timeline_visibility import DependencyVisibility

    widget, item, _, _ = moving_timeline
    view = widget.view
    view.set_dependency_visibility(DependencyVisibility.ALL)
    view._prepare_dependency_routes()
    presenter = view.movement
    presenter.begin(item.event.id)
    monkeypatch.setattr(
        module, "route_wires", lambda *_: pytest.fail("Rerouted during drag")
    )
    presenter.preview(item.event.id, 20)
    qtbot.waitUntil(lambda: presenter.applied_sequence == presenter.sequence)
    view.grab()
    view._prepare_dependency_routes()
    assert not view._dependencies.routing_pending


def test_item_measurement_is_cached_and_invalidated_by_font_and_snapshot(
    moving_timeline, qapp, monkeypatch
):
    from dataclasses import replace

    import src.gui.widgets.timeline.event_item as module

    _widget, item, _, _ = moving_timeline
    first = item._layout()
    measure = module.event_temporal_presentation
    calls = []

    def counted(*args):
        calls.append(1)
        return measure(*args)

    monkeypatch.setattr(module, "event_temporal_presentation", counted)
    for _ in range(100):
        assert item._layout() is first
        item.boundingRect()
    assert calls == []
    item.update_event(replace(item.event, name="Renamed source appearance"))
    second = item._layout()
    assert second is not first
    font = qapp.font()
    try:
        changed = qapp.font()
        changed.setFamily("Courier New")
        qapp.setFont(changed)
        assert item._layout() is not second
    finally:
        qapp.setFont(font)


def test_large_calculated_result_is_sliced_and_newer_targets_do_not_starve_items(
    moving_timeline, qtbot, monkeypatch
):
    import time

    from src.services.event_timing.preview import MovementPreviewSession

    widget, _, _, _ = moving_timeline
    view = widget.view
    events = view._temporal_context.events()
    for index in range(25):
        events.append(
            Event(
                str(index),
                0,
                id=f"extra-{index}",
                attributes=EventTimingDefinition(
                    EndpointDefinition(
                        "event",
                        anchor_id="event:root",
                        offset={"unit": "days", "value": index},
                    )
                ).apply({}),
            )
        )
    view.set_temporal_context(TemporalResolutionContext.build(events, None))
    presenter = view.movement
    presenter.mode = "chain"
    presenter.begin("root")
    session = MovementPreviewSession(
        {
            **presenter.snapshot,
            **presenter.intent,
            "session": presenter.session,
            "world_id": "",
        }
    )
    apply_row = presenter._apply_row

    def slow(*args):
        time.sleep(0.002)
        apply_row(*args)

    monkeypatch.setattr(presenter, "_apply_row", slow)
    for target in (20, 30):
        presenter.preview("root", target)
        request = {
            **presenter.intent,
            "target": target,
            "session": presenter.session,
            "sequence": presenter.sequence,
            "world_id": "",
        }
        presenter.present({**request, **session.calculate(request)})
    assert presenter._presentation_queue
    qtbot.waitUntil(lambda: not presenter._presentation_queue, timeout=3000)
    assert view._event_items["root"].event.lore_date == 30
    assert view._event_items["extra-24"].event.lore_date == 54
    presenter.cancel()
    assert view._event_items["root"].event.lore_date == 10.125


def test_pending_outline_tracks_theme_roles(moving_timeline):
    from src.core.theme_manager import ThemeManager

    widget, item, _, _ = moving_timeline
    presenter = widget.view.movement
    presenter.begin(item.event.id)
    presenter.preview(item.event.id, 20)
    manager = ThemeManager()
    original = manager.current_theme_name
    try:
        for theme in manager.themes:
            manager.set_theme(theme, persist=False)
            assert (
                presenter.outline.label.brush().color().name()
                == manager.get_theme()["mode_text"].lower()
            )
    finally:
        manager.set_theme(original, persist=False)
