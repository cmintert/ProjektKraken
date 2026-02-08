"""Longform Editor Widget Module (Orchestrator).

Provides a split-view interface for editing longform documents:
- Left: Outline tree view (from outline.py)
- Right: Continuous document view (from content.py)
"""

import logging
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.utils.icon_loader import load_icon
from src.gui.utils.shortcut_manager import ShortcutManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.longform.content import LongformContentWidget
from src.gui.widgets.longform.outline import LongformOutlineWidget
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
    remove_requested = Signal(str, str, dict)  # table, id, old_meta
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
        self._sequence = []

        # Web Service Manager
        self.web_manager = WebServiceManager(self)
        self.web_manager.status_changed.connect(self._on_server_status_changed)
        self.web_manager.error_occurred.connect(self._on_server_error)

        # Setup UI
        self._setup_ui()
        self._setup_shortcuts()

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
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet("QToolBar { spacing: 10px; padding: 5px; }")

        # Refresh Button
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.refresh_action = toolbar.addWidget(self.btn_refresh)

        # Filter Button
        btn_filter = QPushButton("Filter...")
        btn_filter.clicked.connect(self.show_filter_dialog_requested.emit)
        toolbar.addWidget(btn_filter)

        # Clear Filters Button
        btn_clear_filters = QPushButton("Clear Filters")
        btn_clear_filters.clicked.connect(self.clear_filters_requested.emit)
        toolbar.addWidget(btn_clear_filters)

        # Export Button
        btn_export = QPushButton("Export to Markdown")
        btn_export.clicked.connect(self.export_requested.emit)
        toolbar.addWidget(btn_export)

        # Export as Vault Button (Obsidian-compatible)
        btn_export_vault = QPushButton("Export as Vault")
        btn_export_vault.setToolTip(
            "Export each entity and event as separate Obsidian-compatible .md files"
        )
        btn_export_vault.clicked.connect(self.export_vault_requested.emit)
        toolbar.addWidget(btn_export_vault)

        # Publish Button
        self.btn_publish = QPushButton("Publish to Web")
        self.btn_publish.setCheckable(True)
        self.btn_publish.clicked.connect(self._toggle_publish)
        toolbar.addWidget(self.btn_publish)

        self.url_label = QLabel("")
        self.url_label.setStyleSheet(
            "color: #FF9900; margin-left: 10px; font-weight: bold;"
        )
        self.url_label.setOpenExternalLinks(True)
        toolbar.addWidget(self.url_label)

        # Spacer to push Find button to far right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Find Button (Discoverability - Far Right)
        self.btn_find = QPushButton()
        self.btn_find.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "search.svg"),
                color=icon_color,
            )
        )
        self.btn_find.setToolTip(f"Find Text ({ShortcutManager.FIND.sequence})")
        self.btn_find.clicked.connect(self._toggle_search)
        toolbar.addWidget(self.btn_find)

        layout.addWidget(toolbar)

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
        btn_prev = QPushButton()
        btn_prev.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "arrow_up.svg"),
                color=icon_color,
            )
        )
        btn_prev.setToolTip("Find Previous (Shift+Enter)")
        btn_prev.clicked.connect(self._perform_search_prev)

        btn_next = QPushButton()
        btn_next.setIcon(
            load_icon(
                os.path.join("default_assets", "icons", "ui_icons", "arrow_down.svg"),
                color=icon_color,
            )
        )
        btn_next.setToolTip("Find Next (Enter)")
        btn_next.clicked.connect(self._perform_search_next)

        btn_close = QPushButton()
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
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Outline
        self.outline = LongformOutlineWidget()
        self.outline.item_selected.connect(self._on_item_selected)
        self.outline.item_promoted.connect(self.promote_requested.emit)
        self.outline.item_demoted.connect(self.demote_requested.emit)
        self.outline.item_moved.connect(self.item_moved.emit)
        self.outline.item_removed.connect(self.remove_requested.emit)
        self.outline.item_move_up.connect(self.move_up_requested.emit)
        self.outline.item_move_down.connect(self.move_down_requested.emit)

        # Right: Content view
        self.content = LongformContentWidget()
        self.content.link_clicked.connect(self.link_clicked.emit)
        self.content.item_selected.connect(self.item_selected.emit)

        splitter.addWidget(self.outline)
        splitter.addWidget(self.content)

        # Set initial sizes (30% outline, 70% content)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter, 1)  # Stretch factor 1

        # Status bar
        self.status_label = QLabel("No items loaded")
        layout.addWidget(self.status_label, 0)  # Stretch factor 0

    def load_sequence(self, sequence: List[Dict[str, Any]]) -> None:
        """Load a longform sequence into the editor.

        Args:
            sequence: Ordered list from build_longform_sequence.

        """
        self._sequence = sequence
        self.outline.load_sequence(sequence)
        self.content.load_content(sequence)

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
        """Handle publish toggle."""
        if checked:
            self.web_manager.start_server(db_path=self.db_path)
        else:
            self.web_manager.stop_server()

    @Slot(bool, str)
    def _on_server_status_changed(self, is_running: bool, url: str) -> None:
        """Update UI based on server status."""
        self.btn_publish.setChecked(is_running)
        if is_running:
            self.btn_publish.setText("Stop Publishing")
            # Create a clickable link
            self.url_label.setText(
                f'<a href="{url}" style="color: #FF9900; text-decoration: none;">'
                f"{url}</a>"
            )
            self.url_label.setToolTip("Click to open in browser")
        else:
            self.btn_publish.setText("Publish to Web")
            self.url_label.setText("")

    @Slot(str)
    def _on_server_error(self, msg: str) -> None:
        """Handle server error manually."""
        self.btn_publish.setChecked(False)
        self.url_label.setText("Error starting server")
        QMessageBox.warning(self, "Web Server Error", msg)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        self.find_shortcut = QShortcut(ShortcutManager.FIND.key_sequence, self)
        self.find_shortcut.activated.connect(self._toggle_search)

        # Escape to close search
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
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
        if self.search_widget.isVisible():
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
        self.refresh_action.setVisible(visible)
