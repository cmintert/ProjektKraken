"""Horizontal strip of recently used values or colours.

Backed by :class:`ColorHistoryService` under a caller-chosen context key.
Click a tile to re-emit the stored value.
"""

import logging
from typing import Any, Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.color_pickers.color_history_service import ColorHistoryService

logger = logging.getLogger(__name__)

_THOUSANDS_ABBREVIATION_THRESHOLD = 1000

_TILE_PX = 22
_MAX_TILES = 12


class _ValueTile(QPushButton):
    """A single clickable tile rendering a colour or a numeric value."""

    def __init__(
        self,
        value: Any,
        is_color: bool,
        tooltip: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._is_color = is_color
        self.setFixedSize(_TILE_PX, _TILE_PX)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        theme = ThemeManager().get_theme()
        border = QColor(theme.get("border", "#555"))
        rect = self.rect().adjusted(1, 1, -1, -1)

        if self._is_color:
            painter.setBrush(QColor(str(self._value)))
            painter.setPen(border)
            painter.drawRoundedRect(rect, 3, 3)
        else:
            painter.setBrush(QColor(theme.get("surface", "#222")))
            painter.setPen(border)
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor(theme.get("text_main", "#eee")))
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                self._short_label(self._value),
            )
        painter.end()

    @staticmethod
    def _short_label(value: Any) -> str:
        try:
            v = int(value)
        except (TypeError, ValueError):
            return str(value)[:4]
        if v >= _THOUSANDS_ABBREVIATION_THRESHOLD:
            return f"{v // _THOUSANDS_ABBREVIATION_THRESHOLD}k"
        return str(v)


class RecentValuesStrip(QWidget):
    """Horizontal strip of the last N values / colours for a context.

    Args:
        context: History namespace (e.g. ``"raster.paint_value"``).
        is_color: ``True`` renders each tile as a colour swatch; ``False``
            renders each tile as a numeric label.
        parent: Parent widget.

    Signals:
        value_chosen: Emitted when the user clicks a tile.  Payload is the
            stored value (``int`` for numeric contexts, ``str`` hex for
            colour contexts).
    """

    value_chosen = Signal(object)

    def __init__(
        self,
        context: str,
        is_color: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize a recent-values strip for one settings context."""
        super().__init__(parent)
        self._context = context
        self._is_color = is_color
        self._formatter: Callable[[Any], str] = str

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._label = QLabel("Recent:")
        self._label.setStyleSheet(
            f"color: {ThemeManager().get_theme()['text_dim']}; font-size: 10px;"
        )
        layout.addWidget(self._label)
        self._tiles_container = QWidget()
        self._tiles_layout = QHBoxLayout(self._tiles_container)
        self._tiles_layout.setContentsMargins(0, 0, 0, 0)
        self._tiles_layout.setSpacing(2)
        layout.addWidget(self._tiles_container, 1)
        layout.addStretch()

        ColorHistoryService.instance().history_changed.connect(self._on_history_changed)
        self.refresh()

    def set_label_formatter(self, formatter: Callable[[Any], str]) -> None:
        """Override the tooltip formatter for numeric tiles.

        Args:
            formatter: Callable mapping value → human string for tooltips.
        """
        self._formatter = formatter
        self.refresh()

    def push(self, value: Any) -> None:
        """Record *value* as the most-recent pick and refresh the strip."""
        ColorHistoryService.instance().push(self._context, value)

    def refresh(self) -> None:
        """Rebuild the tile row from the history service."""
        while self._tiles_layout.count():
            item = self._tiles_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

        items: List[Any] = ColorHistoryService.instance().recent(
            self._context, _MAX_TILES
        )
        self._label.setVisible(bool(items))
        for value in items:
            tooltip = (
                str(value) if self._is_color else self._formatter(value)
            )
            tile = _ValueTile(value, self._is_color, tooltip)
            tile.clicked.connect(lambda _=False, v=value: self.value_chosen.emit(v))
            self._tiles_layout.addWidget(tile)

    def _on_history_changed(self, context: str) -> None:
        if context == self._context:
            self.refresh()
