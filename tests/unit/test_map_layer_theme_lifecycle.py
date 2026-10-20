"""Protect selected layer indexes across theme changes and scrubbing."""

import pytest
from PySide6.QtCore import QPersistentModelIndex, Qt

from src.core.map import MapLayerNode
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel

pytestmark = [
    pytest.mark.ci_fast,
    pytest.mark.usefixtures("isolated_theme_manager"),
]


@pytest.mark.parametrize("outside_only", [False, True])
@pytest.mark.parametrize(
    "theme",
    [
        "dark_mode",
        "light_mode",
        "fantasy_mode",
        "imperial_mode",
        "cyberpunk_mode",
        "muted_light_mode",
    ],
)
def test_theme_then_scrub_preserves_selected_layer(
    qtbot, theme, outside_only, qapp, monkeypatch
):
    node = MapLayerNode(
        name="Selected site", layer_type="marker", id="site", start_date=1000.0
    )
    group = MapLayerNode(name="Places", layer_type="group", children=[node])
    model = MapLayerModel(
        MapLayerNode(name="Root", layer_type="group", children=[group])
    )
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(qapp, "setStyleSheet", panel.setStyleSheet)
    monkeypatch.setattr(qapp, "setPalette", panel.setPalette)
    panel.set_model(model)
    panel.set_playhead_time(0.0)
    panel.set_temporal_filter_enabled(outside_only)
    panel.show()
    panel.select_node(node.id)
    selected = QPersistentModelIndex(panel._tree.currentIndex())
    changes = []
    model.layoutChanged.connect(lambda: changes.append("layout"))
    model.dataChanged.connect(lambda *_args: changes.append("data"))
    manager = ThemeManager()
    previous = manager.current_theme_name
    try:
        manager.set_theme(theme)
        # Recoloring changes decoration data, never the tree layout. Unpaired
        # layoutChanged leaves the filter proxy's persistent mappings stale.
        for time in range(25):
            model.set_current_time(float(time))
            qtbot.wait(1)
            assert selected.isValid()
            assert selected.data(MapLayerModel.NodeIdRole) == node.id
            assert panel._tree.currentIndex().data(Qt.ItemDataRole.DisplayRole) == (
                node.name
            )
        assert "layout" not in changes
        assert "data" in changes
    finally:
        manager.set_theme(previous)
