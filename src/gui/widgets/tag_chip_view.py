"""Fast model/view components for the inspector tag editor."""

from __future__ import annotations

import hashlib
from typing import Any, cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from src.core.theme_manager import ThemeManager

ModelIndex = QModelIndex | QPersistentModelIndex


class TagListModel(QAbstractListModel):
    """Ordered, mutable tag list used by :class:`TagChipView`."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:
        """Return the number of root-level tags."""
        return 0 if parent.isValid() else len(self._tags)

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return tag text for display, tooltips, and consumers."""
        if not index.isValid() or not 0 <= index.row() < len(self._tags):
            return None
        tag = self._tags[index.row()]
        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
            Qt.ItemDataRole.UserRole,
        ):
            return tag
        return None

    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        """Expose enabled, selectable tag items."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_tags(self, tags: list[str]) -> None:
        """Replace all tags in one model reset."""
        self.beginResetModel()
        self._tags = list(tags)
        self.endResetModel()

    def add_tag(self, tag: str) -> None:
        """Append one tag without rebuilding existing items."""
        row = len(self._tags)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tags.append(tag)
        self.endInsertRows()

    def remove_tag(self, row: int) -> str | None:
        """Remove and return the tag at *row*."""
        if not 0 <= row < len(self._tags):
            return None
        self.beginRemoveRows(QModelIndex(), row, row)
        tag = self._tags.pop(row)
        self.endRemoveRows()
        return tag

    def tags(self) -> list[str]:
        """Return an isolated copy of the current tag order."""
        return list(self._tags)


class TagChipDelegate(QStyledItemDelegate):
    """Paint compact, theme-aware tag chips without per-item widgets."""

    remove_requested = Signal(int)

    CHIP_HEIGHT = 28
    MIN_WIDTH = 52
    MAX_WIDTH = 220
    HORIZONTAL_PADDING = 10
    CLOSE_WIDTH = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._base_color: str | None = None
        self._theme = ThemeManager().get_theme()
        self._hovered_close_row: int | None = None

    def set_theme(self, theme: dict[str, Any]) -> None:
        """Update cached theme tokens used during painting."""
        self._theme = theme

    def set_base_color(self, color: str | None) -> None:
        """Set the accent used for chip borders and tint."""
        self._base_color = color

    def set_hovered_close_row(self, row: int | None) -> None:
        """Track which close target should use its destructive hover color."""
        self._hovered_close_row = row

    def _accent(self) -> QColor:
        return QColor(
            self._base_color
            or self._theme.get("accent_secondary", "#4A90D9")
        )

    def color_for_tag(self, tag: str) -> QColor:
        """Return a stable, theme-adjusted color derived from the tag text."""
        digest = hashlib.sha256(tag.encode("utf-8")).digest()
        hue = int.from_bytes(digest[:2], byteorder="big") % 360
        surface = QColor(self._theme.get("surface", "#FFFFFF"))
        lightness = 160 if surface.lightness() < 128 else 100
        return QColor.fromHsl(hue, 185, lightness)

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: ModelIndex,
    ) -> QSize:
        """Return a bounded single-line chip size."""
        # PySide's stubs omit inherited QStyleOption members available at runtime.
        option_data = cast(Any, option)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        text_width = option_data.fontMetrics.horizontalAdvance(text)
        width = (
            text_width
            + (self.HORIZONTAL_PADDING * 2)
            + self.CLOSE_WIDTH
        )
        return QSize(
            max(self.MIN_WIDTH, min(width, self.MAX_WIDTH)),
            self.CHIP_HEIGHT,
        )

    def close_rect(self, option: QStyleOptionViewItem) -> QRect:
        """Return the close affordance hit target for an item option."""
        option_data = cast(Any, option)
        chip_rect = option_data.rect.adjusted(1, 1, -1, -1)
        return QRect(
            chip_rect.right() - self.CLOSE_WIDTH + 1,
            chip_rect.top(),
            self.CLOSE_WIDTH,
            chip_rect.height(),
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: ModelIndex,
    ) -> None:
        """Paint a flat chip, elided label, and close affordance."""
        option_data = cast(Any, option)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        enabled = bool(option_data.state & QStyle.StateFlag.State_Enabled)
        hovered = bool(option_data.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option_data.state & QStyle.StateFlag.State_Selected)
        focused = bool(option_data.state & QStyle.StateFlag.State_HasFocus)
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")

        accent = self.color_for_tag(text)
        fill = QColor(accent)
        fill.setAlpha(120 if selected else 96 if hovered else 72)
        if not enabled:
            fill.setAlpha(18)

        border = QColor(
            (
                self._base_color
                or self._theme.get("primary", accent.name())
            )
            if focused
            else accent
        )
        border.setAlpha(230 if selected or focused else 150)
        if not enabled:
            border = QColor(self._theme.get("border", "#808080"))

        chip_rect = option_data.rect.adjusted(1, 1, -1, -1)
        radius = chip_rect.height() / 2
        painter.setBrush(fill)
        painter.setPen(QPen(border, 1.5 if focused else 1.0))
        painter.drawRoundedRect(chip_rect, radius, radius)

        close_rect = self.close_rect(option)
        text_rect = chip_rect.adjusted(
            self.HORIZONTAL_PADDING,
            0,
            -(self.CLOSE_WIDTH + 2),
            0,
        )
        text_color = QColor(
            self._theme.get("text_main" if enabled else "text_dim", "#E0E0E0")
        )
        painter.setPen(text_color)
        elided = option_data.fontMetrics.elidedText(
            text,
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided,
        )

        close_hovered = enabled and self._hovered_close_row == index.row()
        close_color = QColor(
            self._theme.get(
                "destructive" if close_hovered else "text_dim",
                self._theme.get("error" if close_hovered else "border", "#808080"),
            )
        )
        painter.setPen(
            QPen(
                close_color,
                1.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        center = close_rect.center()
        offset = 3
        painter.drawLine(
            QPoint(center.x() - offset, center.y() - offset),
            QPoint(center.x() + offset, center.y() + offset),
        )
        painter.drawLine(
            QPoint(center.x() + offset, center.y() - offset),
            QPoint(center.x() - offset, center.y() + offset),
        )
        painter.restore()

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: ModelIndex,
    ) -> bool:
        """Remove a tag when its close affordance is released."""
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
            and self.close_rect(option).contains(event.position().toPoint())
            and bool(cast(Any, option).state & QStyle.StateFlag.State_Enabled)
        ):
            self.remove_requested.emit(index.row())
            return True
        return super().editorEvent(event, model, option, index)


class TagChipView(QListView):
    """Wrapping chip view that grows to three rows before scrolling."""

    remove_requested = Signal(int)
    MAX_VISIBLE_ROWS = 3
    SPACING = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._height_refresh_pending = False
        self._hovered_close_row: int | None = None
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSpacing(self.SPACING)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Install a model and track structural changes for height updates."""
        previous = self.model()
        if previous is not None:
            for signal in (
                previous.modelReset,
                previous.rowsInserted,
                previous.rowsRemoved,
            ):
                try:
                    signal.disconnect(self.schedule_height_refresh)
                except (RuntimeError, TypeError):
                    pass
        super().setModel(model)
        if model is None:
            self.schedule_height_refresh()
            return
        model.modelReset.connect(self.schedule_height_refresh)
        model.rowsInserted.connect(self.schedule_height_refresh)
        model.rowsRemoved.connect(self.schedule_height_refresh)
        self.schedule_height_refresh()

    @Slot()
    def schedule_height_refresh(self, *_args: Any) -> None:
        """Coalesce model/resize activity into one height calculation."""
        if self._height_refresh_pending:
            return
        self._height_refresh_pending = True
        QTimer.singleShot(0, self.refresh_height)

    def _row_count_for_width(self, width: int) -> int:
        model = self.model()
        delegate = self.itemDelegate()
        if model is None or delegate is None or model.rowCount() == 0:
            return 0

        available = max(width, TagChipDelegate.MIN_WIDTH)
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        rows = 1
        used = 0
        for row in range(model.rowCount()):
            item_width = delegate.sizeHint(option, model.index(row, 0)).width()
            needed = item_width if used == 0 else item_width + self.SPACING
            if used and used + needed > available:
                rows += 1
                used = item_width
            else:
                used += needed
        return rows

    @Slot()
    def refresh_height(self) -> None:
        """Fit one-to-three rows and enable scrolling only for overflow."""
        self._height_refresh_pending = False
        model = self.model()
        if model is None or model.rowCount() == 0:
            self.hide()
            self.setFixedHeight(0)
            return

        self.show()
        content_width = max(1, self.width() - (self.frameWidth() * 2))
        rows = self._row_count_for_width(content_width)
        visible_rows = min(rows, self.MAX_VISIBLE_ROWS)
        height = (
            visible_rows * TagChipDelegate.CHIP_HEIGHT
            + (visible_rows + 1) * self.SPACING
        )
        if self.height() != height:
            self.setFixedHeight(height)
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if rows > self.MAX_VISIBLE_ROWS
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(policy)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Repack rows when the available width changes."""
        super().resizeEvent(event)
        self.schedule_height_refresh()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Remove the selected chip with Delete."""
        if event.key() == Qt.Key.Key_Delete and self.isEnabled():
            index = self.currentIndex()
            if index.isValid():
                self.remove_requested.emit(index.row())
                event.accept()
                return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Show a pointing cursor only over a close affordance."""
        index = self.indexAt(event.position().toPoint())
        over_close = False
        delegate = self.itemDelegate()
        if index.isValid() and isinstance(delegate, TagChipDelegate):
            option = QStyleOptionViewItem()
            self.initViewItemOption(option)
            cast(Any, option).rect = self.visualRect(index)
            over_close = delegate.close_rect(option).contains(
                event.position().toPoint()
            )
        hovered_row = index.row() if over_close else None
        if hovered_row != self._hovered_close_row:
            previous_row = self._hovered_close_row
            self._hovered_close_row = hovered_row
            if isinstance(delegate, TagChipDelegate):
                delegate.set_hovered_close_row(hovered_row)
            if previous_row is not None:
                self.viewport().update(
                    self.visualRect(self.model().index(previous_row, 0))
                )
            if hovered_row is not None:
                self.viewport().update(self.visualRect(index))
        self.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor
            if over_close
            else Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Restore the default cursor when leaving the view."""
        previous_row = self._hovered_close_row
        self._hovered_close_row = None
        delegate = self.itemDelegate()
        if isinstance(delegate, TagChipDelegate):
            delegate.set_hovered_close_row(None)
        if previous_row is not None and self.model() is not None:
            self.viewport().update(
                self.visualRect(self.model().index(previous_row, 0))
            )
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)
