"""Visual grid of clickable colour swatches with labels and value badges.

Used to replace text combos for discrete class selection in the raster
tools, and as the content of the canvas pop-up palette.  Responsive
flow-layout: tiles wrap to fill the available width.
"""

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.core.theme_manager import ThemeManager

_TILE_SIZE = 40
_TILE_GAP = 4
_LABEL_HEIGHT = 14
_BADGE_HEIGHT = 12


@dataclass
class Swatch:
    """One cell in a :class:`SwatchGridWidget`.

    Attributes:
        value: The raw payload (typically an ``int`` raster value).
        color: Hex colour string (``#RRGGBB`` or ``#RRGGBBAA``).
        label: Human-readable short name shown under the tile.
        hotkey: Optional 1-digit hotkey shown as a corner badge.
    """

    value: object
    color: str
    label: str = ""
    hotkey: Optional[int] = None


class SwatchGridWidget(QWidget):
    """Responsive grid of clickable swatches.

    The widget re-lays out tiles whenever its width changes, so it adapts
    to both dockable panels and narrow toolbars.  Up to nine swatches are
    selectable via the ``1``–``9`` number keys when the widget has focus.

    Signals:
        swatch_clicked: Emitted on left-click.  Payload is the
            :class:`Swatch.value` of the clicked tile.
        swatch_right_clicked: Emitted on right-click.
    """

    swatch_clicked = Signal(object)
    swatch_right_clicked = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the keyboard-accessible swatch grid."""
        super().__init__(parent)
        self._swatches: List[Swatch] = []
        self._active_value: object = None
        self._hover_index: int = -1
        self._tile_rects: List[QRect] = []
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_swatches(self, swatches: List[Swatch]) -> None:
        """Replace the current swatch set and repaint."""
        self._swatches = list(swatches)
        self._hover_index = -1
        self.updateGeometry()
        self.update()

    def set_active_value(self, value: object) -> None:
        """Highlight the swatch matching *value* (no emission)."""
        if value == self._active_value:
            return
        self._active_value = value
        self.update()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        """Return a compact size suitable for the current swatch layout."""
        if not self._swatches:
            return QSize(100, _TILE_SIZE + _LABEL_HEIGHT + _TILE_GAP)
        columns = max(1, self.width() // (_TILE_SIZE + _TILE_GAP))
        rows = (len(self._swatches) + columns - 1) // columns
        h = rows * (_TILE_SIZE + _LABEL_HEIGHT + _TILE_GAP) + _TILE_GAP
        return QSize(_TILE_SIZE + _TILE_GAP, h)

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        """Report that grid height depends on available width."""
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        """Calculate the wrapped grid height for a supplied width."""
        if not self._swatches:
            return _TILE_SIZE + _LABEL_HEIGHT + _TILE_GAP
        columns = max(1, width // (_TILE_SIZE + _TILE_GAP))
        rows = (len(self._swatches) + columns - 1) // columns
        return rows * (_TILE_SIZE + _LABEL_HEIGHT + _TILE_GAP) + _TILE_GAP

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint swatches, selection borders, hotkeys, and labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        theme = ThemeManager().get_theme()
        border_col = QColor(theme.get("border", "#444"))
        primary_col = QColor(theme.get("primary", "#5C82FF"))
        text_col = QColor(theme.get("text_main", "#eee"))
        dim_col = QColor(theme.get("text_dim", "#888"))
        surface_col = QColor(theme.get("surface", "#222"))

        self._tile_rects = self._compute_layout()
        fm = QFontMetrics(self.font())

        for i, swatch in enumerate(self._swatches):
            rect = self._tile_rects[i]
            tile_rect = QRect(rect.x(), rect.y(), _TILE_SIZE, _TILE_SIZE)

            # Tile body
            painter.setBrush(QColor(swatch.color) if swatch.color else surface_col)
            is_active = swatch.value == self._active_value
            is_hover = i == self._hover_index
            pen_width = 2 if is_active else 1
            pen_col = primary_col if is_active else border_col
            if is_hover and not is_active:
                pen_col = text_col
            painter.setPen(QPen(pen_col, pen_width))
            painter.drawRoundedRect(tile_rect, 4, 4)

            # Hotkey badge
            if swatch.hotkey is not None:
                badge_rect = QRect(
                    tile_rect.right() - _BADGE_HEIGHT - 2,
                    tile_rect.top() + 2,
                    _BADGE_HEIGHT,
                    _BADGE_HEIGHT,
                )
                painter.setBrush(surface_col)
                painter.setPen(QPen(border_col, 1))
                painter.drawRoundedRect(badge_rect, 2, 2)
                painter.setPen(text_col)
                font = painter.font()
                font.setPointSize(7)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    badge_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    str(swatch.hotkey),
                )
                font.setBold(False)
                font.setPointSize(9)
                painter.setFont(font)

            # Label under the tile
            if swatch.label:
                label_rect = QRect(
                    rect.x() - 4,
                    tile_rect.bottom() + 1,
                    _TILE_SIZE + 8,
                    _LABEL_HEIGHT,
                )
                painter.setPen(text_col if is_active else dim_col)
                elided = fm.elidedText(
                    swatch.label, Qt.TextElideMode.ElideRight, label_rect.width()
                )
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, elided)
        painter.end()

    def _compute_layout(self) -> List[QRect]:
        rects: List[QRect] = []
        if not self._swatches:
            return rects
        w = max(self.width(), _TILE_SIZE + _TILE_GAP)
        columns = max(1, w // (_TILE_SIZE + _TILE_GAP))
        x_start = _TILE_GAP // 2
        y = _TILE_GAP // 2
        for i in range(len(self._swatches)):
            col = i % columns
            row = i // columns
            x = x_start + col * (_TILE_SIZE + _TILE_GAP)
            y_tile = y + row * (_TILE_SIZE + _LABEL_HEIGHT + _TILE_GAP)
            rects.append(QRect(x, y_tile, _TILE_SIZE, _TILE_SIZE + _LABEL_HEIGHT))
        return rects

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Track the hovered swatch and update its tooltip."""
        pos = event.position().toPoint()
        new_hover = -1
        for i, rect in enumerate(self._tile_rects):
            tile_rect = QRect(rect.x(), rect.y(), _TILE_SIZE, _TILE_SIZE)
            if tile_rect.contains(pos):
                new_hover = i
                break
        if new_hover != self._hover_index:
            self._hover_index = new_hover
            self.update()
            if new_hover >= 0:
                s = self._swatches[new_hover]
                tip = s.label or ""
                if isinstance(s.value, (int, float)):
                    tip = f"{tip}  ({s.value})" if tip else str(s.value)
                self.setToolTip(tip)
            else:
                self.setToolTip("")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Emit left- or right-click selection for the hit swatch."""
        pos = event.position().toPoint()
        for i, rect in enumerate(self._tile_rects):
            tile_rect = QRect(rect.x(), rect.y(), _TILE_SIZE, _TILE_SIZE)
            if not tile_rect.contains(pos):
                continue
            swatch = self._swatches[i]
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            if event.button() == Qt.MouseButton.LeftButton:
                self.swatch_clicked.emit(swatch.value)
            elif event.button() == Qt.MouseButton.RightButton:
                self.swatch_right_clicked.emit(swatch.value)
            event.accept()
            return
        super().mousePressEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the pointer leaves the grid."""
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        """Activate numbered swatches with keys one through nine."""
        key = event.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(self._swatches):
                self.swatch_clicked.emit(self._swatches[idx].value)
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recalculate preferred geometry after a resize."""
        self.updateGeometry()
        super().resizeEvent(event)
