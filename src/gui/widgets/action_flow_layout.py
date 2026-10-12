"""Content-sized action/filter groups that reflow without reconstructing controls."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)


class ActionFlowLayout(QLayout):
    """Keep natural label widths, wrapping groups in their existing focus order."""

    def __init__(
        self, parent: QWidget | None = None, *, uniform_height: bool = False
    ) -> None:
        """Create a standard compact responsive group."""
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._uniform_height = uniform_height
        self.setSpacing(4)
        if parent is not None:
            policy = parent.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
            policy.setHeightForWidth(True)
            parent.setSizePolicy(policy)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        """Retain an item without changing its widget or signal connections."""
        self._items.append(item)
        self.invalidate()

    def addWidget(self, widget: QWidget, stretch: int = 0) -> None:  # noqa: N802
        """Accept ordinary row call sites; flow owns width allocation."""
        if self._uniform_height:
            policy = widget.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
            widget.setSizePolicy(policy)
        super().addWidget(widget)

    def addLayout(self, layout: QLayout) -> None:  # noqa: N802
        """Support nested groups as indivisible flow items."""
        self.addChildLayout(layout)
        self.addItem(layout)

    def addStretch(self, stretch: int = 0) -> None:  # noqa: N802
        """Represent spacing without consuming a whole wrapped line."""
        self.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

    def count(self) -> int:
        """Return retained item count."""
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        """Return an item at a valid index."""
        return self._items[index] if 0 <= index < len(self._items) else None

    # Qt returns None for an invalid index; PySide's takeAt stub omits None.
    def takeAt(self, index: int) -> QLayoutItem | None:  # type: ignore[override]  # noqa: N802
        """Remove an item while preserving widget ownership."""
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Advertise responsive row height to containing Qt layouts."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Calculate the height required at the supplied allocation."""
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def minimumSize(self) -> QSize:  # noqa: N802
        """Allow groups to stack rather than summing their minimum widths."""
        hint = QSize()
        for item in self._items:
            if not item.isEmpty():
                hint = hint.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        hint += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        if self.geometry().width() > 0:
            hint.setHeight(
                max(hint.height(), self.heightForWidth(self.geometry().width()))
            )
        return hint

    def sizeHint(self) -> QSize:  # noqa: N802
        """Expose current reflow height and the unconstrained natural width."""
        width = sum(
            item.sizeHint().width() for item in self._items if not item.isEmpty()
        )
        width += self.spacing() * max(0, self.count() - 1)
        parent = self.parentWidget()
        allocated = parent.width() if parent is not None else width
        return QSize(width, self.heightForWidth(allocated))

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        """Position original controls in readable rows."""
        super().setGeometry(rect)
        height = self._arrange(rect, apply=True)
        parent = self.parentWidget()
        if (
            parent is not None
            and parent.layout() is self
            and parent.minimumHeight() != height
        ):
            parent.setMinimumHeight(height)
            parent.updateGeometry()

    def _arrange(self, rect: QRect, *, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x, y = area.x(), area.y()
        row_height = 0
        uniform_height = (
            self._shared_height(area.width()) if self._uniform_height else 0
        )
        placements: list[tuple[QLayoutItem, QRect]] = []
        for item in self._items:
            if item.isEmpty() or item.spacerItem() is not None:
                continue
            widget = item.widget()
            hint = item.sizeHint().expandedTo(item.minimumSize())
            if widget is not None and widget.objectName() == "OverflowToolBar":
                # Reserve a readable menu route, then let the toolbar overflow
                # secondary commands within the remaining row allocation.
                from src.gui.utils.action_label_metrics import intrinsic_action_size

                menu = widget.findChild(QAbstractButton, "OverflowToolBarMenuButton")
                minimum = (
                    intrinsic_action_size(menu).width()
                    if menu is not None
                    else widget.minimumSizeHint().width()
                )
                remaining = area.right() + 1 - x
                if x > area.x() and remaining < min(area.width(), minimum):
                    x = area.x()
                    y += row_height + self.spacing()
                    row_height = 0
                    remaining = area.width()
                hint.setWidth(min(hint.width(), remaining))
            if widget is not None and widget.hasHeightForWidth():
                hint.setWidth(
                    max(item.minimumSize().width(), min(hint.width(), area.width()))
                )
            if x > area.x() and x + hint.width() > area.right() + 1:
                x = area.x()
                y += row_height + self.spacing()
                row_height = 0
            if widget is not None and widget.hasHeightForWidth():
                hint.setHeight(
                    max(
                        item.minimumSize().height(), widget.heightForWidth(hint.width())
                    )
                )
            elif item.hasHeightForWidth():
                hint.setHeight(item.heightForWidth(hint.width()))
            hint.setHeight(max(hint.height(), uniform_height))
            if apply:
                placements.append((item, QRect(x, y, hint.width(), hint.height())))
            x += hint.width() + self.spacing()
            row_height = max(row_height, hint.height())
        if apply:
            self._place_rows(placements, area)
        return y + row_height - rect.y() + margins.bottom()

    def _shared_height(self, width: int) -> int:
        """Reserve the tallest complete label for every control in this group."""
        height = 0
        for item in self._items:
            if item.isEmpty() or item.spacerItem() is not None:
                continue
            hint = item.sizeHint().expandedTo(item.minimumSize())
            widget = item.widget()
            if widget is not None and widget.hasHeightForWidth():
                allocated = max(item.minimumSize().width(), min(hint.width(), width))
                hint.setHeight(
                    max(item.minimumSize().height(), widget.heightForWidth(allocated))
                )
            height = max(height, hint.height())
        return height

    def _place_rows(
        self, placements: list[tuple[QLayoutItem, QRect]], area: QRect
    ) -> None:
        """Align each reflowed row without changing control or keyboard order."""
        right_edges: dict[int, int] = {}
        for _, rect in placements:
            right_edges[rect.y()] = max(
                right_edges.get(rect.y(), rect.right()), rect.right()
            )
        for item, rect in placements:
            offset = (
                area.right() - right_edges[rect.y()]
                if self.alignment() & Qt.AlignmentFlag.AlignRight
                else 0
            )
            item.setGeometry(rect.translated(offset, 0))
