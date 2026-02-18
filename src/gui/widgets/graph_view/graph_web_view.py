import json
import logging
from typing import Any, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.widgets.graph_view.graph_builder import GraphBuilder

logger = logging.getLogger(__name__)


class GraphBridge(QObject):
    """Bridge for communication between JS/PyVis and Python."""

    # Signal emitted when JS calls nodeClicked
    node_clicked = Signal(str, str)  # (object_type, object_id)
    # Signal emitted when JS updates view state (scale, position)
    view_state_changed = Signal(dict)

    @Slot(str, str)
    def nodeClicked(self, object_type: str, object_id: str) -> None:
        """Called from JavaScript when a node is clicked."""
        self.node_clicked.emit(object_type, object_id)

    @Slot(dict)
    def viewStateChanged(self, state: dict) -> None:
        """Called from JavaScript when view state changes."""
        self.view_state_changed.emit(state)


class GraphWebView(QWidget):
    """Internal widget encapsulating QWebEngineView for graph display.

    Isolates browser-specific logic from the main GraphWidget.
    This is a private internal component - use GraphWidget for public API.

    Signals:
        node_clicked: Emitted when a graph node is clicked (via JS bridge).
        view_state_changed: Emitted when graph view state changes (scale/pan).
    """

    node_clicked = Signal(str, str)  # (object_type, object_id)
    view_state_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the GraphWebView.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        self._bridge = GraphBridge()
        self._bridge.node_clicked.connect(self.node_clicked.emit)
        self._bridge.view_state_changed.connect(self.view_state_changed.emit)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Sets up the web view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._web_view = QWebEngineView()
        self._web_view.setMinimumSize(400, 300)

        # Setup WebChannel
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._web_view.page().setWebChannel(self._channel)

        # Set a dark background before content loads (widget background)
        self._web_view.setStyleSheet("background-color: #1e1e1e;")

        # Set the page's default background color (fills empty space)
        self._web_view.page().setBackgroundColor(QColor("#1e1e1e"))

        # Disable default context menu
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        layout.addWidget(self._web_view)

    def load_html(self, html: str) -> None:
        """Loads HTML content into the web view.

        Args:
            html: HTML string to display.

        """
        self._web_view.setHtml(html)

    def set_background_color(self, color: str) -> None:
        """Sets the background color of the web view.

        Args:
            color: Hex color string (e.g. "#1e1e1e").

        """
        self._web_view.setStyleSheet(f"background-color: {color};")
        self._web_view.page().setBackgroundColor(QColor(color))

    def clear(self) -> None:
        """Clears the web view content."""
        self._web_view.setHtml("")

    def update_graph_data(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        focus_id: str | None = None,
        theme_config: dict[str, str] | None = None,
        lexicon_config: dict[str, Any] | None = None,
    ) -> None:
        """Updates the graph data incrementally without reloading the page.

        Args:
            nodes: New list of node dictionaries.
            edges: New list of edge dictionaries.
            focus_id: Optional ID to focus on.
            theme_config: Optional theme config for node/edge colors.
            lexicon_config: Optional resolved lexicon config with
                'nodes' and 'edges' keys for visual styling.
        """
        theme = theme_config or GraphBuilder.DEFAULT_THEME
        entity_color = theme.get("node_entity_color", GraphBuilder.ENTITY_COLOR)
        event_color = theme.get("node_event_color", GraphBuilder.EVENT_COLOR)
        edge_color = theme.get("edge_color", "#888888")

        node_lexicon = (lexicon_config or {}).get("nodes")
        edge_lexicon = (lexicon_config or {}).get("edges")

        js_nodes = [
            GraphBuilder.prepare_node(
                n, entity_color, event_color, lexicon=node_lexicon
            )
            for n in nodes
        ]
        js_edges = [
            GraphBuilder.prepare_edge(e, edge_color, lexicon=edge_lexicon)
            for e in edges
        ]

        nodes_json = json.dumps(js_nodes)
        edges_json = json.dumps(js_edges)
        focus_json = json.dumps(focus_id) if focus_id else "null"

        script = (
            f"if (window.updateGraph) {{ "
            f"updateGraph({nodes_json}, {edges_json}, {focus_json}); "
            f"}}"
        )
        self._web_view.page().runJavaScript(script)
        logger.debug(
            f"Triggered incremental graph update: Nodes={len(js_nodes)}, "
            f"Edges={len(js_edges)}"
        )
