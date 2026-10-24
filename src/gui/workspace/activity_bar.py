"""Collapsible activity navigation using shared theme controls and native actions."""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.core.workspaces import BUILTIN_WORKSPACES
from src.gui.utils.action_label_metrics import intrinsic_action_size
from src.gui.utils.help_context import declare_inspection, owns_assistance_input
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper


class ActivityBar(QToolBar):
    """Show built-in activities and a bounded menu for custom workspaces."""

    workspace_requested = Signal(str)
    management_requested = Signal(str)
    expanded_changed = Signal(bool)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Keep keyboard activation native and size from current font/style metrics."""
        super().__init__(title, parent)
        self.expanded = False
        self._icons: dict[QAction, str] = {}
        self.workspace_actions: dict[str, QAction] = {}
        self._group = QActionGroup(self)
        self._size_timer = QTimer(self)
        self._size_timer.setSingleShot(True)
        self._size_timer.timeout.connect(self._size_buttons)
        self._menu_origin: QWidget | None = None
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._restore_menu_focus)
        ThemeManager().theme_changed.connect(self._apply_theme)

    def configure_workspaces(self) -> None:
        """Install six activity destinations independently of panel registration."""
        if self.workspace_actions:
            return
        self.clear()
        for definition in BUILTIN_WORKSPACES:
            action = self._action(definition.name, definition.icon)
            action.setObjectName(f"Workspace_{definition.id}")
            action.setCheckable(True)
            self._group.addAction(action)
            action.triggered.connect(
                lambda _checked=False,
                target=definition.id: self.workspace_requested.emit(target)
            )
            self.workspace_actions[definition.id] = action
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.addWidget(spacer)
        self.addSeparator()
        self.workspace_menu = QMenu("Workspaces", self)
        self.workspace_menu.setToolTipsVisible(True)
        self.workspace_menu.aboutToShow.connect(self._remember_menu_focus)
        self.workspace_menu.aboutToHide.connect(self.restore_menu_focus)
        self.management_action = self._action("Workspaces", "sliders")
        button = self.widgetForAction(self.management_action)
        if isinstance(button, QToolButton):
            button.setMenu(self.workspace_menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.expand_action = self._action("Collapse", "workspace-collapse")
        self.expand_action.triggered.connect(
            lambda: self.set_expanded(not self.expanded)
        )
        self._apply_theme()
        self.set_expanded(self.expanded)

    def _action(self, label: str, icon: str) -> QAction:
        action = declare_inspection(
            self.addAction(label),
            "workspace.activity|workspace.navigation|help-inspect-workspace-activity",
        )
        action.setToolTip(label)
        self._icons[action] = icon
        button = self.widgetForAction(action)
        if isinstance(button, QToolButton):
            button.setAccessibleName(label)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return action

    def set_entries(self, entries: list[tuple[str, str]], active: str) -> None:
        """Render current destinations and management availability without activating."""
        self._group.setExclusive(False)
        for identifier, action in self.workspace_actions.items():
            action.setChecked(identifier == active)
        self._group.setExclusive(True)
        self.workspace_menu.clear()
        for identifier, name in entries:
            action = self._menu_action(name)
            action.setCheckable(True)
            action.setChecked(identifier == active)
            action.triggered.connect(
                lambda _checked=False, target=identifier: self.workspace_requested.emit(
                    target
                )
            )
        self.workspace_menu.addSeparator()
        for operation, label in (
            ("save", "Save as workspace…"),
            ("rename", "Rename workspace…"),
            ("delete", "Delete workspace…"),
            ("reset", "Reset workspace layout"),
        ):
            action = self._menu_action(label)
            action.setEnabled(
                operation not in ("rename", "delete") or active.startswith("custom:")
            )
            action.triggered.connect(
                lambda _checked=False, target=operation: self.management_requested.emit(
                    target
                )
            )
        self.workspace_menu.addSeparator()
        label = "Collapse navigation" if self.expanded else "Expand navigation"
        self._menu_action(label).triggered.connect(
            lambda: self.set_expanded(not self.expanded)
        )

    def _menu_action(self, label: str) -> QAction:
        action = declare_inspection(
            self.workspace_menu.addAction(label),
            "workspace.manage|workspace.navigation|help-inspect-workspace-manage",
        )
        action.setToolTip(label)
        return action

    def _remember_menu_focus(self) -> None:
        origin = QApplication.focusWidget()
        self._menu_origin = origin if not isinstance(origin, QMenu) else None

    def restore_menu_focus(self) -> None:
        """Return keyboard ownership after the popup and any modal prompt close."""
        self._return_timer.start(0)

    def _restore_menu_focus(self) -> None:
        if (
            QApplication.activeModalWidget()
            or QApplication.activePopupWidget()
            or owns_assistance_input(QApplication.focusWidget())
        ):
            return
        origin = self._menu_origin
        if (
            origin is not None
            and shiboken6.isValid(origin)
            and origin.isVisible()
            and origin.isEnabled()
        ):
            origin.setFocus(Qt.FocusReason.PopupFocusReason)
        else:
            button = self.widgetForAction(self.management_action)
            if isinstance(button, QToolButton) and button.isVisible():
                button.setFocus(Qt.FocusReason.PopupFocusReason)

    def set_expanded(self, expanded: bool) -> None:
        """Choose labeled or compact navigation without clipping action wording."""
        self.expanded = expanded
        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if expanded
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.setIconSize(QSize(20, 20) if expanded else QSize(18, 18))
        if hasattr(self, "expand_action"):
            label = "Collapse navigation" if expanded else "Expand navigation"
            self.expand_action.setText("Collapse" if expanded else "Expand")
            self.expand_action.setToolTip(label)
            button = self.widgetForAction(self.expand_action)
            if isinstance(button, QToolButton):
                button.setAccessibleName(label)
            self._icons[self.expand_action] = (
                "workspace-collapse" if expanded else "workspace-expand"
            )
            self._apply_theme()
        self._size_timer.start(0)
        self.expanded_changed.emit(expanded)

    def event(self, event: QEvent) -> bool:
        """Recompute after label, font, style or action-list changes."""
        result = super().event(event)
        if hasattr(self, "_size_timer") and event.type() in (
            QEvent.Type.ActionAdded,
            QEvent.Type.ActionRemoved,
            QEvent.Type.ActionChanged,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self._size_timer.start(0)
        return result

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            StyleHelper.get_action_role_style("secondary", "QToolButton")
            if self.expanded
            else StyleHelper.get_icon_navigation_style()
        )
        theme = ThemeManager().get_theme()
        if hasattr(self, "expand_action"):
            button = self.widgetForAction(self.expand_action)
            if isinstance(button, QToolButton):
                button.setStyleSheet(
                    StyleHelper.get_action_role_style("quiet", "QToolButton")
                    if self.expanded
                    else ""
                )
        for action, icon in self._icons.items():
            action.setIcon(
                load_icon(
                    f"default_assets/icons/ui_icons/{icon}.svg",
                    theme["text_main"]
                    if self.expanded
                    else theme["supporting_caption"],
                )
            )
        self._size_timer.start(0)

    def _size_buttons(self) -> None:
        buttons = [
            button
            for action in self.actions()
            if action.isVisible()
            and isinstance(button := self.widgetForAction(action), QToolButton)
        ]
        for button in buttons:
            button.setMinimumSize(0, 0)
            button.setMaximumSize(16777215, 16777215)
        size = QSize(44, 36)
        for button in buttons:
            size = size.expandedTo(intrinsic_action_size(button))
        for button in buttons:
            button.setFixedSize(size)
        margins = self.contentsMargins()
        self.setFixedWidth(size.width() + margins.left() + margins.right() + 4)
