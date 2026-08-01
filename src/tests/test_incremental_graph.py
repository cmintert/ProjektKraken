from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from src.gui.widgets.graph_view.graph_widget import GraphWidget


@pytest.fixture
def graph_widget(qapp: Any) -> GraphWidget:
    """Fixture for GraphWidget with mocked internal components."""
    widget = GraphWidget()

    # Mock the internal web view
    widget._web_view = MagicMock()

    # Mock the builder
    widget._builder = MagicMock()
    widget._builder.build_html.return_value = "<html>Graph</html>"

    return widget


def _web_view_mock(widget: GraphWidget) -> MagicMock:
    """Return the deliberately mocked web-view collaborator."""
    return cast(MagicMock, widget._web_view)


def test_initial_load_uses_full_reload(graph_widget: GraphWidget) -> None:
    """Test that the first call to display_graph uses load_html (full reload)."""
    nodes = [{"id": "1"}]
    edges: list[dict[str, Any]] = []
    web_view = _web_view_mock(graph_widget)

    graph_widget.display_graph(nodes, edges)

    # Should use load_html for the first time
    web_view.load_html.assert_called_once()
    # Should NOT use update_graph_data yet
    if hasattr(web_view, "update_graph_data"):
        web_view.update_graph_data.assert_not_called()


def test_subsequent_load_uses_incremental_update(graph_widget: GraphWidget) -> None:
    """Test that subsequent calls to display_graph use update_graph_data."""
    nodes_1 = [{"id": "1"}]
    edges_1: list[dict[str, Any]] = []
    web_view = _web_view_mock(graph_widget)

    # 1. First load
    graph_widget.display_graph(nodes_1, edges_1)
    web_view.load_html.assert_called_once()

    # Reset mocks for next stage
    web_view.load_html.reset_mock()

    # 2. Second load (Refresh with same or different data)
    nodes_2 = [{"id": "1"}, {"id": "2"}]
    edges_2: list[dict[str, Any]] = []

    # We call display_graph again
    graph_widget.display_graph(nodes_2, edges_2)

    # Should NOT call load_html again (no flicker)
    web_view.load_html.assert_not_called()

    # Should call update_graph_data (incremental update)
    # This will fail initially because the method doesn't exist or isn't called
    assert hasattr(web_view, "update_graph_data")
    web_view.update_graph_data.assert_called_once()
    call_args = web_view.update_graph_data.call_args
    assert call_args[0][0] == nodes_2
    assert call_args[0][1] == edges_2
    assert call_args[1]["focus_id"] is None


def test_theme_change_forces_full_reload(graph_widget: GraphWidget) -> None:
    """Test that changing themes still forces a full load_html call."""
    nodes = [{"id": "1"}]
    edges: list[dict[str, Any]] = []
    web_view = _web_view_mock(graph_widget)

    # 1. First load
    graph_widget.display_graph(nodes, edges)
    web_view.load_html.reset_mock()

    # 2. Simulate theme change (manual call for test)
    # In real app, this clears _is_renderer_ready (if we implement it that way)
    graph_widget._on_theme_changed({"app_bg": "#FFFFFF"})

    # Should call load_html to rebuild with new colors
    web_view.load_html.assert_called()


def test_rename_entity_updates_graph(graph_widget: GraphWidget) -> None:
    """Test that renaming an entity updates the label in the graph."""
    nodes_1 = [{"id": "1", "label": "Old Name", "title": "Old Name"}]
    edges: list[dict[str, Any]] = []
    web_view = _web_view_mock(graph_widget)

    # 1. First load
    graph_widget.display_graph(nodes_1, edges)
    web_view.load_html.assert_called_once()

    # Reset mocks
    web_view.load_html.reset_mock()
    web_view.update_graph_data = MagicMock()

    # 2. Rename (same ID, new label)
    # Note: GraphWidget passes the raw node dict (with "name"), handled by GraphWebView
    nodes_2 = [{"id": "1", "name": "New Name", "title": "New Name"}]

    # We call display_graph again
    graph_widget.display_graph(nodes_2, edges)

    # Should call update_graph_data
    web_view.update_graph_data.assert_called_once()

    # Verify the arguments passed to update_graph_data
    # We verify that GraphWidget passes the new name correctly
    call_args = web_view.update_graph_data.call_args
    assert call_args is not None
    updated_nodes = call_args[0][0]
    assert updated_nodes[0]["name"] == "New Name"
