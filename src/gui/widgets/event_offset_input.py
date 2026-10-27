"""Lossless lore-day input with local keyboard and focused-wheel ownership."""

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QValidator, QWheelEvent
from PySide6.QtWidgets import QAbstractSpinBox, QWidget

from src.core.temporal_expression import MAX_LORE_DAY


class EventOffsetInput(QAbstractSpinBox):
    """Keep the full float value independently of a fixed decimal-place limit."""

    valueChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Use the application's shared abstract-spinbox presentation."""
        super().__init__(parent)
        self._minimum, self._maximum = -MAX_LORE_DAY, MAX_LORE_DAY
        self._value = self._committed = 0.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lineEdit().setText("0")
        self.lineEdit().textEdited.connect(self._draft_changed)
        self.editingFinished.connect(self._commit)

    def value(self) -> float:
        """Return the complete numeric draft, including subnormal offsets."""
        return self._value

    def setValue(self, value: float) -> None:
        """Load a value without rounding its decimal places."""
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Offset must be finite")
        value = max(self._minimum, min(self._maximum, value))
        changed = self._value != value
        self._value = self._committed = value
        self.lineEdit().setText(self._format(value))
        self.lineEdit().setModified(False)
        if changed:
            self.valueChanged.emit(value)

    def setRange(self, minimum: float, maximum: float) -> None:
        """Set supported authoring limits without changing precision."""
        self._minimum, self._maximum = minimum, maximum
        self.setValue(self._value)

    @staticmethod
    def _format(value: float) -> str:
        return "0" if value == 0 else repr(value).removesuffix(".0")

    def validate(self, text: str, position: int) -> tuple[QValidator.State, str, int]:
        """Allow decimal/exponent drafts and reject non-finite coordinates."""
        try:
            value = float(text)
        except ValueError:
            state = (
                QValidator.State.Intermediate
                if all(character in "0123456789+-.eE" for character in text)
                else QValidator.State.Invalid
            )
        else:
            state = (
                QValidator.State.Acceptable
                if math.isfinite(value) and self._minimum <= value <= self._maximum
                else QValidator.State.Invalid
            )
        return state, text, position

    def fixup(self, _text: str) -> str:
        """Restore the last committed value when a local draft is unfinished."""
        return self._format(self._committed)

    def _draft_changed(self, text: str) -> None:
        if self.validate(text, len(text))[0] == QValidator.State.Acceptable:
            self._value = float(text)
            self.valueChanged.emit(self._value)

    def _commit(self) -> None:
        text = self.lineEdit().text()
        value = (
            float(text)
            if self.validate(text, len(text))[0] == QValidator.State.Acceptable
            else self._committed
        )
        self.setValue(value)

    def stepBy(self, steps: int) -> None:
        """Apply deliberate keyboard/spinner increments to the current value."""
        self._commit()
        self.setValue(self._value + steps)

    def stepEnabled(self) -> QAbstractSpinBox.StepEnabledFlag:
        """Expose only increments within the supported range."""
        flags = QAbstractSpinBox.StepEnabledFlag.StepNone
        if self._value < self._maximum:
            flags |= QAbstractSpinBox.StepEnabledFlag.StepUpEnabled
        if self._value > self._minimum:
            flags |= QAbstractSpinBox.StepEnabledFlag.StepDownEnabled
        return flags

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Enter commits locally; Escape cancels a local draft before its editor."""
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._commit()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self.lineEdit().isModified():
            self.setValue(self._committed)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Let an enclosing scroll area own wheel input unless explicitly focused."""
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
