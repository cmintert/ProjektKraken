"""
Tests for Graph View Widgets.

Tests the widget layer components for graph visualization.
"""

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication


# Ensure QApplication exists for widget tests
@pytest.fixture(scope="module")
def qapp():
    """Provides a QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestGraphBuilder:
    """Tests for GraphBuilder class."""

    def test_build_html_returns_string(self, qapp):
        """build_html returns an HTML string."""
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        builder = GraphBuilder()
        nodes = [{"id": "1", "name": "Node A", "object_type": "entity"}]
        edges = []

        html = builder.build_html(nodes, edges)

        assert isinstance(html, str)
        assert "<html>" in html.lower() or "<!doctype" in html.lower()

    def test_build_html_with_edges(self, qapp):
        """build_html handles edges correctly."""
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        builder = GraphBuilder()
        nodes = [
            {"id": "1", "name": "Node A", "object_type": "entity"},
            {"id": "2", "name": "Node B", "object_type": "event"},
        ]
        edges = [{"source_id": "1", "target_id": "2", "rel_type": "involved"}]

        html = builder.build_html(nodes, edges)

        assert isinstance(html, str)
        # HTML should contain the node names
        assert "Node A" in html
        assert "Node B" in html

    def test_build_empty_html(self, qapp):
        """build_empty_html returns placeholder HTML."""
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        builder = GraphBuilder()
        html = builder.build_empty_html()

        assert "No Data to Display" in html


class TestGraphFilterBar:
    """Tests for GraphFilterBar class."""

    def test_init_creates_widget(self, qapp):
        """GraphFilterBar can be instantiated."""
        from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar

        bar = GraphFilterBar()
        assert bar is not None

    def test_set_available_tags(self, qapp):
        """set_available_tags populates the combo box."""
        from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar

        bar = GraphFilterBar()
        bar.set_available_tags(["alpha", "beta", "gamma"])

        # "All Tags" plus 3 tags = 4 items
        assert bar._tag_combo.count() == 4

    def test_get_selected_tags_default(self, qapp):
        """get_selected_tags returns empty list by default (All)."""
        from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar

        bar = GraphFilterBar()
        bar.set_available_tags(["alpha", "beta"])

        tags = bar.get_selected_tags()

        assert tags == []

    def test_filters_changed_signal(self, qapp):
        """filters_changed signal is emitted when selection changes."""
        from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar

        bar = GraphFilterBar()
        bar.set_available_tags(["alpha", "beta"])

        signal_received = []
        bar.filters_changed.connect(lambda: signal_received.append(True))

        # Change selection
        bar._tag_combo.setCurrentIndex(1)

        assert len(signal_received) == 1


class TestGraphWebView:
    """Tests for GraphWebView class."""

    def test_init_creates_widget(self, qapp):
        """GraphWebView can be instantiated."""
        from src.gui.widgets.graph_view.graph_web_view import GraphWebView

        view = GraphWebView()
        assert view is not None

    def test_load_html(self, qapp):
        """load_html sets content without error."""
        from src.gui.widgets.graph_view.graph_web_view import GraphWebView

        view = GraphWebView()
        view.load_html("<html><body>Test</body></html>")
        # No exception = success


class TestGraphWidget:
    """Tests for GraphWidget class."""

    def test_init_creates_widget(self, qapp):
        """GraphWidget can be instantiated."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        assert widget is not None

    def test_set_available_tags_delegates(self, qapp):
        """set_available_tags delegates to filter bar."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        widget.set_available_tags(["tag1", "tag2"])

        # Should have "All Tags" + 2 tags
        assert widget._filter_bar._tag_combo.count() == 3

    def test_set_available_relation_types_delegates(self, qapp):
        """set_available_relation_types delegates to filter bar."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        widget.set_available_relation_types(["rel1", "rel2"])

        # Should have "All Types" + 2 types
        assert widget._filter_bar._rel_type_combo.count() == 3

    def test_get_filter_config_returns_dict(self, qapp):
        """get_filter_config returns proper structure."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        config = widget.get_filter_config()

        assert "tags" in config
        assert "rel_types" in config
        assert isinstance(config["tags"], list)
        assert isinstance(config["rel_types"], list)

    def test_refresh_requested_signal(self, qapp):
        """refresh_requested signal is forwarded from filter bar."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        signal_received = []
        widget.refresh_requested.connect(lambda: signal_received.append(True))

        # Emit from filter bar
        widget._filter_bar.refresh_requested.emit()

        assert len(signal_received) == 1

    def test_filter_changed_signal(self, qapp):
        """filter_changed signal is forwarded from filter bar."""
        from src.gui.widgets.graph_view import GraphWidget

        widget = GraphWidget()
        signal_received = []
        widget.filter_changed.connect(lambda: signal_received.append(True))

        # Set tags and change selection
        widget.set_available_tags(["test"])
        widget._filter_bar._tag_combo.setCurrentIndex(1)

        assert len(signal_received) == 1
