"""
Longform Editor Widget Module.

Provides a split-view interface for editing longform documents:
- Left: Outline tree view with drag/drop reordering and promote/demote
- Right: Continuous document view with synchronized scrolling

The longform editor displays events and entities in a hierarchical document
structure, allowing users to organize narrative content.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QToolBar,
    QLabel,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction, QFont, QTextCursor
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class LongformOutlineWidget(QTreeWidget):
    """
    Tree widget for displaying the longform document outline.

    Supports drag-and-drop reordering and keyboard shortcuts for
    promote/demote operations.
    """

    item_selected = Signal(str, str)  # table, id
    item_moved = Signal(str, str, dict, dict)  # table, id, old_meta, new_meta
    item_promoted = Signal(str, str, dict)  # table, id, old_meta
    item_demoted = Signal(str, str, dict)  # table, id, old_meta
    item_removed = Signal(str, str, dict)  # table, id, old_meta

    def __init__(self, parent=None):
        """Initialize the outline widget."""
        super().__init__(parent)
        self.setHeaderLabel("Document Outline")
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # Store item metadata
        self._item_meta = {}  # Map item -> (table, id, meta)

        # Connect signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def load_sequence(self, sequence: List[Dict[str, Any]]) -> None:
        """
        Load a longform sequence into the tree.

        Args:
            sequence: Ordered list of items from build_longform_sequence.
        """
        self.clear()
        self._item_meta.clear()

        # Build tree structure
        item_map = {}  # Map id -> QTreeWidgetItem
        root_items = []

        for item in sequence:
            tree_item = QTreeWidgetItem()
            title = item["meta"].get("title_override") or item["name"]
            tree_item.setText(0, title)

            # Store metadata
            self._item_meta[id(tree_item)] = (
                item["table"],
                item["id"],
                item["meta"],
            )
            item_map[item["id"]] = tree_item

            # Add to parent or root
            parent_id = item["meta"].get("parent_id")
            if parent_id and parent_id in item_map:
                item_map[parent_id].addChild(tree_item)
            else:
                root_items.append(tree_item)

        # Add root items
        self.addTopLevelItems(root_items)
        self.expandAll()

    def _on_selection_changed(self):
        """Handle selection change."""
        items = self.selectedItems()
        if items:
            item = items[0]
            meta = self._item_meta.get(id(item))
            if meta:
                table, row_id, _ = meta
                self.item_selected.emit(table, row_id)

    def _show_context_menu(self, pos):
        """Show context menu for outline items."""
        # TODO: Implement context menu with promote/demote/remove options
        pass

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Tab:
            # Demote (Tab)
            if event.modifiers() == Qt.ShiftModifier:
                # Promote (Shift+Tab)
                self._promote_selected()
            else:
                self._demote_selected()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _promote_selected(self):
        """Promote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._item_meta.get(id(item))
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_promoted.emit(table, row_id, old_meta.copy())

    def _demote_selected(self):
        """Demote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._item_meta.get(id(item))
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_demoted.emit(table, row_id, old_meta.copy())


class LongformContentWidget(QTextEdit):
    """
    Read-only text view for displaying the continuous longform document.

    Shows the assembled document with headings and content from all items.
    """

    def __init__(self, parent=None):
        """Initialize the content widget."""
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(False)

        # Set monospace font for better readability
        font = QFont("Courier New", 10)
        self.setFont(font)

    def load_content(self, sequence: List[Dict[str, Any]]) -> None:
        """
        Load and display the longform sequence as continuous text.

        Args:
            sequence: Ordered list of items from build_longform_sequence.
        """
        lines = []

        for item in sequence:
            # Add heading
            heading_level = item["heading_level"]
            title = item["meta"].get("title_override") or item["name"]
            heading = "#" * heading_level + " " + title
            lines.append(heading)
            lines.append("")

            # Add content
            content = item.get("content", "").strip()
            if content:
                lines.append(content)
                lines.append("")

            lines.append("")  # Extra spacing between sections

        self.setPlainText("\n".join(lines))

    def scroll_to_item(self, item_index: int) -> None:
        """
        Scroll to a specific item in the document.

        Args:
            item_index: Index of the item in the sequence.
        """
        # Simple implementation: scroll to top for first item
        # More sophisticated implementations would calculate line positions
        if item_index == 0:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.setTextCursor(cursor)


class LongformEditorWidget(QWidget):
    """
    Main longform editor widget with split view.

    Left panel: Outline tree
    Right panel: Continuous document view
    """

    # Signals
    promote_requested = Signal(str, str, dict)  # table, id, old_meta
    demote_requested = Signal(str, str, dict)  # table, id, old_meta
    refresh_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None):
        """Initialize the longform editor."""
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Store current sequence
        self._sequence = []

        # Setup UI
        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_requested.emit)
        toolbar.addAction(refresh_action)

        export_action = QAction("Export to Markdown", self)
        export_action.triggered.connect(self.export_requested.emit)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        help_label = QLabel("  Tab: Demote | Shift+Tab: Promote")
        toolbar.addWidget(help_label)

        layout.addWidget(toolbar)

        # Splitter with outline and content
        splitter = QSplitter(Qt.Horizontal)

        # Left: Outline
        self.outline = LongformOutlineWidget()
        self.outline.item_selected.connect(self._on_item_selected)
        self.outline.item_promoted.connect(self.promote_requested.emit)
        self.outline.item_demoted.connect(self.demote_requested.emit)

        # Right: Content view
        self.content = LongformContentWidget()

        splitter.addWidget(self.outline)
        splitter.addWidget(self.content)

        # Set initial sizes (30% outline, 70% content)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

        # Status bar
        self.status_label = QLabel("No items loaded")
        layout.addWidget(self.status_label)

    def load_sequence(self, sequence: List[Dict[str, Any]]) -> None:
        """
        Load a longform sequence into the editor.

        Args:
            sequence: Ordered list from build_longform_sequence.
        """
        self._sequence = sequence
        self.outline.load_sequence(sequence)
        self.content.load_content(sequence)

        # Update status
        count = len(sequence)
        self.status_label.setText(f"{count} item(s) in document")

    def _on_item_selected(self, table: str, row_id: str):
        """
        Handle item selection in outline.

        Args:
            table: Table name.
            row_id: Row ID.
        """
        # Find index in sequence
        for idx, item in enumerate(self._sequence):
            if item["table"] == table and item["id"] == row_id:
                self.content.scroll_to_item(idx)
                break

    def get_current_selection(self) -> Optional[tuple]:
        """
        Get currently selected item.

        Returns:
            Tuple of (table, id) or None.
        """
        items = self.outline.selectedItems()
        if items:
            item = items[0]
            meta_data = self.outline._item_meta.get(id(item))
            if meta_data:
                table, row_id, _ = meta_data
                return (table, row_id)
        return None
