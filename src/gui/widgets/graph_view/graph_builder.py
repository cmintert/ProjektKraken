"""Graph Builder Module.

Business logic layer for building PyVis networks from graph data. Stateless utility
class that transforms node/edge data into HTML output.
"""

import base64
import json
import logging
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from pyvis.network import Network

from src.core.paths import get_resource_path

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds PyVis Network from node/edge data.

    This is a stateless utility class in the business logic layer. It knows only about
    PyVis, not about Qt or database concerns.
    """

    # Node styling defaults (should be overridden by theme_config)
    ENTITY_COLOR = "#CCCCCC"
    EVENT_COLOR = "#AAAAAA"
    ENTITY_SHAPE = "dot"
    EVENT_SHAPE = "diamond"

    # Graph options
    DEFAULT_HEIGHT = "100%"
    DEFAULT_WIDTH = "100%"

    # Fallback Theme Config
    DEFAULT_THEME = {
        "background_color": "#000000",
        "text_color": "#FFFFFF",
        "node_entity_color": "#CCCCCC",
        "node_event_color": "#AAAAAA",
        "edge_color": "#666666",
    }

    # Cached local vis-network library content
    _vis_js_content: str | None = None
    _vis_css_content: str | None = None
    _vis_utils_content: str | None = None

    @staticmethod
    def prepare_node(
        node: dict[str, Any],
        entity_color: str,
        event_color: str,
        lexicon: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Maps an internal node dict to a Vis.js-compatible node dict.

        Centralizes the node property mapping so that both the full render
        path (_build_network) and the incremental update path
        (GraphWebView.update_graph_data) produce identical output.

        Args:
            node: Internal node dict with id, name, object_type keys.
            entity_color: Hex color for entity nodes.
            event_color: Hex color for event nodes.
            lexicon: Optional lexicon node config dict keyed by type name.
                Each value may contain 'color', 'shape', and 'image' keys.

        Returns:
            Dict with Vis.js-compatible keys (id, label, title, color, shape,
            size, object_type).

        """
        is_entity = node.get("object_type") == "entity"
        name = node.get("name", "Unnamed")
        node_type = node.get("type", "")

        # Defaults
        color = entity_color if is_entity else event_color
        shape = GraphBuilder.ENTITY_SHAPE if is_entity else GraphBuilder.EVENT_SHAPE

        # Apply lexicon overrides if available
        if lexicon and node_type in lexicon:
            style = lexicon[node_type]
            if "color" in style:
                color = style["color"]
            if "shape" in style:
                shape = style["shape"]

        result: dict[str, Any] = {
            "id": node["id"],
            "label": name,
            "title": f"{node.get('object_type', 'item').title()}: {name}",
            "color": color,
            "shape": shape,
            "size": 20,
            "object_type": node.get("object_type", "entity"),
        }

        # If shape is 'image' and a Base64 data URI is provided, set image
        if lexicon and node_type in lexicon:
            style = lexicon[node_type]
            image_data = style.get("image", "")
            if shape == "image" and image_data:
                result["image"] = image_data

        return result

    @staticmethod
    def prepare_edge(
        edge: dict[str, Any],
        edge_color: str,
        lexicon: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Maps an internal edge dict to a Vis.js-compatible edge dict.

        Centralizes the edge property mapping so that both the full render
        path (_build_network) and the incremental update path
        (GraphWebView.update_graph_data) produce identical output.

        Args:
            edge: Internal edge dict with source_id, target_id, rel_type keys.
            edge_color: Hex color for edges.
            lexicon: Optional lexicon edge config dict keyed by rel_type.
                Each value may contain 'color', 'width', and 'dashes' keys.

        Returns:
            Dict with Vis.js-compatible keys (id, from, to, label, title,
            color).

        """
        rel_type = edge.get("rel_type", "")

        # Defaults
        color = edge_color
        width: Optional[int] = None
        dashes: Optional[bool] = None

        # Apply lexicon overrides if available
        if lexicon and rel_type in lexicon:
            style = lexicon[rel_type]
            if "color" in style:
                color = style["color"]
            if "width" in style:
                width = style["width"]
            if "dashes" in style:
                dashes = style["dashes"]

        result: dict[str, Any] = {
            "id": edge.get("id"),
            "from": edge["source_id"],
            "to": edge["target_id"],
            "label": rel_type,
            "title": rel_type,
            "color": color,
        }

        if width is not None:
            result["width"] = width
        if dashes is not None:
            result["dashes"] = dashes

        return result

    @staticmethod
    def image_to_base64(file_path: Path) -> str:
        """Converts an image file to a Base64 data URI for secure rendering.

        Uses MIME type detection to produce a proper data URI that can be
        safely embedded in HTML/JavaScript without file:// protocol issues.

        Args:
            file_path: Absolute path to the image file.

        Returns:
            Base64 data URI string, or empty string if file not found.

        """
        if not file_path.exists():
            logger.warning(f"Image file not found for Base64 encoding: {file_path}")
            return ""

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
        except OSError as e:
            logger.error(f"Failed to read image for Base64 encoding: {e}")
            return ""

    @staticmethod
    def resolve_lexicon_images(
        lexicon: dict[str, Any],
        project_root: Path,
    ) -> dict[str, Any]:
        """Resolves relative icon paths in a lexicon to Base64 data URIs.

        Iterates through the 'nodes' section of a lexicon config and replaces
        relative file paths with inline Base64 data URIs for secure rendering
        in QWebEngineView.

        Args:
            lexicon: Lexicon configuration dictionary with 'nodes' and
                optionally 'edges' keys.
            project_root: Absolute path to the world root directory.

        Returns:
            New lexicon dict with icon paths replaced by Base64 data URIs.

        """
        resolved: dict[str, Any] = {}

        # Resolve node icons
        nodes = lexicon.get("nodes", {})
        resolved_nodes: dict[str, Any] = {}
        for type_name, style in nodes.items():
            resolved_style = dict(style)
            icon_path = style.get("icon", "")
            if icon_path:
                full_path = project_root / icon_path
                data_uri = GraphBuilder.image_to_base64(full_path)
                if data_uri:
                    resolved_style["image"] = data_uri
            resolved_nodes[type_name] = resolved_style
        resolved["nodes"] = resolved_nodes

        # Pass edges through unchanged
        resolved["edges"] = lexicon.get("edges", {})

        return resolved

    @classmethod
    def _load_local_vis_assets(cls) -> tuple[str, str, str]:
        """Loads local vis-network JS, CSS, and PyVis utils files for offline use.

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
        view_state: dict[str, Any] | None = None,
        lexicon_config: dict[str, Any] | None = None,
    ) -> str:
        """Builds a PyVis network and returns HTML string.

        Args:
            nodes: List of node dicts with id, name, type, object_type keys.
            edges: List of edge dicts with source_id, target_id, rel_type keys.
            height: Height of the graph visualization.
            width: Width of the graph visualization.
            theme_config: Optional dictionary with color settings.
            focus_node_id: Optional ID of the node to focus on stabilize.
            view_state: Optional dict with 'scale' and 'position' to restore.
            lexicon_config: Optional resolved lexicon with Base64 images.
                Expected structure: {"nodes": {...}, "edges": {...}}.

        Returns:
            HTML string for embedding in QWebEngineView.

        """
        try:
            theme = theme_config or self.DEFAULT_THEME
            network = self._build_network(
                nodes, edges, height, width, theme, lexicon_config
            )
            html = self._generate_html(network, theme, focus_node_id, view_state)
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
        lexicon_config: dict[str, Any] | None = None,
    ) -> Network:
        """Creates a PyVis Network from node/edge data.

        Args:
            nodes: List of node dicts.
            edges: List of edge dicts.
            height: Graph height.
            width: Graph width.
            theme: Theme configuration dictionary.
            lexicon_config: Optional resolved lexicon config with
                'nodes' and 'edges' keys for visual styling.

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
            "layout": {
                "randomSeed": 42
            },
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

        node_lexicon = (lexicon_config or {}).get("nodes")
        edge_lexicon = (lexicon_config or {}).get("edges")

        for node in nodes:
            prepared = self.prepare_node(
                node, entity_color, event_color, lexicon=node_lexicon
            )
            n_id = prepared.pop("id")
            net.add_node(n_id, **prepared)

        # Add edges
        for edge in edges:
            prepared = self.prepare_edge(edge, edge_color, lexicon=edge_lexicon)
            source = prepared.pop("from")
            target = prepared.pop("to")
            net.add_edge(source, target, **prepared)

        return net

    def _generate_html(
        self,
        network: Network,
        theme: dict[str, str],
        focus_node_id: str | None = None,
        view_state: dict[str, Any] | None = None,
    ) -> str:
        """Generates HTML string from a PyVis network.

        Args:
            network: Configured PyVis Network.
            theme: Theme configuration dictionary.
            view_state: Optional view state to restore.

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
                    var viewState = %VIEW_STATE%;

                    function restoreFocus() {
                        if (viewState) {
                            // Restore exact previous view (pan/zoom)
                            network.moveTo({
                                position: viewState.position,
                                scale: viewState.scale,
                                animation: false // Instant restore
                            });
                        } else if (focusId !== null) {
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
                            }
                        }
                    }

                    // Immediate Restore for View State
                    if (viewState) {
                        restoreFocus();
                    }

                    // Incremental Data Update
                    window.updateGraph = function(newNodes, newEdges, newFocusId) {
                        try {
                            // Access datasets via network instance for reliability
                            var nodes = network.body.data.nodes;
                            var edges = network.body.data.edges;

                            nodes.update(newNodes);
                            var newNodeIds = newNodes.map(function(n) {
                                return n.id;
                            });
                            var currentIds = nodes.getIds();
                            var idsToRemove = currentIds.filter(function(id) {
                                return newNodeIds.indexOf(id) === -1;
                            });
                            nodes.remove(idsToRemove);

                            edges.update(newEdges);
                            var newEdgeIds = newEdges.map(function(e) {
                                return e.id;
                            });
                            var currentEdgeIds = edges.getIds();
                            var edgesToRemove = currentEdgeIds.filter(function(id) {
                                return newEdgeIds.indexOf(id) === -1;
                            });
                            edges.remove(edgesToRemove);

                            if (newFocusId) {
                                focusId = newFocusId;
                                network.selectNodes([newFocusId]);
                            }
                        } catch (err) {
                            console.error("Graph: Update failed", err);
                        }
                    };

                    // Report View State Changes
                    // We debounce this to avoid flooding Python with signals
                    var viewStateTimeout;
                    function reportViewState() {
                        clearTimeout(viewStateTimeout);
                        viewStateTimeout = setTimeout(function() {
                            if (window.bridge) {
                                var scale = network.getScale();
                                var position = network.getViewPosition();
                                window.bridge.viewStateChanged({
                                    scale: scale,
                                    position: position
                                });
                            }
                        }, 200);
                    }

                    network.on("zoom", reportViewState);
                    network.on("dragEnd", reportViewState);
                    network.on("animationFinished", reportViewState);


                    // Try stabilized event first, with timeout fallback
                    // (Only if we didn't already restore viewState)
                    // If we have viewState, we already set the camera,
                    // so we don't need to center on focusId.
                    // But if we DON'T have viewState, we need to wait
                    // for stabilization to center on focusId.
                    if (!viewState) {
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
                }
            }, 50); // Reduced check interval for responsiveness
        </script>
        """

        # Replace placeholder with JSON-serialized ID for safe JS injection
        focus_json = json.dumps(focus_node_id) if focus_node_id else "null"
        view_state_json = json.dumps(view_state) if view_state else "null"

        interaction_script = interaction_script.replace("%FOCUS_ID%", focus_json)
        interaction_script = interaction_script.replace("%VIEW_STATE%", view_state_json)

        html_content = html_content.replace(
            "</body>", f"{qwebchannel_script}\n{interaction_script}\n</body>"
        )

        return html_content

    def build_empty_html(self, theme_config: dict[str, str] = None) -> str:
        """Returns HTML for an empty state message.

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
