"""Graph Widget Module.

Public facade widget for graph visualization of item relationships. This is the only
public interface for the graph view functionality.
"""

from pathlib import Path
from typing import Any, Optional

import shiboken6
from PySide6.QtCore import QEvent, QSize, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.authoring_scope import AuthoringScope
from src.core.logging_config import get_logger
from src.core.relation_vocabulary import Vocabulary, filter_labels, relation_label
from src.core.search_utils import SearchUtils
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme, disconnect_theme
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.graph_view.graph_feedback import GraphFeedback
from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar
from src.gui.widgets.graph_view.graph_projection import GraphProjection
from src.gui.widgets.graph_view.graph_web_view import GraphWebView
from src.gui.widgets.standard_buttons import StandardButton

MIN_GRAPH_WIDTH = 100
MIN_GRAPH_HEIGHT = 100


class GraphWidget(QWidget):
    """Public widget for visualizing item relationships as an interactive graph.

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
    lexicon_save_requested = Signal(dict)  # raw lexicon config to persist
    icon_picker_created = Signal(object)
    lexicon_editor_created = Signal(object)
    connection_requested = Signal(dict)
    interaction_changed = Signal()
    snapshot_presented = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the GraphWidget.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        # Expanding policy prevents dock collapse during resize.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Initialize logger
        self._logger = get_logger(__name__)

        # Private internal components (following MapWidget pattern)
        self._filter_bar = GraphFilterBar()
        self._web_view = declare_inspection(
            GraphWebView(),
            "view.src-gui-widgets-graph-view-graph-widget-graphwidget-init-self-web-view|graph.exploring|help-inspect-view-src-gui-widgets-graph-view-graph-widget-graphwidget-init-self-web-view",
        )
        self._builder = GraphBuilder()
        self._relation_vocabulary: Vocabulary = {}

        # Data Cache
        self._all_nodes: list[dict[str, Any]] = []
        self._all_edges: list[dict[str, Any]] = []
        self._scope = AuthoringScope()
        self._selected_graph_node: tuple[str, str] | None = None
        self._session_positions: dict[str, dict[str, float]] = {}
        self._reveal_edges: frozenset[str] = frozenset()
        self._display_node_ids: frozenset[str] = frozenset()
        # View State Cache (scale, position)
        self._last_view_state: Optional[dict[str, Any]] = None
        self._last_focus_node_id: Optional[str] = None
        self._is_renderer_ready: bool = False

        # Filter State
        self._search_term: str = ""
        self._advanced_filter_config: dict[str, Any] = {"tags": {}, "rel_types": {}}

        self._available_tags: list[str] = []
        self._available_rel_types: list[str] = []

        # Lexicon (Visual Styling)
        self._raw_lexicon: dict[str, Any] = {"nodes": {}, "edges": {}}
        self._resolved_lexicon: dict[str, Any] = {"nodes": {}, "edges": {}}
        self._available_entity_types: list[str] = []
        self._world_assets_dir: str | None = None
        self._icon_metadata: dict[str, Any] = {}
        self._lexicon_editor: Any = None

        # Theme Handling
        from src.core.theme_manager import ThemeManager

        self._theme_manager = ThemeManager()
        self._current_theme_config = self._get_current_theme_config()
        connect_theme(self, self._on_theme_changed)
        self._theme_connected = True

        self._setup_ui()
        self._connect_internal_signals()

        # Show empty state initially
        self._show_empty_state()

    def _setup_ui(self) -> None:
        """Sets up the widget UI layout.

        Creates the vertical layout and adds the filter bar and web view components.
        """
        self.setMinimumSize(MIN_GRAPH_WIDTH, MIN_GRAPH_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        StyleHelper.apply_panel_spacing(layout)
        layout.setSpacing(0)

        # Filter bar at top
        layout.addWidget(self._filter_bar)
        from src.gui.widgets.action_flow_layout import ActionFlowLayout
        from src.gui.widgets.wrapping_choices import WrappingCheckBox
        from src.gui.widgets.wrapping_combo_box import WrappingComboBox

        temporal_row = ActionFlowLayout()
        self.temporal_mode = declare_inspection(
            WrappingComboBox(),
            "src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-temporal-mode|relations.timing|help-inspect-src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-temporal-mode",
        )
        self.temporal_mode.setAccessibleName("Graph temporal view")
        for label, mode in (
            ("At playhead", "at_playhead"),
            ("History to playhead", "history_to_playhead"),
            ("All relations", "all_relations"),
        ):
            self.temporal_mode.addItem(label, mode)
        self.temporal_mode.currentIndexChanged.connect(
            lambda _index: self.refresh_requested.emit()
        )
        self.temporal_mode.currentIndexChanged.connect(self._invalidate_interaction)
        self.show_possible = declare_inspection(
            WrappingCheckBox("Show possible relations"),
            "src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-show-possible|relations.timing|help-inspect-src-gui-widgets-graph-view-graph-widget-graphwidget-setup-ui-self-show-possible",
        )
        self.show_possible.toggled.connect(
            lambda: self._refresh_display_locally(self._last_focus_node_id)
        )
        self.show_possible.toggled.connect(self._invalidate_interaction)
        self.temporal_count = QLabel()
        self.temporal_count.setAccessibleName("Relations with uncertain timing")
        temporal_row.addWidget(self.temporal_mode)
        temporal_row.addWidget(self.show_possible)
        temporal_row.addWidget(self.temporal_count)
        layout.addLayout(temporal_row)
        actions = ActionFlowLayout()
        self.connect_button = declare_inspection(
            StandardButton("Connect…"),
            "graph-connect|graph.exploring|help-inspect-graph-connect",
        )
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self._connect_selected)
        self.relayout_button = declare_inspection(
            StandardButton("Relayout"),
            "graph-relayout|graph.exploring|help-inspect-graph-relayout",
        )
        self.relayout_button.setEnabled(False)
        self.relayout_button.clicked.connect(self._relayout)
        actions.addWidget(self.connect_button)
        actions.addWidget(self.relayout_button)
        layout.addLayout(actions)
        self.feedback = GraphFeedback(self)
        layout.addWidget(self.feedback)
        self.feedback.dismissed.connect(self._invalidate_interaction)

        # Web view fills remaining space
        layout.addWidget(self._web_view, 1)

    def minimumSizeHint(self) -> QSize:
        """Allow the widget to shrink inside its dock.

        Returns:
            QSize: Minimum usable size for the graph widget.
        """
        return QSize(MIN_GRAPH_WIDTH, MIN_GRAPH_HEIGHT)

    def sizeHint(self) -> QSize:
        """Preferred size for the graph widget.

        Returns:
            QSize: Comfortable working size for graph interaction.
        """
        return QSize(400, 300)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Shut down the web engine before the widget is destroyed.

        Args:
            event: The close event.
        """
        if self._theme_connected:
            disconnect_theme(self, self._on_theme_changed)
            self._theme_connected = False
        self._web_view.shutdown()
        super().closeEvent(event)

    def _connect_internal_signals(self) -> None:
        """Connects internal component signals to public signals.

        Wires up the web view and filter bar signals to the appropriate GraphWidget
        signals or internal handlers.
        """
        # Forward web view node clicks
        self._web_view.node_clicked.connect(self._on_graph_node_clicked)
        self._web_view.connection_requested.connect(self._bridge_connection)
        self._web_view.background_clicked.connect(self._background_clicked)
        # Handle view state updates
        self._web_view.view_state_changed.connect(self._on_view_state_changed)

        # Forward filter bar signals
        self._filter_bar.refresh_requested.connect(self.refresh_requested.emit)
        # We manually handle filter changes to sync state
        self._filter_bar.filters_changed.connect(self._on_toolbar_filter_changed)
        self._filter_bar.search_text_changed.connect(self._on_search_text_changed)
        self._filter_bar.show_advanced_filter_requested.connect(self.show_filter_dialog)
        self._filter_bar.show_lexicon_editor_requested.connect(self.show_lexicon_editor)

    def _on_theme_changed(self, theme_data: dict[str, Any]) -> None:
        """Handles theme changes by refreshing the graph with new colors.

        Args:
            theme_data: Dictionary containing the new theme colors.

        """
        if not shiboken6.isValid(self) or not shiboken6.isValid(self._web_view):
            return
        if not shiboken6.isValid(self._web_view._web_view):
            return
        self._current_theme_config = self._get_current_theme_config()

        self._web_view.update_theme(self._current_theme_config)

    def _get_current_theme_config(self) -> dict[str, str]:
        """Extracts relevant colors from the current theme for the graph.

        Returns:
            dict[str, str]: A dictionary of color codes for graph elements
            (background, text, nodes, edges).

        """
        theme = self._theme_manager.get_theme()

        # Map BaseThemeManager keys to GraphBuilder keys
        return {
            "background_color": theme["app_bg"],
            "text_color": theme["text_main"],
            "node_entity_color": theme.get(
                "entity_main", theme.get("accent_secondary", theme["text_main"])
            ),
            "node_event_color": theme.get(
                "event_main", theme.get("primary", theme["text_main"])
            ),
            "edge_color": theme["text_dim"],
            "action_bg": theme.get("mode_bg", theme["app_bg"]),
            "action_border": theme.get("mode_border", theme["text_dim"]),
            "action_text": theme.get("mode_text", theme["text_main"]),
            "focus_ring": theme.get("focus_ring", theme["text_main"]),
        }

    # --- Internal Logic ---

    def _on_toolbar_filter_changed(self) -> None:
        """Handles changes from toolbar combo boxes.

        Syncs the toolbar selection to the advanced configuration's include lists and
        emits the filter_changed signal.
        """
        # Sync toolbar selection to advanced config "include"
        tags = self._filter_bar.get_selected_tags()
        rel_types = self._filter_bar.get_selected_relation_types()

        # Update config (preserving other settings if possible, or reset?)
        # Simple/Toolbar mode usually implies simple include
        self._advanced_filter_config["tags"]["include"] = tags
        self._advanced_filter_config["rel_types"]["include"] = rel_types

        # Emit public signal to trigger data reload (Main Window -> GraphDataService)
        self._invalidate_interaction()
        self.filter_changed.emit()

    def _on_search_text_changed(self, text: str) -> None:
        """Handles search text changes for local filtering.

        Args:
            text: The new search text.

        """
        self._search_term = text.strip()
        self._invalidate_interaction()
        self._refresh_display_locally(self._last_focus_node_id)

    def _on_view_state_changed(self, state: dict) -> None:
        """Handles view state updates from the web view.

        Args:
            state: Dictionary containing 'scale' and 'position' keys.
        """
        self._last_view_state = state
        positions = state.get("positions")
        if isinstance(positions, dict):
            self._session_positions.update(positions)

    def show_filter_dialog(self) -> None:
        """Shows the advanced filter dialog.

        If the dialog is accepted, updates the filter configuration and emits the
        filter_changed signal.
        """
        from PySide6.QtWidgets import QDialog

        from src.gui.dialogs.graph_filter_dialog import GraphFilterDialog

        dialog = GraphFilterDialog(
            self,
            available_tags=self._available_tags,
            available_rel_types=self._available_rel_types,
            current_config=self._advanced_filter_config,
            relation_labels=filter_labels(
                self._available_rel_types, self._relation_vocabulary
            ),
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._advanced_filter_config = dialog.get_filter_config()
            self._logger.info(
                f"Advanced filter applied: {self._advanced_filter_config}"
            )

            # Since advanced filter might change what we need from DB (includes),
            # we request a refresh.
            self._invalidate_interaction()
            self.filter_changed.emit()

    def show_lexicon_editor(self) -> None:
        """Reveal the embedded world graph style editor."""
        from src.gui.utils.settings_navigation import request_settings

        request_settings("world.lexicon", "world")

    def _on_lexicon_preview_requested(self, config: dict[str, Any]) -> None:
        """Updates the graph display immediately based on new lexicon config.

        Args:
            config: The new lexicon configuration from the dialog.
        """
        # Update raw lexicon
        self._raw_lexicon = config

        # Resolve images locally
        from pathlib import Path

        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        project_root = (
            Path(self._world_assets_dir).parent
            if self._world_assets_dir
            else Path.cwd()
        )
        from src.services.graph_lexicon_resolver import resolve_lexicon_images
        from src.services.marker_icon_catalog import MarkerIconCatalog

        resolved = resolve_lexicon_images(
            config,
            project_root,
            image_encoder=GraphBuilder.image_to_base64,
            catalog=MarkerIconCatalog.load(project_root, self._icon_metadata),
        )
        self._resolved_lexicon = resolved

        # Force full rebuild so shape/icon changes take effect
        self._is_renderer_ready = False
        self._refresh_display_locally()

    def _on_graph_node_clicked(self, object_type: str, node_id: str) -> None:
        """Synchronize a canvas selection with the ordinary navigation route."""
        if node_id not in self._display_node_ids:
            return
        self._invalidate_interaction()
        self._selected_graph_node = object_type, node_id
        self._refresh_display_locally(node_id)
        self.node_clicked.emit(object_type, node_id)

    def _background_clicked(self) -> None:
        self._selected_graph_node = None
        self._invalidate_interaction()

    def _connect_selected(self) -> None:
        self._invalidate_interaction()
        kind, identity = self._selected_graph_node or ("", "")
        self.connection_requested.emit({"source": identity, "source_kind": kind})

    def _bridge_connection(self, intent: dict) -> None:
        source = intent.get("source")
        target = intent.get("target")
        if source not in self._display_node_ids or (
            target and target not in self._display_node_ids
        ):
            return
        self._invalidate_interaction()
        self.connection_requested.emit(intent)

    def _relayout(self) -> None:
        self._invalidate_interaction()
        self._web_view.relayout()

    def _invalidate_interaction(self, *_args: object) -> None:
        self.clear_saved_feedback()
        self.interaction_changed.emit()

    def authoring_context_changed(self) -> None:
        """End feedback when the temporal viewing context changes."""
        self._invalidate_interaction()

    def new_node_position(self, source_id: str) -> dict[str, float] | None:
        """Return a placement near a source for keyboard-driven creation."""
        source = self._session_positions.get(source_id)
        if source is None:
            return None
        return {"x": source["x"] + 85.0, "y": source["y"] + 48.0}

    def relation_types(self) -> list[str]:
        """Return the world relation vocabulary for authoring controls."""
        return list(self._available_rel_types)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        """End temporary feedback when the user leaves the graph."""
        self._invalidate_interaction()
        super().hideEvent(event)

    def clear_saved_feedback(self) -> None:
        """Dismiss transient graph feedback and restore the usual filters."""
        self.feedback.hide()
        self._web_view.highlight_relations([])
        if self._reveal_edges:
            self._reveal_edges = frozenset()
            self._refresh_display_locally(self._last_focus_node_id)

    def set_authoring_scope(self, scope: AuthoringScope) -> None:
        """Clear context-dependent feedback and filter the current snapshot."""
        self._scope = scope
        self._invalidate_interaction()
        self._refresh_display_locally(self._last_focus_node_id)

    @property
    def visible_node_ids(self) -> frozenset[str]:
        """Return the identities on the current graph projection."""
        return self._display_node_ids

    def seed_node(self, node_id: str, position: dict[str, float]) -> None:
        """Use the draft's canvas location the first time this node appears."""
        self._session_positions.setdefault(node_id, position)

    def show_saved_relations(
        self, relation_ids: frozenset[str]
    ) -> tuple[tuple[str, ...], int]:
        """Reveal only locally filtered edges and return timing exclusions."""
        _, normal, available = self._project_visible(self._last_focus_node_id)
        normal_ids = {edge["id"] for edge in normal}
        eligible_ids = set(available) & relation_ids
        self._reveal_edges = frozenset(eligible_ids - normal_ids)
        reasons = self._filter_reasons(available, self._reveal_edges)
        if self._reveal_edges:
            self._refresh_display_locally(self._last_focus_node_id)
        self._web_view.highlight_relations(sorted(eligible_ids))
        return reasons, len(relation_ids) - len(eligible_ids)

    def _filter_reasons(
        self, eligible: dict[str, dict], revealed: frozenset[str]
    ) -> tuple[str, ...]:
        by_id = {node["id"]: node for node in self._all_nodes}
        edges = [eligible[edge_id] for edge_id in revealed]
        nodes = [
            by_id[edge[key]] for edge in edges for key in ("source_id", "target_id")
        ]
        tags = self._advanced_filter_config.get("tags", {})
        types = self._advanced_filter_config.get("rel_types", {})
        reasons = []
        if any(
            not SearchUtils.matches_search(node, self._search_term) for node in nodes
        ):
            reasons.append("search")
        if any(not self._passes_tag_filter(node, tags) for node in nodes):
            reasons.append("tags")
        if any(not self._passes_rel_type_filter(edge, types) for edge in edges):
            reasons.append("relation type")
        return tuple(reasons)

    def _project_visible(
        self, focus_id: str | None
    ) -> tuple[list[dict], list[dict], dict[str, dict]]:
        tag_config = self._advanced_filter_config.get("tags", {})
        rel_config = self._advanced_filter_config.get("rel_types", {})
        scoped = {
            node["id"]: node
            for node in self._all_nodes
            if self._scope.matches(node.get("tags", []))
        }
        types = set(rel_config.get("include", []))
        connected = (
            {
                edge[key]
                for edge in self._all_edges
                if not types or self._passes_rel_type_filter(edge, rel_config)
                for key in ("source_id", "target_id")
            }
            if types
            else scoped.keys()
        )
        visible = {
            node_id: node
            for node_id, node in scoped.items()
            if node_id in connected
            and SearchUtils.matches_search(node, self._search_term)
            and self._passes_tag_filter(node, tag_config)
        }
        edges = []
        eligible = {}
        uncertain_count = hidden_count = 0
        for edge in self._all_edges:
            source, target = edge["source_id"], edge["target_id"]
            if source not in scoped or target not in scoped:
                continue
            passes_local = (
                source in visible
                and target in visible
                and self._passes_rel_type_filter(edge, rel_config)
            )
            if edge.get("validity_status") in {"possible", "indeterminate"}:
                uncertain_count += int(passes_local)
                if not self.show_possible.isChecked() and focus_id not in (
                    source,
                    target,
                ):
                    hidden_count += int(passes_local)
                    continue
            eligible[edge["id"]] = edge
            if passes_local:
                edges.append(edge)
        self.temporal_count.setText(
            f"{uncertain_count} uncertain ({hidden_count} hidden)"
            if uncertain_count
            else ""
        )
        return list(visible.values()), edges, eligible

    def _refresh_display_locally(self, focus_node_id: str | None = None) -> None:
        """Render the current scoped snapshot and any narrow result exception."""
        nodes, edges, eligible = self._project_visible(focus_node_id)
        visible_ids = {node["id"] for node in nodes}
        extra = [
            eligible[identity]
            for identity in sorted(self._reveal_edges & eligible.keys())
        ]
        if extra:
            edge_ids = {edge["id"] for edge in edges}
            edges.extend(edge for edge in extra if edge["id"] not in edge_ids)
            wanted = {edge[key] for edge in extra for key in ("source_id", "target_id")}
            nodes.extend(
                node for node in self._all_nodes if node["id"] in wanted - visible_ids
            )
        projected = GraphProjection.project_edges(
            edges,
            suppress_redundant_mentions=self._should_suppress_redundant_mentions(
                self._advanced_filter_config.get("rel_types", {})
            ),
        )
        self._display_node_ids = frozenset(node["id"] for node in nodes)
        if (
            self._selected_graph_node
            and self._selected_graph_node[1] not in self._display_node_ids
        ):
            self._selected_graph_node = None
        self.connect_button.setEnabled(bool(nodes))
        self.relayout_button.setEnabled(bool(nodes))
        positioned = [
            dict(node, position=position)
            if (position := self._session_positions.get(node["id"]))
            else node
            for node in nodes
        ]
        self._render_projection(positioned, projected, focus_node_id)

    def _render_projection(
        self, nodes: list[dict], edges: list[dict], focus_id: str | None
    ) -> None:
        edges = [
            dict(
                edge,
                display_label=relation_label(
                    edge.get("rel_type", ""), self._relation_vocabulary
                ),
            )
            for edge in edges
        ]
        self._web_view.set_theme_data(nodes, edges, self._resolved_lexicon)
        if not nodes and not self._is_renderer_ready:
            return
        if not self._is_renderer_ready or focus_id != self._last_focus_node_id:
            # Match the renderer's focus selection without emitting navigation.
            focused = next((node for node in nodes if node["id"] == focus_id), None)
            if focused is not None:
                self._selected_graph_node = (
                    focused.get("object_type", "entity"),
                    focused["id"],
                )
            elif not self._is_renderer_ready:
                self._selected_graph_node = None
        lexicon = self._resolved_lexicon
        if self._is_renderer_ready:
            self._web_view.update_graph_data(
                nodes,
                edges,
                focus_id=focus_id,
                theme_config=self._current_theme_config,
                lexicon_config=lexicon,
            )
        else:
            self._web_view.load_html(
                self._builder.build_html(
                    nodes,
                    edges,
                    theme_config=self._current_theme_config,
                    focus_node_id=focus_id,
                    view_state=(
                        self._last_view_state
                        if focus_id == self._last_focus_node_id
                        else None
                    ),
                    lexicon_config=lexicon,
                )
            )
            self._is_renderer_ready = True
        self._last_focus_node_id = focus_id

    def _should_suppress_redundant_mentions(self, rel_config: dict) -> bool:
        """Return whether generated mention suppression applies to this view.

        An include filter that explicitly requests ``mentions`` takes precedence
        over the default noise-reduction projection.
        """
        included = rel_config.get("include", [])
        return not any(str(rel_type).casefold() == "mentions" for rel_type in included)

    def _passes_tag_filter(self, node: dict, config: dict) -> bool:
        """Checks if a node passes the tag filter configuration.

        Args:
            node: The node data dictionary.
            config: The tag filter configuration dictionary.

        Returns:
            bool: True if the node passes the filter, False otherwise.

        """
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
        """Checks if an edge passes the relation type filter configuration.

        Args:
            edge: The edge data dictionary.
            config: The relation type filter configuration dictionary.

        Returns:
            bool: True if the edge passes the filter, False otherwise.

        """
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

        return not include or rel_type in include

    # --- Public API ---

    def set_available_tags(self, tags: list[str]) -> None:
        """Sets the list of available tags.

        Args:
            tags: A list of tag strings.

        """
        self._available_tags = tags
        self._filter_bar.set_available_tags(tags)

    @property
    def relation_vocabulary(self) -> Vocabulary:
        """Expose read-only wording to graph authoring details."""
        return self._relation_vocabulary

    def set_relation_vocabulary(self, vocabulary: Vocabulary) -> None:
        """Redraw captions against the current graph without requerying edges."""
        if vocabulary == self._relation_vocabulary:
            return
        self._relation_vocabulary = vocabulary
        self.set_available_relation_types(self._available_rel_types)
        if self._all_nodes:
            self._refresh_display_locally(self._last_focus_node_id)

    def set_available_relation_types(self, rel_types: list[str]) -> None:
        """Sets the list of available relation types.

        Args:
            rel_types: A list of relation type strings.

        """
        self._available_rel_types = rel_types
        self._filter_bar.set_available_relation_types(
            rel_types, filter_labels(rel_types, self._relation_vocabulary)
        )

    def set_lexicon_config(
        self,
        raw: dict[str, Any],
        resolved: dict[str, Any],
    ) -> None:
        """Sets the visual lexicon configuration.

        Args:
            raw: Raw lexicon config with file paths (for editor dialog).
            resolved: Resolved lexicon config with Base64 data URIs (for rendering).

        """
        editor = self._lexicon_editor
        if editor is not None and shiboken6.isValid(editor) and editor.isVisible():
            self._on_lexicon_preview_requested(editor.get_lexicon_config())
            return
        if self._raw_lexicon == raw and self._resolved_lexicon == resolved:
            return
        self._raw_lexicon = raw
        self._resolved_lexicon = resolved
        # Force full rebuild to apply new styles
        self._is_renderer_ready = False
        self._refresh_display_locally()

    def set_available_entity_types(self, entity_types: list[str]) -> None:
        """Sets the available entity types for the lexicon editor.

        Args:
            entity_types: List of entity type strings.

        """
        self._available_entity_types = entity_types

    def apply_icon_library_snapshot(self, payload: dict[str, Any]) -> None:
        """Refresh icons while preserving the active Visual Lexicon draft."""
        snapshot = payload.get("icon_library", {})
        self._icon_metadata = snapshot.get("metadata", {})
        self.set_world_assets_dir(str(Path(payload["world_root"]) / "assets"))
        editor = self._lexicon_editor
        config = (
            editor.get_lexicon_config()
            if editor is not None and shiboken6.isValid(editor)
            else self._raw_lexicon
        )
        self._on_lexicon_preview_requested(config)

    def set_world_assets_dir(self, path: str | None) -> None:
        """Sets the world assets directory for icon imports.

        Args:
            path: Absolute path to the world's assets directory, or None.

        """
        self._world_assets_dir = path

    def get_filter_config(self) -> dict[str, list[str]]:
        """Returns the current filter configuration.

        Returns:
            dict[str, list[str]]: The current filter configuration, containing
            'tags' and 'rel_types' includes for database queries.

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
        """Displays the graph with the provided nodes and edges.

        Caches the data and triggers a local refresh of the display.

        Args:
            nodes: List of node data dictionaries.
            edges: List of edge data dictionaries.
            focus_node_id: Optional ID of a node to focus on.

        """
        self._all_nodes = nodes
        self._all_edges = edges
        self._logger.debug(
            f"Received {len(nodes)} nodes, {len(edges)} edges. Refreshing display."
        )

        # We need to update SearchUtils to handle dicts before this works.
        # I will do that in the next step.
        self._refresh_display_locally(focus_node_id)
        self.snapshot_presented.emit()

    def _show_empty_state(self) -> None:
        """Displays the empty state message in the web view."""
        html = self._builder.build_empty_html()
        self._web_view.load_html(html)

    def clear(self) -> None:
        """Clears the graph display and internal data cache."""
        self._web_view.clear()
        self._all_nodes = []
        self._all_edges = []
        self._session_positions.clear()
        self._last_view_state = None
        self._last_focus_node_id = None
        self._selected_graph_node = None
        self._is_renderer_ready = False
        self._invalidate_interaction()
        self._refresh_display_locally()

    def showEvent(self, event: QEvent) -> None:
        """Handle widget show event by refreshing the graph view.

        Args:
            event: The show event.
        """

        def _refresh() -> None:
            """Refresh the web view content."""
            try:
                reload_fn = getattr(self._web_view, "reload", None)
                if callable(reload_fn):
                    reload_fn()
                else:
                    self._web_view.update()
            except Exception as e:
                self._logger.exception(f"GraphWidget: refresh on show failed: {e}")

        # Schedule refresh on next event loop iteration
        QTimer.singleShot(0, _refresh)
