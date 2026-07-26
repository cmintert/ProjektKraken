"""Inline popover colour picker — the non-modal replacement for ``QColorDialog``.

Layout inspired by Krita's advanced colour selector and Figma's colour
popover:

* Saturation-value square (click/drag to pick S and V).
* Hue strip to the right (vertical rainbow).
* Hex entry with live round-trip preview.
* Recent-colours strip via :class:`RecentValuesStrip` on context
  ``"palette.color"``.

The popover closes when the user presses ``Esc``, clicks outside, or
accepts the hex input.  Callers typically connect to :pyattr:`color_chosen`
and/or :pyattr:`color_changed`.
"""

from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.color_pickers.recent_values_strip import RecentValuesStrip

_SV_WIDTH = 180
_SV_HEIGHT = 140
_HUE_WIDTH = 18


class _SVSquare(QWidget):
    """Saturation-value picker square for a fixed hue."""

    sv_changed = Signal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_SV_WIDTH, _SV_HEIGHT)
        self._hue: float = 0.0
        self._saturation: float = 1.0
        self._value: float = 1.0
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_hue(self, hue: float) -> None:
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def set_sv(self, s: float, v: float) -> None:
        self._saturation = max(0.0, min(1.0, s))
        self._value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Horizontal saturation: white → saturated hue colour
        hue_color = QColor.fromHsvF(self._hue, 1.0, 1.0)
        sat_grad = QLinearGradient(0, 0, self.width(), 0)
        sat_grad.setColorAt(0.0, QColor("white"))
        sat_grad.setColorAt(1.0, hue_color)
        painter.fillRect(self.rect(), sat_grad)

        # Vertical value: transparent → opaque black, multiplied on top
        val_grad = QLinearGradient(0, 0, 0, self.height())
        val_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        val_grad.setColorAt(1.0, QColor(0, 0, 0, 255))
        painter.fillRect(self.rect(), val_grad)

        # Crosshair
        x = int(self._saturation * (self.width() - 1))
        y = int((1.0 - self._value) * (self.height() - 1))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawEllipse(QPoint(x, y), 5, 5)
        painter.setPen(QPen(QColor("black"), 1))
        painter.drawEllipse(QPoint(x, y), 5, 5)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().x(), event.position().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().x(), event.position().y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _update_from_pos(self, x: float, y: float) -> None:
        self._saturation = max(0.0, min(1.0, x / max(1, self.width() - 1)))
        self._value = 1.0 - max(0.0, min(1.0, y / max(1, self.height() - 1)))
        self.update()
        self.sv_changed.emit(self._saturation, self._value)


class _HueStrip(QWidget):
    """Vertical rainbow hue picker."""

    hue_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_HUE_WIDTH, _SV_HEIGHT)
        self._hue: float = 0.0
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def set_hue(self, hue: float) -> None:
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        for i in range(7):
            t = i / 6.0
            grad.setColorAt(t, QColor.fromHsvF(t, 1.0, 1.0))
        painter.fillRect(self.rect(), grad)

        y = int(self._hue * (self.height() - 1))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawLine(0, y, self.width(), y)
        painter.setPen(QPen(QColor("black"), 1))
        painter.drawLine(0, y, self.width(), y)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _update_from_pos(self, y: float) -> None:
        self._hue = max(0.0, min(1.0, y / max(1, self.height() - 1)))
        self.update()
        self.hue_changed.emit(self._hue)


class InlineColorPickerPopover(QFrame):
    """Popover colour picker that replaces modal ``QColorDialog`` calls.

    The popover auto-closes on outside click, ``Esc``, or when the user
    presses Enter in the hex field.

    Usage::

        picker = InlineColorPickerPopover(parent, initial_color="#8f00ff")
        picker.color_chosen.connect(on_chosen)
        picker.show_at(button.mapToGlobal(button.rect().bottomLeft()))

    Signals:
        color_changed: Emitted live during picking.  Payload is hex.
        color_chosen: Emitted when the popover closes with a committed
            colour (Enter pressed or "OK" clicked).  Payload is hex.
    """

    color_changed = Signal(str)
    color_chosen = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        initial_color: str = "#808080",
        history_context: str = "palette.color",
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._history_context = history_context
        self._color = QColor(initial_color)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        body = QHBoxLayout()
        body.setSpacing(6)
        self._sv = _SVSquare()
        self._hue = _HueStrip()
        body.addWidget(self._sv)
        body.addWidget(self._hue)
        layout.addLayout(body)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(6)
        self._preview = QFrame()
        self._preview.setFixedSize(32, 24)
        self._preview.setFrameShape(QFrame.Shape.StyledPanel)
        preview_row.addWidget(self._preview)
        preview_row.addWidget(QLabel("Hex:"))
        self._hex_edit = QLineEdit()
        self._hex_edit.setFixedWidth(96)
        self._hex_edit.setPlaceholderText("#RRGGBB")
        preview_row.addWidget(self._hex_edit, 1)
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setFixedWidth(48)
        preview_row.addWidget(self._ok_btn)
        layout.addLayout(preview_row)

        self._recent = RecentValuesStrip(history_context, is_color=True, parent=self)
        self._recent.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self._recent)

        self._apply_theme()
        self._sync_from_color()

        # Wire signals
        self._sv.sv_changed.connect(self._on_sv_changed)
        self._hue.hue_changed.connect(self._on_hue_changed)
        self._hex_edit.editingFinished.connect(self._on_hex_committed)
        self._ok_btn.clicked.connect(self._commit_and_close)
        self._recent.value_chosen.connect(self._on_recent_chosen)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_at(self, global_pos: QPoint) -> None:
        """Show the popover anchored so its top-left is at *global_pos*."""
        # Clamp to screen
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.adjustSize()
            w, h = self.width(), self.height()
            x = min(max(geo.left(), global_pos.x()), geo.right() - w)
            y = min(max(geo.top(), global_pos.y()), geo.bottom() - h)
            self.move(QPoint(x, y))
        else:
            self.move(global_pos)
        self.show()
        self._sv.setFocus(Qt.FocusReason.PopupFocusReason)

    def color_hex(self) -> str:
        """Return the current colour as ``#RRGGBB``."""
        return self._color.name()

    def set_color(self, hex_color: str) -> None:
        """Update the displayed colour from a hex string."""
        new = QColor(hex_color)
        if not new.isValid():
            return
        self._color = new
        self._sync_from_color()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = ThemeManager().get_theme()
        self.setStyleSheet(
            f"QFrame {{ background-color: {theme.get('background', '#1e1e1e')}; "
            f"border: 1px solid {theme.get('border', '#555')}; "
            f"border-radius: 6px; }}"
            f"QLabel {{ color: {theme.get('text_main', '#eee')}; border: none; }}"
            f"QLineEdit {{ background-color: {theme.get('surface', '#222')}; "
            f"color: {theme.get('text_main', '#eee')}; "
            f"border: 1px solid {theme.get('border', '#555')}; "
            f"border-radius: 3px; padding: 2px 4px; }}"
            f"QPushButton {{ background-color: {theme.get('primary', '#5C82FF')}; "
            f"color: #111; border-radius: 3px; padding: 2px 6px; }}"
            f"QPushButton:hover {{ background-color: {theme.get('border', '#555')}; "
            f"color: {theme.get('text_main', '#eee')}; }}"
        )

    def _sync_from_color(self) -> None:
        h, s, v, _ = self._color.getHsvF()
        self._sv.set_hue(h if h >= 0 else 0.0)
        self._sv.set_sv(s, v)
        self._hue.set_hue(h if h >= 0 else 0.0)
        self._hex_edit.blockSignals(True)
        self._hex_edit.setText(self._color.name())
        self._hex_edit.blockSignals(False)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        theme = ThemeManager().get_theme()
        self._preview.setStyleSheet(
            f"QFrame {{ background-color: {self._color.name()}; "
            f"border: 1px solid {theme.get('border', '#555')}; "
            f"border-radius: 3px; }}"
        )

    def _emit_live(self) -> None:
        self._hex_edit.blockSignals(True)
        self._hex_edit.setText(self._color.name())
        self._hex_edit.blockSignals(False)
        self._refresh_preview()
        self.color_changed.emit(self._color.name())

    # Signal handlers

    def _on_sv_changed(self, s: float, v: float) -> None:
        h, _, _, _ = self._color.getHsvF()
        if h < 0:
            h = 0.0
        self._color = QColor.fromHsvF(h, s, v)
        self._emit_live()

    def _on_hue_changed(self, h: float) -> None:
        _, s, v, _ = self._color.getHsvF()
        self._color = QColor.fromHsvF(h, s, v)
        self._sv.set_hue(h)
        self._emit_live()

    def _on_hex_committed(self) -> None:
        text = self._hex_edit.text().strip()
        if not text.startswith("#"):
            text = f"#{text}"
        new = QColor(text)
        if new.isValid():
            self._color = new
            self._sync_from_color()
            self.color_changed.emit(self._color.name())

    def _on_recent_chosen(self, value: object) -> None:
        if isinstance(value, str):
            self.set_color(value)
            self.color_changed.emit(self._color.name())

    def _commit_and_close(self) -> None:
        hex_str = self._color.name()
        self._recent.push(hex_str)
        self.color_chosen.emit(hex_str)
        self.close()

    def keyPressEvent(self, event: object) -> None:  # type: ignore[override]
        key = getattr(event, "key", lambda: None)()
        if key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit_and_close()
            event.accept()
            return
        super().keyPressEvent(event)
