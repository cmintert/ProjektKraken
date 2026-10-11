"""Native indicator choices with intentionally wrapping, accessible labels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QPaintEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QRadioButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QWidget,
)

from src.gui.utils.action_label_metrics import (
    ActionButtonStyleOption,
    ActionLabelGeometry,
    wrapping_text_flags,
)

if TYPE_CHECKING:

    class _ChoiceAPI(QAbstractButton):
        """Typing view of the native methods supplied by the next MRO class."""

        def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
            """Native choice constructor supplied by QCheckBox/QRadioButton."""

        def initStyleOption(self, option: QStyleOptionButton) -> None:  # noqa: N802
            """Native choice style option supplied by the concrete Qt class."""
else:
    _ChoiceAPI = object


class _WrappingChoice(_ChoiceAPI):
    """Presentation mixin; checked state and keyboard behavior remain native."""

    def _configure_wrapping(self) -> None:
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _label_rect(self, size: QSize) -> QRect:
        option = ActionButtonStyleOption()
        self.initStyleOption(option)
        option.rect = QRect(QPoint(), size)
        element = (
            QStyle.SubElement.SE_CheckBoxContents
            if isinstance(self, QCheckBox)
            else QStyle.SubElement.SE_RadioButtonContents
        )
        return self.style().subElementRect(element, option, self)

    def label_geometry(self, size: QSize | None = None) -> ActionLabelGeometry:
        """Expose precisely the same wrapping geometry used by painting."""
        rect = self._label_rect(self.size() if size is None else size)
        flags = int(wrapping_text_flags(self.fontMetrics(), rect.width(), self.text()))
        bounds = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, rect.width()), 100000), flags, self.text()
        )
        return ActionLabelGeometry(self.text(), bounds.size(), rect)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Declare height-dependent wrapping to Qt layouts."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Reserve every wrapped line and the native indicator."""
        geometry = self.label_geometry(QSize(width, super().sizeHint().height()))
        return max(
            super().sizeHint().height(),
            geometry.required.height()
            + max(0, super().sizeHint().height() - geometry.available.height()),
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        """Use natural width with sufficient height at the current allocation."""
        hint = super().sizeHint()
        hint.setHeight(self.heightForWidth(self.width()))
        return hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Allow readable word wrapping instead of forcing the complete row wide."""
        hint = super().sizeHint()
        rect = self._label_rect(hint)
        words = self.text()
        word_width = max(
            (self.fontMetrics().horizontalAdvance(word) for word in words), default=0
        )
        return QSize(
            hint.width() - rect.width() + word_width, self.fontMetrics().height()
        )

    def hitButton(self, point: QPoint) -> bool:  # noqa: N802
        """Keep the full indicator-and-label region as one click target."""
        return self.rect().contains(point)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Notify parent layouts when the number of wrapped lines changes."""
        super().resizeEvent(event)
        required = self.heightForWidth(self.width())
        if self.minimumHeight() != required:
            self.setMinimumHeight(required)
        self.updateGeometry()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw a native indicator and focus with the complete wrapped wording."""
        option = ActionButtonStyleOption()
        self.initStyleOption(option)
        option.text = ""
        painter = QStylePainter(self)
        control = (
            QStyle.ControlElement.CE_CheckBox
            if isinstance(self, QCheckBox)
            else QStyle.ControlElement.CE_RadioButton
        )
        painter.drawControl(control, option)
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) | int(
            wrapping_text_flags(
                self.fontMetrics(), self._label_rect(self.size()).width(), self.text()
            )
        )
        self.style().drawItemText(
            painter,
            self._label_rect(self.size()),
            flags,
            self.palette(),
            self.isEnabled(),
            self.text(),
            QPalette.ColorRole.WindowText,
        )


class WrappingCheckBox(_WrappingChoice, QCheckBox):
    """A checkbox whose entire label remains visible in constrained forms."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Initialize the native checkbox with wrapping layout participation."""
        super().__init__(text, parent)
        self._configure_wrapping()


class WrappingRadioButton(_WrappingChoice, QRadioButton):
    """A radio choice with the same label/layout contract as a checkbox."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Initialize the native radio with wrapping layout participation."""
        super().__init__(text, parent)
        self._configure_wrapping()
