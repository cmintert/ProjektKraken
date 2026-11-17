"""Connected display retains native actions and semantic identity in all themes."""

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.connected_features import ConnectedFeatures
from src.gui.widgets.map.map_label_item import MapLabelItem
from tests.integration.test_connected_map_projection import read_frame
from tests.integration.test_map_hierarchy_authoring import authoring as _authoring
from tests.integration.test_map_hierarchy_authoring import registration

pytestmark = pytest.mark.ci_fast
authoring = _authoring


@pytest.mark.parametrize(
    "theme", list(json.loads(Path("themes.json").read_text("utf-8")))
)
@pytest.mark.parametrize("font_size", [10, 20])
def test_connected_menu_and_point_are_visible_and_keyboard_navigable(
    authoring, qtbot, theme, font_size
):
    widget, _, commands, _, _ = authoring
    manager = ThemeManager()
    manager.set_theme(theme)
    menu = QMenu(widget)
    menu.setFont(QFont("Segoe UI", font_size))
    menu.setStyleSheet(
        manager.format_stylesheet(Path("src/resources/main.qss").read_text("utf-8"))
    )
    overlay = ConnectedFeatures(widget.view, menu)
    menu.popup(widget.mapToGlobal(widget.rect().center()))
    qtbot.wait(0)
    for action in menu.actions():
        if action.text():
            assert menu.actionGeometry(
                action
            ).width() >= menu.fontMetrics().horizontalAdvance(action.text())
    actions = [a for a in menu.actions() if a.isCheckable()]
    assert not actions[1].isEnabled()
    menu.setActiveAction(actions[0])
    QTest.keyClick(menu, Qt.Key.Key_Return)
    assert overlay.enabled
    widget.resize(360, 640)
    widget.view.fit_to_view()
    qtbot.wait(0)
    frame = read_frame()
    overlay.display(frame)
    point = overlay.items[0]
    assert point.pen().color().name() == manager.get_theme()["entity_main"].lower()
    (label,) = point.childItems()
    assert isinstance(label, MapLabelItem)
    assert label._text == frame["points"][0]["label"]
    assert label.isVisible()
    assert label.acceptedMouseButtons() == Qt.MouseButton.NoButton
    transform = widget.view.viewportTransform()
    label_transform = label.deviceTransform(transform)
    label_bounds = label_transform.mapRect(label.boundingRect()).toAlignedRect()
    assert widget.view.viewport().rect().contains(label_bounds)
    point_transform = point.deviceTransform(transform)
    transform.scale(2, 2)
    zoomed_label = label.deviceTransform(transform)
    zoomed_point = point.deviceTransform(transform)
    assert zoomed_label.m11() == label_transform.m11() == 1
    assert zoomed_label.dy() - zoomed_point.dy() == pytest.approx(
        label_transform.dy() - point_transform.dy()
    )
    source = []
    overlay.source_requested.connect(source.append)
    widget.view.setFocus()
    point.setFocus()
    QTest.keyClick(widget.view.viewport(), Qt.Key.Key_Return)
    assert source == ["old"]
    assert not commands
    from src.services.map_projection import MapProjector
    from tests.unit.test_map_geometry_projection import geometry_snapshot

    overlay.display(MapProjector(geometry_snapshot()).frame("new", 0))
    assert label.scene() is None
    assert len(overlay.items) == 1
    shape = overlay.items[0]
    assert not shape.childItems()
    assert shape.pen().color().name() == manager.get_theme()["entity_main"].lower()
    assert shape.path().fillRule() == Qt.FillRule.OddEvenFill
    assert not shape.flags() & shape.GraphicsItemFlag.ItemIsMovable
    assert "Base Geometry" in shape.toolTip()
    evidence = os.environ.get("KRT_PROJECTION_EVIDENCE")
    if evidence:
        output = Path(evidence)
        output.mkdir(parents=True, exist_ok=True)
        qtbot.wait(0)
        assert (
            widget.view.viewport()
            .grab()
            .save(str(output / f"{theme}-{font_size}-geometry.png"))
        )
    overlay.clear()


def test_projected_open_path_hit_shape_excludes_implicit_fill(qapp):
    from PySide6.QtCore import QPointF

    from src.core.projected_geometry import ProjectedGeometry
    from src.gui.widgets.map.connected_features import ProjectedShape

    model = ProjectedGeometry(
        "source", "old", "new", "path", lines=(((0.1, 0.1), (0.9, 0.1), (0.9, 0.9)),)
    )
    data = {
        **model.to_dict(),
        "object_type": "entity",
        "label": "Road",
        "source_name": "Source map",
        "opacity": 1,
    }
    item = ProjectedShape(data, 400, 400, lambda: None)
    assert item.path().contains(QPointF(300, 100))  # Qt implicitly fills open paths.
    assert not item.shape().contains(QPointF(300, 100))
    assert item.shape().contains(QPointF(360, 200))
    assert item.shape().contains(QPointF(200, 40))


def test_footprint_zoom_refreshes_and_projected_focus_owns_enter(authoring, qtbot):
    widget, handler, commands, _, _ = authoring
    handler.on_register_detail_map_requested("source", "parent", registration())
    assert widget.view.is_editing_footprint
    widget.view.fit_to_view()
    with qtbot.waitSignal(widget.view.zoom_factor_changed) as changed:
        widget.view.zoom_to_footprint()
    assert changed.args[0] == widget.view.zoom_factor
    assert widget.view.zoom_factor > 1

    overlay = ConnectedFeatures(widget.view, widget.map_settings_menu)
    overlay.enabled = True
    overlay.display(read_frame())
    sources = []
    overlay.source_requested.connect(sources.append)
    widget.view.setFocus()
    overlay.items[0].setFocus()
    QTest.keyClick(widget.view.viewport(), Qt.Key.Key_Return)
    assert sources == ["old"]
    assert widget.view.is_editing_footprint
    assert not commands
    overlay.clear()
