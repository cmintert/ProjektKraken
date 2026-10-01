from unittest.mock import MagicMock

import pytest
from pytestqt.qtbot import QtBot

from src.gui.widgets.graph_view.graph_web_view import GraphWebView

pytestmark = pytest.mark.ci_fast


def test_update_graph_data_maps_properties_correctly(qapp: object, qtbot: QtBot) -> None:
    """Test that update_graph_data correctly maps Python-side properties to Vis.js ones.

    Specifically verifies:
    - name -> label (for nodes)
    - source_id -> from (for edges)
    - target_id -> to (for edges)
    """
    web_view = GraphWebView()
    qtbot.addWidget(web_view)

    # Mock the internal QWebEngineView and its page
    mock_engine_view = MagicMock()
    mock_page = MagicMock()

    # Replace the rendering collaborator while preserving the real wrapper.
    web_view._web_view = mock_engine_view
    mock_engine_view.page.return_value = mock_page

    # Input Data
    nodes = [{"id": "n1", "name": "Test Node", "type": "entity"}]
    edges = [
        {"id": "e1", "source_id": "n1", "target_id": "n2", "rel_type": "linked_to"}
    ]

    # Call method
    web_view.update_graph_data(nodes, edges)

    # Verify runJavaScript was called
    mock_page.runJavaScript.assert_called_once()
    script = mock_page.runJavaScript.call_args[0][0]

    # Check for Node Mapping (name -> label)
    # Simple substring check is robust enough for JSON structure verification here
    assert '"label": "Test Node"' in script

    # Check for Edge Mapping (source_id -> from, target_id -> to)
    assert '"from": "n1"' in script
    assert '"to": "n2"' in script

    # Check for Edge Label/Title mapping from rel_type
    assert '"label": "linked_to"' in script
    assert '"title": "linked_to"' in script
