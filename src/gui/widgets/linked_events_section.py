"""Visible Entity history controls and their existing chronological display."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMenu, QToolButton, QVBoxLayout, QWidget

from src.gui.utils.help_context import declare_inspection
from src.gui.utils.style_helper import StyleHelper
from src.gui.utils.theme_connections import connect_theme
from src.gui.widgets.menu_caret import PhosphorToolMenuButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.gui.widgets.timeline_display_widget import TimelineDisplayWidget


class LinkedEventsSection(QWidget):
    """Keep history creation, empty-state guidance and cards in one visible home."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build shared secondary actions without owning authoring decisions."""
        super().__init__(parent)
        declare_inspection(
            self,
            "src-gui-widgets-entity-editor-entityeditorwidget-build-timeline-section-self-timeline-checkbox|authoring.details|help-inspect-src-gui-widgets-entity-editor-entityeditorwidget-build-timeline-section-self-timeline-checkbox",
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("Linked events")
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        self.menu = QMenu(self)
        self.add_event_button = self._menu_button(
            "Add event…",
            "entity-timeline-add-event|authoring.details|help-lifecycle-event",
        )
        self.empty_action = self._menu_button(
            "Add the first event…",
            "entity-timeline-first-event|authoring.details|help-lifecycle-event",
        )
        self.action_bar = OverflowToolBar(self)
        self.action_bar.add_button(self.add_event_button, pinned=True)
        self.action_bar.add_button(self.empty_action, pinned=True)
        layout.addWidget(self.action_bar)
        self.display = TimelineDisplayWidget(self)
        layout.addWidget(self.display)
        self.set_has_events(False)
        self._apply_theme()
        connect_theme(self, self._apply_theme)

    def _apply_theme(self, _theme: dict | None = None) -> None:
        """Use the shared secondary role and native menu cue in every palette."""
        style = StyleHelper.get_tool_button_style() + StyleHelper.get_menu_caret_style()
        for button in (self.add_event_button, self.empty_action):
            button.setStyleSheet(style)

    def _menu_button(self, text: str, declaration: str) -> PhosphorToolMenuButton:
        """Give equivalent menu routes the same styling, focus and Help meaning."""
        button = declare_inspection(
            PhosphorToolMenuButton(self),
            declaration,
        )
        button.setText(text)
        button.setAccessibleName(text)
        button.setToolTip("Create a historical Event or link an existing Event")
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(self.menu)
        return button

    def set_has_events(self, has_events: bool) -> None:
        """Offer one creation action, with explicit guidance in an empty history."""
        self.action_bar.set_button_available(self.add_event_button, has_events)
        self.action_bar.set_button_available(self.empty_action, not has_events)
        self.setFocusProxy(self.add_event_button if has_events else self.empty_action)

    def picker_anchor(self) -> QWidget:
        """Return the actual menu access control, including narrow overflow."""
        if self.action_bar.overflow_button.isVisibleTo(self):
            return self.action_bar.overflow_button
        if self.add_event_button.isVisibleTo(self):
            return self.add_event_button
        return self.empty_action
