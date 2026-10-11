"""Choice inputs that reserve closed-field wheel editing for explicit focus.

Ignored events propagate through Qt to the surrounding scroll surface. Popup
views retain Qt's normal scrolling and selection behavior.
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QWidget


class ScrollSafeComboBox(QComboBox):
    """Choice input with closed-field wheel editing only while focused."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Keep click/Tab focus without acquiring focus through scrolling."""
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Reserve the native field height when effective font/style changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            if not callable(getattr(self, "label_geometry", None)):
                self.setMinimumHeight(self.sizeHint().height())
            self.updateGeometry()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Pass unfocused navigation to the parent; preserve focused editing."""
        if not self.hasFocus() and not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)
