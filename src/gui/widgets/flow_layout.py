"""Flow Layout Module.

Provides a custom QLayout that arranges widgets horizontally and wraps them to the next
line if they exceed the available width.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """A layout that wraps widgets horizontally.

    Adapted from official Qt Flow Layout example for PySide6.
    """

    def __init__(self, parent: QWidget = None, margin: int = -1, spacing: int = -1):
        """Initializes the FlowLayout.

        Args:
            parent: The parent widget.
            margin: The margin around the layout.
            spacing: The spacing between widgets.
        """
        super().__init__(parent)
        if margin != -1:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[QLayoutItem] = []

    def __del__(self):
        """Cleans up the layout items."""
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem):
        """Adds an item to the layout."""
        self._items.append(item)

    def count(self) -> int:
        """Returns the number of items in the layout."""
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem:
        """Returns the item at the given index."""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        """Removes and returns the item at the given index."""
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        """Returns the expanding directions."""
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self) -> bool:
        """Returns True as the height depends on the width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Returns the preferred height for the given width."""
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect):
        """Sets the geometry of the layout."""
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        """Returns the preferred size of the layout."""
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """Returns the minimum size of the layout."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """Calculates the positions of the items.

        Args:
            rect: The rectangle to layout the items in.
            test_only: If True, only calculates the height without moving items.

        Returns:
            int: The total height of the layout.
        """
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            space_x = self.spacing()
            if space_x == -1 and widget is not None:
                style = widget.style()
                space_x = style.layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal
                )

            space_y = self.spacing()
            if space_y == -1 and widget is not None:
                style = widget.style()
                space_y = style.layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical
                )

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom
