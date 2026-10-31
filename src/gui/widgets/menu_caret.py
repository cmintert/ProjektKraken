"""Local Phosphor caret presentation with unchanged native menu behavior."""

from typing import cast

from PySide6.QtCore import QRect
from PySide6.QtGui import QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from src.core.theme_manager import ThemeManager
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.standard_buttons import StandardButton
from src.gui.widgets.wrapping_buttons import WrappingToolButton


class _CaretPresentation:
    """Share only cue drawing; Qt retains all press and keyboard handling."""

    _caret: QIcon

    def _install_caret(self) -> None:
        widget = cast(QWidget, self)
        widget.setProperty("phosphorCaret", True)
        widget.setStyleSheet(StyleHelper.get_menu_caret_style())
        self._refresh_caret()
        connect_theme(self, self._refresh_caret)

    def _refresh_caret(self, _theme: dict | None = None) -> None:
        self._caret = load_icon(
            "default_assets/icons/ui_icons/caret-down.svg",
            ThemeManager().get_theme()["text_dim"],
        )
        cast(QWidget, self).update()

    def _paint_caret(self, painter: QPainter) -> None:
        widget = cast(QWidget, self)
        self._caret.paint(
            painter, QRect(widget.width() - 16, (widget.height() - 8) // 2, 8, 8)
        )


class PhosphorToolMenuButton(_CaretPresentation, WrappingToolButton):
    """Wrapping native tool-menu access with a small spaced Phosphor cue."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create native tool-menu access with the shared local cue."""
        super().__init__(parent)
        self._install_caret()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint native control states and the separated dropdown caret."""
        super().paintEvent(event)
        painter = QPainter(self)
        self._paint_caret(painter)


class PhosphorPushMenuButton(_CaretPresentation, StandardButton):
    """Standard push-menu access retaining existing secondary button chrome."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create standard push-menu access without changing its action role."""
        super().__init__(text, parent)
        self._install_caret()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint native control states and the separated dropdown caret."""
        super().paintEvent(event)
        painter = QPainter(self)
        self._paint_caret(painter)
