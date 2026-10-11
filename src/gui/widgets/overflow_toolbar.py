"""Responsive action row that moves lower-priority buttons into a menu."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, QTimer
from PySide6.QtGui import QAction, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QGridLayout,
    QLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.action_label_metrics import intrinsic_action_size
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.wrapping_buttons import WrappingToolButton


def _allocated_size(button: QAbstractButton, width: int) -> QSize:
    """Use intentional wrapping only after an individual control cannot fit."""
    hint = intrinsic_action_size(button)
    if callable(getattr(button, "label_geometry", None)) and button.hasHeightForWidth():
        allocated = max(
            button.minimumSizeHint().width(), min(hint.width(), max(1, width))
        )
        return QSize(allocated, button.heightForWidth(allocated))
    return hint


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
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._items: list[_ToolbarItem] = []
        self._updating = False
        self._refresh_pending = False
        self._rows_height = 0
        self._placement: tuple | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._queued_refresh)

        self._layout = QGridLayout(self)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self.overflow_menu = QMenu(self)
        self.overflow_menu.aboutToShow.connect(self._sync_menu_actions)
        self.overflow_button = WrappingToolButton(self)
        self.overflow_button.setObjectName("OverflowToolBarMenuButton")
        self.overflow_button.setText("More actions")
        self.overflow_button.setAccessibleName("More actions")
        self.overflow_button.setToolTip("More actions")
        self.overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.overflow_button.setMenu(self.overflow_menu)
        self._apply_theme()
        ThemeManager().theme_changed.connect(self._apply_theme)
        self.overflow_button.hide()
        self._layout.addWidget(self.overflow_button, 0, 0)

    def _apply_theme(self, _theme: dict | None = None) -> None:
        """Refresh overflow styling from the active application theme."""
        self.overflow_button.setStyleSheet(StyleHelper.get_overflow_button_style())

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
        button.setProperty("toolbarMinimumWidth", button.minimumWidth())
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setMinimumWidth(self._required_button_width(button))
        button.installEventFilter(self)

        action = QAction(self._action_title(button), self.overflow_menu)
        action.setToolTip(button.toolTip())
        action.setCheckable(button.isCheckable())
        action.setChecked(button.isChecked())
        menu_getter = getattr(button, "menu", None)
        if callable(menu_getter) and (button_menu := menu_getter()) is not None:
            action.setMenu(button_menu)
        action.triggered.connect(
            lambda checked=False, target=button: self._trigger_button(target, checked)
        )
        if button.isCheckable():
            button.toggled.connect(action.setChecked)
        self.overflow_menu.addAction(action)

        self._items.append(_ToolbarItem(button, action, priority, pinned, available))
        self._layout.addWidget(button, 0, len(self._items))
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
        """Allow primary actions and overflow access to occupy separate rows."""
        widths = [
            (
                item.button.minimumSizeHint().width()
                if callable(getattr(item.button, "label_geometry", None))
                else self._required_button_width(item.button)
            )
            for item in self._items
            if item.pinned and item.available
        ]
        if self._items:
            widths.append(self.overflow_button.minimumSizeHint().width())
        height = max(
            [intrinsic_action_size(self.overflow_button).height()]
            + [item.button.sizeHint().height() for item in self._items]
        )
        return QSize(max(widths, default=0), height)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Prefer the complete action row rather than a previous narrow state."""
        active = [item for item in self._items if item.available]
        width = sum(self._required_button_width(item.button) for item in active)
        width += self._layout.spacing() * max(0, len(active) - 1)
        return QSize(width, self.heightForWidth(self.width()))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Advertise pinned-action reflow to the parent layout."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Calculate rows without depending on a previous width allocation."""
        active = [item for item in self._items if item.available]
        sizes = [_allocated_size(item.button, width) for item in active]
        spacing = self._layout.spacing()
        if (
            sum(size.width() for size in sizes) + spacing * max(0, len(sizes) - 1)
            <= width
        ):
            return max((size.height() for size in sizes), default=0)
        pins = [_allocated_size(item.button, width) for item in active if item.pinned]
        pins.append(_allocated_size(self.overflow_button, width))
        used = total = row_height = 0
        for size in pins:
            if used and used + spacing + size.width() > width:
                total += row_height + spacing
                used = row_height = 0
            used += size.width() + (spacing if used else 0)
            row_height = max(row_height, size.height())
        return total + row_height

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Move actions into or out of overflow when available width changes."""
        super().resizeEvent(event)
        self._schedule_refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Resolve visibility once style-dependent size hints are available."""
        super().showEvent(event)
        self._schedule_refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Rebalance when a managed button changes enabled or styled state."""
        if event.type() in (
            QEvent.Type.EnabledChange,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.LayoutRequest,
        ):
            self._schedule_refresh()
        return super().eventFilter(watched, event)

    def _schedule_refresh(self) -> None:
        if not self._refresh_pending:
            self._refresh_pending = True
            self._refresh_timer.start(0)

    def _queued_refresh(self) -> None:
        self._refresh_pending = False
        self._update_overflow()

    def event(self, event: QEvent) -> bool:
        """Observe text-driven layout requests as well as explicit refreshes."""
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "_items"):
            self._schedule_refresh()
        return result

    def _update_overflow(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._rebalance()
        finally:
            self._updating = False

    def _rebalance(self) -> None:
        if not self._items:
            self.overflow_button.hide()
            return

        active_items = [item for item in self._items if item.available]
        available = max(0, self.contentsRect().width())
        menu_size = _allocated_size(self.overflow_button, available)
        self.overflow_button.setMinimumSize(menu_size)
        for item in active_items:
            size = _allocated_size(item.button, available)
            if callable(getattr(item.button, "label_geometry", None)):
                size.setWidth(item.button.minimumSizeHint().width())
            item.button.setMinimumSize(size)
        self.overflow_button.setMinimumWidth(
            self.overflow_button.minimumSizeHint().width()
        )

        spacing = self._layout.spacing()
        widths = {
            id(item): max(
                item.button.minimumWidth(),
                (
                    _allocated_size(item.button, available)
                    if item.pinned
                    else intrinsic_action_size(item.button)
                ).width(),
            )
            for item in active_items
        }
        visible = list(active_items)
        total = sum(widths[id(item)] for item in visible)
        total += spacing * max(0, len(visible) - 1)

        if total > available:
            available_for_buttons = max(
                0,
                available - menu_size.width() - spacing,
            )
            candidates = sorted(
                (item for item in active_items if not item.pinned),
                key=lambda item: (
                    isinstance(item.button, QCheckBox),
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

        focused = self.focusWidget()
        visible_ids = {id(item) for item in visible}
        for item in self._items:
            item.button.setVisible(id(item) in visible_ids)
        has_overflow = len(visible) != len(active_items)
        self.overflow_button.setVisible(has_overflow)
        self._position_buttons(visible, has_overflow, available)
        self._sync_menu_actions()
        if focused in self.overflowed_buttons() and has_overflow:
            self.overflow_button.setFocus()

    def _position_buttons(
        self, visible: list[_ToolbarItem], has_overflow: bool, available: int
    ) -> None:
        """Wrap pinned actions and menu access while retaining button instances."""
        focused = self.focusWidget()
        placement = (
            tuple(
                (id(item.button), item.button.minimumSize().toTuple())
                for item in visible
            ),
            has_overflow,
            available,
            self.overflow_button.sizeHint().toTuple(),
        )
        if placement == self._placement:
            return
        self._placement = placement
        for column in range(self._layout.columnCount()):
            self._layout.setColumnStretch(column, 0)
        for item in self._items:
            self._layout.removeWidget(item.button)
        self._layout.removeWidget(self.overflow_button)
        ordered = [
            item.button for item in visible if not isinstance(item.button, QCheckBox)
        ]
        if has_overflow:
            ordered.append(self.overflow_button)
        checkboxes = [
            item.button for item in visible if isinstance(item.button, QCheckBox)
        ]
        ordered.extend(checkboxes)
        row = column = used = height = row_height = 0
        for button in ordered:
            hint = _allocated_size(button, available)
            width = max(button.minimumWidth(), hint.width())
            if column and used + self._layout.spacing() + width > available:
                self._layout.setColumnStretch(column, 1)
                row += 1
                column = used = 0
                height += row_height + self._layout.spacing()
                row_height = 0
            if button in checkboxes and column:
                self._layout.setColumnStretch(column, 1)
                column += 1
            self._layout.addWidget(button, row, column)
            if column:
                used += self._layout.spacing()
            used += width
            row_height = max(row_height, hint.height(), button.minimumHeight())
            column += 1
        self._layout.setColumnStretch(column, 1 if not checkboxes else 0)
        total_height = height + row_height
        if total_height != self._rows_height:
            self._rows_height = total_height
            self.setMinimumHeight(total_height)
            self.updateGeometry()
        # If a focused secondary action entered overflow, keep its route focused.
        if focused in self.overflowed_buttons() and has_overflow:
            self.overflow_button.setFocus()

    def _required_button_width(self, button: QAbstractButton) -> int:
        """Return a DPI-safe width that preserves styled button labels."""
        return max(
            int(button.property("toolbarMinimumWidth") or 0),
            intrinsic_action_size(button).width(),
        )

    def _sync_menu_actions(self) -> None:
        for item in self._items:
            item.action.setText(self._action_title(item.button))
            item.action.setToolTip(item.button.toolTip())
            item.action.setEnabled(item.button.isEnabled())
            item.action.setChecked(item.button.isChecked())
            item.action.setFont(self.overflow_menu.font())
            item.action.setVisible(item.available and item.button.isHidden())

    @staticmethod
    def _action_title(button: QAbstractButton) -> str:
        """Use complete command names for compact/icon controls in the menu."""
        explicit = button.property("toolbarActionLabel")
        if explicit:
            return str(explicit)
        if isinstance(button, QToolButton) and not button.icon().isNull():
            return button.accessibleName() or button.text()
        return button.text() or button.accessibleName()

    @staticmethod
    def _trigger_button(button: QAbstractButton, checked: bool) -> None:
        # click() owns the original control's toggling and signal order.
        button.click()
