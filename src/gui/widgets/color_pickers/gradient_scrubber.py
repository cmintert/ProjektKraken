"""Horizontal gradient strip with click/drag to pick continuous values.

Renders the active :class:`ColorMap`'s ramp so the user can see which
colour corresponds to which value before committing.  Hovering shows the
raw raster value and — when the colour map has a display mapping — its
real-world display string (e.g. ``23.5 °C``).
"""

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygon,
)
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.map_data_buffer import ColorMap, format_display_value

_BAR_HEIGHT = 22
_HANDLE_HEIGHT = 8
_TOTAL_HEIGHT = _BAR_HEIGHT + _HANDLE_HEIGHT + 2


class GradientScrubberWidget(QWidget):
    """Click/drag across a rendered gradient to pick a value.

    Args:
        parent: Parent widget.

    Signals:
        value_changed: Emitted during a drag with the current value.
        value_committed: Emitted on mouse release with the final value.
    """

    value_changed = Signal(int)
    value_committed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize a theme-aware gradient value scrubber."""
        super().__init__(parent)
        self._color_map: Optional[ColorMap] = None
        self._value_min: int = 0
        self._value_max: int = 65535
        self._value: int = 0
        self._dragging: bool = False
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_TOTAL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_color_map(self, color_map: Optional[ColorMap]) -> None:
        """Update the rendered gradient.  Pass ``None`` to clear."""
        self._color_map = color_map
        if color_map is not None:
            if color_map.stretch_min is not None:
                self._value_min = int(color_map.stretch_min)
            if color_map.stretch_max is not None:
                self._value_max = int(color_map.stretch_max)
        self.update()

    def set_range(self, min_value: int, max_value: int) -> None:
        """Explicitly override the value range (overrides stretch bounds)."""
        self._value_min = int(min_value)
        self._value_max = max(int(max_value), self._value_min + 1)
        self.update()

    def set_value(self, value: int) -> None:
        """Move the handle to *value* without emitting signals."""
        clamped = max(self._value_min, min(self._value_max, int(value)))
        if clamped == self._value:
            return
        self._value = clamped
        self.update()

    def value(self) -> int:
        """Return the current handle value."""
        return self._value

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        """Paint the active gradient, border, and value handle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        theme = ThemeManager().get_theme()
        border_col = QColor(theme.get("border", "#444"))
        handle_col = QColor(theme.get("primary", "#5C82FF"))
        surface_col = QColor(theme.get("surface", "#222"))

        bar_rect = QRect(0, 0, self.width(), _BAR_HEIGHT)

        # Render the gradient (fallback = flat surface color if no map)
        if self._color_map is not None and self._color_map.gradient_stops:
            grad = QLinearGradient(0, 0, self.width(), 0)
            for stop in self._color_map.gradient_stops:
                grad.setColorAt(
                    max(0.0, min(1.0, stop.position)), QColor(stop.color)
                )
            painter.setBrush(grad)
        elif self._color_map is not None and self._color_map.entries:
            # Palette fallback — horizontal bands per entry.
            painter.setBrush(surface_col)
        else:
            painter.setBrush(surface_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(bar_rect, 3, 3)

        if (
            self._color_map is not None
            and not self._color_map.gradient_stops
            and self._color_map.entries
        ):
            # Draw discrete bands for palette-type maps.
            entries = sorted(self._color_map.entries, key=lambda e: e.value)
            if entries:
                for idx, entry in enumerate(entries):
                    frac_start = idx / len(entries)
                    frac_end = (idx + 1) / len(entries)
                    band = QRect(
                        int(frac_start * self.width()),
                        1,
                        max(1, int((frac_end - frac_start) * self.width())),
                        _BAR_HEIGHT - 2,
                    )
                    painter.fillRect(band, QColor(entry.color))

        # Handle indicator
        x = self._value_to_x(self._value)
        handle = QPolygon(
            [
                QPoint(x, _BAR_HEIGHT - 1),
                QPoint(x - 6, _BAR_HEIGHT + _HANDLE_HEIGHT),
                QPoint(x + 6, _BAR_HEIGHT + _HANDLE_HEIGHT),
            ]
        )
        painter.setBrush(handle_col)
        painter.setPen(QPen(handle_col.darker(140), 1))
        painter.drawPolygon(handle)

        painter.end()

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Begin a left-button value scrub."""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._dragging = True
        self._set_from_pos(event.position().x())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Update the value and tooltip while the pointer moves."""
        if self._dragging:
            self._set_from_pos(event.position().x())
        self._maybe_show_tooltip(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Finish a scrub and emit the committed value."""
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.value_committed.emit(self._value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_from_pos(self, x: float) -> None:
        new_value = self._x_to_value(x)
        if new_value == self._value:
            return
        self._value = new_value
        self.update()
        self.value_changed.emit(new_value)

    def _maybe_show_tooltip(self, pos: QPoint) -> None:
        hover_value = self._x_to_value(pos.x())
        if self._color_map is not None and self._color_map.display_min is not None:
            try:
                display = format_display_value(self._color_map, hover_value)
                text = f"{hover_value}  →  {display}"
            except Exception:
                text = str(hover_value)
        else:
            text = str(hover_value)
        QToolTip.showText(self.mapToGlobal(pos), text, self)

    def _value_to_x(self, value: int) -> int:
        span = max(1, self._value_max - self._value_min)
        frac = (value - self._value_min) / span
        return int(frac * max(1, self.width() - 1))

    def _x_to_value(self, x: float) -> int:
        frac = max(0.0, min(1.0, x / max(1, self.width() - 1)))
        span = self._value_max - self._value_min
        return int(round(self._value_min + frac * span))
