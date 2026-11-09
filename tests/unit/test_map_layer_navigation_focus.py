"""Returning from Layers gives map navigation its keyboard ownership back."""

from copy import deepcopy

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from tests.unit.test_map_feature_actions import (
    add_feature,
)
from tests.unit.test_map_feature_actions import (
    feature_map as _feature_map,
)
from tests.unit.test_map_space_pan import move_with_left_button, scroll_position

pytestmark = pytest.mark.ci_fast
feature_map = _feature_map


@pytest.mark.parametrize("kind", ["group", "point", "path", "region"])
def test_layers_to_map_space_drag_pans_without_toggling_selection(
    feature_map, qtbot, qapp, kind
):
    widget = feature_map
    item = add_feature(widget, "point" if kind == "group" else kind)
    panel = widget.layer_panel
    model = widget.get_layer_model()
    node = (
        next(n for n in model.root.children if n.layer_type == "group")
        if kind == "group"
        else panel.feature_node("target")
    )
    widget.activateWindow()
    qapp.setActiveWindow(widget)
    tree = panel.tree_view
    index = panel._proxy_model.mapFromSource(model.index_from_node(node))
    QTest.mouseMove(tree.viewport(), tree.visualRect(index).center())
    QTest.mouseClick(
        tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualRect(index).center()
    )
    qtbot.waitUntil(tree.hasFocus)
    assert panel.selected_node_id == node.id
    widget.view.scale(4, 4)
    widget.view.centerOn(300, 200)
    start = widget.view.viewport().rect().center()
    QTest.mouseMove(widget.view.viewport(), start)
    qtbot.wait(0)
    visible = node.visible
    selected = panel.selected_node_id
    position = item.pos()
    geometry = deepcopy(getattr(item, "_geometry", []))
    before = scroll_position(widget.view)
    # Deliver to the actual focus owner, as the physical keyboard does.
    QTest.keyPress(qapp.focusWidget(), Qt.Key.Key_Space)
    try:
        assert node.visible == visible
        assert widget.view._space_pressed
        QTest.mousePress(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        end = start + QPoint(40, 25)
        move_with_left_button(widget.view, end)
        QTest.mouseRelease(widget.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    finally:
        QTest.keyRelease(qapp.focusWidget(), Qt.Key.Key_Space)
    after = scroll_position(widget.view)
    assert after[0] < before[0] and after[1] < before[1]
    assert panel.selected_node_id == selected
    assert node.visible == visible
    assert item.pos() == position
    assert list(getattr(item, "_geometry", [])) == geometry
    assert not widget.view._space_pressed


def test_space_over_layers_still_toggles_its_focused_row(feature_map, qtbot, qapp):
    widget = feature_map
    add_feature(widget)
    panel = widget.layer_panel
    node = panel.feature_node("target")
    widget.activateWindow()
    qapp.setActiveWindow(widget)
    panel.select_node(node.id)
    tree = panel.tree_view
    QTest.mouseMove(tree.viewport(), tree.visualRect(tree.currentIndex()).center())
    tree.setFocus()
    qtbot.waitUntil(tree.hasFocus)
    before = node.visible
    QTest.keyClick(qapp.focusWidget(), Qt.Key.Key_Space)
    assert node.visible != before
    assert not widget.view._space_pressed


def test_entering_map_does_not_take_focus_from_a_text_edit(feature_map, qtbot, qapp):
    widget = feature_map
    editor = QLineEdit(widget.layer_panel)
    editor.setText("Draft")
    editor.show()
    widget.activateWindow()
    qapp.setActiveWindow(widget)
    QTest.mouseMove(widget.layer_panel.tree_view.viewport(), QPoint(10, 10))
    editor.setFocus()
    qtbot.waitUntil(editor.hasFocus)
    QTest.mouseMove(widget.view.viewport(), widget.view.viewport().rect().center())
    qtbot.wait(0)
    assert editor.hasFocus()
    QTest.keyClick(qapp.focusWidget(), Qt.Key.Key_Space)
    assert editor.text() == "Draft "
    assert not widget.view._space_pressed


def test_entering_map_during_a_layers_drag_keeps_tree_focus(feature_map, qtbot, qapp):
    widget = feature_map
    add_feature(widget)
    tree = widget.layer_panel.tree_view
    widget.layer_panel.select_node("target")
    widget.activateWindow()
    qapp.setActiveWindow(widget)
    start = tree.visualRect(tree.currentIndex()).center()
    QTest.mouseMove(tree.viewport(), start)
    tree.setFocus()
    qtbot.waitUntil(tree.hasFocus)
    QTest.mousePress(tree.viewport(), Qt.MouseButton.LeftButton, pos=start)
    try:
        QTest.mouseMove(widget.view.viewport(), widget.view.viewport().rect().center())
        qtbot.wait(0)
        assert tree.hasFocus()
        assert not widget.view._space_pressed
    finally:
        QTest.mouseRelease(tree.viewport(), Qt.MouseButton.LeftButton, pos=start)
