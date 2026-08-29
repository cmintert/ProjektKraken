"""Reusable tab container for one fixed workspace zone."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSizePolicy,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.workspace.panel_registry import ZONE_NAMES, ZoneName

PANEL_MIME_TYPE = "application/x-projektkraken-panel"


class WorkspaceTabBar(QTabBar):
    """Tab bar that can send panel IDs to another workspace zone."""

    panel_drop_requested = Signal(str)
    panel_drag_started = Signal(str)
    panel_drag_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a drop-enabled tab bar."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_start = QPoint()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Remember the start of a possible cross-zone tab drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a semantic panel drag after Qt's normal threshold."""
        if not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < (
            QApplication.startDragDistance()
        ):
            super().mouseMoveEvent(event)
            return
        index = self.tabAt(self._drag_start)
        if index < 0:
            super().mouseMoveEvent(event)
            return
        panel_id = self.tabData(index)
        if not isinstance(panel_id, str):
            super().mouseMoveEvent(event)
            return

        mime_data = QMimeData()
        mime_data.setData(PANEL_MIME_TYPE, panel_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        self.panel_drag_started.emit(panel_id)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.panel_drag_finished.emit()
            self._drag_start = QPoint()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept Kraken panel drags."""
        if event.mimeData().hasFormat(PANEL_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """Keep a Kraken panel drag accepted while it crosses this tab bar."""
        if event.mimeData().hasFormat(PANEL_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Request movement of the dropped panel into this tab bar's zone."""
        if not event.mimeData().hasFormat(PANEL_MIME_TYPE):
            super().dropEvent(event)
            return
        payload = event.mimeData().data(PANEL_MIME_TYPE)
        panel_id = bytes(payload.data()).decode("utf-8", errors="ignore")
        if panel_id:
            self.panel_drop_requested.emit(panel_id)
            event.acceptProposedAction()


class PaneContainer(QWidget):
    """Generic tabbed container for one of Kraken's four workspace zones."""

    panel_move_requested = Signal(str, str)
    panel_drag_started = Signal(str)
    panel_drag_finished = Signal()

    def __init__(self, zone: ZoneName, parent: QWidget | None = None) -> None:
        """Create a tab container for one fixed workspace zone."""
        super().__init__(parent)
        if zone not in ZONE_NAMES:
            raise ValueError(f"Unknown zone: {zone}")
        self.zone = zone
        self.setObjectName(f"WorkspacePane_{zone}")
        self.setAcceptDrops(True)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName(f"WorkspaceTabs_{zone}")
        self.tabs.setDocumentMode(True)
        tab_bar = WorkspaceTabBar(self.tabs)
        tab_bar.setMovable(True)
        self.tabs.setTabBar(tab_bar)
        tab_bar.panel_drop_requested.connect(self._request_drop)
        tab_bar.panel_drag_started.connect(self.panel_drag_started)
        tab_bar.panel_drag_finished.connect(self.panel_drag_finished)
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_menu)
        layout.addWidget(self.tabs)

        self.empty_drop_hint = QLabel("Drop panel here", self)
        self.empty_drop_hint.setObjectName(f"WorkspaceDropTarget_{zone}")
        self.empty_drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_drop_hint.hide()
        layout.addWidget(self.empty_drop_hint, 1)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Allow the splitter to negotiate compact peripheral zones."""
        return QSize(0, 0)

    def set_drag_target_active(self, active: bool) -> None:
        """Show an explicit drop surface when this pane has no tabs."""
        show_hint = active and not self.panel_ids()
        self.empty_drop_hint.setVisible(show_hint)
        self.tabs.setVisible(not show_hint)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept panel drags over an empty pane's drop surface."""
        if event.mimeData().hasFormat(PANEL_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """Keep panel drags accepted across the empty drop surface."""
        if event.mimeData().hasFormat(PANEL_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Move a panel dropped onto this pane's empty drop surface."""
        if not event.mimeData().hasFormat(PANEL_MIME_TYPE):
            super().dropEvent(event)
            return
        payload = event.mimeData().data(PANEL_MIME_TYPE)
        panel_id = bytes(payload.data()).decode("utf-8", errors="ignore")
        if panel_id:
            self._request_drop(panel_id)
            event.acceptProposedAction()

    def add_panel(self, panel_id: str, title: str, widget: QWidget) -> int:
        """Add a panel widget without recreating it."""
        existing = self.index_of(panel_id)
        if existing >= 0:
            return existing
        index = self.tabs.addTab(widget, title)
        self.tabs.tabBar().setTabData(index, panel_id)
        self.tabs.setTabToolTip(index, title)
        return index

    def remove_panel(self, panel_id: str) -> QWidget | None:
        """Remove and return a panel without deleting its widget."""
        index = self.index_of(panel_id)
        if index < 0:
            return None
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        return widget

    def activate_panel(self, panel_id: str) -> bool:
        """Activate a panel tab if it belongs to this zone."""
        index = self.index_of(panel_id)
        if index < 0:
            return False
        self.tabs.setCurrentIndex(index)
        return True

    def set_panel_title(self, panel_id: str, title: str) -> bool:
        """Update a panel's tab title without exposing the tab widget."""
        index = self.index_of(panel_id)
        if index < 0:
            return False
        self.tabs.setTabText(index, title)
        self.tabs.setTabToolTip(index, title)
        return True

    def contains_panel(self, panel_id: str) -> bool:
        """Return whether this zone contains *panel_id*."""
        return self.index_of(panel_id) >= 0

    def panel_ids(self) -> list[str]:
        """Return panel IDs in visible tab order."""
        result: list[str] = []
        bar = self.tabs.tabBar()
        for index in range(self.tabs.count()):
            panel_id = bar.tabData(index)
            if isinstance(panel_id, str):
                result.append(panel_id)
        return result

    def current_panel_id(self) -> str | None:
        """Return the active panel ID, if any."""
        index = self.tabs.currentIndex()
        if index < 0:
            return None
        panel_id = self.tabs.tabBar().tabData(index)
        return panel_id if isinstance(panel_id, str) else None

    def index_of(self, panel_id: str) -> int:
        """Return the tab index for *panel_id*, or ``-1``."""
        bar = self.tabs.tabBar()
        for index in range(self.tabs.count()):
            if bar.tabData(index) == panel_id:
                return index
        return -1

    def _request_drop(self, panel_id: str) -> None:
        self.panel_move_requested.emit(panel_id, self.zone)

    def _show_tab_menu(self, position: QPoint) -> None:
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        panel_id = self.tabs.tabBar().tabData(index)
        if not isinstance(panel_id, str):
            return
        menu = QMenu(self)
        for zone in ZONE_NAMES:
            action = menu.addAction(f"Move to {zone.title()}")
            action.setEnabled(zone != self.zone)
            action.triggered.connect(
                lambda _checked=False, target=zone: self.panel_move_requested.emit(
                    panel_id, target
                )
            )
        menu.exec(self.tabs.tabBar().mapToGlobal(position))
