from PySide6.QtCore import Qt

from src.app.constants import MAP_LAYER_TYPE_GROUP, MAP_LAYER_TYPE_MARKER
from src.core.map import MapLayerNode
from src.gui.widgets.map.map_layer_model import MapLayerModel


class MockMapWidget:
    def __init__(self, model):
        self._layer_model = model
        self.rename_requested_signal_received = []

    def _on_layer_renamed(self, node_id: str, new_name: str) -> None:
        """Handle a layer rename from the panel.
        Updates the node name in the model, refreshes the view, and emits
        a signal so the command stack can persist the change.
        """
        if self._layer_model is None:
            return
        node = self._layer_model.find_node_by_id(node_id)
        if node is None:
            return

        node.name = new_name
        idx = self._layer_model.index_from_node(node)

        # This is the logic from map_widget.py
        self._layer_model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
        self._layer_model.layer_tree_changed.emit()
        self.rename_requested_signal_received.append((node_id, new_name))


def test_renaming_flow():
    # Setup model
    root = MapLayerNode(name="Root", layer_type=MAP_LAYER_TYPE_GROUP)
    child = MapLayerNode(
        name="Old Name", layer_type=MAP_LAYER_TYPE_MARKER, id="test-node"
    )
    root.children.append(child)

    model = MapLayerModel(root=root)
    widget = MockMapWidget(model)

    # Simulate signal from panel
    widget._on_layer_renamed("test-node", "New Name")

    # Verify model update
    node = model.find_node_by_id("test-node")
    assert node.name == "New Name"

    # Verify persistence signal (simulated)
    assert len(widget.rename_requested_signal_received) == 1
    assert widget.rename_requested_signal_received[0] == ("test-node", "New Name")

    # Verify data() returns correct display value
    idx = model.index_from_node(node)
    display_data = model.data(idx, Qt.ItemDataRole.DisplayRole)
    # Note: DisplayRole includes icon prefix
    assert "New Name" in display_data


if __name__ == "__main__":
    test_renaming_flow()
