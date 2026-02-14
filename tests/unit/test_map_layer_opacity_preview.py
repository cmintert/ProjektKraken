"""Unit tests for the MapLayerModel opacity preview functionality.

Verifies that:
1. set_node_opacity(preview=True) updates the node locally.
2. set_node_opacity(preview=True) does NOT emit layer_tree_changed.
3. set_node_opacity(preview=False) emits layer_tree_changed.
"""

import pytest

from src.app.constants import MAP_LAYER_TYPE_MARKER
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel


@pytest.fixture
def model() -> MapLayerModel:
    """A minimal model for testing."""
    root = MapLayerNode(
        name="Root",
        id="root",
        children=[
            MapLayerNode(
                name="Marker Layer",
                layer_type=MAP_LAYER_TYPE_MARKER,
                id="marker-layer",
                opacity=1.0,
            )
        ],
    )
    return MapLayerModel(root=root)


def test_preview_opacity_updates_local_state(model: MapLayerModel) -> None:
    """Preview mode should still update the node's opacity value."""
    node = model.find_node_by_id("marker-layer")
    assert node is not None
    assert node.opacity == 1.0

    model.set_node_opacity(node, 0.5, preview=True)

    assert node.opacity == 0.5


def test_preview_opacity_suppresses_tree_changed_signal(model: MapLayerModel) -> None:
    """Preview mode should NOT emit layer_tree_changed (preventing auto-save)."""
    received: list[bool] = []
    model.layer_tree_changed.connect(lambda: received.append(True))

    node = model.find_node_by_id("marker-layer")
    assert node is not None

    # Enable preview mode
    model.set_node_opacity(node, 0.5, preview=True)

    # Should not have received signal
    assert len(received) == 0


def test_commit_opacity_emits_tree_changed_signal(model: MapLayerModel) -> None:
    """Normal mode (preview=False) SHOULD emit layer_tree_changed."""
    received: list[bool] = []
    model.layer_tree_changed.connect(lambda: received.append(True))

    node = model.find_node_by_id("marker-layer")
    assert node is not None

    # Disable preview mode (default)
    model.set_node_opacity(node, 0.5, preview=False)

    # Should have received signal
    assert len(received) == 1
