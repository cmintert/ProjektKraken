"""Intentional multiline form actions with shared native button presentation."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QIcon, QPaintEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionToolButton,
    QStylePainter,
    QWidget,
)

from src.gui.utils.action_label_metrics import (
    ActionButtonStyleOption,
    ActionLabelGeometry,
    action_label_geometry,
    wrapping_text_flags,
)
from src.gui.widgets.standard_buttons import (
    LabelSizedToolButton,
    PrimaryButton,
    StandardButton,
)


class _ToolOption(QStyleOptionToolButton):
    """Typed runtime tool-option fields missing from generated PySide stubs."""

    rect: QRect
    text: str
    icon: QIcon


def _label_rect(button: QAbstractButton, size: QSize) -> QRect:
    rect = QRect(QPoint(), size)
    if isinstance(button, QPushButton):
        option = ActionButtonStyleOption()
        button.initStyleOption(option)
        option.rect = rect
        return button.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, button
        )
    geometry = action_label_geometry(button, size)
    text_size = button.fontMetrics().size(Qt.TextFlag.TextShowMnemonic, button.text())
    chrome = geometry.required - text_size
    icon_width = button.iconSize().width() + 4 if not button.icon().isNull() else 0
    left = max(0, (chrome.width() - icon_width) // 2)
    top = max(0, chrome.height() // 2)
    return rect.adjusted(left + icon_width, top, -left, -(chrome.height() - top))


def _geometry(
    button: QAbstractButton, size: QSize | None = None
) -> ActionLabelGeometry:
    available = _label_rect(button, button.size() if size is None else size)
    required = (
        button.fontMetrics()
        .boundingRect(
            QRect(0, 0, max(1, available.width()), 100000),
            int(
                wrapping_text_flags(
                    button.fontMetrics(), available.width(), button.text()
                )
            ),
            button.text(),
        )
        .size()
    )
    return ActionLabelGeometry(button.text(), required, available)


def _height(button: QAbstractButton, width: int, hint: QSize) -> int:
    geometry = _geometry(button, QSize(width, hint.height()))
    return geometry.required.height() + max(
        0, hint.height() - geometry.available.height()
    )


def _minimum(button: QAbstractButton, hint: QSize) -> QSize:
    rect = _label_rect(button, hint)
    widest = max(
        (
            button.fontMetrics().horizontalAdvance(character)
            for character in button.text()
        ),
        default=0,
    )
    return QSize(widest + hint.width() - rect.width(), hint.height())


def _configure(button: QAbstractButton) -> None:
    policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    button.setSizePolicy(policy)


def _paint_text(button: QAbstractButton, painter: QStylePainter) -> None:
    rect = _label_rect(button, button.size())
    flags = int(Qt.AlignmentFlag.AlignCenter) | int(
        wrapping_text_flags(button.fontMetrics(), rect.width(), button.text())
    )
    button.style().drawItemText(
        painter,
        rect,
        flags,
        button.palette(),
        button.isEnabled(),
        button.text(),
        QPalette.ColorRole.ButtonText,
    )


class WrappingPushButton(StandardButton):
    """A form/dialog action whose complete label wraps at the allocated width."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Retain native activation and accessible text while enabling wrapping."""
        super().__init__(text, parent)
        _configure(self)

    def label_geometry(self, size: QSize | None = None) -> ActionLabelGeometry:
        """Return the same content geometry used by painting."""
        return _geometry(self, size)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Expose multiline height to Qt layouts."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Reserve all wrapped lines and native style padding."""
        return _height(self, width, super().sizeHint())

    def sizeHint(self) -> QSize:  # noqa: N802
        """Keep natural width while accounting for the current wrapping height."""
        hint = super().sizeHint()
        return QSize(hint.width(), self.heightForWidth(self.width()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Allow wrapping at word boundaries rather than clipping."""
        return _minimum(self, super().sizeHint())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reserve every wrapped line after the parent chooses a width."""
        super().resizeEvent(event)
        required = self.heightForWidth(self.width())
        if self.minimumHeight() != required:
            self.setMinimumHeight(required)
            self.updateGeometry()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint native button states and the full multiline label."""
        option = ActionButtonStyleOption()
        self.initStyleOption(option)
        option.text = ""
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        _paint_text(self, painter)


class WrappingPrimaryButton(WrappingPushButton, PrimaryButton):
    """Primary semantic role with the shared complete multiline presentation."""


class WrappingToolButton(LabelSizedToolButton):
    """A disclosure/form tool with intentional multiline wording."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize native checked/keyboard behavior and responsive height."""
        super().__init__(parent)
        _configure(self)

    def label_geometry(self, size: QSize | None = None) -> ActionLabelGeometry:
        """Return the same content geometry used by painting."""
        return _geometry(self, size)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        """Expose multiline height to Qt layouts."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        """Reserve all wrapped lines plus icon/style decoration."""
        return _height(self, width, super().sizeHint())

    def sizeHint(self) -> QSize:  # noqa: N802
        """Keep natural width while accounting for the current wrapping height."""
        hint = super().sizeHint()
        return QSize(hint.width(), self.heightForWidth(self.width()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Permit wrapping while retaining complete words and icon spacing."""
        return _minimum(self, super().sizeHint())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reserve every wrapped line after the parent chooses a width."""
        super().resizeEvent(event)
        required = self.heightForWidth(self.width())
        if self.minimumHeight() != required:
            self.setMinimumHeight(required)
            self.updateGeometry()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint native tool states, the original icon and multiline text."""
        option = _ToolOption()
        self.initStyleOption(option)
        option.text = ""
        option.icon = QIcon()
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option)
        if not self.icon().isNull():
            rect = _label_rect(self, self.size())
            icon_rect = QRect(
                rect.left() - self.iconSize().width() - 4,
                rect.center().y() - self.iconSize().height() // 2,
                self.iconSize().width(),
                self.iconSize().height(),
            )
            self.icon().paint(painter, icon_rect)
        _paint_text(self, painter)
