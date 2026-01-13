"""
Graph Builder Module.

Business logic layer for building PyVis networks from graph data.
Stateless utility class that transforms node/edge data into HTML output.

Note: Requires optional graph dependency (pyvis).
Install with: pip install -e .[graph]
"""

import json
import logging
import os
import re
import tempfile
from typing import Any

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "PyVis not available. Graph visualization disabled. "
        "Install with: pip install -e .[graph]"
    )

from src.core.paths import get_resource_path

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

    # Cached local vis-network library content
    _vis_js_content: str | None = None
    _vis_css_content: str | None = None
    _vis_utils_content: str | None = None

    @classmethod
    def _load_local_vis_assets(cls) -> tuple[str, str, str]:
        """
        Loads local vis-network JS, CSS, and PyVis utils files for offline use.

        Caches the content on first load to avoid repeated file I/O.

        Returns:
            Tuple of (js_content, css_content, utils_content) strings.
        """
        if cls._vis_js_content is None or cls._vis_css_content is None:
            try:
                vis_js_path = get_resource_path(
                    os.path.join("lib", "vis-9.1.2", "vis-network.min.js")
                )
                vis_css_path = get_resource_path(
                    os.path.join("lib", "vis-9.1.2", "vis-network.css")
                )
                vis_utils_path = get_resource_path(
                    os.path.join("lib", "bindings", "utils.js")
                )

                with open(vis_js_path, encoding="utf-8") as f:
                    cls._vis_js_content = f.read()

                with open(vis_css_path, encoding="utf-8") as f:
                    cls._vis_css_content = f.read()

                with open(vis_utils_path, encoding="utf-8") as f:
                    cls._vis_utils_content = f.read()

                logger.debug(
                    f"Loaded vis-network assets: JS={len(cls._vis_js_content)} bytes, "
                    f"CSS={len(cls._vis_css_content)} bytes, "
                    f"Utils={len(cls._vis_utils_content)} bytes"
                )

            except FileNotFoundError as e:
                logger.error(f"Local vis-network assets not found: {e}")
                cls._vis_js_content = ""
                cls._vis_css_content = ""
                cls._vis_utils_content = ""

        return cls._vis_js_content, cls._vis_css_content, cls._vis_utils_content

    def build_html(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        height: str = "100%",
        width: str = "100%",
        theme_config: dict[str, str] = None,
        focus_node_id: str | None = None,
    ) -> str:
        """
        Builds a PyVis network and returns HTML string.

        Args:
            nodes: List of node dicts with id, name, type, object_type keys.
            edges: List of edge dicts with source_id, target_id, rel_type keys.
            height: Height of the graph visualization.
            width: Width of the graph visualization.
            theme_config: Optional dictionary with color settings.
            focus_node_id: Optional ID of the node to focus on stabilize.

        Returns:
            HTML string for embedding in QWebEngineView.
        """
        if not PYVIS_AVAILABLE:
            error_msg = "PyVis not installed. Install with: pip install -e .[graph]"
            logger.error(error_msg)
            return f"""
            <html><body style="background:#1e1e1e;color:#fff;padding:20px;">
            <h2>Graph Visualization Unavailable</h2>
            <p>{error_msg}</p>
            </body></html>
            """
        
        try:
            theme = theme_config or self.DEFAULT_THEME
            network = self._build_network(nodes, edges, height, width, theme)
            html = self._generate_html(network, theme, focus_node_id)
            logger.debug(
                f"Generated graph HTML: {len(nodes)} nodes, {len(edges)} edges"
            )
            return html
        except Exception as e:
            logger.error(f"Failed to build graph: {type(e).__name__}: {e}")
            # Return error HTML so user can see the problem
            error_msg = str(e).replace('"', "&quot;")
            return f"""
            <html><body style="background:#1e1e1e;color:#fff;padding:20px;">
            <h2>Graph Error</h2>
            <p>Failed to build graph: {type(e).__name__}: {error_msg}</p>
            </body></html>
            """

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

    def _generate_html(
        self, network: Network, theme: dict[str, str], focus_node_id: str | None = None
    ) -> str:
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
            temp_path = f.name
            network.save_graph(temp_path)
            f.flush()

        # Read back the HTML and clean up
        try:
            with open(temp_path, encoding="utf-8") as html_file:
                html_content = html_file.read()
        finally:
            os.unlink(temp_path)

        # Replace CDN-loaded vis-network with inline local assets for offline use
        vis_js, vis_css, vis_utils = self._load_local_vis_assets()
        if vis_js and vis_css:
            # Remove CDN script tags for vis-network
            html_content = re.sub(
                r'<script[^>]*src="[^"]*vis-network[^"]*"[^>]*>\s*</script>',
                "",
                html_content,
            )
            # Remove CDN link tags for vis-network CSS
            html_content = re.sub(
                r'<link[^>]*href="[^"]*vis-network[^"]*"[^>]*/?>',
                "",
                html_content,
            )
            # Remove Bootstrap CDN (not needed for embedded graph)
            html_content = re.sub(
                r'<link[^>]*href="[^"]*bootstrap[^"]*"[^>]*/?>',
                "",
                html_content,
            )
            html_content = re.sub(
                r'<script[^>]*src="[^"]*bootstrap[^"]*"[^>]*>\s*</script>',
                "",
                html_content,
            )
            # Remove PyVis utils.js relative path reference (doesn't work with setHtml)
            html_content = re.sub(
                r'<script[^>]*src="lib/bindings/utils\.js"[^>]*>\s*</script>',
                "",
                html_content,
            )

            # Inject local vis-network CSS, JS, and utils inline
            inline_vis = f"""
            <style type="text/css">{vis_css}</style>
            <script type="text/javascript">{vis_js}</script>
            <script type="text/javascript">{vis_utils}</script>
            """
            # Insert after <head>
            html_content = html_content.replace("<head>", f"<head>{inline_vis}")

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
                    
                    // Interaction: Click
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

                    // Interaction: Restore Focus
                    // Use 'stabilized' event which fires when physics stops
                    var focusId = %FOCUS_ID%;
                    
                    function restoreFocus() {
                        if (focusId !== null) {
                            // Check if node exists in dataset
                            var nodeData = nodes.get(focusId);
                            if (nodeData) {
                                // Select node visually
                                network.selectNodes([focusId]);
                                // Focus view on node
                                network.focus(focusId, {
                                    scale: 1.0,
                                    animation: {
                                        duration: 500,
                                        easingFunction: "easeInOutQuad"
                                    }
                                });
                                console.log("Graph: Focused on node", focusId);
                            } else {
                                console.log("Graph: Focus node not found", focusId);
                            }
                        }
                    }
                    
                    // Try stabilized event first, with timeout fallback
                    var focusRestored = false;
                    network.once("stabilized", function() {
                        if (!focusRestored) {
                            focusRestored = true;
                            restoreFocus();
                        }
                    });
                    
                    // Fallback: if stabilized doesn't fire within 2s, force focus
                    setTimeout(function() {
                        if (!focusRestored) {
                            focusRestored = true;
                            restoreFocus();
                        }
                    }, 2000);
                }
            }, 100);
        </script>
        """

        # Replace placeholder with JSON-serialized ID for safe JS injection
        focus_json = json.dumps(focus_node_id) if focus_node_id else "null"
        interaction_script = interaction_script.replace("%FOCUS_ID%", focus_json)

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
