"""Tests for centralized node/edge mapping helpers in GraphBuilder.

Verifies that prepare_node and prepare_edge produce identical output
regardless of which render path uses them (full or incremental).
"""

import pytest

from src.gui.widgets.graph_view.graph_builder import GraphBuilder


class TestPrepareNode:
    """Tests for GraphBuilder.prepare_node static method."""

    def test_entity_node_uses_entity_color_and_shape(self) -> None:
        """Entity nodes get entity color and dot shape."""
        node = {"id": "n1", "name": "Kingdom", "object_type": "entity"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["id"] == "n1"
        assert result["label"] == "Kingdom"
        assert result["color"] == "#AAA"
        assert result["shape"] == GraphBuilder.ENTITY_SHAPE
        assert result["object_type"] == "entity"

    def test_event_node_uses_event_color_and_shape(self) -> None:
        """Event nodes get event color and diamond shape."""
        node = {"id": "n2", "name": "Battle", "object_type": "event"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["color"] == "#BBB"
        assert result["shape"] == GraphBuilder.EVENT_SHAPE

    def test_title_generated_from_object_type_and_name(self) -> None:
        """Title follows the pattern 'Type: Name'."""
        node = {"id": "n1", "name": "Hero", "object_type": "entity"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["title"] == "Entity: Hero"

    def test_missing_name_defaults_to_unnamed(self) -> None:
        """Nodes without a name key default to 'Unnamed' for label and title."""
        node = {"id": "n1", "object_type": "entity"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["label"] == "Unnamed"
        assert result["title"] == "Entity: Unnamed"

    def test_missing_object_type_defaults_to_entity(self) -> None:
        """Nodes without object_type default to entity for the field value."""
        node = {"id": "n1", "name": "Unknown"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["object_type"] == "entity"

    def test_size_is_always_20(self) -> None:
        """All nodes have size 20."""
        node = {"id": "n1", "name": "X", "object_type": "entity"}
        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB")

        assert result["size"] == 20


class TestPrepareEdge:
    """Tests for GraphBuilder.prepare_edge static method."""

    def test_source_and_target_mapped_to_from_and_to(self) -> None:
        """source_id maps to 'from' and target_id maps to 'to'."""
        edge = {"id": "e1", "source_id": "n1", "target_id": "n2", "rel_type": "ally"}
        result = GraphBuilder.prepare_edge(edge, "#CCC")

        assert result["from"] == "n1"
        assert result["to"] == "n2"

    def test_rel_type_mapped_to_label_and_title(self) -> None:
        """rel_type becomes both label and title."""
        edge = {"id": "e1", "source_id": "n1", "target_id": "n2", "rel_type": "ally"}
        result = GraphBuilder.prepare_edge(edge, "#CCC")

        assert result["label"] == "ally"
        assert result["title"] == "ally"

    def test_missing_rel_type_defaults_to_empty(self) -> None:
        """Missing rel_type defaults to empty string."""
        edge = {"source_id": "n1", "target_id": "n2"}
        result = GraphBuilder.prepare_edge(edge, "#CCC")

        assert result["label"] == ""
        assert result["title"] == ""

    def test_edge_color_applied(self) -> None:
        """Edge color is set from the parameter."""
        edge = {"source_id": "n1", "target_id": "n2"}
        result = GraphBuilder.prepare_edge(edge, "#FF0000")

        assert result["color"] == "#FF0000"

    def test_edge_id_preserved(self) -> None:
        """Edge id is preserved from input."""
        edge = {"id": "e1", "source_id": "n1", "target_id": "n2"}
        result = GraphBuilder.prepare_edge(edge, "#CCC")

        assert result["id"] == "e1"


class TestHelperConsistency:
    """Tests that full and incremental paths produce the same mapping."""

    def test_prepare_node_output_matches_build_network(self, qapp: None) -> None:
        """prepare_node produces the same fields as _build_network adds to PyVis."""
        builder = GraphBuilder()
        node = {"id": "n1", "name": "Test", "object_type": "entity"}
        theme = {
            "node_entity_color": "#E1",
            "node_event_color": "#E2",
            "edge_color": "#ED",
            "background_color": "#BG",
            "text_color": "#TX",
        }

        prepared = GraphBuilder.prepare_node(node, "#E1", "#E2")

        # Build a network via the full path and inspect the added node
        net = builder._build_network([node], [], "100%", "100%", theme)
        net_node = net.get_node("n1")

        assert prepared["label"] == net_node["label"]
        assert prepared["title"] == net_node["title"]
        assert prepared["color"] == net_node["color"]
        assert prepared["shape"] == net_node["shape"]
        assert prepared["size"] == net_node["size"]

    def test_prepare_edge_output_matches_build_network(self, qapp: None) -> None:
        """prepare_edge produces the same fields as _build_network adds to PyVis."""
        builder = GraphBuilder()
        nodes = [
            {"id": "n1", "name": "A", "object_type": "entity"},
            {"id": "n2", "name": "B", "object_type": "entity"},
        ]
        edge = {"id": "e1", "source_id": "n1", "target_id": "n2", "rel_type": "link"}
        theme = {
            "node_entity_color": "#E1",
            "node_event_color": "#E2",
            "edge_color": "#ED",
            "background_color": "#BG",
            "text_color": "#TX",
        }

        prepared = GraphBuilder.prepare_edge(edge, "#ED")

        net = builder._build_network(nodes, [edge], "100%", "100%", theme)
        # PyVis stores edges as list of dicts
        net_edges = net.get_edges()
        assert len(net_edges) == 1
        net_edge = net_edges[0]

        assert prepared["from"] == net_edge["from"]
        assert prepared["to"] == net_edge["to"]
        assert prepared["label"] == net_edge["label"]
        assert prepared["title"] == net_edge["title"]
        assert prepared["color"] == net_edge["color"]
