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

    # Default Theme Config
    DEFAULT_THEME = {
        "background_color": "#1e1e1e",
        "text_color": "#ffffff",
        "node_entity_color": "#4A90D9",
        "node_event_color": "#E67E22",
        "edge_color": "#888888",
    }

    def build_html(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        height: str = "100%",
        width: str = "100%",
        theme_config: dict[str, str] = None,
    ) -> str:
        """
        Builds a PyVis network and returns HTML string.

        Args:
            nodes: List of node dicts with id, name, type, object_type keys.
            edges: List of edge dicts with source_id, target_id, rel_type keys.
            height: Height of the graph visualization.
            width: Width of the graph visualization.
            theme_config: Optional dictionary with color settings.

        Returns:
            HTML string for embedding in QWebEngineView.
        """
        theme = theme_config or self.DEFAULT_THEME
        network = self._build_network(nodes, edges, height, width, theme)
        return self._generate_html(network, theme)

    def _build_network(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        height: str,
        width: str,
        theme: dict[str, str],
    ) -> Network:
        """
        Creates a PyVis Network from node/edge data.

        Args:
            nodes: List of node dicts.
            edges: List of edge dicts.
            height: Graph height.
            width: Graph width.
            theme: Theme configuration dictionary.

        Returns:
            Configured PyVis Network.
        """
        net = Network(
            height=height,
            width=width,
            bgcolor=theme.get("background_color", "#1e1e1e"),
            font_color=theme.get("text_color", "white"),
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
        entity_color = theme.get("node_entity_color", self.ENTITY_COLOR)
        event_color = theme.get("node_event_color", self.EVENT_COLOR)
        edge_color = theme.get("edge_color", "#888888")

        for node in nodes:
            color = entity_color if node.get("object_type") == "entity" else event_color
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
                object_type=node.get("object_type", "entity"),
            )

        # Add edges
        for edge in edges:
            net.add_edge(
                edge["source_id"],
                edge["target_id"],
                title=edge.get("rel_type", ""),
                label=edge.get("rel_type", ""),
                color=edge_color,
            )

        return net

    def _generate_html(self, network: Network, theme: dict[str, str]) -> str:
        """
        Generates HTML string from a PyVis network.

        Args:
            network: Configured PyVis Network.
            theme: Theme configuration dictionary.

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
        bg_color = theme.get("background_color", "#1e1e1e")

        background_fix_css = f"""
        <style>
            html, body {{
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                background-color: {bg_color};
                overflow: hidden;
            }}
            .card {{
                width: 100% !important;
                height: 100% !important;
                background-color: {bg_color};
                border: none !important;
                margin: 0 !important;
            }}
            .card-body {{
                width: 100% !important;
                height: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                background-color: {bg_color};
            }}
            #mynetwork {{
                width: 100% !important;
                height: 100% !important;
                background-color: {bg_color};
                border: none !important;
                margin: 0 !important;
            }}
            /* Hide unused header elements */
            h1, center {{
                display: none !important;
            }}
        </style>
        """
        # Insert CSS right after <head>
        html_content = html_content.replace("<head>", f"<head>{background_fix_css}")

        # Inject QWebChannel script and interaction logic
        qwebchannel_script = (
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
        )

        # We need to hook into the pyvis generated script.
        # PyVis creates a variable 'network' (the vis.Network instance) and 'nodes'.
        # We append our script at the end of the body to ensure variable exists.

        interaction_script = """
        <script type="text/javascript">
            // Setup QWebChannel
            document.addEventListener("DOMContentLoaded", function() {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.bridge = channel.objects.bridge;
                });
            });

            // Wait for network to be initialized (PyVis usually inits at bottom).
            // Safer to set timeout or check if network is defined.
            // PyVis 0.3.2+ typically matches 'network' variable name.
            
            var checkNetwork = setInterval(function() {
                if (typeof network !== 'undefined') {
                    clearInterval(checkNetwork);
                    
                    network.on("click", function (params) {
                        if (params.nodes.length > 0) {
                            var nodeId = params.nodes[0];
                            // We need to look up object_type.
                            // PyVis 'nodes' is a vis.DataSet or DataView.
                            var nodeData = nodes.get(nodeId);
                            
                            if (nodeData && window.bridge) {
                                // Default to 'entity' if missing, but should be there
                                var objType = nodeData.object_type || "entity";
                                window.bridge.nodeClicked(objType, String(nodeId));
                            }
                        }
                    });
                }
            }, 100);
        </script>
        """

        html_content = html_content.replace(
            "</body>", f"{qwebchannel_script}\n{interaction_script}\n</body>"
        )

        return html_content

    def build_empty_html(self, theme_config: dict[str, str] = None) -> str:
        """
        Returns HTML for an empty state message.

        Args:
            theme_config: Optional dictionary with color settings.

        Returns:
            HTML string with empty state message.
        """
        theme = theme_config or self.DEFAULT_THEME
        bg_color = theme.get("background_color", "#1e1e1e")
        text_color = theme.get("text_color", "#888888")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    background-color: {bg_color};
                    color: {text_color};
                    font-family: 'Segoe UI', sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .message {{
                    text-align: center;
                }}
                h2 {{ color: {text_color}; opacity: 0.7; }}
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
