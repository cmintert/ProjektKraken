import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.graph import export_graph


@pytest.fixture
def mock_db_service():
    with patch("src.cli.graph.DatabaseService") as mock:
        yield mock


@pytest.fixture
def mock_graph_service():
    with patch("src.cli.graph.GraphDataService") as mock:
        yield mock


def test_export_graph_success(mock_db_service, mock_graph_service, tmp_path):
    """Test successful graph export."""
    out_file = tmp_path / "graph.json"
    args = argparse.Namespace(
        database="world.kraken", out_file=str(out_file), tags=None, verbose=False
    )

    service_instance = mock_graph_service.return_value
    test_data = {"nodes": [{"id": "1", "label": "Node 1"}], "edges": []}
    service_instance.get_graph_data.return_value = test_data

    assert export_graph(args) == 0

    # Verify file content
    assert out_file.exists()
    with open(out_file) as f:
        data = json.load(f)
        assert data == test_data


def test_export_graph_with_tags(mock_db_service, mock_graph_service, tmp_path):
    """Test graph export with tag filtering."""
    out_file = tmp_path / "graph.json"
    args = argparse.Namespace(
        database="world.kraken",
        out_file=str(out_file),
        tags="tag1, tag2",
        verbose=False,
    )

    service_instance = mock_graph_service.return_value
    service_instance.get_graph_data.return_value = {"nodes": [], "edges": []}

    assert export_graph(args) == 0

    service_instance.get_graph_data.assert_called_once()
    call_kwargs = service_instance.get_graph_data.call_args.kwargs
    assert call_kwargs["include_tags"] == ["tag1", "tag2"]


def test_export_graph_failure(mock_db_service, mock_graph_service, tmp_path):
    """Test failed graph export."""
    out_file = tmp_path / "graph.json"
    args = argparse.Namespace(
        database="world.kraken", out_file=str(out_file), tags=None, verbose=False
    )

    service_instance = mock_graph_service.return_value
    service_instance.get_graph_data.side_effect = Exception("DB Error")

    assert export_graph(args) == 1
