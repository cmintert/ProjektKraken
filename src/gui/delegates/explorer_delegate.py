"""Native Explorer rows with an explanatory caption for a filtered active item."""

from typing import Any, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from src.core.theme_manager import ThemeManager
from src.gui.models.explorer_filter_proxy import ExplorerFilterProxyModel
from src.gui.utils.style_helper import StyleHelper

PINNED_CAPTION = "Active item · Hidden by filters"


class ExplorerDelegate(QStyledItemDelegate):
    """Retain native row affordances and explain the active filter exception."""

    def _caption_rect(self, option: QStyleOptionViewItem) -> QRect:
        """Measure wrapping against the actual viewport and native checkbox."""
        opt = cast(Any, option)
        if opt.widget is not None:
            opt.rect.setWidth(opt.widget.viewport().width())
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        width = (
            style.subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, option, opt.widget
            ).width()
            - 4
        )
        return opt.fontMetrics.boundingRect(
            QRect(0, 0, max(1, width), 10000),
            Qt.TextFlag.TextWordWrap,
            PINNED_CAPTION,
        )

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Allow the complete caption to wrap without shrinking typography."""
        size = super().sizeHint(option, index)
        if index.data(ExplorerFilterProxyModel.PinnedRole):
            prepared = QStyleOptionViewItem(option)
            self.initStyleOption(prepared, index)
            size.setHeight(size.height() + self._caption_rect(prepared).height() + 4)
        return size

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Keep native selection, focus and checkbox geometry for the pinned row."""
        if not index.data(ExplorerFilterProxyModel.PinnedRole):
            super().paint(painter, option, index)
            self._paint_focus(painter, option)
            return
        prepared = QStyleOptionViewItem(option)
        self.initStyleOption(prepared, index)
        opt = cast(Any, prepared)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        title = opt.text
        opt.text = ""
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, prepared, painter, widget
        )
        text_rect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, prepared, widget
        ).adjusted(2, 2, -2, -2)
        if widget is not None:
            text_rect.setRight(min(text_rect.right(), widget.viewport().width() - 2))
        painter.save()
        painter.setClipRect(text_rect)
        painter.setFont(opt.font)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)
        group = QPalette.ColorGroup.Active if enabled else QPalette.ColorGroup.Disabled
        role = (
            QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )
        painter.setPen(opt.palette.color(group, role))
        title_rect = QRect(text_rect)
        title_rect.setHeight(opt.fontMetrics.height())
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            opt.fontMetrics.elidedText(
                title, Qt.TextElideMode.ElideRight, text_rect.width()
            ),
        )
        text_rect.setTop(title_rect.bottom() + 2)
        caption_color = (
            opt.palette.color(group, role)
            if selected or not enabled
            else QColor(ThemeManager().get_theme()["supporting_caption"])
        )
        painter.setPen(caption_color)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap, PINNED_CAPTION)
        painter.restore()
        self._paint_focus(painter, option)

    def _paint_focus(self, painter: QPainter, option: QStyleOptionViewItem) -> None:
        """Use the shared focus role over both ordinary and pinned rows."""
        opt = cast(Any, option)
        if (
            opt.state & QStyle.StateFlag.State_HasFocus
            and opt.state & QStyle.StateFlag.State_Enabled
        ):
            rect = opt.rect
            if opt.widget is not None:
                rect = rect.intersected(opt.widget.viewport().rect())
            StyleHelper.draw_item_focus_frame(painter, rect)
