"""Responsive action row that moves lower-priority buttons into a menu."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize
from PySide6.QtGui import QAction, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QHBoxLayout,
    QLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper


@dataclass
class _ToolbarItem:
    button: QAbstractButton
    action: QAction
    priority: int
    pinned: bool
    available: bool


class OverflowToolBar(QWidget):
    """Keep important buttons intact and overflow secondary actions by priority."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an initially empty responsive action row."""
        super().__init__(parent)
        self.setObjectName("OverflowToolBar")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._items: list[_ToolbarItem] = []

        self._layout = QHBoxLayout(self)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self.overflow_menu = QMenu(self)
        self.overflow_menu.aboutToShow.connect(self._sync_menu_actions)
        self.overflow_button = QToolButton(self)
        self.overflow_button.setObjectName("OverflowToolBarMenuButton")
        self.overflow_button.setText("...")
        self.overflow_button.setAccessibleName("More actions")
        self.overflow_button.setToolTip("More actions")
        self.overflow_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.overflow_button.setMenu(self.overflow_menu)
        self.overflow_button.setFixedSize(40, 32)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self.overflow_button.hide()
        self._layout.addWidget(self.overflow_button)

    def _apply_theme(self, _theme: dict | None = None) -> None:
        """Refresh overflow styling from the active application theme."""
        self.overflow_button.setStyleSheet(
            StyleHelper.get_overflow_button_style()
        )

    def add_button(
        self,
        button: QAbstractButton,
        *,
        priority: int = 0,
        pinned: bool = False,
        available: bool = True,
    ) -> None:
        """Add a button, with higher priorities retained for longer."""
        button.setParent(self)
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setMinimumWidth(button.sizeHint().width())
        button.installEventFilter(self)

        action = QAction(button.text(), self.overflow_menu)
        action.setToolTip(button.toolTip())
        action.setCheckable(button.isCheckable())
        action.setChecked(button.isChecked())
        menu_getter = getattr(button, "menu", None)
        if callable(menu_getter) and (button_menu := menu_getter()) is not None:
            action.setMenu(button_menu)
        action.triggered.connect(
            lambda checked=False, target=button: self._trigger_button(
                target, checked
            )
        )
        if button.isCheckable():
            button.toggled.connect(action.setChecked)
        self.overflow_menu.addAction(action)

        self._items.append(
            _ToolbarItem(button, action, priority, pinned, available)
        )
        self._layout.insertWidget(self._layout.count() - 1, button)
        self._update_overflow()

    def overflowed_buttons(self) -> list[QAbstractButton]:
        """Return buttons currently represented in the overflow menu."""
        return [
            item.button
            for item in self._items
            if item.available and item.button.isHidden()
        ]

    def set_button_available(
        self,
        button: QAbstractButton,
        available: bool,
    ) -> None:
        """Include or exclude a context-dependent action from the toolbar."""
        for item in self._items:
            if item.button is button:
                item.available = available
                self._update_overflow()
                return
        raise ValueError("Button is not managed by this toolbar")

    def refresh(self) -> None:
        """Recalculate which actions fit after external state changes."""
        self._update_overflow()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Advertise only enough width for pinned actions and overflow access."""
        widths = [
            item.button.minimumSizeHint().width()
            for item in self._items
            if item.pinned and item.available
        ]
        if self._items:
            widths.append(self.overflow_button.sizeHint().width())
        spacing = self._layout.spacing() * max(0, len(widths) - 1)
        height = max(
            [self.overflow_button.sizeHint().height()]
            + [item.button.sizeHint().height() for item in self._items]
        )
        return QSize(sum(widths) + spacing, height)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Move actions into or out of overflow when available width changes."""
        super().resizeEvent(event)
        self._update_overflow()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Resolve visibility once style-dependent size hints are available."""
        super().showEvent(event)
        self._update_overflow()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Rebalance when a managed button changes enabled or styled state."""
        if event.type() in (
            QEvent.Type.EnabledChange,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self._update_overflow()
        return super().eventFilter(watched, event)

    def _update_overflow(self) -> None:
        if not self._items:
            self.overflow_button.hide()
            return

        active_items = [item for item in self._items if item.available]
        for item in active_items:
            item.button.setMinimumWidth(item.button.sizeHint().width())

        spacing = self._layout.spacing()
        available = max(0, self.contentsRect().width())
        widths = {
            id(item): max(
                item.button.minimumWidth(),
                item.button.sizeHint().width(),
            )
            for item in active_items
        }
        visible = list(active_items)
        total = sum(widths[id(item)] for item in visible)
        total += spacing * max(0, len(visible) - 1)

        if total > available:
            available_for_buttons = max(
                0,
                available - self.overflow_button.sizeHint().width() - spacing,
            )
            candidates = sorted(
                (item for item in active_items if not item.pinned),
                key=lambda item: (
                    item.priority if item.button.isEnabled() else -10_000,
                    -self._items.index(item),
                ),
            )
            while candidates and total > available_for_buttons:
                item = candidates.pop(0)
                visible.remove(item)
                total -= widths[id(item)]
                if visible:
                    total -= spacing

        visible_ids = {id(item) for item in visible}
        for item in self._items:
            item.button.setVisible(id(item) in visible_ids)
        has_overflow = len(visible) != len(active_items)
        self.overflow_button.setVisible(has_overflow)
        self._sync_menu_actions()

    def _sync_menu_actions(self) -> None:
        for item in self._items:
            item.action.setText(item.button.text())
            item.action.setToolTip(item.button.toolTip())
            item.action.setEnabled(item.button.isEnabled())
            item.action.setChecked(item.button.isChecked())
            item.action.setVisible(item.available and item.button.isHidden())

    @staticmethod
    def _trigger_button(button: QAbstractButton, checked: bool) -> None:
        if isinstance(button, QCheckBox):
            button.setChecked(checked)
            return
        if button.isCheckable():
            button.setChecked(checked)
        button.click()
