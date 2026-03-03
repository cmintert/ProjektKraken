"""Base Editor Mixin Module.

Provides shared behavior for editor widgets (EventEditorWidget, EntityEditorWidget).
Centralizes dirty-state tracking, drag-drop acceptance, and hidden-attribute handling
so that both editors stay consistent without code duplication.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QPoint
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent

logger = logging.getLogger(__name__)


class BaseEditorMixin:
    """Mixin providing shared editor behavior.

    Subclasses must define the following attributes before using mixin methods:

    Attributes expected on self:
        _is_loading (bool): Guard against dirty during load.
        _is_dirty (bool): Current dirty state.
        _is_drag_over (bool): Whether a drag is over the editor.
        _selected_relation_type (str): Currently selected relation type for drops.
        _type_picker: Optional relation type picker widget.
        _hidden_attributes (dict): Underscore-prefixed attributes preserved on save.
        btn_save: Save button widget.
        btn_discard: Discard button widget.
        autosave_manager: AutoSaveManager instance.
        dirty_changed: Signal(bool).

    Subclasses must implement:
        _get_current_item_id() -> Optional[str]: Returns the current item ID.
        _get_editor_label() -> str: Returns a label for logging (e.g., "EventEditor").
    """

    def _get_current_item_id(self) -> Optional[str]:
        """Returns the current item ID or None if no item is loaded.

        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def _get_editor_label(self) -> str:
        """Returns a short label for log messages (e.g., 'EventEditor').

        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def set_dirty(self, dirty: bool) -> None:
        """Sets the dirty state of the editor.

        Ignores dirty=True while loading or when no item is loaded.

        Args:
            dirty: True if changes are unsaved, False otherwise.

        """
        label = self._get_editor_label()

        if self._is_loading and dirty:
            logger.debug(f"[{label}] set_dirty({dirty}) ignored - loading in progress")
            return

        if self._get_current_item_id() is None and dirty:
            logger.debug(f"[{label}] set_dirty({dirty}) ignored - no item loaded")
            return

        if self._is_dirty != dirty:
            self._is_dirty = dirty
            self.dirty_changed.emit(dirty)
            self.btn_save.setEnabled(dirty)
            self.btn_discard.setEnabled(dirty)
            if dirty:
                self.btn_save.setText("Save Changes *")
                self.autosave_manager.start_timer()
            else:
                self.btn_save.setText("Save Changes")
                self.autosave_manager.stop_timer()

    def has_unsaved_changes(self) -> bool:
        """Returns True if the editor has unsaved changes."""
        return self._is_dirty

    def _extract_hidden_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Separates hidden (underscore-prefixed) attributes from display attributes.

        Stores hidden attributes internally for preservation on save.

        Args:
            attributes: Full attributes dict from the data model.

        Returns:
            Display-only attributes (keys not starting with underscore).

        """
        self._hidden_attributes = {
            k: v for k, v in attributes.items() if k.startswith("_")
        }
        return {k: v for k, v in attributes.items() if not k.startswith("_")}

    def _merge_hidden_attributes(self, base_attrs: Dict[str, Any]) -> None:
        """Merges preserved hidden attributes back into the attributes dict.

        Args:
            base_attrs: The attributes dict being prepared for save (mutated).

        """
        if hasattr(self, "_hidden_attributes"):
            for k, v in self._hidden_attributes.items():
                if k not in base_attrs:
                    base_attrs[k] = v

    def _save_desc_cursor_state(self) -> Tuple[int, bool]:
        """Save the description editor's cursor position and focus state.

        Returns:
            Tuple of (cursor_position, had_focus).

        """
        if hasattr(self, "desc_edit") and hasattr(self.desc_edit, "editor"):
            cursor_pos = self.desc_edit.editor.textCursor().position()
            had_focus = self.desc_edit.editor.hasFocus()
            return cursor_pos, had_focus
        return 0, False

    def _restore_desc_cursor_state(self, cursor_pos: int, had_focus: bool) -> None:
        """Restore the description editor's cursor position and focus.

        The cursor position is always restored so that a setHtml call inside
        the reload path (which resets the cursor to 0) never silently discards
        the user's previous caret location.  Focus is only stolen back when
        the editor actually had keyboard focus before the reload.

        Args:
            cursor_pos: Cursor position to restore.
            had_focus: Whether the description editor had focus before reload.

        """
        if hasattr(self, "desc_edit") and hasattr(self.desc_edit, "editor"):
            text_len = len(self.desc_edit.editor.toPlainText())
            cursor = self.desc_edit.editor.textCursor()
            cursor.setPosition(min(cursor_pos, text_len))
            self.desc_edit.editor.setTextCursor(cursor)
            if had_focus:
                self.desc_edit.editor.setFocus()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event to accept MIME data from Project Explorer.

        Args:
            event: QDragEnterEvent with MIME data.

        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if (
            event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE)
            and self._get_current_item_id()
        ):
            event.acceptProposedAction()
            self._is_drag_over = True
            self._selected_relation_type = "related"
            self._show_drop_hint(self._selected_relation_type)
            logger.debug(
                f"{self._get_editor_label()}: Accepting drag from Project Explorer"
            )
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Handle drag move event.

        Args:
            event: QDragMoveEvent.

        """
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if (
            event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE)
            and self._get_current_item_id()
        ):
            event.acceptProposedAction()
            if not self._is_drag_over:
                self._is_drag_over = True
            self._show_drop_hint(self._selected_relation_type)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Handle drag leave event - hide drop hint and type picker.

        Args:
            event: QDragLeaveEvent.

        """
        self._is_drag_over = False
        self._hide_drop_hint()
        if self._type_picker and self._type_picker.isVisible():
            self._type_picker.hide()
        logger.debug(f"{self._get_editor_label()}: Drag left editor area")

    def _show_type_picker(self, position: QPoint) -> None:
        """Show the relation type picker at the specified position.

        Args:
            position: Position relative to this widget.

        """
        if not self._type_picker:
            from src.gui.widgets.relation_type_picker import RelationTypePicker

            self._type_picker = RelationTypePicker()
            self._type_picker.type_selected.connect(self._on_relation_type_selected)

        default_types = [
            "related",
            "caused",
            "participated_in",
            "located_at",
            "owns",
            "created_by",
            "part_of",
        ]

        all_types = set(default_types)
        if hasattr(self, "_suggestion_types") and self._suggestion_types:
            all_types.update(self._suggestion_types)

        self._type_picker.set_relation_types(list(all_types))
        global_pos = self.mapToGlobal(position)
        self._type_picker.show_at_position(global_pos)
        self._hide_drop_hint()

    def _on_relation_type_selected(self, relation_type: str) -> None:
        """Handle relation type selection from picker.

        Args:
            relation_type: The selected relation type.

        """
        if hasattr(self, "_initiated_relation_drop") and self._initiated_relation_drop:
            data = self._initiated_relation_drop
            self._create_relation(
                data["source_id"],
                data["source_type"],
                data["source_name"],
                relation_type,
            )
            self._initiated_relation_drop = None
        else:
            self._selected_relation_type = relation_type
            logger.info(
                f"{self._get_editor_label()}: Relation type selected: {relation_type}"
            )
            self._show_drop_hint(self._selected_relation_type)
