"""After-Effects / Figma-style scrubbable spin box.

Press-and-drag horizontally to increment the value by pixels × sensitivity;
release to commit.  A single click without drag still focuses the line edit
for keyboard entry.  Shift speeds up scrubbing; Ctrl slows it down.
"""

from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QSpinBox, QWidget

_SCRUB_THRESHOLD_PX = 3
_DEFAULT_SENSITIVITY = 1.0
_SHIFT_MULTIPLIER = 10.0
_CTRL_MULTIPLIER = 0.1


class NumericScrubberSpinBox(QSpinBox):
    """``QSpinBox`` with horizontal press-drag scrubbing.

    Scrubbing sensitivity scales with the spin box range so that a 0–65535
    range moves faster per pixel than a 0–100 range.  Shift accelerates
    (10×), Ctrl decelerates (0.1×) for fine control.

    Args:
        parent: Parent widget.
        sensitivity: Base pixels-per-value multiplier.  ``1.0`` maps
            roughly 1 px → one step scaled by ``(max - min) / 500``.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        sensitivity: float = _DEFAULT_SENSITIVITY,
    ) -> None:
        super().__init__(parent)
        self._sensitivity = sensitivity
        self._drag_origin: Optional[QPoint] = None
        self._drag_start_value: int = 0
        self._scrubbing: bool = False
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.pos()
            self._drag_start_value = self.value()
            self._scrubbing = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_origin is None:
            super().mouseMoveEvent(event)
            return
        dx = event.pos().x() - self._drag_origin.x()
        if not self._scrubbing and abs(dx) < _SCRUB_THRESHOLD_PX:
            return
        self._scrubbing = True
        step = self._scrub_step(event.modifiers())
        new_value = self._drag_start_value + int(round(dx * step))
        new_value = max(self.minimum(), min(self.maximum(), new_value))
        self.setValue(new_value)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._drag_origin is not None and not self._scrubbing:
            # Treat as a click → give the line edit focus for typing.
            self.selectAll()
            line_edit = self.lineEdit()
            if line_edit is not None:
                line_edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._drag_origin = None
        was_scrubbing = self._scrubbing
        self._scrubbing = False
        if was_scrubbing:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: object) -> None:  # type: ignore[override]
        QCursor.setPos(QCursor.pos())  # no-op; keeps API symmetric
        super().enterEvent(event)

    def _scrub_step(self, modifiers: Qt.KeyboardModifier) -> float:
        """Return pixels-per-value step scaled by range and modifiers."""
        span = max(1, self.maximum() - self.minimum())
        base = (span / 500.0) * self._sensitivity
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            base *= _SHIFT_MULTIPLIER
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            base *= _CTRL_MULTIPLIER
        return max(base, 1.0 / 100.0)
