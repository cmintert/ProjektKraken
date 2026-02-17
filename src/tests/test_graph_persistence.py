from typing import Any
from unittest.mock import MagicMock, call

import pytest
from PySide6.QtCore import QObject, Signal

from src.gui.widgets.graph_view.graph_widget import GraphWidget


# Mock the bridge signal which doesn't exist yet on the real class
class MockBridge(QObject):
    node_clicked = Signal(str, str)
    view_state_changed = Signal(dict)


@pytest.fixture
def graph_widget(qapp: Any) -> GraphWidget:
    """Fixture for GraphWidget with mocked internal components."""
    widget = GraphWidget()

    # Mock the internal web view and its bridge
    widget._web_view = MagicMock()
    # We need a real QObject for the bridge to emit signals
    widget._web_view._bridge = MockBridge()

    # Mock the builder
    widget._builder = MagicMock()
    widget._builder.build_html.return_value = "<html>Graph</html>"

    # Initialize _last_focus_node_id if it doesn't exist yet (simulating implementation)
    if not hasattr(widget, "_last_focus_node_id"):
        widget._last_focus_node_id = None

    return widget


def test_view_state_caching(graph_widget: GraphWidget) -> None:
    """Test that view state from the bridge is cached in the widget."""
    test_state = {"scale": 1.5, "position": {"x": 100, "y": 200}}

    # Manually trigger connection simulation
    if hasattr(graph_widget, "_on_view_state_changed"):
        graph_widget._web_view._bridge.view_state_changed.connect(
            graph_widget._on_view_state_changed
        )

    graph_widget._web_view._bridge.view_state_changed.emit(test_state)
    assert getattr(graph_widget, "_last_view_state", None) == test_state


def test_display_graph_same_focus_id_preserves_state(graph_widget: GraphWidget) -> None:
    """Test that refreshing with the SAME focus_node_id preserves view state."""
    # 1. Setup: User was looking at Node 1, zoomed in
    test_state = {"scale": 2.0, "position": {"x": 10, "y": 20}}
    setattr(graph_widget, "_last_view_state", test_state)

    # We pretend the widget already knows we are looking at Node 1
    graph_widget._last_focus_node_id = "1"

    nodes = [{"id": "1", "name": "Entity 1"}]
    edges = []

    # 2. Action: Refresh data for Node 1 (Simulated Save)
    graph_widget.display_graph(nodes, edges, focus_node_id="1")

    # 3. Verify: Builder receives the PRESERVED view state
    graph_widget._builder.build_html.assert_called()
    call_args = graph_widget._builder.build_html.call_args
    assert call_args.kwargs.get("view_state") == test_state

    # Verify we updated the tracking (it remains "1")
    assert graph_widget._last_focus_node_id == "1"


def test_display_graph_diff_focus_id_resets_state(graph_widget: GraphWidget) -> None:
    """Test that switching to a DIFFERENT focus_node_id resets view state."""
    # 1. Setup: User was looking at Node 1
    test_state = {"scale": 2.0, "position": {"x": 10, "y": 20}}
    setattr(graph_widget, "_last_view_state", test_state)
    graph_widget._last_focus_node_id = "1"

    nodes = [{"id": "1"}, {"id": "2"}]
    edges = []

    # 2. Action: Navigate to Node 2
    graph_widget.display_graph(nodes, edges, focus_node_id="2")

    # 3. Verify: Builder receives NONE for view_state (Reset)
    graph_widget._builder.build_html.assert_called()
    call_args = graph_widget._builder.build_html.call_args
    assert call_args.kwargs.get("view_state") is None

    # Verify we updated the tracking
    assert graph_widget._last_focus_node_id == "2"


def test_display_graph_no_focus_id_resets_state(graph_widget: GraphWidget) -> None:
    """Test that clearing focus (None) resets view state."""
    # 1. Setup: User was looking at Node 1
    test_state = {"scale": 2.0, "position": {"x": 10, "y": 20}}
    setattr(graph_widget, "_last_view_state", test_state)
    graph_widget._last_focus_node_id = "1"

    # 2. Action: Clear selection but keep data -> should reset view to default layout
    nodes = [{"id": "1"}, {"id": "2"}]
    edges = []
    graph_widget.display_graph(nodes, edges, focus_node_id=None)

    # 3. Verify: Builder receives NONE
    graph_widget._builder.build_html.assert_called()
    call_args = graph_widget._builder.build_html.call_args
    assert call_args.kwargs.get("view_state") is None

    # Verify we updated the tracking
    assert graph_widget._last_focus_node_id is None
