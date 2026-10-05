"""Choice inputs that reserve closed-field wheel editing for explicit focus.

Ignored events propagate through Qt to the surrounding scroll surface. Popup
views retain Qt's normal scrolling and selection behavior.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QWidget


class ScrollSafeComboBox(QComboBox):
    """Choice input with closed-field wheel editing only while focused."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Keep click/Tab focus without acquiring focus through scrolling."""
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Pass unfocused navigation to the parent; preserve focused editing."""
        if not self.hasFocus() and not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)
