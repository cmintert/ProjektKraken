"""Splitter Tab Inspector Widget Module.

Provides a custom QSplitter-based widget that supports vertical stacking of tabs with
drag-and-drop functionality.
"""

from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QMenu,
    QSplitter,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.logging_config import get_logger

logger = get_logger(__name__)

INSPECTOR_TAB_MIME_TYPE = "application/x-inspector-tab"
_DRAG_START_DISTANCE_PX = 20


def _decode_source_index(mime_data: QMimeData) -> int | None:
    """Return a validated source index from inspector-tab MIME data."""
    if not mime_data.hasFormat(INSPECTOR_TAB_MIME_TYPE):
        return None
    try:
        return int(bytes(mime_data.data(INSPECTOR_TAB_MIME_TYPE).data()).decode())
    except (TypeError, ValueError, UnicodeDecodeError):
        logger.warning("Ignoring malformed inspector-tab drag data")
        return None


def _source_tab_widget(source: object) -> QTabWidget | None:
    """Resolve a drag source to its owning tab widget."""
    if not isinstance(source, DraggableTabBar):
        return None
    parent = source.parentWidget()
    return parent if isinstance(parent, QTabWidget) else None


def _move_tab(
    source: QTabWidget,
    target: QTabWidget,
    source_index: int,
    target_index: int,
) -> bool:
    """Move one tab only after both endpoints and the source item are valid."""
    if source_index < 0 or source_index >= source.count():
        return False
    widget = source.widget(source_index)
    if widget is None:
        return False

    target_index = max(0, min(target_index, target.count()))
    if source is target:
        if source.count() <= 1:
            source.setCurrentIndex(source_index)
            return True
        destination = min(target_index, source.count() - 1)
        source.tabBar().moveTab(source_index, destination)
        source.setCurrentIndex(destination)
        return True

    title = source.tabText(source_index)
    icon = source.tabIcon(source_index)
    tooltip = source.tabToolTip(source_index)
    enabled = source.isTabEnabled(source_index)
    source.removeTab(source_index)

    try:
        inserted_index = target.insertTab(target_index, widget, icon, title)
        target.setTabToolTip(inserted_index, tooltip)
        target.setTabEnabled(inserted_index, enabled)
        target.setCurrentIndex(inserted_index)
    except Exception:
        logger.exception("Failed to insert moved inspector tab; restoring source")
        restored_index = source.insertTab(source_index, widget, icon, title)
        source.setTabToolTip(restored_index, tooltip)
        source.setTabEnabled(restored_index, enabled)
        source.setCurrentIndex(restored_index)
        return False
    return True


class DraggableTabBar(QTabBar):
    """A QTabBar that supports drag-and-drop for rearranging tabs across different
    QTabWidgets within the same splitter.
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
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Initiate drag if moved far enough."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)

        drag_distance = (
            event.position().toPoint() - self._drag_start_pos
        ).manhattanLength()
        if drag_distance < _DRAG_START_DISTANCE_PX:
            return super().mouseMoveEvent(event)

        idx = self.tabAt(self._drag_start_pos)
        if idx < 0:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(INSPECTOR_TAB_MIME_TYPE, str(idx).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept tab drag data."""
        if event.mimeData().hasFormat(INSPECTOR_TAB_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop onto this tab bar."""
        if not event.mimeData().hasFormat(INSPECTOR_TAB_MIME_TYPE):
            return

        source_tab_widget = _source_tab_widget(event.source())
        source_idx = _decode_source_index(event.mimeData())
        target_tab_widget = self.parentWidget()
        if (
            source_tab_widget is None
            or source_idx is None
            or not isinstance(target_tab_widget, QTabWidget)
            or source_idx < 0
            or source_idx >= source_tab_widget.count()
        ):
            event.ignore()
            return

        title = source_tab_widget.tabText(source_idx)

        target_name = (
            source_tab_widget.objectName()
            if hasattr(source_tab_widget, "objectName")
            else None
        )
        logger.debug(
            f"DraggableTabBar.dropEvent: source_idx={source_idx}, "
            f"title='{title}', source_tab_widget={target_name}"
        )

        drop_idx = self.tabAt(event.position().toPoint())
        if drop_idx < 0:
            drop_idx = self.count()
        if not _move_tab(source_tab_widget, target_tab_widget, source_idx, drop_idx):
            event.ignore()
            return

        logger.debug("DraggableTabBar.dropEvent: moved tab, scheduling cleanup")

        # Cleanup empty source pane - schedule on next tick
        QTimer.singleShot(0, lambda: self._cleanup_empty_pane(source_tab_widget))

        event.acceptProposedAction()

    def _cleanup_empty_pane(self, tab_widget: QTabWidget) -> None:
        """Remove a tab widget from splitter if it has no tabs left.

        Uses delayed deletion with re-check to avoid race conditions during
        drag/reparent operations.

        Args:
            tab_widget: The tab widget to check and potentially remove.

        """
        logger.debug(
            f"DraggableTabBar._cleanup_empty_pane: checking tab_widget="
            f"{getattr(tab_widget, 'objectName', lambda: None)()}"
        )

        if tab_widget.count() == 0:
            splitter = self._find_parent_splitter(tab_widget)
            if splitter and splitter.count() > 1:
                logger.info("Pane empty — hiding and scheduling deletion")
                tab_widget.hide()

                def _maybe_delete() -> None:
                    """Check conditions and delete empty pane if appropriate."""
                    # Re-check conditions before deleting
                    if (
                        tab_widget.count() == 0
                        and tab_widget.parent() is splitter
                        and splitter.count() > 1
                    ):
                        logger.info("Deleting empty pane now")
                        tab_widget.setParent(None)
                        tab_widget.deleteLater()
                    else:
                        logger.debug(
                            "Skipping deletion; pane no longer empty or reparented"
                        )

                # Delay deletion by 200ms to let reparent operations complete
                QTimer.singleShot(200, _maybe_delete)

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
        self.currentChanged.connect(self._remember_section)
        self.overflow_button = QToolButton(self)
        self.overflow_button.setText("…")
        self.overflow_button.setToolTip("All inspector tabs")
        self.overflow_button.setAccessibleName("All inspector tabs")
        self.overflow_button.setFixedSize(32, 32)
        self.overflow_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.overflow_menu = QMenu(self.overflow_button)
        self.overflow_button.setMenu(self.overflow_menu)
        self.overflow_menu.aboutToShow.connect(self._populate_overflow)
        self.setCornerWidget(self.overflow_button, Qt.Corner.TopRightCorner)
        self.overflow_button.hide()
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._show_layout_menu)
        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._style_overflow)
        self._style_overflow()

    def _style_overflow(self) -> None:
        from src.gui.utils.style_helper import StyleHelper

        self.overflow_button.setStyleSheet(
            StyleHelper.get_tool_button_style()
            + StyleHelper.get_inspector_focus_style()
        )

    def _inspector(self) -> Optional["SplitterTabInspector"]:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, SplitterTabInspector):
                return parent
            parent = parent.parentWidget()
        return None

    def _populate_overflow(self) -> None:
        self.overflow_menu.clear()
        inspector = self._inspector()
        if inspector is not None:
            inspector.populate_sections(self.overflow_menu)

    def _show_layout_menu(self, position: QPoint) -> None:
        inspector = self._inspector()
        if inspector is None:
            return
        index = self.tabBar().tabAt(position)
        if index >= 0:
            self.setCurrentIndex(index)
        inspector._active_section = self.currentWidget()
        menu = QMenu(self)
        split = menu.addAction("Split active section below")
        split.setEnabled(self.count() > 1)
        split.triggered.connect(inspector.split_active_section)
        menu.addAction("Reset inspector layout").triggered.connect(
            inspector.reset_layout
        )
        menu.exec(self.tabBar().mapToGlobal(position))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Only show tab overflow access when the full tab strip cannot fit."""
        super().resizeEvent(event)
        self._update_overflow()

    def tabInserted(self, index: int) -> None:  # noqa: N802
        """Recheck overflow after drag, split, or initial tab insertion."""
        super().tabInserted(index)
        self._update_overflow()

    def tabRemoved(self, index: int) -> None:  # noqa: N802
        """Hide overflow again when removing a tab creates sufficient space."""
        super().tabRemoved(index)
        self._update_overflow()

    def _update_overflow(self) -> None:
        if hasattr(self, "overflow_button"):
            self.overflow_button.setVisible(
                self.tabBar().sizeHint().width() > self.width()
            )

    def _remember_section(self, index: int) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, SplitterTabInspector):
                parent._active_section = self.widget(index)
                return
            parent = parent.parentWidget()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drops to create vertical splits."""
        if event.mimeData().hasFormat(INSPECTOR_TAB_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop to create a vertical split.

        If dropped on the body (not the tab bar), create a new pane.
        """
        # Let the tab bar handle it if the drop is on the tab bar
        local_pos = event.position().toPoint()
        tab_bar_rect = self.tabBar().rect()
        if tab_bar_rect.contains(self.tabBar().mapFrom(self, local_pos)):
            return  # Tab bar will handle

        if not event.mimeData().hasFormat(INSPECTOR_TAB_MIME_TYPE):
            return

        source_tab_widget = _source_tab_widget(event.source())
        source_idx = _decode_source_index(event.mimeData())
        splitter = self._find_parent_splitter()
        if (
            source_tab_widget is None
            or source_idx is None
            or splitter is None
            or source_idx < 0
            or source_idx >= source_tab_widget.count()
        ):
            event.ignore()
            return
        title = source_tab_widget.tabText(source_idx)

        target_name = (
            source_tab_widget.objectName()
            if hasattr(source_tab_widget, "objectName")
            else None
        )
        logger.debug(
            f"dropEvent: source_idx={source_idx}, title='{title}', "
            f"source_tab_widget={target_name}"
        )

        # Create a new DraggableTabWidget in the splitter
        new_tab_widget = DraggableTabWidget()
        idx = splitter.indexOf(self)
        splitter.insertWidget(idx + 1, new_tab_widget)
        if not _move_tab(source_tab_widget, new_tab_widget, source_idx, 0):
            new_tab_widget.setParent(None)
            new_tab_widget.deleteLater()
            event.ignore()
            return

        logger.debug("dropEvent: moved tab, scheduling cleanup check for source pane")

        # Cleanup empty source pane (after creating new one)
        # Schedule on next tick to avoid race between removeTab and cleanup
        QTimer.singleShot(
            0, lambda: self._cleanup_empty_pane(source_tab_widget, splitter)
        )

        event.acceptProposedAction()

    def _cleanup_empty_pane(self, tab_widget: QTabWidget, splitter: QSplitter) -> None:
        """Remove a tab widget from splitter if it has no tabs left.

        Uses delayed deletion with re-check to avoid race conditions during
        drag/reparent operations.

        Args:
            tab_widget: The tab widget to check and potentially remove.
            splitter: The parent splitter containing the tab widget.

        """
        logger.debug(
            f"_cleanup_empty_pane: checking tab_widget="
            f"{getattr(tab_widget, 'objectName', lambda: None)()}"
        )

        if tab_widget.count() == 0 and splitter.count() > 1:
            logger.info("Pane empty — hiding and scheduling deletion")
            tab_widget.hide()

            def _maybe_delete() -> None:
                """Check conditions and delete empty pane if appropriate."""
                # Re-check conditions before deleting
                if (
                    tab_widget.count() == 0
                    and tab_widget.parent() is splitter
                    and splitter.count() > 1
                ):
                    logger.info("Deleting empty pane now")
                    tab_widget.setParent(None)
                    tab_widget.deleteLater()
                else:
                    logger.debug(
                        "Skipping deletion; pane no longer empty or reparented"
                    )

            # Delay deletion by 200ms to let reparent operations complete
            QTimer.singleShot(200, _maybe_delete)

    def _find_parent_splitter(self) -> Optional[QSplitter]:
        """Find the parent QSplitter."""
        parent = self.parent()
        while parent:
            if isinstance(parent, QSplitter):
                return parent
            parent = parent.parent()
        return None


class SplitterTabInspector(QWidget):
    """A widget that provides a vertically splittable tab container.

    Tabs can be dragged to the tab bar to rearrange, or dropped on the body of another
    tab widget to create a vertical split.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the splitter tab inspector."""
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sections: list[tuple[QWidget, str]] = []
        self._active_section: QWidget | None = None
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

    def add_tab(
        self, widget: QWidget, title: str, tooltip: Optional[str] = None
    ) -> None:
        """Add a tab to the main tab widget.

        Args:
            widget (QWidget): The widget to add.
            title (str): The tab title.
            tooltip (str, optional): The tab tooltip.

        """
        index = self.main_tabs.addTab(widget, title)
        self._sections.append((widget, title))
        if tooltip:
            self.main_tabs.setTabToolTip(index, tooltip)

    def populate_sections(self, menu: QMenu) -> None:
        """Find each section in its current pane, including dragged sections."""
        for widget, title in self._sections:
            action = menu.addAction(title)
            action.triggered.connect(
                lambda _checked=False, section=widget: self.activate_section(section)
            )

    def activate_section(self, section: QWidget) -> None:
        """Activate a section without moving it out of its split pane."""
        for tabs in self.findChildren(DraggableTabWidget):
            index = tabs.indexOf(section)
            if index >= 0:
                tabs.setCurrentIndex(index)
                self._active_section = section
                section.setFocus(Qt.FocusReason.OtherFocusReason)
                return

    def split_active_section(self) -> None:
        """Split the focused pane's current section using a discoverable action."""
        from PySide6.QtWidgets import QApplication

        panes = [self.splitter.widget(i) for i in range(self.splitter.count())]
        focus = QApplication.focusWidget()
        tabs = next(
            (p for p in panes if focus is not None and p.isAncestorOf(focus)),
            next(
                (
                    p
                    for p in panes
                    if isinstance(p, DraggableTabWidget)
                    and p.currentWidget() is self._active_section
                ),
                panes[0],
            ),
        )
        if not isinstance(tabs, DraggableTabWidget) or tabs.count() <= 1:
            return
        new_tabs = DraggableTabWidget()
        self.splitter.insertWidget(self.splitter.indexOf(tabs) + 1, new_tabs)
        _move_tab(tabs, new_tabs, tabs.currentIndex(), 0)
        self.splitter.setSizes([1] * self.splitter.count())

    def reset_layout(self) -> None:
        """Restore original section order without recreating any content."""
        panes = self.findChildren(DraggableTabWidget)
        target = panes[0]
        for widget, title in self._sections:
            tooltip = ""
            for pane in panes:
                index = pane.indexOf(widget)
                if index >= 0:
                    tooltip = pane.tabToolTip(index)
                    pane.removeTab(index)
                    break
            index = target.addTab(widget, title)
            target.setTabToolTip(index, tooltip)
        for pane in panes[1:]:
            pane.setParent(None)
            pane.deleteLater()
        self.main_tabs = target
        self._tab_widgets = [target]
        target.setCurrentIndex(0)

    def get_main_tabs(self) -> QTabWidget:
        """Return the main tab widget."""
        return self.main_tabs

    def minimumSizeHint(self) -> QSize:
        """Prevent tab inspector collapse.

        Returns:
            QSize: Minimum size for usable tab inspector.

        """
        from PySide6.QtCore import QSize

        return QSize(200, 150)  # Minimum height for at least one tab visible

    def sizeHint(self) -> QSize:
        """Preferred size for tab inspector.

        Returns:
            QSize: Comfortable working size for inspector tabs.

        """
        from PySide6.QtCore import QSize

        return QSize(400, 500)  # Ideal size for tab content
