"""Window-scoped keyboard traversal without authoring or persistence effects."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import cast

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QGridLayout,
    QLayout,
    QMenu,
    QScrollArea,
    QSplitter,
    QTabBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from src.gui.utils.help_context import declare_inspection, owns_assistance_input
from src.gui.utils.shortcut_manager import ShortcutManager
from src.gui.workspace.panel_registry import ZoneName
from src.gui.workspace.workspace_shell import WorkspaceShell

_REGIONS = ("rail", "left", "center", "right", "bottom")


class FocusNavigationController(QObject):
    """Keep Tab local and provide deliberate movement between visible regions."""

    def __init__(
        self,
        shell: WorkspaceShell,
        focus_surface: Callable[[], QWidget | None],
        exit_focus: Callable[[], None],
        parent: QWidget,
    ) -> None:
        """Bind presentation-only endpoints and scoped application input."""
        super().__init__(parent)
        self.shell = shell
        self._focus_surface = focus_surface
        self._exit_focus = exit_focus
        self._last: dict[str, weakref.ReferenceType[QWidget]] = {}
        self._region: str | None = None
        self._repairing = False
        self._native_tab: tuple[QWidget, bool] | None = None
        self._repair_origin: str | None = None
        self._repair_focus: weakref.ReferenceType[QWidget] | None = None
        shell.destroyed.connect(self._detach)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.installEventFilter(self)
            app.focusChanged.connect(self._remember)
        shell.layout_changed.connect(self._schedule_repair)
        self._repair_timer = QTimer(self)
        self._repair_timer.setSingleShot(True)
        self._repair_timer.timeout.connect(self._repair)

    def _detach(self) -> None:
        """Stop application callbacks before the shell's child widgets disappear."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.removeEventFilter(self)
            app.focusChanged.disconnect(self._remember)
        self._repair_timer.stop()

    def install_actions(self, menu: QMenu) -> None:
        """Expose accelerators through the existing View menu."""
        menu.addSeparator()
        for shortcut, forward in (
            (ShortcutManager.NEXT_PANEL_REGION, True),
            (ShortcutManager.PREVIOUS_PANEL_REGION, False),
        ):
            action = declare_inspection(
                QAction(shortcut.name, self),
                "workspace.focus-region|workspace.navigation|help-inspect-workspace-focus-region",
            )
            action.setShortcut(shortcut.key_sequence)
            action.triggered.connect(
                lambda _checked=False, direction=forward: self.move_region(direction)
            )
            menu.addAction(action)

    def _root(self, region: str) -> QWidget:
        return (
            self.shell.activity_bar
            if region == "rail"
            else self.shell.panes[cast(ZoneName, region)]
        )

    def _region_for(self, widget: QWidget | None) -> str | None:
        if (
            not shiboken6.isValid(self.shell)
            or widget is None
            or not shiboken6.isValid(widget)
        ):
            return None
        for region in _REGIONS:
            root = self._root(region)
            if root is widget or root.isAncestorOf(widget):
                return region
        return None

    @staticmethod
    def _eligible(widget: QWidget) -> bool:
        available = (
            shiboken6.isValid(widget)
            and widget.isVisible()
            and widget.isEnabled()
            and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
        )
        if not available:
            return False
        if not widget.visibleRegion().isEmpty():
            return True
        # Scrollable form fields remain reachable; clipped tab/toolbar controls do not.
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return not parent.visibleRegion().isEmpty()
            parent = parent.parentWidget()
        return False

    def _children(self, widget: QWidget) -> list[QWidget]:
        """Read layout order while treating native composite inputs as one stop."""
        if isinstance(widget, QTabWidget):
            bar = widget.tabBar()
            close = bar.tabButton(bar.currentIndex(), QTabBar.ButtonPosition.RightSide)
            return [item for item in (bar, close, widget.currentWidget()) if item]
        if isinstance(widget, QTabBar):
            return []
        if isinstance(widget, QScrollArea):
            return [widget.widget()] if widget.widget() else []
        if isinstance(widget, (QAbstractScrollArea, QComboBox)):
            return []
        if isinstance(widget, QSplitter):
            return [widget.widget(i) for i in range(widget.count())]
        if isinstance(widget, QToolBar):
            children = [
                child for a in widget.actions() if (child := widget.widgetForAction(a))
            ]
            extension = widget.findChild(QWidget, "qt_toolbar_ext_button")
            return children + ([extension] if extension is not None else [])
        if widget.inherits("QWebEngineView"):
            return []
        layout = widget.layout()
        if layout is None:
            return widget.findChildren(
                QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
            )
        result: list[QWidget] = []

        def visit_layout(layout: QLayout) -> None:
            indices = list(range(layout.count()))
            if isinstance(layout, QGridLayout):
                # Qt returns (row, column, rowSpan, columnSpan); the stub uses object.
                indices.sort(
                    key=lambda index: cast(
                        tuple[int, int, int, int], layout.getItemPosition(index)
                    )[:2]
                )
            for index in indices:
                item = layout.itemAt(index)
                if item is None:
                    continue
                if child := item.widget():
                    result.append(child)
                elif child_layout := item.layout():
                    visit_layout(child_layout)

        visit_layout(layout)
        return result

    def targets(self, root: QWidget) -> list[QWidget]:
        """Return current visible controls, once each, in presentation order."""
        if not root.isVisible() or root.width() <= 0 or root.height() <= 0:
            return []
        result: list[QWidget] = []
        seen: set[int] = set()

        def visit(widget: QWidget) -> None:
            if not widget.isVisible() or not widget.isEnabled():
                return
            target = widget.focusProxy() or widget
            if (
                not isinstance(widget, QScrollArea)
                and self._eligible(target)
                and id(target) not in seen
            ):
                seen.add(id(target))
                result.append(target)
            for child in self._children(widget):
                visit(child)

        visit(root)
        return result

    def _scope(self, widget: QWidget) -> QWidget | None:
        surface = self._focus_surface()
        if surface is not None and (surface is widget or surface.isAncestorOf(widget)):
            return surface
        region = self._region_for(widget)
        return self._root(region) if region else None

    def move_local(self, origin: QWidget, forward: bool) -> bool:
        """Advance one eligible control and wrap within the current surface."""
        root = self._scope(origin)
        targets = self.targets(root) if root is not None else []
        if not targets:
            return False
        index = next((i for i, item in enumerate(targets) if item is origin), None)
        if index is None:
            index = next(
                (i for i, item in enumerate(targets) if item.isAncestorOf(origin)),
                -1 if forward else 0,
            )
        target = targets[(index + (1 if forward else -1)) % len(targets)]
        target.setFocus(
            Qt.FocusReason.TabFocusReason
            if forward
            else Qt.FocusReason.BacktabFocusReason
        )
        for ancestor in self._ancestors(target):
            if isinstance(ancestor, QScrollArea):
                ancestor.ensureWidgetVisible(target)
        return True

    def _blocked(self) -> bool:
        return bool(
            QApplication.activeModalWidget()
            or QApplication.activePopupWidget()
            or owns_assistance_input(QApplication.focusWidget())
        )

    def move_region(self, forward: bool = True) -> None:
        """Move deliberately without activating workspaces or inactive panels."""
        if self._blocked():
            return
        current = self._region_for(QApplication.focusWidget()) or self._region
        self._exit_focus()
        available = [region for region in _REGIONS if self.targets(self._root(region))]
        if not available:
            return
        index = (
            available.index(current) if current in available else (-1 if forward else 0)
        )
        region = available[(index + (1 if forward else -1)) % len(available)]
        self._focus_region(region)

    def _focus_region(self, region: str) -> None:
        targets = self.targets(self._root(region))
        if not targets:
            return
        previous = self._last.get(region)
        remembered = previous() if previous else None
        if remembered in targets:
            remembered.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        target = targets[0]
        if region == "rail":
            rail = self.shell.activity_bar
            target = next(
                (
                    rail.widgetForAction(a)
                    for a in rail.workspace_actions.values()
                    if a.isChecked() and rail.widgetForAction(a) in targets
                ),
                target,
            )
        target.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _remember(self, _old: QWidget | None, now: QWidget | None) -> None:
        if not shiboken6.isValid(self.shell):
            return
        if self._native_tab is not None and now is not None:
            root, forward = self._native_tab
            self._native_tab = None
            if not (root is now or root.isAncestorOf(now)):
                targets = self.targets(root)
                if targets:
                    targets[0 if forward else -1].setFocus(
                        Qt.FocusReason.TabFocusReason
                    )
                    return
        region = self._region_for(now)
        if region is not None and now is not None:
            self._region = region
            self._last[region] = weakref.ref(now)

    def _schedule_repair(self) -> None:
        self._repair_timer.start(0)

    def _repair(self) -> None:
        if not shiboken6.isValid(self.shell):
            return
        if self._repairing or self._region is None or self._blocked():
            return
        origin = self._repair_origin or self._region
        restored = self._repair_focus() if self._repair_focus is not None else None
        self._repair_origin = None
        self._repair_focus = None
        now = QApplication.focusWidget()
        if (
            now is not None
            and now.isVisible()
            and self._region_for(now) is not None
            and (self._region_for(now) == origin or now is restored)
        ):
            return
        self._repairing = True
        try:
            for region in dict.fromkeys((origin, "center", "rail")):
                if self.targets(self._root(region)):
                    self._last.pop(region, None)
                    self._focus_region(region)
                    break
        finally:
            self._repairing = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Intercept only local traversal; native popups and editing keep ownership."""
        if not shiboken6.isValid(self.shell):
            return False
        if isinstance(watched, QWidget) and event.type() == QEvent.Type.Hide:
            focused = QApplication.focusWidget()
            if focused is not None and (
                watched is focused or watched.isAncestorOf(focused)
            ):
                region = self._region_for(focused)
                if (
                    region is not None
                    and watched is not self.shell
                    and self._repair_origin is None
                ):
                    self._repair_origin = region
                    self._repair_focus = weakref.ref(focused)
                    self._schedule_repair()
        if not isinstance(watched, QWidget) or not isinstance(event, QKeyEvent):
            return False
        if event.type() != QEvent.Type.KeyPress or owns_assistance_input(watched):
            return False
        if event.key() not in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            return False
        root = self._scope(watched)
        if (
            root is None
            or QApplication.activeModalWidget()
            or QApplication.activePopupWidget()
        ):
            return False
        forward = event.key() != Qt.Key.Key_Backtab and not bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        # Item delegates own cell commit/navigation. Wrap only if they leave the region.
        if any(
            isinstance(item, QAbstractItemView) for item in self._ancestors(watched)
        ):
            self._native_tab = (root, forward)
            QTimer.singleShot(0, self._clear_native_tab)
            return False
        return self.move_local(watched, forward)

    @staticmethod
    def _ancestors(widget: QWidget) -> list[QWidget]:
        result = []
        candidate: QWidget | None = widget
        while candidate is not None:
            result.append(candidate)
            candidate = candidate.parentWidget()
        return result

    def _clear_native_tab(self) -> None:
        self._native_tab = None
