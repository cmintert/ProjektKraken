"""KRT-102: navigation wins over genuine interactive map scene items."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsView

from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.map.marker_item import MarkerItem

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def view(qtbot, monkeypatch):
    monkeypatch.setenv("KRAKEN_NO_OPENGL", "1")
    widget = MapGraphicsView()
    qtbot.addWidget(widget)
    image = QImage(2000, 2000, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    widget.pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    widget.graphics_scene.addItem(widget.pixmap_item)
    bounds = QRectF(0, 0, 2000, 2000)
    widget.coord_system.set_scene_rect(bounds)
    widget.setSceneRect(bounds)
    widget.resize(500, 400)
    widget.show()
    widget.setFocus()
    qtbot.waitUntil(widget.isVisible)
    widget.centerOn(1000, 1000)
    return widget


def add_item(view, kind):
    geometry = [
        {"x": 0.4, "y": 0.4},
        {"x": 0.6, "y": 0.4},
        {"x": 0.6, "y": 0.6},
        {"x": 0.4, "y": 0.6},
    ]
    if kind == "empty":
        return None, QPointF(970, 970)
    if kind == "marker":
        item = MarkerItem("item", "entity", "A marker", view.pixmap_item)
        item.setPos(970, 970)
        view.graphics_scene.addItem(item)
        view.markers["item"] = item
        return item, item.scenePos()
    cls = RegionItem if kind == "region" else PathItem
    if kind == "path":
        geometry = [{"x": 0.4, "y": 0.485}, {"x": 0.6, "y": 0.485}]
    item = cls("item", "entity", "A feature", view.pixmap_item, geometry, 0.5, 0.5)
    view.graphics_scene.addItem(item)
    view.feature_items["item"] = item
    return item, QPointF(970, 970)


def move_with_left_button(view, position):
    viewport = view.viewport()
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(position),
        QPointF(viewport.mapToGlobal(position)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, event)


def scroll_position(view):
    return view.horizontalScrollBar().value(), view.verticalScrollBar().value()


def pan(view, start=None, release_space_first=False):
    start = start or view.viewport().rect().center()
    before = scroll_position(view)
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    end = start + QPoint(45, 25)
    move_with_left_button(view, end)
    if release_space_first:
        QTest.keyRelease(view, Qt.Key.Key_Space)
        # An unfinished physical drag cannot become an edit after key release.
        move_with_left_button(view, end + QPoint(10, 10))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    if not release_space_first:
        QTest.keyRelease(view, Qt.Key.Key_Space)
    after = scroll_position(view)
    assert after[0] < before[0]
    assert after[1] < before[1]


@pytest.mark.parametrize("kind", ["region", "path", "marker", "empty"])
def test_space_drag_scrolls_without_item_side_effects(view, kind):
    item, scene_point = add_item(view, kind)
    start = view.mapFromScene(scene_point)
    if item is not None:
        assert view.itemAt(start) is item
    clicks = []
    geometry = deepcopy(getattr(item, "_geometry", None))
    position = item.pos() if item is not None else None
    if item is not None:
        item.clicked.connect(lambda *args: clicks.append(args))
    before = scroll_position(view)
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    end = start + QPoint(55, 35)
    move_with_left_button(view, end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QTest.keyRelease(view, Qt.Key.Key_Space)
    after = scroll_position(view)
    assert after[0] < before[0]
    assert after[1] < before[1]
    assert clicks == []
    assert view.graphics_scene.selectedItems() == []
    if item is not None:
        assert item.pos() == position
        assert getattr(item, "_geometry", None) == geometry


@pytest.mark.parametrize(
    "mode", ["drawing", "vertices", "raster", "placement", "calibration"]
)
def test_pan_preserves_tool_state_and_bypasses_all_edit_callbacks(
    view, monkeypatch, mode
):
    item, _ = add_item(view, "region")
    if mode == "drawing":
        view.start_drawing("region")
        view._add_drawing_vertex(QPointF(850, 850))
    elif mode == "vertices":
        view._start_vertex_editing(item)
    elif mode == "raster":
        view.start_raster_editing("raster")
    elif mode == "placement":
        view.start_marker_placement()
    else:
        view.calibration_mode = True
        view.setDragMode(QGraphicsView.DragMode.NoDrag)
        view.setCursor(Qt.CursorShape.CrossCursor)

    tool_state = (
        deepcopy(item._geometry),
        list(view._drawing_tool._drawing_vertices),
        list(view.calibration_points),
        view._marker_placement_position,
    )
    drag_mode, cursor = view.dragMode(), view.viewport().cursor().shape()
    callbacks = []
    for tool, methods in (
        (view._drawing_tool, ("handle_mouse_press", "handle_mouse_move")),
        (view._vertex_editor, ("handle_mouse_move",)),
        (
            view._raster_edit_tool,
            ("handle_mouse_press", "handle_mouse_move", "handle_mouse_release"),
        ),
        (
            view._trajectory_edit_overlay,
            ("follow_second_location_cursor", "place_second_location"),
        ),
    ):
        for method in methods:
            callback = Mock(return_value=True)
            monkeypatch.setattr(tool, method, callback)
            callbacks.append(callback)
    mutations = []
    for signal in (
        view.drawing_finished,
        view.feature_geometry_changed,
        view.feature_geometry_preview_changed,
        view.raster_stroke_completed,
        view.add_marker_requested,
        view.calibration_completed,
        view.trajectory_second_destination_placed,
    ):
        signal.connect(lambda *args: mutations.append(args))
    pan(view, release_space_first=True)
    assert view.isInteractive()
    assert view.dragMode() == drag_mode
    assert view.viewport().cursor().shape() == cursor
    assert tool_state == (
        item._geometry,
        view._drawing_tool._drawing_vertices,
        view.calibration_points,
        view._marker_placement_position,
    )
    assert mutations == []
    for callback in callbacks:
        callback.assert_not_called()


def test_early_space_release_does_not_select_then_normal_click_still_works(view):
    item, point = add_item(view, "region")
    clicks = []
    item.clicked.connect(lambda *args: clicks.append(args))
    pan(view, view.mapFromScene(point), release_space_first=True)
    assert clicks == []
    assert not item.isSelected()
    assert view.isInteractive()
    pan(view, view.mapFromScene(point))
    QTest.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, pos=view.mapFromScene(point)
    )
    assert item.isSelected()
    assert len(clicks) == 1


@pytest.mark.parametrize("interactive", [False, True])
def test_autorepeat_preserves_original_interaction_and_custom_cursor(view, interactive):
    view.setInteractive(interactive)
    view.setDragMode(QGraphicsView.DragMode.NoDrag)
    view.setCursor(Qt.CursorShape.CrossCursor)
    view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
    QTest.keyPress(view, Qt.Key.Key_Space)
    for event_type in (QEvent.Type.KeyRelease, QEvent.Type.KeyPress):
        repeat = QKeyEvent(
            event_type, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ", True
        )
        QApplication.sendEvent(view, repeat)
        assert view._space_pressed
        assert not view.isInteractive()
    QTest.keyRelease(view, Qt.Key.Key_Space)
    QTest.keyRelease(view, Qt.Key.Key_Space)
    assert view.isInteractive() is interactive
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    assert view.cursor().shape() == Qt.CursorShape.CrossCursor
    assert view.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor


@pytest.mark.parametrize(
    "loss",
    [
        QEvent.Type.FocusOut,
        QEvent.Type.WindowDeactivate,
        QEvent.Type.Hide,
        QEvent.Type.UngrabMouse,
    ],
)
def test_lost_focus_or_mouse_grab_restores_state_and_ignores_late_release(view, loss):
    item, point = add_item(view, "region")
    start = view.mapFromScene(point)
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    move_with_left_button(view, start + QPoint(20, 20))
    receiver = view.viewport() if loss == QEvent.Type.UngrabMouse else view
    QApplication.sendEvent(receiver, QEvent(loss))
    assert not view._space_pressed
    assert view.isInteractive()
    move_with_left_button(view, start + QPoint(40, 40))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert not item.isSelected()
    pan(view)


def test_tool_change_during_pan_retains_new_mode_without_stray_placement(view):
    start = view.viewport().rect().center()
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    move_with_left_button(view, start + QPoint(20, 20))
    view.start_marker_placement()
    assert view.isInteractive()
    assert not view._space_pressed
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    move_with_left_button(view, start + QPoint(40, 40))
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.keyRelease(view, Qt.Key.Key_Space)
    assert not view.has_marker_placement_preview
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    assert view.viewport().cursor().shape() == Qt.CursorShape.CrossCursor
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert view.has_marker_placement_preview


@pytest.mark.parametrize("kind", ["marker", "region"])
def test_pan_over_real_item_label_preserves_selection(view, kind):
    item, _ = add_item(view, kind)
    label = item._label_item
    label.setPos(item.mapFromScene(QPointF(1000, 1000)))
    label.show()
    point = label.mapToScene(label.boundingRect().center())
    view.centerOn(point)
    start = view.mapFromScene(point)
    assert view.itemAt(start) is label
    pan(view, start)
    assert not item.isSelected()


@pytest.mark.parametrize("kind", ["vertices", "appearance"])
def test_pan_over_real_edit_handle_cannot_change_geometry_or_appearance(view, kind):
    if kind == "vertices":
        item, _ = add_item(view, "region")
        view._start_vertex_editing(item)
        handle = view._vertex_handles[0]
        before = deepcopy(item._geometry)
    else:
        item, _ = add_item(view, "marker")
        view.start_marker_appearance_edit(item.marker_id)
        handle = item._resize_handle
        before = deepcopy(item.appearance_payload())
    view.centerOn(handle.scenePos())
    start = view.mapFromScene(handle.scenePos())
    assert view.itemAt(start) is handle
    pan(view, start)
    after = item._geometry if kind == "vertices" else item.appearance_payload()
    assert after == before
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag


@pytest.mark.parametrize("editing", [False, True])
def test_pan_over_footprint_does_not_navigate_or_change_registration(view, editing):
    from src.gui.widgets.map.detail_map_footprint_item import DetailMapFootprintItem

    registration = {
        "mode": "aspect_locked_affine",
        "version": 1,
        "master_center_norm": {"x": 0.5, "y": 0.5},
        "scale_norm": 0.25,
        "rotation_deg": 0.0,
        "aspect_ratio": 1.5,
        "confidence": "user_confirmed",
    }
    item = DetailMapFootprintItem(
        "detail", "A detail map", "parent", registration, 2000, 2000
    )
    view.graphics_scene.addItem(item)
    item.set_edit_mode(editing)
    point = item.footprint_bounds_rect().topLeft() if editing else QPointF(970, 970)
    view.centerOn(point)
    start = view.mapFromScene(point)
    assert view.itemAt(start) is item
    changes = []
    item.detail_map_clicked.connect(changes.append)
    item.registration_changed.connect(changes.append)
    pan(view, start)
    assert changes == []
    assert item.current_registration() == registration


def test_space_pan_cannot_paint_real_raster_buffer(view):
    import numpy as np

    from src.gui.widgets.map.map_data_buffer import (
        ColorMap,
        GradientStop,
        MapDataBuffer,
    )
    from src.gui.widgets.map.raster_layer_item import RasterLayerItem

    buffer = MapDataBuffer(width=64, height=64, default_value=0)
    colors = ColorMap(
        type="gradient",
        gradient_stops=[GradientStop(0, "#00000000"), GradientStop(1, "#ffffffff")],
    )
    item = RasterLayerItem(buffer, colors, QRectF(0, 0, 2000, 2000), node_id="raster")
    view.graphics_scene.addItem(item)
    view._raster_items["raster"] = item
    view.start_raster_editing("raster")
    view._raster_edit_tool.paint_value = 200
    completed = []
    view.raster_stroke_completed.connect(lambda *args: completed.append(args))
    pan(view, release_space_first=True)
    assert np.all(buffer._data == 0)
    assert completed == []
    assert not view._raster_edit_tool._stroke_active
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.viewport().rect().center(),
    )
    assert np.any(buffer._data != 0)
    assert len(completed) == 1


def test_pan_suppresses_double_click_and_context_menu_then_restores_menu(
    view, monkeypatch
):
    from PySide6.QtGui import QContextMenuEvent

    item, point = add_item(view, "region")
    start = view.mapFromScene(point)
    menu = Mock()
    double_click = Mock(return_value=True)
    monkeypatch.setattr(view._interaction, "show_feature_context_menu", menu)
    monkeypatch.setattr(view._drawing_tool, "handle_double_click", double_click)
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    context = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, start)
    QApplication.sendEvent(view.viewport(), context)
    menu.assert_not_called()
    double_click.assert_not_called()
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.keyRelease(view, Qt.Key.Key_Space)
    QApplication.sendEvent(
        view.viewport(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, start)
    )
    menu.assert_called_once()
    assert menu.call_args.args[0] is item


def test_missing_mouse_release_recovers_on_hover_and_next_pan(view):
    start = view.viewport().rect().center()
    QTest.keyPress(view, Qt.Key.Key_Space)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    move_with_left_button(view, start + QPoint(20, 20))
    hover = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(start),
        QPointF(view.viewport().mapToGlobal(start)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), hover)
    assert not view._space_pressed
    assert view.isInteractive()
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    pan(view)


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text(encoding="utf-8")))
)
def test_narrow_styled_map_restores_cursor_and_tool_across_themes(
    view, qtbot, monkeypatch, theme
):
    from src.core.theme_manager import ThemeManager

    manager = ThemeManager()
    assert theme in manager.themes
    monkeypatch.setattr(manager, "current_theme_name", theme)
    view.setStyleSheet(
        manager.format_stylesheet(
            Path("src/resources/main.qss").read_text(encoding="utf-8")
        )
    )
    item, point = add_item(view, "region")
    view.resize(260, 180)
    view.setCursor(Qt.CursorShape.CrossCursor)
    qtbot.wait(1)
    view.centerOn(point)
    cursor = view.viewport().cursor().shape()
    pan(view, view.mapFromScene(point))
    assert view.isInteractive()
    assert view.viewport().cursor().shape() == cursor
    assert not item.isSelected()


def test_normal_marker_drag_still_moves_marker_after_pan(view):
    item, point = add_item(view, "marker")
    pan(view, view.mapFromScene(point))
    before_scroll = scroll_position(view)
    before_item = item.pos()
    start = view.mapFromScene(item.scenePos())
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    end = start + QPoint(40, 20)
    move_with_left_button(view, end)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert item.pos().x() > before_item.x()
    assert item.pos().y() > before_item.y()
    assert scroll_position(view) == before_scroll
