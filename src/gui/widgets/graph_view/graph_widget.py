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

        # Data Cache
        self._all_nodes: list[dict[str, Any]] = []
        self._all_edges: list[dict[str, Any]] = []

        # Filter State
        self._search_term: str = ""
        self._advanced_filter_config: dict[str, Any] = {"tags": {}, "rel_types": {}}

        self._available_tags: list[str] = []
        self._available_rel_types: list[str] = []

        # Theme Handling
        from src.core.theme_manager import ThemeManager

        self._theme_manager = ThemeManager()
        self._current_theme_config = self._get_current_theme_config()
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

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
        # We manually handle filter changes to sync state
        self._filter_bar.filters_changed.connect(self._on_toolbar_filter_changed)
        self._filter_bar.search_text_changed.connect(self._on_search_text_changed)
        self._filter_bar.show_advanced_filter_requested.connect(self.show_filter_dialog)

    def _on_theme_changed(self, theme_data: dict[str, Any]) -> None:
        """Handles theme changes by refreshing the graph."""
        self._current_theme_config = self._get_current_theme_config()

        # Update Web View background to match theme immediately
        bg_color = self._current_theme_config.get("background_color", "#1e1e1e")
        self._web_view.set_background_color(bg_color)

        # Refresh display with new colors
        self._refresh_display_locally()

    def _get_current_theme_config(self) -> dict[str, str]:
        """Extracts relevant colors from the current theme."""
        theme = self._theme_manager.get_theme()

        # Map BaseThemeManager keys to GraphBuilder keys
        return {
            "background_color": theme.get("app_bg", "#1e1e1e"),
            "text_color": theme.get("text_main", "#ffffff"),
            # Entity -> Accent/Primary (e.g. "#4A90D9" or "#FF9900")
            "node_entity_color": theme.get("accent_secondary", "#4A90D9"),
            # Event -> Primary (e.g. "#E67E22")
            "node_event_color": theme.get("primary", "#E67E22"),
            "edge_color": theme.get("text_dim", "#888888"),
        }

    # --- Internal Logic ---

    def _on_toolbar_filter_changed(self) -> None:
        """Handles changes from toolbar combo boxes."""
        # Sync toolbar selection to advanced config "include"
        tags = self._filter_bar.get_selected_tags()
        rel_types = self._filter_bar.get_selected_relation_types()

        # Update config (preserving other settings if possible, or reset?)
        # Simple/Toolbar mode usually implies simple include
        self._advanced_filter_config["tags"]["include"] = tags
        self._advanced_filter_config["rel_types"]["include"] = rel_types

        # Emit public signal to trigger data reload (Main Window -> GraphDataService)
        self.filter_changed.emit()

    def _on_search_text_changed(self, text: str) -> None:
        """Handles search text changes (Local filtering)."""
        self._search_term = text.strip()
        self._refresh_display_locally()

    def show_filter_dialog(self) -> None:
        """Shows the advanced filter dialog."""
        from PySide6.QtWidgets import QDialog

        from src.gui.dialogs.graph_filter_dialog import GraphFilterDialog

        dialog = GraphFilterDialog(
            self,
            available_tags=self._available_tags,
            available_rel_types=self._available_rel_types,
            current_config=self._advanced_filter_config,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._advanced_filter_config = dialog.get_filter_config()
            logger.info(f"Advanced filter applied: {self._advanced_filter_config}")

            # Since advanced filter might change what we need from DB (includes),
            # we request a refresh.
            self.filter_changed.emit()

    def _refresh_display_locally(self, focus_node_id: str | None = None) -> None:
        """Refreshes the graph display using cached data and local filters."""
        if not self._all_nodes and not self._all_edges:
            self._web_view.load_html(
                self._builder.build_empty_html(self._current_theme_config)
            )
            return

        filtered_nodes = []
        filtered_ids = set()

        from src.core.search_utils import SearchUtils

        # Retrieve filter configs
        tag_config = self._advanced_filter_config.get("tags", {})
        rel_config = self._advanced_filter_config.get("rel_types", {})

        # -- Step 1: Filter Nodes (Search & Tags) --
        for node in self._all_nodes:
            # 1. Search Filter
            if not SearchUtils.matches_search(node, self._search_term):
                continue

            # 2. Tag Filter (Advanced)
            if not self._passes_tag_filter(node, tag_config):
                continue

            filtered_nodes.append(node)
            filtered_ids.add(node["id"])

        # -- Step 2: Filter Edges (Rel Types & node existence) --
        filtered_edges = []

        for edge in self._all_edges:
            # Check if source and target are in filtered nodes
            if (
                edge["source_id"] not in filtered_ids
                or edge["target_id"] not in filtered_ids
            ):
                continue

            # Check Relation Type Filter
            if not self._passes_rel_type_filter(edge, rel_config):
                continue

            filtered_edges.append(edge)

        # -- Step 3: Render --
        if not filtered_nodes:
            self._web_view.load_html(
                self._builder.build_empty_html(self._current_theme_config)
            )
        else:
            html = self._builder.build_html(
                filtered_nodes,
                filtered_edges,
                theme_config=self._current_theme_config,
                focus_node_id=focus_node_id,
            )
            self._web_view.load_html(html)
            logger.debug(
                f"Refreshed graph: {len(filtered_nodes)} nodes, "
                f"{len(filtered_edges)} edges, focus_id={focus_node_id}"
            )

    def _passes_tag_filter(self, node: dict, config: dict) -> bool:
        """Checks if a node passes the tag filter config."""
        include = config.get("include", [])
        exclude = config.get("exclude", [])
        include_mode = config.get("include_mode", "any")
        case_sensitive = config.get("case_sensitive", False)

        node_tags = node.get("tags", [])
        # Normalization for case sensitivity
        if not case_sensitive:
            node_tags = [t.lower() for t in node_tags]
            include = [t.lower() for t in include]
            exclude = [t.lower() for t in exclude]

        # Exclude check (Any match excludes)
        for tag in exclude:
            if tag in node_tags:
                return False

        # Include check
        if not include:
            return True  # No include filter = Include All

        matches = [t for t in include if t in node_tags]

        if include_mode == "all":
            # Must have ALL included tags
            # e.g. include=["A", "B"] -> node must have A AND B
            # This means len(matches) must equal len(include)
            # But wait, include list might have dupes? Assuming unique.
            # Using sets is safer.
            return set(include).issubset(set(node_tags))
        else:
            # Any (OR)
            return len(matches) > 0

    def _passes_rel_type_filter(self, edge: dict, config: dict) -> bool:
        """Checks if an edge passes the relation type filter config."""
        include = config.get("include", [])
        exclude = config.get("exclude", [])
        # Rel type is single value, so "all" mode matches "any"
        case_sensitive = config.get("case_sensitive", False)

        rel_type = edge.get("rel_type", "")
        if not case_sensitive:
            rel_type = rel_type.lower()
            include = [t.lower() for t in include]
            exclude = [t.lower() for t in exclude]

        if rel_type in exclude:
            return False

        if not include:
            return True

        return rel_type in include

    # --- Public API ---

    def set_available_tags(self, tags: list[str]) -> None:
        """
        Sets available tags from Main Window.
        """
        self._available_tags = tags
        self._filter_bar.set_available_tags(tags)

    def set_available_relation_types(self, rel_types: list[str]) -> None:
        """
        Sets available relation types from Main Window.
        """
        self._available_rel_types = rel_types
        self._filter_bar.set_available_relation_types(rel_types)

    def get_filter_config(self) -> dict[str, list[str]]:
        """
        Returns filter config for DataService (Includes only).
        """
        # Extract includes for DB query
        tags = self._advanced_filter_config.get("tags", {}).get("include", [])
        rel_types = self._advanced_filter_config.get("rel_types", {}).get("include", [])

        return {
            "tags": tags,
            "rel_types": rel_types,
        }

    def display_graph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        focus_node_id: str | None = None,
    ) -> None:
        """
        Receives data from Main Window, caches it, and triggers rendering.
        """
        self._all_nodes = nodes
        self._all_edges = edges
        logger.debug(
            f"Received {len(nodes)} nodes, {len(edges)} edges. Refreshing display."
        )

        # We need to update SearchUtils to handle dicts before this works.
        # I will do that in the next step.
        self._refresh_display_locally(focus_node_id)

    def _show_empty_state(self) -> None:
        """Displays the empty state message."""
        html = self._builder.build_empty_html()
        self._web_view.load_html(html)

    def clear(self) -> None:
        """Clears the graph display."""
        self._web_view.clear()
        self._all_nodes = []
        self._all_edges = []
