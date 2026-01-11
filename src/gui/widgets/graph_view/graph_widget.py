"""
Graph Widget Module.

Public facade widget for graph visualization of item relationships.
This is the only public interface for the graph view functionality.
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar
from src.gui.widgets.graph_view.graph_web_view import GraphWebView

logger = logging.getLogger(__name__)


class GraphWidget(QWidget):
    """
    Public widget for visualizing item relationships as an interactive graph.

    Encapsulates internal components (GraphFilterBar, GraphWebView, GraphBuilder)
    and exposes a clean public API for MainWindow integration.

    This is the only public interface for graph visualization. MainWindow should
    never interact with internal components directly.

    Signals:
        node_clicked: Emitted when a graph node is clicked.
        refresh_requested: Emitted when user requests data refresh.
        filter_changed: Emitted when filters change (for lazy refresh).

    Example:
        graph = GraphWidget()
        graph.set_available_tags(["protagonist", "villain"])
        graph.set_available_relation_types(["involved", "caused"])
        graph.display_graph(nodes, edges)
    """

    # Public signals
    node_clicked = Signal(str, str)  # (object_type, object_id)
    refresh_requested = Signal()
    filter_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the GraphWidget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Private internal components (following MapWidget pattern)
        self._filter_bar = GraphFilterBar()
        self._web_view = GraphWebView()
        self._builder = GraphBuilder()

        self._setup_ui()
        self._connect_internal_signals()

        # Show empty state initially
        self._show_empty_state()

    def _setup_ui(self) -> None:
        """Sets up the widget UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Filter bar at top
        layout.addWidget(self._filter_bar)

        # Web view fills remaining space
        layout.addWidget(self._web_view, 1)

    def _connect_internal_signals(self) -> None:
        """Connects internal component signals to public signals."""
        # Forward web view node clicks
        self._web_view.node_clicked.connect(self.node_clicked.emit)

        # Forward filter bar signals
        self._filter_bar.refresh_requested.connect(self.refresh_requested.emit)
        self._filter_bar.filters_changed.connect(self.filter_changed.emit)

    # --- Public API ---

    def set_available_tags(self, tags: list[str]) -> None:
        """
        Sets available tags for filtering.

        Args:
            tags: List of tag names.
        """
        self._filter_bar.set_available_tags(tags)

    def set_available_relation_types(self, rel_types: list[str]) -> None:
        """
        Sets available relation types for filtering.

        Args:
            rel_types: List of relation type names.
        """
        self._filter_bar.set_available_relation_types(rel_types)

    def get_filter_config(self) -> dict[str, list[str]]:
        """
        Returns current filter configuration.

        Returns:
            Dict with 'tags' and 'rel_types' keys, each containing
            a list of selected filter values. Empty list means "all".
        """
        return {
            "tags": self._filter_bar.get_selected_tags(),
            "rel_types": self._filter_bar.get_selected_relation_types(),
        }

    def display_graph(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> None:
        """
        Builds and displays the graph from provided data.

        Args:
            nodes: List of node dicts with id, name, type, object_type keys.
            edges: List of edge dicts with source_id, target_id, rel_type keys.
        """
        if not nodes:
            html = self._builder.build_empty_html()
        else:
            html = self._builder.build_html(nodes, edges)

        self._web_view.load_html(html)
        logger.debug(f"Displayed graph with {len(nodes)} nodes and {len(edges)} edges")

    def _show_empty_state(self) -> None:
        """Displays the empty state message."""
        html = self._builder.build_empty_html()
        self._web_view.load_html(html)

    def clear(self) -> None:
        """Clears the graph display."""
        self._web_view.clear()
