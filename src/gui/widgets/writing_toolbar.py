"""Presentation of existing WikiTextEdit commands in three compact tiers."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSizePolicy, QToolButton

from src.core.theme_manager import ThemeManager
from src.gui.utils.help_context import declare_inspection
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.menu_caret import PhosphorToolMenuButton as WritingMenuButton
from src.gui.widgets.overflow_toolbar import OverflowToolBar


class WritingToolbarPresentation(QObject):
    """Arrange existing commands without owning editing or navigation behavior."""

    def __init__(self, owner: Any) -> None:
        """Build a menu row and a compact formatting row for the live editor."""
        super().__init__(owner)
        self.owner = owner
        view = owner.editor
        self._menus: dict[str, QMenu] = {}
        self._menu_buttons: list[QToolButton] = []
        self.menu_row = OverflowToolBar(owner, overflow_button_type=WritingMenuButton)
        self.menu_row.setObjectName("WritingMenuRow")
        owner.layout().addWidget(self.menu_row)
        self._name_actions()
        self._view_actions()
        self._build_menus()

        self.heading_button = declare_inspection(
            WritingMenuButton(owner.toolbar),
            "src-gui-widgets-writing-toolbar-writingtoolbarpresentation-init-self-heading-button|writing.edit|help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-init-self-heading-button",
        )
        self.heading_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.heading_button.setText("Headings")
        self.heading_button.setAccessibleName("Headings")
        self.heading_button.setToolTip("Choose a heading style")
        self.heading_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.heading_button.setMenu(self._menus["Headings"])
        owner.toolbar.addWidget(self.heading_button)
        owner.toolbar.addSeparator()
        for action in (view.action_bold, view.action_italic, view.action_body):
            owner.toolbar.addAction(action)
        owner.toolbar.setObjectName("WritingFormattingToolbar")
        owner.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        owner.toolbar.setIconSize(QSize(18, 18))
        for action in (view.action_bold, view.action_italic, view.action_body):
            button = owner.toolbar.widgetForAction(action)
            if button is not None:
                button.setAccessibleName(action.text())

        self._format_actions = (view.action_bold, view.action_italic, view.action_body)
        self._format_widths: dict[QAction, int] = {}
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._reflow_formatting)
        owner.toolbar.installEventFilter(self)
        self.apply_theme()
        self._reflow_timer.start(0)
        ThemeManager().theme_changed.connect(self.apply_theme)

    def _name_actions(self) -> None:
        """Use accurate labels while preserving the actions and their handlers."""
        view = self.owner.editor
        for action, title in (
            (view.action_bold, "Bold"),
            (view.action_italic, "Italic"),
            (view.action_h1, "Heading 1"),
            (view.action_h2, "Heading 2"),
            (view.action_h3, "Heading 3"),
            (view.action_body, "Clear Formatting"),
        ):
            action.setText(title)
            action.setToolTip(f"{title} ({action.shortcut().toString()})")
        view.action_body.setToolTip(
            view.action_body.toolTip() + "\nRemove heading, bold and italic formatting"
        )

    def _view_actions(self) -> None:
        """Keep the wrapper's mode, contents and spelling commands intact."""
        owner = self.owner
        owner.action_toggle_mode = declare_inspection(
            QAction("Markdown source", owner),
            "src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-mode|writing.edit|help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-mode",
        )
        owner.action_toggle_mode.setToolTip(
            "Toggle between Rendered HTML and Markdown Source"
        )
        owner.action_toggle_mode.triggered.connect(owner._toggle_view_mode)
        owner.action_toggle_toc = declare_inspection(
            QAction("Table of contents", owner),
            "src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-toc|writing.edit|help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-toggle-toc",
        )
        owner.action_toggle_toc.setToolTip("Toggle Table of Contents sidebar")
        owner.action_toggle_toc.triggered.connect(owner._toggle_toc)
        owner.action_spell_check = declare_inspection(
            QAction("Spell & grammar checking", owner),
            "src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-spell-check|writing.edit|help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-view-actions-owner-action-spell-check",
        )
        owner.action_spell_check.setCheckable(True)
        owner.action_spell_check.setToolTip(
            "Enable or disable spell and grammar checking"
        )
        owner.action_spell_check.triggered.connect(owner._set_spell_check_enabled)
        owner.action_spell_check.setChecked(
            cast(bool, QSettings().value("SpellCheck/enabled", False, type=bool))
        )

    def _build_menus(self) -> None:
        """Expose existing commands through conventional, labeled menus."""
        owner = self.owner
        view = owner.editor
        for title in ("Edit", "Insert", "Format", "View", "Tools", "Headings"):
            self._menus[title] = QMenu(title, owner)
        self._menus["Edit"].aboutToShow.connect(self._refresh_edit_menu)
        for action in (view.action_h1, view.action_h2, view.action_h3):
            self._menus["Headings"].addAction(action)
        format_menu = self._menus["Format"]
        format_menu.addMenu(self._menus["Headings"])
        for action in (view.action_bold, view.action_italic, view.action_body):
            format_menu.addAction(action)
        self._menus["View"].addAction(owner.action_toggle_mode)
        self._menus["View"].addAction(owner.action_toggle_toc)
        self._menus["Tools"].addAction(owner.action_spell_check)
        for title in ("Edit", "Insert", "Format", "View", "Tools"):
            button = declare_inspection(
                WritingMenuButton(owner),
                "src-gui-widgets-writing-toolbar-writingtoolbarpresentation-build-menus-button|writing.edit|help-inspect-src-gui-widgets-writing-toolbar-writingtoolbarpresentation-build-menus-button",
            )
            button.setText(title)
            button.setAccessibleName(title)
            button.setToolTip(f"{title} menu")
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            button.setMenu(self._menus[title])
            self.menu_row.add_button(button)
            self._menu_buttons.append(button)

    def _refresh_edit_menu(self) -> None:
        """Use QTextEdit's own commands and current enabled/disabled state."""
        menu = self._menus["Edit"]
        menu.clear()
        standard_menu = self.owner.editor.createStandardContextMenu()
        for action in standard_menu.actions():
            standard_menu.removeAction(action)
            action.setParent(menu)
            menu.addAction(action)
        standard_menu.deleteLater()

    def install_link_actions(self) -> None:
        """Share the live link actions after the wrapper has created them."""
        owner = self.owner
        menu = self._menus["Insert"]
        owner.action_link_entry.setToolTip("Link to an existing entry")
        for action in (
            owner.action_link_entry,
            owner.action_open_link,
            owner.action_peek_link,
        ):
            menu.addAction(action)
        self.apply_theme()

    def apply_theme(self, _theme: dict | None = None) -> None:
        """Refresh shared action roles and locally bundled Phosphor icons."""
        theme = ThemeManager().get_theme()
        control_style = StyleHelper.get_writing_editor_control_style()
        self.menu_row.setStyleSheet(StyleHelper.get_writing_editor_row_style())
        self.owner.toolbar.setStyleSheet(
            StyleHelper.get_editor_toolbar_style() + control_style
        )
        for button in self._menu_buttons:
            button.setStyleSheet(control_style)
        self.menu_row.overflow_button.setStyleSheet(control_style)
        if hasattr(self.owner, "link_toolbar"):
            self.owner.link_toolbar.setStyleSheet(
                StyleHelper.get_writing_editor_row_style()
            )
            for button in self.owner.link_toolbar.findChildren(QToolButton):
                button.setStyleSheet(control_style)
            self.owner.link_toolbar.overflow_button.setStyleSheet(control_style)
        for action, filename in (
            (self.owner.editor.action_bold, "text-b.svg"),
            (self.owner.editor.action_italic, "text-italic.svg"),
            (self.owner.editor.action_body, "eraser.svg"),
        ):
            action.setIcon(
                load_icon(
                    f"default_assets/icons/ui_icons/{filename}", theme["text_main"]
                )
            )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Recalculate compact command placement after geometry/style changes."""
        if watched is self.owner.toolbar and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self._reflow_timer.start(0)
        return super().eventFilter(watched, event)

    def _reflow_formatting(self) -> None:
        """Remove only strip presentations; full labeled menus retain actions."""
        toolbar = self.owner.toolbar
        for action in self._format_actions:
            button = toolbar.widgetForAction(action)
            if button is not None:
                self._format_widths[action] = button.sizeHint().width()
        remaining = max(
            0,
            toolbar.contentsRect().width()
            - self.heading_button.sizeHint().width()
            - 24,
        )
        desired = []
        for action in self._format_actions:
            width = self._format_widths.get(action, 40) + 4
            if width <= remaining:
                desired.append(action)
                remaining -= width
        current = [
            action for action in toolbar.actions() if action in self._format_actions
        ]
        if current == desired:
            return
        for action in current:
            toolbar.removeAction(action)
        for action in desired:
            toolbar.addAction(action)
            button = toolbar.widgetForAction(action)
            if button is not None:
                button.setAccessibleName(action.text())
