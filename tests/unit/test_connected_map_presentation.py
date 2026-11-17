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
from tests.integration.test_connected_map_projection import read_frame
from tests.integration.test_map_hierarchy_authoring import authoring as _authoring

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
    overlay.display(read_frame())
    point = overlay.items[0]
    assert point.pen().color().name() == manager.get_theme()["entity_main"].lower()
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
    assert len(overlay.items) == 1
    shape = overlay.items[0]
    assert shape.pen().color().name() == manager.get_theme()["entity_main"].lower()
    assert shape.path().fillRule() == Qt.FillRule.OddEvenFill
    assert not shape.flags() & shape.GraphicsItemFlag.ItemIsMovable
    assert "Base Geometry" in shape.toolTip()
    evidence = os.environ.get("KRT_PROJECTION_EVIDENCE")
    if evidence:
        output = Path(evidence)
        output.mkdir(parents=True, exist_ok=True)
        widget.resize(360, 640)
        widget.view.fit_to_view()
        qtbot.wait(0)
        assert (
            widget.view.viewport()
            .grab()
            .save(str(output / f"{theme}-{font_size}-geometry.png"))
        )
    overlay.clear()
