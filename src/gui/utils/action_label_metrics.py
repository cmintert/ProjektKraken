"""Style-aware action label geometry shared by layouts and verification.

This module measures presentation only. It never changes wording or repairs a
widget at runtime. Verification must also check ancestor clipping and rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QPushButton,
    QRadioButton,
    QStyle,
    QStyleOptionButton,
    QToolButton,
)


class ActionButtonStyleOption(QStyleOptionButton):
    """Typed view of runtime Qt fields omitted from PySide's generated stubs."""

    rect: QRect
    text: str
    icon: QIcon
    iconSize: QSize


@dataclass(frozen=True)
class ActionLabelGeometry:
    """Required label bounds and the style's available label rectangle."""

    text: str
    required: QSize
    available: QRect

    @property
    def fits(self) -> bool:
        """Whether both dimensions preserve the complete label."""
        return (
            self.available.width() >= self.required.width()
            and self.available.height() >= self.required.height()
        )


def wrapping_text_flags(metrics: QFontMetrics, width: int, text: str) -> Qt.TextFlag:
    """Prefer words; retain every glyph when one word exceeds the allocation."""
    longest = max((metrics.horizontalAdvance(word) for word in text.split()), default=0)
    wrapping = (
        Qt.TextFlag.TextWrapAnywhere if longest > width else Qt.TextFlag.TextWordWrap
    )
    return wrapping | Qt.TextFlag.TextShowMnemonic


def action_label_geometry(
    button: QAbstractButton, size: QSize | None = None
) -> ActionLabelGeometry:
    """Measure an ordinary Qt button using its effective font and style.

    Tool buttons use the style's complete content size because Qt exposes no
    tool-button text subelement. Icon-only tools are audited for accessible
    names separately. Subclasses with custom paint need their own adapter.
    """
    rect = (
        QRect(button.rect())
        if size is None
        else QRect(0, 0, size.width(), size.height())
    )
    flags = Qt.TextFlag.TextShowMnemonic
    required = (
        button.fontMetrics().size(flags, button.text()) if button.text() else QSize()
    )
    if isinstance(button, QToolButton):
        # Use the native tool implementation's complete styled hint. Calling
        # CT_ToolButton again adds common-style chrome already replaced by QSS,
        # producing false height failures on styled menu buttons.
        styled = QToolButton.sizeHint(button)
        # This adapter compares the whole control with the complete styled
        # content requirement, including arrow/menu decoration and QSS padding.
        return ActionLabelGeometry(button.text(), styled, rect)
    option = ActionButtonStyleOption()
    option.initFrom(button)
    option.rect = rect
    option.text = button.text()
    option.icon = button.icon()
    option.iconSize = button.iconSize()
    if isinstance(button, QCheckBox):
        element = QStyle.SubElement.SE_CheckBoxContents
    elif isinstance(button, QRadioButton):
        element = QStyle.SubElement.SE_RadioButtonContents
    elif isinstance(button, QPushButton):
        button.initStyleOption(option)
        option.rect = rect
        element = QStyle.SubElement.SE_PushButtonContents
    else:
        raise TypeError(f"No action-label adapter for {type(button).__name__}")
    available = button.style().subElementRect(element, option, button)
    if isinstance(button, QPushButton):
        if not button.icon().isNull():
            # Qt's button painter separates icon and text by four logical px.
            available.setWidth(available.width() - button.iconSize().width() - 4)
        if button.menu() is not None:
            available.setWidth(
                available.width()
                - button.style().pixelMetric(
                    QStyle.PixelMetric.PM_MenuButtonIndicator, option, button
                )
            )
    return ActionLabelGeometry(button.text(), required, available)


def intrinsic_action_size(button: QAbstractButton) -> QSize:
    """Return a style-aware hint without inheriting previously raised minima."""
    button.ensurePolished()
    hint = button.sizeHint()
    geometry = action_label_geometry(button, hint)
    return QSize(
        hint.width() + max(0, geometry.required.width() - geometry.available.width()),
        hint.height()
        + max(0, geometry.required.height() - geometry.available.height()),
    )
