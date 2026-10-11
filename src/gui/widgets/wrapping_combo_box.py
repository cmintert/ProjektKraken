"""A scroll-safe mode selector with complete, wrapping selected wording."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QPaintEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QWidget,
)

from src.gui.utils.action_label_metrics import ActionLabelGeometry, wrapping_text_flags
from src.gui.widgets.choice_inputs import ScrollSafeComboBox


class _ComboOption(QStyleOptionComboBox):
    """Typed view of runtime Qt option fields missing from generated stubs."""

    rect: QRect
    currentText: str


class WrappingComboBox(ScrollSafeComboBox):
    """Keep every selected mode/command word visible without shrinking fonts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize native popup/model/keyboard and safe-wheel behavior."""
        super().__init__(parent)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.currentTextChanged.connect(self.updateGeometry)

    def label_geometry(self, size: QSize | None = None) -> ActionLabelGeometry:
        """Expose the same label rectangle and wrapping used by painting."""
        option = _ComboOption()
        self.initStyleOption(option)
        if size is not None:
            option.rect = QRect(0, 0, size.width(), size.height())
        available = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            self,
        )
        text = self.currentText() or self.placeholderText()
        required = (
            self.fontMetrics()
            .boundingRect(
                QRect(0, 0, max(1, available.width()), 100000),
                int(
                    wrapping_text_flags(self.fontMetrics(), available.width(), text)
                    & ~Qt.TextFlag.TextShowMnemonic
                ),
                text,
            )
            .size()
            if text
            else QSize()
        )
        return ActionLabelGeometry(text, required, available)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Advertise selected-label wrapping to Qt layouts."""
        return not self.isEditable()

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Reserve complete selected wording and native input padding."""
        hint = super().sizeHint()
        geometry = self.label_geometry(QSize(width, hint.height()))
        return max(
            hint.height(),
            geometry.required.height() + hint.height() - geometry.available.height(),
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        """Include complete placeholder/selected wording in the natural hint."""
        hint = super().sizeHint()
        geometry = self.label_geometry(hint)
        width = (
            self.fontMetrics().horizontalAdvance(geometry.text)
            + hint.width()
            - geometry.available.width()
        )
        return QSize(max(hint.width(), width), self.heightForWidth(self.width()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Permit wrapping at complete word boundaries."""
        hint = super().sizeHint()
        geometry = self.label_geometry(hint)
        widest = max(
            (self.fontMetrics().horizontalAdvance(word) for word in geometry.text),
            default=0,
        )
        return QSize(widest + hint.width() - geometry.available.width(), hint.height())

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Notify layouts when font/style measurement changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep sufficient vertical space after a selected label wraps."""
        super().resizeEvent(event)
        required = self.heightForWidth(self.width())
        if not self.isEditable() and self.minimumHeight() != required:
            self.setMinimumHeight(required)
            self.updateGeometry()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint native input/arrow states and the full multiline mode label."""
        if self.isEditable():
            super().paintEvent(event)
            return
        option = _ComboOption()
        self.initStyleOption(option)
        option.currentText = ""
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        geometry = self.label_geometry()
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) | int(
            wrapping_text_flags(
                self.fontMetrics(), geometry.available.width(), geometry.text
            )
            & ~Qt.TextFlag.TextShowMnemonic
        )
        self.style().drawItemText(
            painter,
            geometry.available,
            flags,
            self.palette(),
            self.isEnabled(),
            geometry.text,
            QPalette.ColorRole.ButtonText,
        )
