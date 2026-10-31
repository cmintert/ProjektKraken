"""Shared menu and overflow control for timeline dependency visibility."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu, QToolButton, QWidget

from src.core.timeline_visibility import (
    DEPENDENCY_VISIBILITY_LABELS,
    DependencyVisibility,
)
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.menu_caret import PhosphorToolMenuButton

_HELP = (
    "timeline.show-dependencies|timeline.viewing|"
    "help-inspect-timeline-show-dependencies"
)


class DependencyVisibilityButton(PhosphorToolMenuButton):
    """Expose one mode choice through the same toolbar and overflow menu."""

    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build exclusive actions with stable Help and accessible labels."""
        super().__init__(parent)
        self.mode = DependencyVisibility.SELECTED
        self.mode_menu = declare_inspection(QMenu(self), _HELP)
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_actions = {}
        for mode, label in DEPENDENCY_VISIBILITY_LABELS.items():
            action = declare_inspection(self.mode_menu.addAction(label), _HELP)
            action.setCheckable(True)
            action.setData(mode.value)
            self.mode_group.addAction(action)
            self.mode_actions[mode] = action
        self.mode_group.triggered.connect(
            lambda action: self.mode_changed.emit(str(action.data()))
        )
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setMenu(self.mode_menu)
        self.set_mode(self.mode)
        self._apply_theme()
        connect_theme(self, self._apply_theme)

    def set_mode(self, mode: DependencyVisibility) -> None:
        """Render a choice without emitting another preference mutation."""
        self.mode = mode
        self.mode_actions[mode].setChecked(True)
        label = f"Dependencies: {mode.value.title()}"
        self.setText(label)
        self.setAccessibleName(label)
        self.setToolTip(
            "Choose All, Selected, Show dependency trail, or Off. "
            "Selected shows direct connections; Trail shows the whole connected "
            "network. Select an event to use Selected or Trail."
        )

    def _apply_theme(self, _theme: dict | None = None) -> None:
        """Use shared secondary controls and menu caret roles in every palette."""
        self.setStyleSheet(
            StyleHelper.get_tool_button_style() + StyleHelper.get_menu_caret_style()
        )
