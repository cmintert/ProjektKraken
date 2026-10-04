"""Numeric inputs that reserve wheel editing for an explicitly focused field.

Unfocused wheel events are ignored so Qt can deliver them to the enclosing
scroll surface. StrongFocus keeps click/Tab editing without wheel-acquired focus.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox, QWidget


class ScrollSafeSpinBox(QSpinBox):
    """Integer input with wheel editing only while focused."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Keep keyboard and click focus, excluding focus acquired by scrolling."""
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Pass navigation to the parent unless this field owns input focus."""
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class ScrollSafeDoubleSpinBox(QDoubleSpinBox):
    """Decimal input with wheel editing only while focused."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Keep keyboard and click focus, excluding focus acquired by scrolling."""
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Pass navigation to the parent unless this field owns input focus."""
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)
