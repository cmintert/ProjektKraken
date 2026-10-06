"""Longform Editor Widget Module (Orchestrator).

Provides a split-view interface for editing longform documents:
- Left: Outline tree view (from outline.py)
- Right: Continuous document view (from content.py)
"""

import html
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.shortcut_manager import ShortcutManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.empty_state_widget import EmptyStateWidget
from src.gui.widgets.longform.content import LongformContentWidget
from src.gui.widgets.longform.membership import LongformMembershipWidget
from src.gui.widgets.longform.outline import LongformOutlineWidget
from src.gui.widgets.overflow_toolbar import OverflowToolBar
from src.services.web_service_manager import WebServiceManager

logger = logging.getLogger(__name__)


class LongformEditorWidget(QWidget):
    """Main longform editor widget with split view.

    Left panel: Outline tree
    Right panel: Continuous document view
    """

    # Signals
    promote_requested = Signal(str, str, dict)  # table, id, old_meta
    demote_requested = Signal(str, str, dict)  # table, id, old_meta
    delete_requested = Signal(str, str)  # table, id - completely delete the item
    remove_requested = Signal(str, str, dict)
    show_membership_requested = Signal()
    add_requested = Signal(str, str)
    move_up_requested = Signal(str, str, dict)  # table, id, old_meta
    move_down_requested = Signal(str, str, dict)  # table, id, old_meta
    refresh_requested = Signal()
    export_requested = Signal()
    export_vault_requested = Signal()  # For Obsidian-compatible vault export
    item_selected = Signal(str, str)  # table, id
    item_moved = Signal(str, str, dict, dict)  # table, id, old_meta, new_meta
    link_clicked = Signal(str)
    show_filter_dialog_requested = Signal()
    clear_filters_requested = Signal()

    def __init__(
        self, parent: Optional[QWidget] = None, db_path: Optional[str] = None
    ) -> None:
        """Initialize the longform editor."""
        super().__init__(parent)
        self.db_path = db_path
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Store current sequence
        self._sequence: list[dict[str, Any]] = []

        # Web Service Manager
        self.web_manager = WebServiceManager(self)
        self.web_manager.status_changed.connect(self._on_server_status_changed)
        self.web_manager.error_occurred.connect(self._on_server_error)

        # Setup UI
        self._setup_ui()
        self._setup_shortcuts()
        ThemeManager().theme_changed.connect(self._apply_action_theme)
        self._apply_action_theme()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop server on close."""
        self.web_manager.stop_server()
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Theme for icons
        theme = ThemeManager().get_theme()
        icon_color = theme["text_main"]

        # Toolbar
        toolbar = self.action_toolbar = OverflowToolBar(self)
        self.btn_add = QPushButton("Add content…")
        self.btn_add.clicked.connect(self.show_membership_requested.emit)
        toolbar.add_button(self.btn_add, priority=100)
        self.btn_outline_actions = QPushButton("Outline actions")
        self.btn_outline_actions.setToolTip(
            "Select an outline item to arrange or remove it"
        )
        self.outline_actions_menu = QMenu(self)
        self.outline_actions_menu.aboutToShow.connect(self._prepare_outline_actions)
        self.btn_outline_actions.setMenu(self.outline_actions_menu)
        toolbar.add_button(self.btn_outline_actions, priority=90)

        # Refresh Button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        toolbar.add_button(self.btn_refresh)

        # Filter Button
        btn_filter = QPushButton("Filter...")
        btn_filter.clicked.connect(self.show_filter_dialog_requested.emit)
        toolbar.add_button(btn_filter)

        # Clear Filters Button
        btn_clear_filters = QPushButton("Clear Filters")
        btn_clear_filters.clicked.connect(self.clear_filters_requested.emit)
        toolbar.add_button(btn_clear_filters)

        # Export Button
        btn_export = QPushButton("Export to Markdown")
        btn_export.clicked.connect(self.export_requested.emit)
        toolbar.add_button(btn_export)

        # Export as Vault Button (Obsidian-compatible)
        btn_export_vault = QPushButton("Export as Vault")
        btn_export_vault.setToolTip(
            "Export each entity and event as separate Obsidian-compatible .md files"
        )
        btn_export_vault.clicked.connect(self.export_vault_requested.emit)
        toolbar.add_button(btn_export_vault)

        # Local publishing is the safe, frictionless default. LAN sharing is a
        # separate action because it changes the server's network exposure.
        self.btn_publish = QPushButton("Publish Locally")
        self.btn_publish.setCheckable(True)
        self.btn_publish.clicked.connect(self._toggle_publish)
        toolbar.add_button(self.btn_publish)

        self.btn_share_lan = QPushButton("Share on LAN...")
        self.btn_share_lan.setCheckable(True)
        self.btn_share_lan.clicked.connect(self._toggle_lan_share)
        toolbar.add_button(self.btn_share_lan)

        self.url_label = QLabel("")
        self.url_label.setStyleSheet(StyleHelper.get_wiki_link_style())
        self.url_label.setOpenExternalLinks(True)
        self.url_label.hide()

        self.access_code_label = QLabel("")
        self.access_code_label.hide()

        # Find Button (Discoverability - Far Right)
        self.btn_find = QPushButton("Find")
        self.btn_find.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "search.svg"),
                color=icon_color,
            )
        )
        self.btn_find.setToolTip(f"Find Text ({ShortcutManager.FIND.sequence})")
        self.btn_find.clicked.connect(self._toggle_search)
        toolbar.add_button(self.btn_find, priority=80)

        layout.addWidget(toolbar)
        self.url_label.setWordWrap(True)
        layout.addWidget(self.url_label)
        layout.addWidget(self.access_code_label)
        self.membership = LongformMembershipWidget(self)
        self.membership.add_requested.connect(self.add_requested.emit)
        self.membership.cancelled.connect(self._hide_membership)
        layout.addWidget(self.membership)

        # Search Bar (Hidden by default)
        self.search_widget = QWidget()
        search_layout = QHBoxLayout(self.search_widget)
        StyleHelper.apply_form_spacing(search_layout)
        search_layout.setContentsMargins(10, 5, 10, 5)

        search_label = QLabel("Find:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find text...")
        self.search_input.returnPressed.connect(self._perform_search_next)

        # Icons
        btn_prev = QPushButton("Previous")
        btn_prev.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "arrow_up.svg"),
                color=icon_color,
            )
        )
        btn_prev.setToolTip("Find Previous (Shift+Enter)")
        btn_prev.clicked.connect(self._perform_search_prev)

        btn_next = QPushButton("Next")
        btn_next.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "arrow_down.svg"),
                color=icon_color,
            )
        )
        btn_next.setToolTip("Find Next (Enter)")
        btn_next.clicked.connect(self._perform_search_next)

        btn_close = QPushButton("Close")
        btn_close.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "close.svg"),
                color=icon_color,
            )
        )
        btn_close.setToolTip("Close Search (Esc)")
        btn_close.clicked.connect(self._hide_search)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_prev)
        search_layout.addWidget(btn_next)
        search_layout.addWidget(btn_close)

        self.search_widget.setVisible(False)
        layout.addWidget(self.search_widget)

        # Splitter with outline and content
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Outline
        self.outline = LongformOutlineWidget()
        self.outline.item_selected.connect(self._on_item_selected)
        self.outline.item_promoted.connect(self.promote_requested.emit)
        self.outline.item_demoted.connect(self.demote_requested.emit)
        self.outline.item_moved.connect(self.item_moved.emit)
        self.outline.item_deleted.connect(self.delete_requested.emit)
        self.outline.item_removed.connect(self.remove_requested.emit)
        self.outline.itemSelectionChanged.connect(self._update_outline_actions)
        self.outline.item_move_up.connect(self.move_up_requested.emit)
        self.outline.item_move_down.connect(self.move_down_requested.emit)

        # Right: Content view
        self.content = LongformContentWidget()
        self.content.link_clicked.connect(self.link_clicked.emit)
        self.content.item_selected.connect(self._on_content_selected)

        self._splitter.addWidget(self.outline)
        self._splitter.addWidget(self.content)

        # Set initial sizes (30% outline, 70% content)
        self._splitter.setSizes([300, 700])

        layout.addWidget(self._splitter, 1)  # Stretch factor 1

        # Empty State
        self.empty_state = EmptyStateWidget(
            title="No Content Available",
            description=(
                "World content appears automatically.\n"
                "Add content… restores removed entries."
            ),
        )
        self.btn_empty_add = self.empty_state.add_action(
            "Add content…", self.show_membership_requested.emit, primary=True
        )
        self.btn_empty_clear = self.empty_state.add_action(
            "Clear Filters", self.clear_filters_requested.emit
        )
        layout.addWidget(self.empty_state, 1)

        # Status bar
        self.status_label = QLabel("No items loaded")
        layout.addWidget(self.status_label, 0)  # Stretch factor 0
        self._update_outline_actions()

    def _prepare_outline_actions(self) -> None:
        self.outline.populate_actions_menu(self.outline_actions_menu)

    def _update_outline_actions(self) -> None:
        self.btn_outline_actions.setEnabled(bool(self.outline.selectedItems()))

    def _hide_membership(self) -> None:
        self.membership.hide()
        self.btn_add.setFocus()

    def _apply_action_theme(self, _theme: dict | None = None) -> None:
        """Use shared neutral controls and refresh icon colors on theme changes."""
        theme = ThemeManager().get_theme()
        self.setStyleSheet(
            f"LongformEditorWidget {{ background-color: {theme['app_bg']}; }}"
        )
        self.btn_empty_add.setStyleSheet(StyleHelper.get_primary_button_style())
        self.btn_empty_clear.setStyleSheet(StyleHelper.get_secondary_button_style())
        self.empty_state._apply_title_style()
        self.empty_state._description_label.setStyleSheet(
            StyleHelper.get_empty_state_style()
        )
        for button in self.findChildren(QPushButton):
            if button.parent() in (self.action_toolbar, self.search_widget):
                button.setStyleSheet(StyleHelper.get_secondary_button_style())
        self.url_label.setStyleSheet(StyleHelper.get_wiki_link_style())
        self.btn_find.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "search.svg"),
                color=theme["text_main"],
            )
        )

    @Slot(str, str)
    def _on_content_selected(self, table: str, row_id: str) -> None:
        """Keep card and outline action targets consistent without double navigation."""
        iterator = QTreeWidgetItemIterator(self.outline)
        while item := iterator.value():
            metadata = self.outline._get_item_metadata(item)
            if metadata is not None and metadata[:2] == (table, row_id):
                with QSignalBlocker(self.outline):
                    self.outline.setCurrentItem(item)
                self._update_outline_actions()
                break
            iterator += 1
        self.item_selected.emit(table, row_id)

    def load_sequence(self, sequence: List[Dict[str, Any]]) -> None:
        """Load a longform sequence into the editor.

        Args:
            sequence: Ordered list from build_longform_sequence.

        """
        same_content = sequence == self._sequence
        cursor = self.content.textCursor()
        scroll = self.content.verticalScrollBar().value()
        self._sequence = sequence
        with QSignalBlocker(self.outline):
            self.outline.load_sequence(sequence)
        self._update_outline_actions()
        self.content.setSearchPaths(
            [str(Path(self.db_path).resolve().parent)] if self.db_path else []
        )
        if not same_content:
            self.content.load_content(sequence)
        else:
            self.content.setTextCursor(cursor)
            self.content.verticalScrollBar().setValue(scroll)

        # Toggle empty state
        if not sequence:
            self._splitter.hide()
            self.empty_state.show()
        else:
            self._splitter.show()
            self.empty_state.hide()

        # Update status
        count = len(sequence)
        self.status_label.setText(f"{count} item(s) in document")

    @Slot(str, str)
    def _on_item_selected(self, table: str, row_id: str) -> None:
        """Handle item selection in outline.

        Args:
            table: Table name.
            row_id: Row ID.

        """
        # Find index in sequence
        for idx, item in enumerate(self._sequence):
            if item["table"] == table and item["id"] == row_id:
                self.content.scroll_to_item(idx)
                break

        # Emit signal to notify parent (MainWindow)
        self.item_selected.emit(table, row_id)

    def get_current_selection(self) -> Optional[tuple]:
        """Get currently selected item.

        Returns:
            Tuple of (table, id) or None.

        """
        if items := self.outline.selectedItems():
            item = items[0]
            if meta_data := self.outline._item_meta.get(id(item)):
                table, row_id, _ = meta_data
                return (table, row_id)
        return None

    def minimumSizeHint(self) -> QSize:
        """Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable longform editor.

        """
        return QSize(400, 300)  # Width for split view, height for toolbar + content

    def sizeHint(self) -> QSize:
        """Preferred size for the longform editor.

        Returns:
            QSize: Comfortable working size for editing longform documents.

        """
        return QSize(600, 700)  # Comfortable size for split view

    @Slot(bool)
    def _toggle_publish(self, checked: bool) -> None:
        """Handle localhost-only publishing."""
        if checked:
            if self.web_manager.is_running:
                self.web_manager.stop_server()
            self.web_manager.start_server(db_path=self.db_path, share_on_lan=False)
        elif self.web_manager.is_running and not self.web_manager.is_lan_shared:
            self.web_manager.stop_server()

    @Slot(bool)
    def _toggle_lan_share(self, checked: bool) -> None:
        """Start or stop explicit authenticated LAN sharing."""
        if not checked:
            if self.web_manager.is_lan_shared:
                self.web_manager.stop_server()
            return

        answer = QMessageBox.question(
            self,
            "Share Longform on LAN",
            "Other devices on this local network can open the published longform "
            "after entering the generated access code. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.btn_share_lan.setChecked(False)
            return

        if self.web_manager.is_running:
            self.web_manager.stop_server()
        self.web_manager.start_server(db_path=self.db_path, share_on_lan=True)

    @Slot(bool, str)
    def _on_server_status_changed(self, is_running: bool, url: str) -> None:
        """Update UI based on server status."""
        is_lan_shared = is_running and self.web_manager.is_lan_shared
        self.url_label.setVisible(is_running)
        self.access_code_label.setVisible(is_lan_shared)
        self.btn_publish.setChecked(is_running and not is_lan_shared)
        self.btn_share_lan.setChecked(is_lan_shared)
        if is_running:
            self.btn_publish.setText(
                "Stop Local Publishing" if not is_lan_shared else "Publish Locally"
            )
            self.btn_share_lan.setText(
                "Stop LAN Sharing" if is_lan_shared else "Share on LAN..."
            )
            # Create a clickable link
            escaped_url = html.escape(url, quote=True)
            self.url_label.setText(f'<a href="{escaped_url}">{escaped_url}</a>')
            self.url_label.setToolTip("Click to open in browser")
            access_code = self.web_manager.access_code
            if access_code:
                formatted_code = f"{access_code[:4]} {access_code[4:]}"
                self.access_code_label.setText(f"Access code: {formatted_code}")
            else:
                self.access_code_label.setText("")
        else:
            self.btn_publish.setText("Publish Locally")
            self.btn_share_lan.setText("Share on LAN...")
            self.url_label.setText("")
            self.access_code_label.setText("")
        self.action_toolbar.refresh()

    @Slot(str)
    def _on_server_error(self, msg: str) -> None:
        """Handle server error manually."""
        self.btn_publish.setChecked(False)
        self.btn_share_lan.setChecked(False)
        self.access_code_label.setText("")
        self.url_label.setText("Error starting server")
        QMessageBox.warning(self, "Web Server Error", msg)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        self.find_shortcut = QShortcut(ShortcutManager.FIND.key_sequence, self)
        self.find_shortcut.activated.connect(self._toggle_search)

        # Escape to close search (only when this editor has focus)
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.esc_shortcut.activated.connect(self._handle_escape)

    def _toggle_search(self) -> None:
        """Toggle search bar visibility."""
        if self.search_widget.isVisible():
            # If visible and focused, hide. If visible and not focused, focus.
            if self.search_input.hasFocus():
                self._hide_search()
            else:
                self.search_input.setFocus()
                self.search_input.selectAll()
        else:
            self.search_widget.setVisible(True)
            self.search_input.setFocus()
            self.search_input.selectAll()

    def _hide_search(self) -> None:
        """Hide search bar and clear focus."""
        self.search_widget.setVisible(False)
        self.content.setFocus()

    def _handle_escape(self) -> None:
        """Handle escape key."""
        if self.membership.isVisible():
            self._hide_membership()
        elif self.search_widget.isVisible():
            self._hide_search()

    def _perform_search_next(self) -> None:
        """Search for next occurrence."""
        if text := self.search_input.text():
            self.content.find_text(text, backward=False)
            # Note: If not found, we could implement wrap-around logic here

    def _perform_search_prev(self) -> None:
        """Search for previous occurrence."""
        if text := self.search_input.text():
            self.content.find_text(text, backward=True)

    def set_refresh_button_visible(self, visible: bool) -> None:
        """Sets the visibility of the manual refresh button."""
        self.action_toolbar.set_button_available(self.btn_refresh, visible)
