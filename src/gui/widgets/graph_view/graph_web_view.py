"""
Graph Web View Module.

Private internal component encapsulating QWebEngineView for graph display.
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class GraphBridge(QObject):
    """Bridge for communication between JS/PyVis and Python."""

    # Signal emitted when JS calls nodeClicked
    node_clicked = Signal(str, str)  # (object_type, object_id)

    @Slot(str, str)
    def nodeClicked(self, object_type: str, object_id: str) -> None:
        """Called from JavaScript when a node is clicked."""
        self.node_clicked.emit(object_type, object_id)


class GraphWebView(QWidget):
    """
    Internal widget encapsulating QWebEngineView for graph display.

    Isolates browser-specific logic from the main GraphWidget.
    This is a private internal component - use GraphWidget for public API.

    Signals:
        node_clicked: Emitted when a graph node is clicked (via JS bridge).
    """

    node_clicked = Signal(str, str)  # (object_type, object_id)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initializes the GraphWebView.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._bridge = GraphBridge()
        self._bridge.node_clicked.connect(self.node_clicked.emit)
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

        layout.addWidget(self._web_view)

    def load_html(self, html: str) -> None:
        """
        Loads HTML content into the web view.

        Args:
            html: HTML string to display.
        """
        self._web_view.setHtml(html)

    def set_background_color(self, color: str) -> None:
        """
        Sets the background color of the web view.

        Args:
            color: Hex color string (e.g. "#1e1e1e").
        """
        self._web_view.setStyleSheet(f"background-color: {color};")
        self._web_view.page().setBackgroundColor(QColor(color))

    def clear(self) -> None:
        """Clears the web view content."""
        self._web_view.setHtml("")
