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

    def __init__(self, parent: QWidget = None, margin: int = -1, spacing: int = -1) -> None:
        """Create a FlowLayout with optional parent and spacing.

        Parameters:
            parent: Optional parent widget.
            margin: If not -1, set all contents margins to this value.
            spacing: Layout spacing.
        """
        super().__init__(parent)
        if margin != -1:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        """Adds an item to the layout."""
        self._items.append(item)

    def count(self) -> int:
        """
        Return the number of items managed by the layout.

        Returns:
            count (int): Number of QLayoutItem objects currently stored in the layout.
        """
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem:
        """
        Retrieve the layout item at the specified index.

        Returns:
            The QLayoutItem at the given index, or `None` if the index is out of range.
        """
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        """Remove and return the layout item at the specified index.

        Parameters:
            index (int): Position of the item to remove.

        Returns:
            QLayoutItem or None: The removed item or None.
        """
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        """
        Indicates that the layout may expand in the horizontal direction.

        Returns:
            Qt.Orientation: `Qt.Orientation.Horizontal` when the layout can expand.
        """
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self) -> bool:
        """
        Indicates whether the layout's preferred height depends on its width.

        Returns:
            bool: `True` if the layout's height depends on its width, `False` otherwise.
        """
        return True

    def heightForWidth(self, width: int) -> int:
        """
        Compute the preferred height for a given available width.

        Parameters:
            width (int): Available width in pixels that constrains the layout.

        Returns:
            int: Preferred height required to arrange all items within the given width.
        """
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        """
        Apply the given rectangle to the layout and arrange child items within it.

        Parameters:
            rect (QRect): The bounding rectangle to assign to the layout.
        """
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        """
        Provide the layout's preferred size.

        Returns:
            QSize: Preferred size of the layout.
        """
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """Compute the minimum QSize required to contain all items."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """Arrange layout items, wrapping when width is exceeded.

        Parameters:
            rect (QRect): Bounding rectangle.
            test_only (bool): If True, compute height without setting geometries.

        Returns:
            int: Total height consumed.
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
