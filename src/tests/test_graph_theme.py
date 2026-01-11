from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.gui.widgets.graph_view.graph_widget import GraphWidget


@pytest.fixture
def graph_widget(qapp: Any) -> GraphWidget:
    """Fixture for GraphWidget."""
    widget = GraphWidget()
    return widget


def test_theme_change_triggers_update(graph_widget: GraphWidget) -> None:
    """Test that changing the theme updates the graph configuration."""

    # Mock builder to check calls
    graph_widget._builder = MagicMock()
    graph_widget._builder.build_empty_html.return_value = "<html>Empty</html>"
    graph_widget._builder.build_html.return_value = "<html>Graph</html>"

    # Mock web view to check background calls
    graph_widget._web_view = MagicMock()

    # Mock data to ensure we hit the render path
    graph_widget._all_nodes = [{"id": "1", "name": "Node", "object_type": "entity"}]
    graph_widget._all_edges = []

    # Simulate theme change signal with keys from BaseThemeManager
    new_theme_data = {
        "app_bg": "#FF0000",
        "text_main": "#00FF00",
        "accent_secondary": "#0000FF",
        "primary": "#FFFF00",
        "text_dim": "#00FFFF",
    }

    # Mock get_theme to return our new theme
    with patch.object(
        graph_widget._theme_manager, "get_theme", return_value=new_theme_data
    ):
        graph_widget._on_theme_changed(new_theme_data)

    # Check if _get_current_theme_config extracted and mapped correctly
    config = graph_widget._current_theme_config
    assert config["background_color"] == "#FF0000"  # app_bg
    assert config["text_color"] == "#00FF00"  # text_main
    assert config["node_entity_color"] == "#0000FF"  # accent_secondary

    # Verify set_background_color was called on web view
    graph_widget._web_view.set_background_color.assert_called_with("#FF0000")

    # verify builder was called with new config
    # Since we have nodes, build_html should be called
    graph_widget._builder.build_html.assert_called()
    call_args = graph_widget._builder.build_html.call_args
    assert call_args.kwargs["theme_config"] == config
