"""Qt WebEngine view and bridge used by the relationship graph."""

import json
import logging
import weakref
from typing import Any, Optional

import shiboken6
from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QPalette, QResizeEvent, QShowEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.theme_connections import connect_theme, disconnect_theme
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.graph_view.theme_update import (
    theme_frame_script,
    theme_update_script,
)

logger = logging.getLogger(__name__)
_THEME_READY_ATTEMPTS = 250


class GraphBridge(QObject):
    """Bridge for communication between JS/PyVis and Python."""

    # Signal emitted when JS calls nodeClicked
    node_clicked = Signal(str, str)  # (object_type, object_id)
    # Signal emitted when JS updates view state (scale, position)
    view_state_changed = Signal(dict)
    connection_requested = Signal(dict)
    background_clicked = Signal(int)
    renderer_ready = Signal(int)

    @Slot(str, str)
    def nodeClicked(self, object_type: str, object_id: str) -> None:
        """Called from JavaScript when a node is clicked."""
        self.node_clicked.emit(object_type, object_id)

    @Slot(dict)
    def viewStateChanged(self, state: dict) -> None:
        """Called from JavaScript when view state changes."""
        self.view_state_changed.emit(state)

    @Slot(dict)
    def connectionRequested(self, intent: dict) -> None:
        """Forward a detached canvas gesture for Qt-side validation."""
        self.connection_requested.emit(intent)

    @Slot(int)
    def backgroundClicked(self, generation: int) -> None:
        """Forward an empty-canvas click, separate from canvas movement."""
        self.background_clicked.emit(generation)

    @Slot(int)
    def rendererReady(self, generation: int) -> None:
        """Report that incremental updates can now reach this renderer."""
        self.renderer_ready.emit(generation)


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
    theme_applied = Signal(int)
    connection_requested = Signal(dict)
    background_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the GraphWebView.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)
        self._page_generation = 0
        self._renderer_generation: int | None = 0
        self._pending_graph_update = ""
        self._highlighted_relation_ids: list[str] = []
        self._theme_revision = 0
        self._pending_theme: dict[str, str] | None = None
        self._theme_nodes: list[dict[str, Any]] = []
        self._theme_edges: list[dict[str, Any]] = []
        self._theme_lexicon: dict[str, Any] = {}
        self._page_loaded = False
        self._theme_inflight = False
        self._closed = False
        self._theme_attempts = 0
        self._awaiting_theme_frame = False
        self._reveal_after_theme = False
        self._theme_timer = QTimer(self)
        self._theme_timer.setSingleShot(True)
        self._theme_timer.setInterval(20)
        self._theme_timer.timeout.connect(self._try_theme)
        self._bridge = GraphBridge()
        self._bridge.node_clicked.connect(self.node_clicked.emit)
        self._bridge.view_state_changed.connect(self._accept_view_state)
        self._bridge.connection_requested.connect(self._accept_connection)
        self._bridge.background_clicked.connect(self._accept_background)
        self._bridge.renderer_ready.connect(self._accept_renderer)
        self._setup_ui()
        self._theme_cover = QWidget(self)
        self._theme_cover.setAutoFillBackground(True)
        self._theme_cover.hide()

    def _accept_view_state(self, state: dict) -> None:
        if state.get("generation", self._page_generation) == self._page_generation:
            self.view_state_changed.emit(state)

    def _accept_connection(self, intent: dict) -> None:
        if intent.get("generation") == self._page_generation:
            self.connection_requested.emit(intent)

    def _accept_background(self, generation: int) -> None:
        if generation == self._page_generation:
            self.background_clicked.emit()

    def _accept_renderer(self, generation: int) -> None:
        if generation == self._page_generation:
            self._renderer_generation = generation
            if self._pending_graph_update:
                self._run_graph_script(self._pending_graph_update)
                self._pending_graph_update = ""
            self.highlight_relations(self._highlighted_relation_ids)

    def relayout(self) -> None:
        """Ask the current renderer to explicitly recompute its layout."""
        self._run_graph_script("window.relayoutGraph?.()")

    def highlight_relations(self, identities: list[str]) -> None:
        """Highlight saved edges without changing inspector selection."""
        self._highlighted_relation_ids = identities
        if self._renderer_generation == self._page_generation:
            self._run_graph_script(
                f"window.highlightGraphRelations?.({json.dumps(identities)})"
            )

    def _run_graph_script(self, script: str) -> None:
        if not self._closed:
            self._web_view.page().runJavaScript(
                f"if (window.__krakenGraphGeneration === {self._page_generation}) "
                f"{{ {script}; }}"
            )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep the theme cover above the complete browser viewport."""
        super().resizeEvent(event)
        if hasattr(self, "_theme_cover"):
            self._theme_cover.setGeometry(self.rect())

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Resume frame acknowledgement when an occluded browser becomes visible."""
        super().showEvent(event)
        self._theme_attempts = 0
        self._try_theme()

    def _setup_ui(self) -> None:
        """Sets up the web view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._web_view = QWebEngineView()
        self._web_view.setMinimumSize(400, 300)
        self._web_view.loadFinished.connect(self._load_finished)

        # Setup WebChannel
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._web_view.page().setWebChannel(self._channel)

        self._apply_theme(ThemeManager().get_theme())
        connect_theme(self, self._apply_theme)
        self._theme_connected = True

        # Disable default context menu
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        layout.addWidget(self._web_view)

    @Slot(dict)
    def _apply_theme(self, theme: dict) -> None:
        """Apply the active surface colour before graph content loads."""
        if not shiboken6.isValid(self) or not shiboken6.isValid(self._web_view):
            return
        self.set_background_color(theme["app_bg"])

    def load_html(self, html: str) -> None:
        """Loads HTML content into the web view.

        Args:
            html: HTML string to display.

        """
        self._page_generation += 1
        self._renderer_generation = None
        self._pending_graph_update = ""
        self._page_loaded = False
        self._theme_inflight = False
        self._theme_attempts = 0
        self._awaiting_theme_frame = False
        self._theme_timer.stop()
        marker = (
            f"<script>window.__krakenGraphGeneration={self._page_generation};</script>"
        )
        marked = html.replace("<head>", "<head>" + marker, 1)
        if marked == html:
            marked = marker + html
        self._web_view.setHtml(marked)

    def _load_finished(self, success: bool) -> None:
        self._page_loaded = success
        if not self._closed:
            self._try_theme()
            if success and self._pending_theme is None:
                self._theme_cover.hide()

    def set_theme_data(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        lexicon: dict[str, Any],
    ) -> None:
        """Retain the currently projected data for renderer-only recoloring."""
        self._theme_nodes = nodes
        self._theme_edges = edges
        self._theme_lexicon = lexicon

    def update_theme(self, theme: dict[str, str]) -> None:
        """Apply the latest theme once the current page's JS renderer is ready."""
        if self._closed:
            return
        self._pending_theme = dict(theme)
        self._theme_revision += 1
        self._theme_attempts = 0
        self._awaiting_theme_frame = False
        self.set_background_color(theme["background_color"])
        self._reveal_after_theme = ThemeManager().has_scoped_presentation
        if self._reveal_after_theme:
            palette = QPalette(self._theme_cover.palette())
            palette.setColor(
                QPalette.ColorRole.Window, QColor(theme["background_color"])
            )
            self._theme_cover.setPalette(palette)
            self._theme_cover.setGeometry(self.rect())
            self._theme_cover.show()
            self._theme_cover.raise_()
        self._try_theme()

    def _theme_script(
        self, theme: dict[str, str], generation: int, revision: int
    ) -> str:
        """Prepare colors once; frame polling never repeats renderer work."""
        if self._awaiting_theme_frame:
            return theme_frame_script(generation, revision)
        nodes = [
            GraphBuilder.prepare_node(
                node,
                theme["node_entity_color"],
                theme["node_event_color"],
                lexicon=self._theme_lexicon.get("nodes"),
            )
            for node in self._theme_nodes
        ]
        edges = [
            GraphBuilder.prepare_edge(
                edge,
                theme["edge_color"],
                lexicon=self._theme_lexicon.get("edges"),
            )
            for edge in self._theme_edges
        ]
        return theme_update_script(
            theme,
            nodes,
            edges,
            generation,
            revision if self._reveal_after_theme else None,
        )

    def _try_theme(self) -> None:
        if (
            self._closed
            or not self._page_loaded
            or self._theme_inflight
            or self._pending_theme is None
        ):
            return
        generation, revision = self._page_generation, self._theme_revision
        checking_frame = self._awaiting_theme_frame
        script = self._theme_script(self._pending_theme, generation, revision)
        self._theme_inflight = True
        reference = weakref.ref(self)

        def completed(result: Any) -> None:
            view = reference()
            if (
                view is None
                or not shiboken6.isValid(view)
                or view._closed
                or generation != view._page_generation
            ):
                return
            view._theme_inflight = False
            if revision != view._theme_revision:
                view._try_theme()
            elif result is True:
                if view._reveal_after_theme and not checking_frame:
                    view._awaiting_theme_frame = True
                    view._theme_timer.start()
                else:
                    view._pending_theme = None
                    view._theme_cover.hide()
                    view.theme_applied.emit(revision)
            else:
                view._theme_attempts += 1
                if view._theme_attempts < _THEME_READY_ATTEMPTS:
                    view._theme_timer.start()
                else:
                    logger.warning("Graph theme renderer readiness timed out")

        self._web_view.page().runJavaScript(script, completed)

    def set_background_color(self, color: str) -> None:
        """Sets the background color of the web view.

        Args:
            color: Hex color string (e.g. "#1e1e1e").

        """
        if not shiboken6.isValid(self) or not shiboken6.isValid(self._web_view):
            return
        style = f"background-color: {color};"
        if self._web_view.styleSheet() != style:
            self._web_view.setStyleSheet(style)
        self._web_view.page().setBackgroundColor(QColor(color))

    def clear(self) -> None:
        """Clears the web view content."""
        self._pending_theme = None
        self.set_theme_data([], [], {})
        self.load_html("")

    def shutdown(self) -> None:
        """Shut down the web engine to prevent teardown segfaults.

        Must be called before the widget is destroyed to ensure the
        QWebEnginePage is released before the profile is deleted.
        """
        if self._closed:
            return
        self._closed = True
        self._page_generation += 1
        self._pending_theme = None
        self._theme_timer.stop()
        if self._theme_connected:
            disconnect_theme(self, self._apply_theme)
            self._theme_connected = False
        if not shiboken6.isValid(self._web_view):
            return
        self._web_view.stop()
        # Qt accepts None to detach the channel; the stub omits this overload.
        self._web_view.page().setWebChannel(None)  # type: ignore[arg-type]
        self._web_view.hide()
        self._web_view.deleteLater()

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
        edge_color = theme.get("edge_color", ThemeManager().get_theme()["text_dim"])

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
        if "text_color" in theme:
            for item in js_nodes:
                item["font"] = {"color": theme["text_color"]}
        label_colors = GraphBuilder.edge_label_colors(theme)
        for edge in js_edges:
            edge["font"] = label_colors

        nodes_json = json.dumps(js_nodes)
        edges_json = json.dumps(js_edges)
        focus_json = json.dumps(focus_id) if focus_id else "null"

        script = (
            f"if (window.updateGraph) {{ "
            f"updateGraph({nodes_json}, {edges_json}, {focus_json}); "
            f"}}"
        )
        if self._renderer_generation == self._page_generation:
            self._run_graph_script(script)
        else:
            self._pending_graph_update = script
