"""Protect proxy indexes when a layer removal shifts its destination group."""

import pytest
from PySide6.QtCore import QPersistentModelIndex
from PySide6.QtTest import QAbstractItemModelTester

from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map.map_layer_panel import MapLayerPanel

pytestmark = pytest.mark.ci_fast


@pytest.mark.parametrize("outside_only", [False, True])
def test_move_to_shifted_group_preserves_proxy_mapping(qtbot, outside_only):
    """Insertion must announce the group's new row after removing its sibling."""
    site = MapLayerNode(name="Site", layer_type="region", start_date=100.0)
    other = MapLayerNode(name="Other", layer_type="marker", start_date=100.0)
    group = MapLayerNode(name="Group", layer_type="group", children=[other])
    raster = MapLayerNode(name="Raster", layer_type="raster")
    model = MapLayerModel(
        MapLayerNode(name="Root", layer_type="group", children=[site, group, raster])
    )
    panel = MapLayerPanel()
    qtbot.addWidget(panel)
    panel.set_model(model)
    panel.set_playhead_time(0.0)
    panel.set_temporal_filter_enabled(outside_only)
    panel.show()
    tester = QAbstractItemModelTester(
        panel._proxy_model, QAbstractItemModelTester.FailureReportingMode.Warning
    )
    group_proxy = QPersistentModelIndex(
        panel._proxy_model.mapFromSource(model.index_from_node(group))
    )
    other_proxy = QPersistentModelIndex(
        panel._proxy_model.mapFromSource(model.index_from_node(other))
    )
    assert model.move_layer(
        model.index_from_node(site), model.index_from_node(group), 0
    )
    assert model.root.children == [group, raster]
    assert group.children == [site, other]
    assert group_proxy.isValid() and group_proxy.row() == 0
    assert other_proxy.isValid() and other_proxy.row() == 1
    proxy_site = panel._proxy_model.mapFromSource(model.index_from_node(site))
    assert proxy_site.isValid()
    assert proxy_site.parent() == group_proxy
    assert proxy_site.data(MapLayerModel.NodeIdRole) == site.id
    assert other_proxy.data(MapLayerModel.NodeIdRole) == other.id
    panel.set_playhead_time(1.0)
    qtbot.wait(1)
    assert tester
