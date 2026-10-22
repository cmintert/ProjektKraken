"""Reusable tab container for one fixed workspace zone."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSizePolicy,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper
from src.gui.workspace.panel_registry import ZONE_NAMES, ZoneName
from src.gui.workspace.rounded_frame import RoundedWorkspaceFrame

PANEL_MIME_TYPE = "application/x-projektkraken-panel"
_PANE_CORNER_RADIUS = 9
_PANEL_CLOSE_ICON = "default_assets/icons/ui_icons/x-circle.svg"


class WorkspaceTabBar(QTabBar):
    """Tab bar that can send panel IDs to another workspace zone."""

    panel_drop_requested = Signal(str, int)
    panel_drag_started = Signal(str)
    panel_drag_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a drop-enabled tab bar."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._drag_start = QPoint()
        self._drag_panel_id: str | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Remember the start of a possible cross-zone tab drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            index = self.tabAt(self._drag_start)
            panel_id = self.tabData(index) if index >= 0 else None
            self._drag_panel_id = panel_id if isinstance(panel_id, str) else None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a semantic panel drag after Qt's normal threshold."""
        if not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        position = event.position().toPoint()
        if (
            self._drag_panel_id is None
            or self.rect().contains(position)
            or (position - self._drag_start).manhattanLength()
            < QApplication.startDragDistance()
        ):
            super().mouseMoveEvent(event)
            return
        panel_id = self._drag_panel_id

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
            self._drag_panel_id = None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Forget the drag origin after Qt finishes a local tab move."""
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_panel_id = None

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
            position = event.position().toPoint()
            index = self.tabAt(position)
            if index < 0:
                index = self.count()
            elif position.x() >= self.tabRect(index).center().x():
                index += 1
            self.panel_drop_requested.emit(panel_id, index)
            event.acceptProposedAction()


class PaneContainer(QWidget):
    """Generic tabbed container for one of Kraken's four workspace zones."""

    panel_move_requested = Signal(str, str, int)
    panel_drag_started = Signal(str)
    panel_drag_finished = Signal()
    panel_order_changed = Signal()
    panel_activated = Signal(str)
    panel_close_requested = Signal(str)

    def __init__(self, zone: ZoneName, parent: QWidget | None = None) -> None:
        """Create a tab container for one fixed workspace zone."""
        super().__init__(parent)
        if zone not in ZONE_NAMES:
            raise ValueError(f"Unknown zone: {zone}")
        self.zone = zone
        self.setObjectName(f"WorkspacePane_{zone}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAcceptDrops(True)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(self)
        # One pixel for the frame plus four pixels of air above the tab row.
        layout.setContentsMargins(1, 5, 1, 1)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName(f"WorkspaceTabs_{zone}")
        self.tabs.setDocumentMode(True)
        tab_bar = WorkspaceTabBar(self.tabs)
        tab_bar.setMovable(True)
        self.tabs.setTabBar(tab_bar)
        self.tabs.setTabsClosable(True)
        # Reserve space in Qt's tab-row layout, so tabs and scroll buttons
        # cannot extend beneath the painted outer corners.
        for corner in (Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner):
            spacer = QLabel(self.tabs)
            # QLabel supplies the valid sizeHint needed by QTabWidget's style
            # layout; a bare QWidget's invalid hint makes Qt ignore the inset.
            spacer.setFixedSize(_PANE_CORNER_RADIUS + 1, _PANE_CORNER_RADIUS)
            spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.tabs.setCornerWidget(spacer, corner)
        tab_bar.panel_drop_requested.connect(self._request_drop)
        tab_bar.panel_drag_started.connect(self.panel_drag_started)
        tab_bar.panel_drag_finished.connect(self.panel_drag_finished)
        tab_bar.tabMoved.connect(self.panel_order_changed)
        self.tabs.currentChanged.connect(self._on_current_changed)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_tab_menu)
        layout.addWidget(self.tabs)

        self.empty_drop_hint = QLabel("Open a panel from View → Panels", self)
        self.empty_drop_hint.setObjectName(f"WorkspaceDropTarget_{zone}")
        self.empty_drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_drop_hint.hide()
        layout.addWidget(self.empty_drop_hint, 1)

        self._corners = RoundedWorkspaceFrame(self, _PANE_CORNER_RADIUS)
        self._corners.raise_()
        ThemeManager().theme_changed.connect(self._refresh_close_buttons)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep rounded outer corners aligned with the entire tabbed pane."""
        super().resizeEvent(event)
        self._corners.setGeometry(self.rect())
        self._corners.raise_()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Allow the splitter to negotiate compact peripheral zones."""
        return QSize(0, 0)

    def set_drag_target_active(self, active: bool) -> None:
        """Show an explicit drop surface when this pane has no tabs."""
        show_hint = not self.panel_ids()
        self.empty_drop_hint.setText(
            "Drop panel here" if active else "Open a panel from View → Panels"
        )
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

    def add_panel(
        self, panel_id: str, title: str, widget: QWidget, index: int = -1
    ) -> int:
        """Add a panel widget without recreating it."""
        existing = self.index_of(panel_id)
        if existing >= 0:
            return existing
        index = (
            self.tabs.insertTab(index, widget, title)
            if index >= 0
            else self.tabs.addTab(widget, title)
        )
        self.tabs.tabBar().setTabData(index, panel_id)
        self.tabs.setTabToolTip(index, title)
        close_button = QToolButton(self.tabs.tabBar())
        close_button.setObjectName("WorkspacePanelCloseButton")
        close_button.clicked.connect(
            lambda _checked=False, target=panel_id: self.panel_close_requested.emit(
                target
            )
        )
        self.tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, close_button
        )
        self._style_close_button(index)
        self.set_drag_target_active(False)
        return index

    def remove_panel(self, panel_id: str) -> QWidget | None:
        """Remove and return a panel without deleting its widget."""
        index = self.index_of(panel_id)
        if index < 0:
            return None
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        self.set_drag_target_active(False)
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
        self._style_close_button(index)
        return True

    def _style_close_button(self, index: int) -> None:
        """Apply the small Phosphor cue and shared quiet action states."""
        close_button = self.tabs.tabBar().tabButton(
            index, QTabBar.ButtonPosition.RightSide
        )
        if not isinstance(close_button, QToolButton):
            return
        title = self.tabs.tabText(index)
        close_button.setAccessibleName(f"Close {title} panel")
        close_button.setToolTip(f"Close {title} panel")
        close_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        close_button.setFixedSize(20, 20)
        close_button.setIconSize(QSize(14, 14))
        close_button.setIcon(
            load_icon(_PANEL_CLOSE_ICON, ThemeManager().get_theme()["text_dim"])
        )
        close_button.setStyleSheet(
            StyleHelper.get_action_role_style(
                "quiet", "QToolButton#WorkspacePanelCloseButton"
            )
            + "\nQToolButton#WorkspacePanelCloseButton {"
            " border-radius: 10px; padding: 0px; }"
        )

    def _refresh_close_buttons(self, _theme: dict | None = None) -> None:
        """Recolor every panel close icon when the active palette changes."""
        for index in range(self.tabs.count()):
            self._style_close_button(index)

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

    def _on_current_changed(self, _index: int) -> None:
        """Publish the semantic ID of the newly active tab."""
        panel_id = self.current_panel_id()
        if panel_id is not None:
            self.panel_activated.emit(panel_id)

    def _on_tab_close_requested(self, index: int) -> None:
        """Ask the shell to close the panel represented by this tab."""
        panel_id = self.tabs.tabBar().tabData(index)
        if isinstance(panel_id, str):
            self.panel_close_requested.emit(panel_id)

    def index_of(self, panel_id: str) -> int:
        """Return the tab index for *panel_id*, or ``-1``."""
        bar = self.tabs.tabBar()
        for index in range(self.tabs.count()):
            if bar.tabData(index) == panel_id:
                return index
        return -1

    def _request_drop(self, panel_id: str, index: int = -1) -> None:
        self.panel_move_requested.emit(panel_id, self.zone, index)

    def _show_tab_menu(self, position: QPoint) -> None:
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        panel_id = self.tabs.tabBar().tabData(index)
        if not isinstance(panel_id, str):
            return
        menu = declare_inspection(
            QMenu(self),
            "src-gui-workspace-pane-container-panecontainer-show-tab-menu-menu|workspace.navigation|help-inspect-src-gui-workspace-pane-container-panecontainer-show-tab-menu-menu",
        )
        for zone in ZONE_NAMES:
            action = declare_inspection(
                menu.addAction(f"Move to {zone.title()}"),
                "src-gui-workspace-pane-container-panecontainer-show-tab-menu-action|workspace.navigation|help-inspect-src-gui-workspace-pane-container-panecontainer-show-tab-menu-action",
            )
            action.setEnabled(zone != self.zone)
            action.triggered.connect(
                lambda _checked=False, target=zone: self.panel_move_requested.emit(
                    panel_id, target, -1
                )
            )
        menu.exec(self.tabs.tabBar().mapToGlobal(position))
