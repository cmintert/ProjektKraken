"""
Longform Editor Widget Module.

Provides a split-view interface for editing longform documents:
- Left: Outline tree view with drag/drop reordering and promote/demote
- Right: Continuous document view with synchronized scrolling

The longform editor displays events and entities in a hierarchical document
structure, allowing users to organize narrative content.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QDrag,
    QDropEvent,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.wiki_text_edit import WikiTextEdit
from src.services.web_service_manager import WebServiceManager

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

    COLOR_EVENT = QColor("#0078D4")
    COLOR_ENTITY = QColor("#FF9900")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
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

    def startDrag(self, supportedActions: Qt.DropActions) -> None:
        """
        Override to provide custom MIME data for external drags.

        Supports both internal reordering and external drag to map.
        Uses the same MIME type as Project Explorer for DRY compatibility.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        item = self.currentItem()
        if not item:
            return

        # Get item metadata
        meta_data = self._item_meta.get(id(item))
        if not meta_data:
            super().startDrag(supportedActions)
            return

        table, row_id, meta = meta_data

        # Map table names to item types
        item_type = "event" if table == "events" else "entity"
        item_name = meta.get("title_override") or item.text(0)

        # Build MIME data
        data = {"id": row_id, "type": item_type, "name": item_name}

        # Use base class mime data to preserve internal move functionality
        mime_data = self.mimeData([item])
        mime_data.setData(KRAKEN_ITEM_MIME_TYPE, json.dumps(data).encode("utf-8"))
        # Also set plain text for debugging
        mime_data.setText(f"{item_type}:{row_id}")

        # Create drag
        drag = QDrag(self)
        drag.setMimeData(mime_data)

        # Execute drag - CopyAction for external, MoveAction for internal
        drag.exec(Qt.CopyAction | Qt.MoveAction)

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event to reorder items.
        Calculates new parent, depth, and position.
        """
        # 1. capture selection before drop (the item being moved)
        # In QTreeWidget with InternalMove, selection is preserved
        selected = self.selectedItems()
        if not selected:
            super().dropEvent(event)
            return

        item = selected[0]

        # 2. Perform the move visually
        super().dropEvent(event)

        # 3. Analyze new state
        parent = item.parent()

        # Calculate new parent ID and depth
        new_parent_id = None
        new_depth = 0

        if parent:
            # We need to find meta for the parent
            # But wait, parent is a QTreeWidgetItem, we need its data
            # We stored _item_meta key as id(tree_item)
            p_val = self._item_meta.get(id(parent))
            if p_val:
                # p_val is (table, row_id, meta)
                new_parent_id = p_val[1]
                new_depth = p_val[2].get("depth", 0) + 1

        # Calculate new position based on siblings
        # item is now at its new location in the tree
        # We need its index and siblings

        # Re-get siblings properly
        sibling_count = parent.childCount() if parent else self.topLevelItemCount()
        idx = parent.indexOfChild(item) if parent else self.indexOfTopLevelItem(item)

        # Get prev and next siblings
        prev_sibling = None
        next_sibling = None

        if idx > 0:
            prev_sibling = (
                parent.child(idx - 1) if parent else self.topLevelItem(idx - 1)
            )

        if idx < sibling_count - 1:
            next_sibling = (
                parent.child(idx + 1) if parent else self.topLevelItem(idx + 1)
            )

        # Get positions
        prev_pos = 0.0
        next_pos = 0.0

        if prev_sibling:
            if id(prev_sibling) in self._item_meta:
                prev_pos = self._item_meta[id(prev_sibling)][2].get("position", 0.0)

        if next_sibling:
            if id(next_sibling) in self._item_meta:
                next_pos = self._item_meta[id(next_sibling)][2].get("position", 0.0)

        # Logic for new position
        new_pos = 100.0  # default

        if prev_sibling and next_sibling:
            # Between two items
            new_pos = (prev_pos + next_pos) / 2.0
        elif prev_sibling:
            # End of list (or after only sibling)
            # Add 100
            new_pos = prev_pos + 100.0
        elif next_sibling:
            # Start of list
            # Half of next, or next - 100?
            if next_pos > 0:
                new_pos = next_pos / 2.0
            else:
                # Should not happen typically if gap is 100
                new_pos = -50.0  # Something smaller

        # 4. Emit signal
        # Get old meta
        if id(item) in self._item_meta:
            table, row_id, old_meta = self._item_meta[id(item)]

            new_meta = old_meta.copy()
            new_meta["position"] = new_pos
            new_meta["parent_id"] = new_parent_id
            new_meta["depth"] = new_depth

            # Emit
            self.item_moved.emit(table, row_id, old_meta, new_meta)

    def load_sequence(self, sequence: List[Dict[str, Any]]) -> None:
        """
        Load a longform sequence into the tree.

        Args:
            sequence: Ordered list of items from build_longform_sequence.
        """
        # Preserve current selection
        selected_item_id = None
        selected_table = None
        items = self.selectedItems()
        if items:
            meta_data = self._item_meta.get(id(items[0]))
            if meta_data:
                selected_table, selected_item_id, _ = meta_data

        self.clear()
        self._item_meta.clear()

        # Build tree structure
        item_map = {}  # Map id -> QTreeWidgetItem
        root_items = []

        for item in sequence:
            tree_item = QTreeWidgetItem()
            title = item["meta"].get("title_override") or item["name"]
            tree_item.setText(0, title)

            # Color code
            if item["table"] == "events":
                tree_item.setForeground(0, QBrush(self.COLOR_EVENT))
            elif item["table"] == "entities":
                tree_item.setForeground(0, QBrush(self.COLOR_ENTITY))

            # Store metadata
            # IMPORTANT: We must store the updated meta so we can
            # calculate positions correctly!
            # The sequence should be up to date from DB.
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

        # Restore selection if it existed
        if selected_item_id and selected_item_id in item_map:
            item_to_select = item_map[selected_item_id]
            self.setCurrentItem(item_to_select)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        items = self.selectedItems()
        if items:
            item = items[0]
            meta = self._item_meta.get(id(item))
            if meta:
                table, row_id, _ = meta
                self.item_selected.emit(table, row_id)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu for outline items."""
        # TODO: Implement context menu with promote/demote/remove options
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for promote/demote operations."""
        # Check for Ctrl+[ (promote)
        if (
            event.key() == Qt.Key_BracketLeft
            and event.modifiers() == Qt.ControlModifier
        ):
            self._promote_selected()
            event.accept()
        # Check for Ctrl+] (demote)
        elif (
            event.key() == Qt.Key_BracketRight
            and event.modifiers() == Qt.ControlModifier
        ):
            self._demote_selected()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _promote_selected(self) -> None:
        """Promote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._item_meta.get(id(item))
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_promoted.emit(table, row_id, old_meta.copy())

    def _demote_selected(self) -> None:
        """Demote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._item_meta.get(id(item))
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_demoted.emit(table, row_id, old_meta.copy())


class LongformContentWidget(WikiTextEdit):
    """
    Read-only text view for displaying the continuous longform document.

    Shows the assembled document with headings and content from all items.
    inherits from WikiTextEdit to support WikiLink rendering and navigation.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the content widget."""
        super().__init__(parent)
        self.setReadOnly(True)

    def load_content(self, sequence: List[Dict[str, Any]]) -> None:
        """
        Load and display the longform sequence as continuous text.

        Args:
            sequence: Ordered list of items from build_longform_sequence.
        """
        lines = []

        for idx, item in enumerate(sequence):
            # Add anchor for navigation
            lines.append(f'<a name="item-{idx}"></a>')

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

            lines.append("")
            lines.append("---")  # Horizontal rule for separation
            lines.append("")

        self.set_wiki_text("\n".join(lines))

    def scroll_to_item(self, item_index: int) -> None:
        """
        Scroll to a specific item in the document.

        Args:
            item_index: Index of the item in the sequence.
        """
        self.scrollToAnchor(f"item-{item_index}")


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
    item_selected = Signal(str, str)  # table, id
    item_moved = Signal(str, str, dict, dict)  # table, id, old_meta, new_meta
    link_clicked = Signal(str)

    def __init__(
        self, parent: Optional[QWidget] = None, db_path: Optional[str] = None
    ) -> None:
        """Initialize the longform editor."""
        super().__init__(parent)
        self.db_path = db_path
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Set size policy to prevent dock collapse
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Store current sequence
        self._sequence = []

        # Web Service Manager
        self.web_manager = WebServiceManager(self)
        self.web_manager.status_changed.connect(self._on_server_status_changed)
        self.web_manager.error_occurred.connect(self._on_server_error)

        # Setup UI
        self._setup_ui()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop server on close."""
        self.web_manager.stop_server()
        super().closeEvent(event)

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet(
            "QToolBar { spacing: 10px; margin-top: 5px; margin-bottom: 5px; "
            "padding: 2px 0px; }"
        )

        # Refresh Button
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_requested.emit)
        toolbar.addWidget(btn_refresh)

        # Export Button
        btn_export = QPushButton("Export to Markdown")
        btn_export.clicked.connect(self.export_requested.emit)
        toolbar.addWidget(btn_export)

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
        # Make it clickable manually since QLabel link handling can be
        # tricky without HTML
        toolbar.addWidget(self.url_label)

        layout.addWidget(toolbar)

        # Splitter with outline and content
        splitter = QSplitter(Qt.Horizontal)

        # Left: Outline
        self.outline = LongformOutlineWidget()
        self.outline.item_selected.connect(self._on_item_selected)
        self.outline.item_promoted.connect(self.promote_requested.emit)
        self.outline.item_demoted.connect(self.demote_requested.emit)
        self.outline.item_moved.connect(self.item_moved.emit)

        # Right: Content view
        self.content = LongformContentWidget()
        self.content.link_clicked.connect(self.link_clicked.emit)

        splitter.addWidget(self.outline)
        splitter.addWidget(self.content)

        # Set initial sizes (30% outline, 70% content)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter, 1)  # Stretch factor 1

        # Status bar
        self.status_label = QLabel("No items loaded")
        layout.addWidget(self.status_label, 0)  # Stretch factor 0

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

    def _on_item_selected(self, table: str, row_id: str) -> None:
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

        # Emit signal to notify parent (MainWindow)
        self.item_selected.emit(table, row_id)

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

    def minimumSizeHint(self) -> QSize:
        """
        Override to prevent dock collapse.

        Returns:
            QSize: Minimum size for usable longform editor.
        """
        return QSize(400, 300)  # Width for split view, height for toolbar + content

    def sizeHint(self) -> QSize:
        """
        Preferred size for the longform editor.

        Returns:
            QSize: Comfortable working size for editing longform documents.
        """
        return QSize(600, 700)  # Comfortable size for split view

    def _toggle_publish(self, checked: bool) -> None:
        """Handle publish toggle."""
        if checked:
            self.web_manager.start_server(db_path=self.db_path)
        else:
            self.web_manager.stop_server()

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

    def _on_server_error(self, msg: str) -> None:
        """Handle server error manually."""
        from PySide6.QtWidgets import QMessageBox

        self.publish_action.setChecked(False)
        self.url_label.setText("Error starting server")
        QMessageBox.warning(self, "Web Server Error", msg)
