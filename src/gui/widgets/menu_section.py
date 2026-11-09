"""Visible, non-interactive section headings for native menus."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMenu, QWidgetAction

from src.gui.ui_constants import Spacing
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme


def add_menu_section(menu: QMenu, text: str) -> QWidgetAction:
    """Add a readable heading when the native style omits separator titles."""
    action = QWidgetAction(menu)
    action.setText(text)
    action.setProperty("menuSection", True)
    label = QLabel(text, menu)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    label.setContentsMargins(
        Spacing.WIDE, Spacing.STANDARD, Spacing.WIDE, Spacing.COMPACT
    )

    def apply_theme() -> None:
        label.setStyleSheet(
            StyleHelper.get_section_header_style()
            + StyleHelper.get_supporting_caption_style()
        )

    connect_theme(label, apply_theme)
    apply_theme()
    action.setDefaultWidget(label)
    action.setEnabled(False)
    menu.addAction(action)
    return action
