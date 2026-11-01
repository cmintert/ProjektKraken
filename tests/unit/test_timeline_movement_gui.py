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
