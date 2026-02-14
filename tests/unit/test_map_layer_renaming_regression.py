"""
Regression test for MapWidget layer renaming double-signal issue.
Verifies that renaming a layer does NOT emit layer_tree_changed.
"""

from unittest.mock import MagicMock

import pytest

from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel
from src.gui.widgets.map_widget import MapWidget


@pytest.fixture
def map_widget(qtbot):
    widget = MapWidget()
    # Mock view to avoid heavy graphics initialization
    widget.view = MagicMock()
    qtbot.addWidget(widget)
    return widget


def test_layer_rename_no_double_signals(map_widget):
    """
    Test that _on_layer_renamed does NOT emit layer_tree_changed.
    It should only emit layer_rename_requested to avoid double commands (SaveLayerTree + RenameLayer).
    """
    # Setup model
    root = MapLayerNode(name="Root")
    child = MapLayerNode(name="Name", id="test-node")
    root.children.append(child)
    model = MapLayerModel(root)

    # Inject model into widget
    map_widget._layer_model = model

    # Spies
    tree_changed_spy = []
    rename_requested_spy = []

    map_widget.layer_tree_changed.connect(lambda: tree_changed_spy.append(True))
    map_widget.layer_rename_requested.connect(
        lambda nid, name: rename_requested_spy.append((nid, name))
    )

    # Connect model signal to widget (as done in _build_layer_model)
    model.layer_tree_changed.connect(map_widget.layer_tree_changed.emit)

    # Trigger rename
    map_widget._on_layer_renamed("test-node", "New Name")

    # Assertions
    # 1. Rename requested should be emitted
    assert len(rename_requested_spy) == 1
    assert rename_requested_spy[0] == ("test-node", "New Name")

    # 2. Layer tree changed should NOT be emitted
    assert len(tree_changed_spy) == 0
