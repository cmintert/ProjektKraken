"""
Graph Builder Module.

Business logic layer for building PyVis networks from graph data.
Stateless utility class that transforms node/edge data into HTML output.
"""

import logging
import tempfile
from typing import Any

from pyvis.network import Network

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds PyVis Network from node/edge data.

    This is a stateless utility class in the business logic layer.
    It knows only about PyVis, not about Qt or database concerns.
    """

    # Node styling by object_type
    ENTITY_COLOR = "#4A90D9"  # Blue for entities
    EVENT_COLOR = "#E67E22"  # Orange for events
    ENTITY_SHAPE = "dot"
    EVENT_SHAPE = "diamond"

    # Graph options
    DEFAULT_HEIGHT = "100%"
    DEFAULT_WIDTH = "100%"

    def build_html(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        height: str = "100%",
        width: str = "100%",
    ) -> str:
        """
        Builds a PyVis network and returns HTML string.

        Args:
            nodes: List of node dicts with id, name, type, object_type keys.
            edges: List of edge dicts with source_id, target_id, rel_type keys.
            height: Height of the graph visualization.
            width: Width of the graph visualization.

        Returns:
            HTML string for embedding in QWebEngineView.
        """
        network = self._build_network(nodes, edges, height, width)
        return self._generate_html(network)

    def _build_network(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        height: str,
        width: str,
    ) -> Network:
        """
        Creates a PyVis Network from node/edge data.

        Args:
            nodes: List of node dicts.
            edges: List of edge dicts.
            height: Graph height.
            width: Graph width.

        Returns:
            Configured PyVis Network.
        """
        net = Network(
            height=height,
            width=width,
            bgcolor="#1e1e1e",  # Dark background
            font_color="white",
            directed=True,
        )

        # Configure physics for better layout
        net.set_options(
            """
        {
            "physics": {
                "enabled": true,
                "barnesHut": {
                    "gravitationalConstant": -8000,
                    "centralGravity": 0.3,
                    "springLength": 150,
                    "springConstant": 0.04
                },
                "stabilization": {
                    "iterations": 100
                }
            },
            "nodes": {
                "borderWidth": 2,
                "font": {
                    "size": 12,
                    "face": "Segoe UI"
                }
            },
            "edges": {
                "arrows": {
                    "to": {
                        "enabled": true,
                        "scaleFactor": 0.5
                    }
                },
                "font": {
                    "size": 10,
                    "align": "middle"
                },
                "smooth": {
                    "type": "curvedCW",
                    "roundness": 0.2
                }
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200
            }
        }
        """
        )

        # Add nodes
        for node in nodes:
            color = (
                self.ENTITY_COLOR
                if node.get("object_type") == "entity"
                else self.EVENT_COLOR
            )
            shape = (
                self.ENTITY_SHAPE
                if node.get("object_type") == "entity"
                else self.EVENT_SHAPE
            )

            net.add_node(
                node["id"],
                label=node.get("name", "Unnamed"),
                title=f"{node.get('object_type', 'item').title()}: {node.get('name')}",
                color=color,
                shape=shape,
                size=20,
            )

        # Add edges
        for edge in edges:
            net.add_edge(
                edge["source_id"],
                edge["target_id"],
                title=edge.get("rel_type", ""),
                label=edge.get("rel_type", ""),
                color="#888888",
            )

        return net

    def _generate_html(self, network: Network) -> str:
        """
        Generates HTML string from a PyVis network.

        Args:
            network: Configured PyVis Network.

        Returns:
            HTML string.
        """
        # PyVis requires writing to a file, so we use a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            network.save_graph(f.name)
            f.flush()

            # Read back the HTML
            with open(f.name, encoding="utf-8") as html_file:
                html_content = html_file.read()

        # Inject CSS to set background color and ensure full container height
        # PyVis uses a .card container, so we must force it to full height
        # Also hide header elements that might cause white slivers
        background_fix_css = """
        <style>
            html, body {
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                background-color: #1e1e1e;
                overflow: hidden;
            }
            .card {
                width: 100% !important;
                height: 100% !important;
                background-color: #1e1e1e;
                border: none !important;
                margin: 0 !important;
            }
            .card-body {
                width: 100% !important;
                height: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                background-color: #1e1e1e;
            }
            #mynetwork {
                width: 100% !important;
                height: 100% !important;
                background-color: #1e1e1e;
                border: none !important;
                margin: 0 !important;
            }
            /* Hide unused header elements */
            h1, center {
                display: none !important;
            }
        </style>
        """
        # Insert CSS right after <head>
        html_content = html_content.replace("<head>", f"<head>{background_fix_css}")

        return html_content

    def build_empty_html(self) -> str:
        """
        Returns HTML for an empty state message.

        Returns:
            HTML string with empty state message.
        """
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    background-color: #1e1e1e;
                    color: #888;
                    font-family: 'Segoe UI', sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .message {
                    text-align: center;
                }
                h2 { color: #aaa; }
            </style>
        </head>
        <body>
            <div class="message">
                <h2>No Data to Display</h2>
                <p>Select tags or relation types to filter, then click Refresh.</p>
            </div>
        </body>
        </html>
        """
