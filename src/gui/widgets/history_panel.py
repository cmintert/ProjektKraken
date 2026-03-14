"""History Panel Widget Module.

Provides a visual display of command history for undo/redo operations.
Shows a list of executed commands with visual indicators for current position.
"""

import logging
from typing import Dict, List, Optional

import shiboken6
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.theme_manager import ThemeManager
from src.gui.widgets.standard_buttons import DestructiveButton, StandardButton

logger = logging.getLogger(__name__)


class HistoryPanelWidget(QWidget):
    """Widget displaying command history for undo/redo visualization.

    Features:
    - Visual list of all commands in history
    - Current position indicator
    - Undo/Redo buttons
    - Clear history button
    - Theme-aware styling
    - Real-time updates on history changes

    Signals:
        undo_clicked: Emitted when undo button is clicked
        redo_clicked: Emitted when redo button is clicked
        clear_history_clicked: Emitted when clear history button is clicked
    """

    # Signals
    undo_clicked = Signal()
    redo_clicked = Signal()
    clear_history_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the history panel widget.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self._undo_stack: List[Dict[str, object]] = []
        self._redo_stack: List[Dict[str, object]] = []
        self._refreshing = False  # Reentrance guard
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        self._apply_theme()
        self._connect_theme_changes()
        logger.debug("HistoryPanelWidget initialized")

    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header with buttons
        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)

        # Undo button
        self.undo_btn = StandardButton("⟲ Undo")
        self.undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo_clicked.emit)
        self.undo_btn.setEnabled(False)
        header_layout.addWidget(self.undo_btn)

        # Redo button
        self.redo_btn = StandardButton("⟳ Redo")
        self.redo_btn.setToolTip("Redo undone action (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo_clicked.emit)
        self.redo_btn.setEnabled(False)
        header_layout.addWidget(self.redo_btn)

        # Clear button (destructive action)
        self.clear_btn = DestructiveButton("✕ Clear")
        self.clear_btn.setToolTip("Clear all history")
        self.clear_btn.clicked.connect(self.clear_history_clicked.emit)
        self.clear_btn.setEnabled(False)
        header_layout.addWidget(self.clear_btn)

        layout.addLayout(header_layout)

        # Status label
        self.status_label = QLabel("No history")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(9)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)

        # Command list
        self.command_list = QListWidget()
        self.command_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.command_list.setAlternatingRowColors(True)
        layout.addWidget(self.command_list)

        # Info label
        self.info_label = QLabel("▲ Can undo  |  ▼ Can redo")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(8)
        self.info_label.setFont(font)
        layout.addWidget(self.info_label)

    def _apply_theme(self) -> None:
        """Apply current theme colors to the widget."""
        try:
            from src.gui.utils.style_helper import StyleHelper

            theme = ThemeManager().get_theme()

            # Set background and text color directly to the widget
            # (without broad CSS selector to avoid inheritance issues)
            self.setAutoFillBackground(True)
            palette = self.palette()
            palette.setColor(
                self.backgroundRole(), QColor(theme.get("surface", "#323232"))
            )
            palette.setColor(
                self.foregroundRole(), QColor(theme.get("text_main", "#E0E0E0"))
            )
            self.setPalette(palette)

            # Apply Stylesheet for components
            self.undo_btn.setStyleSheet(StyleHelper.get_icon_button_style())
            self.redo_btn.setStyleSheet(StyleHelper.get_icon_button_style())
            self.command_list.setStyleSheet(StyleHelper.get_list_widget_style())

            # Specific colors for labels
            self.status_label.setStyleSheet(StyleHelper.get_empty_state_style())
            self.info_label.setStyleSheet(StyleHelper.get_preview_label_style())

            logger.debug("Theme applied to history panel (v2)")

        except Exception as e:
            logger.error(f"Failed to apply theme: {e}")

    def _connect_theme_changes(self) -> None:
        """Connect to theme change signals for live updates."""
        try:
            ThemeManager().theme_changed.connect(self._on_theme_changed)
        except Exception as e:
            logger.error(f"Failed to connect theme changes: {e}")

    @Slot(dict)
    def _on_theme_changed(self, theme_data: dict) -> None:
        """Handle theme change events.

        Args:
            theme_data: New theme data dictionary
        """
        self._apply_theme()
        # Refresh display to re-generate items with new theme colors
        self._refresh_display()

    @Slot(list, list)
    def update_history(
        self,
        undo_snapshots: List[Dict[str, object]],
        redo_snapshots: List[Dict[str, object]],
    ) -> None:
        """Update the history display with current stacks.

        Args:
            undo_snapshots: List of command snapshot dicts
            redo_snapshots: List of command snapshot dicts
        """
        self._undo_stack = undo_snapshots
        self._redo_stack = redo_snapshots
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the command list display.

        Protected by a reentrance guard and shiboken validity check
        so that concurrent or stale calls cannot cause C++ access
        violations.
        """
        if self._refreshing:
            return
        self._refreshing = True
        try:
            if not shiboken6.isValid(self.command_list):
                logger.debug("_refresh_display: command_list C++ object deleted")
                return

            self.command_list.clear()

            total_commands = len(self._undo_stack) + len(self._redo_stack)

            # Update status label
            if total_commands == 0:
                self.status_label.setText("No history")
            else:
                undo_count = len(self._undo_stack)
                redo_count = len(self._redo_stack)
                self.status_label.setText(
                    f"{total_commands} command{'s' if total_commands != 1 else ''} "
                    f"({undo_count} undo / {redo_count} redo)"
                )

            # Update button states
            self.undo_btn.setEnabled(len(self._undo_stack) > 0)
            self.redo_btn.setEnabled(len(self._redo_stack) > 0)
            self.clear_btn.setEnabled(total_commands > 0)

            # Display commands - redo stack first (most recent undone at top)
            if self._redo_stack:
                for i, command in enumerate(reversed(self._redo_stack)):
                    self._add_command_item(command, can_redo=True, is_top=i == 0)

            # Then undo stack (most recent at top)
            if self._undo_stack:
                for i, command in enumerate(reversed(self._undo_stack)):
                    self._add_command_item(command, can_undo=True, is_top=i == 0)
        except RuntimeError:
            logger.debug("_refresh_display: RuntimeError (widget deleted)")
        finally:
            self._refreshing = False

    def _add_command_item(
        self,
        command_snapshot: Dict[str, object],
        can_undo: bool = False,
        can_redo: bool = False,
        is_top: bool = False,
    ) -> None:
        """Add a command to the list display.

        Args:
            command_snapshot: Dictionary containing command details
                (``description``, ``timestamp``).
            can_undo: Whether this command can be undone
            can_redo: Whether this command can be redone
            is_top: Whether this is the most recent command in its stack
        """
        try:
            description = command_snapshot.get("description", "Unknown Command")
            ts_str = ""
            timestamp = command_snapshot.get("timestamp")

            if timestamp:
                import datetime

                dt = datetime.datetime.fromtimestamp(timestamp)
                ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")

            # Build display text
            prefix = "  "
            if can_undo:
                if is_top:
                    prefix = "▲ "
            elif can_redo:
                if is_top:
                    prefix = "▼ "

            text = f"{prefix}{description}"
            if ts_str:
                text += f" ({ts_str})"

            # Create list item
            item = QListWidgetItem(text)

            # Style based on state
            theme = ThemeManager().get_theme()

            if can_undo:
                # Commands that can be undone - normal color
                color = QColor(theme.get("text_main", "#E0E0E0"))
                if is_top:
                    # Highlight the next undo command
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                    bg_color = QColor(theme.get("primary", "#4A9EFF"))
                    bg_color.setAlpha(30)
                    item.setBackground(QBrush(bg_color))
            elif can_redo:
                # Commands that have been undone - dimmed
                color = QColor(theme.get("text_dim", "#808080"))
                if is_top:
                    # Highlight the next redo command
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                    bg_color = QColor(theme.get("accent", "#FF9800"))
                    bg_color.setAlpha(30)
                    item.setBackground(QBrush(bg_color))
            else:
                color = QColor(theme.get("text_main", "#E0E0E0"))

            item.setForeground(QBrush(color))

            # Add to list
            self.command_list.addItem(item)

        except Exception as e:
            logger.error(f"Failed to add command item: {e}")

    def clear_display(self) -> None:
        """Clear the history display."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._refresh_display()
