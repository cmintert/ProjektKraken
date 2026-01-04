"""
Splitter Tab Inspector Widget Module.

Provides a custom QSplitter-based widget that supports vertical stacking
of tabs with drag-and-drop functionality.
"""

from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QSplitter,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class DraggableTabBar(QTabBar):
    """
    A QTabBar that supports drag-and-drop for rearranging tabs
    across different QTabWidgets within the same splitter.
    """

    tab_dragged = Signal(int)  # Emitted when a tab drag starts

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the draggable tab bar."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_start_pos = QPoint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track drag start position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Initiate drag if moved far enough."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)

        if (event.pos() - self._drag_start_pos).manhattanLength() < 20:
            return super().mouseMoveEvent(event)

        idx = self.tabAt(self._drag_start_pos)
        if idx < 0:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-inspector-tab", str(idx).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept tab drag data."""
        if event.mimeData().hasFormat("application/x-inspector-tab"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop onto this tab bar."""
        if not event.mimeData().hasFormat("application/x-inspector-tab"):
            return

        source_bar = event.source()
        if source_bar is None:
            return

        source_idx = int(
            event.mimeData().data("application/x-inspector-tab").data().decode()
        )
        source_tab_widget = source_bar.parent()

        # Get the widget and title from source
        widget = source_tab_widget.widget(source_idx)
        title = source_tab_widget.tabText(source_idx)

        # Remove from source
        source_tab_widget.removeTab(source_idx)

        # Cleanup empty source pane
        self._cleanup_empty_pane(source_tab_widget)

        # Insert into this tab widget
        target_tab_widget = self.parent()
        drop_idx = self.tabAt(event.pos())
        if drop_idx < 0:
            drop_idx = self.count()
        target_tab_widget.insertTab(drop_idx, widget, title)
        target_tab_widget.setCurrentIndex(drop_idx)

        event.acceptProposedAction()

    def _cleanup_empty_pane(self, tab_widget: QTabWidget) -> None:
        """Remove a tab widget from splitter if it has no tabs left."""
        if tab_widget.count() == 0:
            splitter = self._find_parent_splitter(tab_widget)
            if splitter and splitter.count() > 1:
                tab_widget.setParent(None)
                tab_widget.deleteLater()

    def _find_parent_splitter(self, widget: QWidget) -> Optional[QSplitter]:
        """Find the parent QSplitter of a widget."""
        parent = widget.parent()
        while parent:
            if isinstance(parent, QSplitter):
                return parent
            parent = parent.parent()
        return None


class DraggableTabWidget(QTabWidget):
    """A QTabWidget with a draggable tab bar."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize with custom tab bar."""
        super().__init__(parent)
        self.setTabBar(DraggableTabBar(self))
        self.setAcceptDrops(True)
        self.setMovable(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drops to create vertical splits."""
        if event.mimeData().hasFormat("application/x-inspector-tab"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop to create a vertical split.
        If dropped on the body (not the tab bar), create a new pane.
        """
        # Let the tab bar handle it if the drop is on the tab bar
        local_pos = event.pos()
        tab_bar_rect = self.tabBar().rect()
        if tab_bar_rect.contains(self.tabBar().mapFrom(self, local_pos)):
            return  # Tab bar will handle

        if not event.mimeData().hasFormat("application/x-inspector-tab"):
            return

        source_bar = event.source()
        if source_bar is None:
            return

        source_idx = int(
            event.mimeData().data("application/x-inspector-tab").data().decode()
        )
        source_tab_widget = source_bar.parent()

        # Get the widget and title from source
        widget = source_tab_widget.widget(source_idx)
        title = source_tab_widget.tabText(source_idx)

        # Remove from source
        source_tab_widget.removeTab(source_idx)

        # Create a new DraggableTabWidget in the splitter
        splitter = self._find_parent_splitter()
        if splitter:
            new_tab_widget = DraggableTabWidget()
            new_tab_widget.addTab(widget, title)

            # Insert after this widget
            idx = splitter.indexOf(self)
            splitter.insertWidget(idx + 1, new_tab_widget)

            # Cleanup empty source pane (after creating new one)
            self._cleanup_empty_pane(source_tab_widget, splitter)

        event.acceptProposedAction()

    def _cleanup_empty_pane(self, tab_widget: QTabWidget, splitter: QSplitter) -> None:
        """Remove a tab widget from splitter if it has no tabs left."""
        if tab_widget.count() == 0 and splitter.count() > 1:
            tab_widget.setParent(None)
            tab_widget.deleteLater()

    def _find_parent_splitter(self) -> Optional[QSplitter]:
        """Find the parent QSplitter."""
        parent = self.parent()
        while parent:
            if isinstance(parent, QSplitter):
                return parent
            parent = parent.parent()
        return None


class SplitterTabInspector(QWidget):
    """
    A widget that provides a vertically splittable tab container.
    Tabs can be dragged to the tab bar to rearrange, or dropped
    on the body of another tab widget to create a vertical split.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the splitter tab inspector."""
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Set splitter constraints to prevent collapse
        self.splitter.setChildrenCollapsible(False)  # Prevent full collapse
        self.splitter.setHandleWidth(4)  # Make handle easier to grab

        main_layout.addWidget(self.splitter)

        # Initial tab widget
        self.main_tabs = DraggableTabWidget()
        self.splitter.addWidget(self.main_tabs)

        # Track all tab widgets for cleanup
        self._tab_widgets = [self.main_tabs]

    def add_tab(self, widget: QWidget, title: str) -> None:
        """
        Add a tab to the main tab widget.

        Args:
            widget (QWidget): The widget to add.
            title (str): The tab title.
        """
        self.main_tabs.addTab(widget, title)

    def get_main_tabs(self) -> QTabWidget:
        """Return the main tab widget."""
        return self.main_tabs

    def minimumSizeHint(self) -> QSize:
        """
        Prevent tab inspector collapse.

        Returns:
            QSize: Minimum size for usable tab inspector.
        """
        from PySide6.QtCore import QSize

        return QSize(200, 150)  # Minimum height for at least one tab visible

    def sizeHint(self) -> QSize:
        """
        Preferred size for tab inspector.

        Returns:
            QSize: Comfortable working size for inspector tabs.
        """
        from PySide6.QtCore import QSize

        return QSize(400, 500)  # Ideal size for tab content
