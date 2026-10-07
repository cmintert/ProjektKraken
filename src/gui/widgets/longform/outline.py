"""Longform Outline Widget.

Handles the tree view representation of the longform document structure.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDrag,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

logger = logging.getLogger(__name__)


class LongformOutlineWidget(QTreeWidget):
    """Tree widget for displaying the longform document outline.

    Supports drag-and-drop reordering and keyboard shortcuts for promote/demote
    operations.
    """

    item_selected = Signal(str, str)  # table, id
    browse_requested = Signal(str, str)
    gesture_started = Signal()
    item_moved = Signal(str, str, dict, dict)  # table, id, old_meta, new_meta
    item_promoted = Signal(str, str, dict)  # table, id, old_meta
    item_demoted = Signal(str, str, dict)  # table, id, old_meta
    item_deleted = Signal(str, str)  # table, id - completely delete the item
    item_removed = Signal(str, str, dict)  # document membership only
    item_move_up = Signal(str, str, dict)  # table, id, old_meta
    item_move_down = Signal(str, str, dict)  # table, id, old_meta

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the outline widget."""
        super().__init__(parent)
        self.setHeaderLabel("Document Outline")
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Store item metadata
        self._item_meta: dict[int, tuple[str, str, dict[str, Any]]] = {}
        self._pointer_pressed = False
        self._dragged = False

        # Connect signals
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)

        from src.core.theme_manager import ThemeManager

        ThemeManager().theme_changed.connect(self._on_theme_changed)
        self._update_colors()

    def _update_colors(self) -> None:
        """Update colors from current theme."""
        from src.core.theme_manager import ThemeManager

        theme = ThemeManager().get_theme()
        # Fallback to defaults if theme keys missing
        self.color_event = QColor(theme["event_main"])
        self.color_entity = QColor(theme["entity_main"])
        from src.gui.utils.style_helper import StyleHelper

        self.setStyleSheet(
            StyleHelper.get_tree_view_style()
            + StyleHelper.get_item_view_selection_style("QTreeView")
        )

    @Slot(dict)
    def _on_theme_changed(self, theme: dict) -> None:
        """Handle theme change."""
        self._update_colors()
        self._colorize_items()

    def _colorize_items(self) -> None:
        """Re-apply colors to all items."""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            meta = self._item_meta.get(id(item))
            if meta:
                table = meta[0]
                if table == "events":
                    item.setForeground(0, QBrush(self.color_event))
                elif table == "entities":
                    item.setForeground(0, QBrush(self.color_entity))
            iterator += 1

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Override to provide custom MIME data for external drags.

        Supports both internal reordering and external drag to map. Uses the same MIME
        type as Project Explorer for DRY compatibility.
        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        self._dragged = True
        self.gesture_started.emit()

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
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Select locally while the pointer gesture is unresolved."""
        self._pointer_pressed = event.button() == Qt.MouseButton.LeftButton
        self._dragged = False
        if self._pointer_pressed:
            self.gesture_started.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Browse only a completed click, never the release after a drag."""
        browse = self._pointer_pressed and not self._dragged
        self._pointer_pressed = False
        super().mouseReleaseEvent(event)
        if browse and event.button() == Qt.MouseButton.LeftButton:
            self._browse_selected()

    def _browse_selected(self) -> None:
        item = self.currentItem()
        if item is not None and item in self.selectedItems():
            meta = self._get_item_metadata(item)
            if meta is not None:
                self.browse_requested.emit(meta[0], meta[1])

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event to reorder items.

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

        if prev_sibling and id(prev_sibling) in self._item_meta:
            prev_pos = self._item_meta[id(prev_sibling)][2].get("position", 0.0)

        if next_sibling and id(next_sibling) in self._item_meta:
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
        """Load a longform sequence into the tree.

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
                tree_item.setForeground(0, QBrush(self.color_event))
            elif item["table"] == "entities":
                tree_item.setForeground(0, QBrush(self.color_entity))

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

    @Slot()
    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        items = self.selectedItems()
        if items:
            item = items[0]
            meta = self._item_meta.get(id(item))
            if meta:
                table, row_id, _ = meta
                self.item_selected.emit(table, row_id)

    def _get_item_metadata(
        self, item: QTreeWidgetItem
    ) -> Optional[tuple[str, str, Dict[str, Any]]]:
        """Get metadata for a tree widget item.

        Args:
            item: Tree widget item.

        Returns:
            Optional tuple of (table, row_id, metadata) or None if not found.

        """
        return self._item_meta.get(id(item))

    def _get_item_position_info(
        self, item: QTreeWidgetItem
    ) -> Optional[tuple[Optional[QTreeWidgetItem], int, int]]:
        """Get position information for an item.

        Args:
            item: Tree widget item.

        Returns:
            Optional tuple of (parent, current_index, sibling_count) or None.

        """
        parent = item.parent()
        if parent:
            current_index = parent.indexOfChild(item)
            sibling_count = parent.childCount()
        else:
            current_index = self.indexOfTopLevelItem(item)
            sibling_count = self.topLevelItemCount()

        return (parent, current_index, sibling_count)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu for outline items.

        Args:
            pos: Position where context menu was requested.

        """
        item = self.itemAt(pos)
        if not item:
            return
        self.setCurrentItem(item)
        menu = QMenu(self)
        self.populate_actions_menu(menu)
        self._display_context_menu(menu, self.mapToGlobal(pos))

    def populate_actions_menu(self, menu: QMenu) -> None:
        """Share selected-item actions between visible and context menus."""
        menu.clear()
        item = self.currentItem()
        if item is None or not item.isSelected():
            action = menu.addAction("Select an outline item first")
            action.setEnabled(False)
            return

        meta_data = self._get_item_metadata(item)
        if not meta_data:
            return

        table, row_id, old_meta = meta_data

        # Check if item can be moved up or down
        pos_info = self._get_item_position_info(item)
        if not pos_info:
            return

        parent, index, sibling_count = pos_info
        can_move_up = index > 0
        can_move_down = index < sibling_count - 1

        # Move Up action
        move_up_action = QAction("Move Up", menu)
        move_up_action.setEnabled(can_move_up)
        move_up_action.triggered.connect(lambda: self._move_up_selected())
        menu.addAction(move_up_action)

        # Move Down action
        move_down_action = QAction("Move Down", menu)
        move_down_action.setEnabled(can_move_down)
        move_down_action.triggered.connect(lambda: self._move_down_selected())
        menu.addAction(move_down_action)

        menu.addSeparator()

        # Promote action
        # Note: Context menu disables this for depth 0 as UX improvement,
        # but keyboard shortcut (Ctrl+[) still works and command validates
        promote_action = QAction("Promote", menu)
        promote_action.setToolTip("Lift this section one level")
        current_depth = old_meta.get("depth", 0)
        promote_action.setEnabled(current_depth > 0)
        promote_action.triggered.connect(lambda: self._promote_selected())
        menu.addAction(promote_action)

        # Demote action (can only demote if there's a previous sibling to become parent)
        demote_action = QAction("Demote", menu)
        demote_action.setToolTip("Nest beneath the preceding sibling")
        can_demote = False
        if parent:
            can_demote = parent.indexOfChild(item) > 0
        else:
            can_demote = self.indexOfTopLevelItem(item) > 0
        demote_action.setEnabled(can_demote)
        demote_action.triggered.connect(lambda: self._demote_selected())
        menu.addAction(demote_action)

        menu.addSeparator()

        remove_action = menu.addAction("Remove from document")
        remove_action.setToolTip("Keep the world entry and lift its child sections")
        remove_action.triggered.connect(self._remove_selected)

        # Complete deletion uses the application coordinator's safety guard.
        delete_action = QAction("Delete from world…", menu)
        delete_action.triggered.connect(lambda: self._delete_selected())
        menu.addAction(delete_action)

    @staticmethod
    def _display_context_menu(menu: QMenu, global_pos: QPoint) -> None:
        """Display a prepared outline context menu."""
        menu.exec(global_pos)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for promote/demote operations."""
        from src.gui.utils.shortcut_manager import ShortcutManager

        # Check for OUTLINE_PROMOTE
        if ShortcutManager.check_event(event, ShortcutManager.OUTLINE_PROMOTE):
            self._promote_selected()
            event.accept()
        # Check for OUTLINE_DEMOTE
        elif ShortcutManager.check_event(event, ShortcutManager.OUTLINE_DEMOTE):
            self._demote_selected()
            event.accept()
        elif event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._dragged = True
            self._pointer_pressed = False
            self.gesture_started.emit()
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
            if event.key() in (
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
                Qt.Key.Key_Home,
                Qt.Key.Key_End,
                Qt.Key.Key_PageUp,
                Qt.Key.Key_PageDown,
            ):
                self._browse_selected()

    def _promote_selected(self) -> None:
        """Promote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._get_item_metadata(item)
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_promoted.emit(table, row_id, old_meta.copy())

    def _demote_selected(self) -> None:
        """Demote the selected item."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._get_item_metadata(item)
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_demoted.emit(table, row_id, old_meta.copy())

    def _move_up_selected(self) -> None:
        """Move the selected item up in its sibling list."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._get_item_metadata(item)
        if not meta_data:
            return

        table, row_id, old_meta = meta_data

        # Get position info
        pos_info = self._get_item_position_info(item)
        if not pos_info:
            return

        parent, current_index, sibling_count = pos_info
        if current_index <= 0:
            return  # Can't move up

        # Emit signal - position calculation done in manager
        self.item_move_up.emit(table, row_id, old_meta.copy())

    def _move_down_selected(self) -> None:
        """Move the selected item down in its sibling list."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._get_item_metadata(item)
        if not meta_data:
            return

        table, row_id, old_meta = meta_data

        # Get position info
        pos_info = self._get_item_position_info(item)
        if not pos_info:
            return

        parent, current_index, sibling_count = pos_info
        if current_index >= sibling_count - 1:
            return  # Can't move down

        # Emit signal - position calculation done in manager
        self.item_move_down.emit(table, row_id, old_meta.copy())

    def _delete_selected(self) -> None:
        """Delete the selected item completely (Event or Entity)."""
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        meta_data = self._get_item_metadata(item)
        if meta_data:
            table, row_id, old_meta = meta_data
            self.item_deleted.emit(table, row_id)

    def _remove_selected(self) -> None:
        """Request reversible membership removal, preserving the world entry."""
        item = self.currentItem()
        if item is not None and item.isSelected():
            meta_data = self._get_item_metadata(item)
            if meta_data:
                table, row_id, old_meta = meta_data
                self.item_removed.emit(table, row_id, old_meta.copy())
