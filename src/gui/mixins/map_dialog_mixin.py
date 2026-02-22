"""Map Dialog & User-Input Mixin.

Provides object-selection dialogs, map CRUD dialogs, and marker
creation/deletion confirmation dialogs for the MapWidget.
"""

import logging
import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from src.app.constants import IMAGE_FILE_FILTER

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MapDialogMixin:
    """Mixin providing user-facing dialogs for the MapWidget.

    Requires the host class to have:
        - self.map_selector: QComboBox
        - self.map_created: Signal(str, str)
        - self.map_deleted: Signal(str)
        - self.marker_created: Signal(str, str, str, str, float, float)
        - self.marker_delete_confirmed: Signal(str)
        - self.create_entity_requested: Signal(str, str)
        - self.create_event_requested: Signal(str, str)
        - self._cached_entities: list
        - self._cached_events: list
        - self.get_selected_map_id(): method
    """

    _NEW_ENTITY_SENTINEL = "<New Entity...>"
    _NEW_EVENT_SENTINEL = "<New Event...>"

    def set_cached_items(self, entities: list, events: list) -> None:
        """Stores the entity/event caches for the object-selection dialog.

        Called by MainWindow when data is refreshed so the map's
        object-picker dialog can offer existing entities and events.

        Args:
            entities: List of entity objects.  Each must have ``.id``
                (``str``) and ``.name`` (``str``) attributes.
            events: List of event objects.  Each must have ``.id``
                (``str``) and ``.name`` (``str``) attributes.

        """
        self._cached_entities = entities
        self._cached_events = events

    def _select_or_create_object(
        self, dialog_title: str, dialog_label: str
    ) -> tuple[str, str, str] | None:
        """Shows a selection dialog with existing items + new-item options.

        Returns:
            Tuple of (object_id, object_type, name) on success, or None
            if the user cancels.

        """
        entities = getattr(self, "_cached_entities", [])
        events = getattr(self, "_cached_events", [])

        items: list[str] = [
            self._NEW_ENTITY_SENTINEL,
            self._NEW_EVENT_SENTINEL,
        ]
        for e in entities:
            items.append(f"{e.name} (Entity)")
        for e in events:
            items.append(f"{e.name} (Event)")

        # Sort existing items, keep sentinels at top
        sentinels = items[:2]
        existing = sorted(items[2:])
        items = sentinels + existing

        item_text, ok = QInputDialog.getItem(
            self, dialog_title, dialog_label, items, 0, False
        )
        if not ok or not item_text:
            return None

        if item_text == self._NEW_ENTITY_SENTINEL:
            return self._create_new_entity_inline()
        if item_text == self._NEW_EVENT_SENTINEL:
            return self._create_new_event_inline()

        if item_text.endswith(" (Entity)"):
            name = item_text[:-9]
            obj = next((e for e in entities if e.name == name), None)
            if obj:
                return obj.id, "entity", obj.name
        elif item_text.endswith(" (Event)"):
            name = item_text[:-8]
            obj = next((e for e in events if e.name == name), None)
            if obj:
                return obj.id, "event", obj.name

        return None

    def _create_new_entity_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits ``create_entity_requested``.

        Returns:
            Tuple of (new_id, 'entity', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return None
        name = name.strip()
        new_id = str(uuid.uuid4())
        self.create_entity_requested.emit(new_id, name)
        logger.info(f"Created new entity '{name}' ({new_id}) from map")
        return new_id, "entity", name

    def _create_new_event_inline(self) -> tuple[str, str, str] | None:
        """Prompts for a name and emits ``create_event_requested``.

        Returns:
            Tuple of (new_id, 'event', name) or None if cancelled.

        """
        name, ok = QInputDialog.getText(self, "New Event", "Event Name:")
        if not ok or not name.strip():
            return None
        name = name.strip()
        new_id = str(uuid.uuid4())
        self.create_event_requested.emit(new_id, name)
        logger.info(f"Created new event '{name}' ({new_id}) from map")
        return new_id, "event", name

    @Slot()
    def _on_create_map_clicked(self) -> None:
        """Shows file/name dialogs and emits ``map_created``."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Map Image", "", IMAGE_FILE_FILTER
        )
        if not file_path:
            return
        name, ok = QInputDialog.getText(self, "New Map", "Map Name:")
        if not ok or not name.strip():
            return
        self.map_created.emit(file_path, name.strip())

    @Slot()
    def _on_delete_map_clicked(self) -> None:
        """Shows confirmation dialog and emits ``map_deleted``."""
        map_id = self.map_selector.currentData()
        if not map_id:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Map",
            "Are you sure you want to delete this map and all its markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.map_deleted.emit(map_id)

    @Slot(float, float)
    def _on_create_marker_requested(self, x: float, y: float) -> None:
        """Shows object-selection dialog and emits ``marker_created``."""
        map_id = self.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(self, "No Map", "Please create or select a map first.")
            return
        result = self._select_or_create_object("Add Marker", "Select Object:")
        if not result:
            return
        obj_id, obj_type, name = result
        self.marker_created.emit(map_id, obj_id, obj_type, name, x, y)

    @Slot(str)
    def _on_delete_marker_requested(self, marker_id: str) -> None:
        """Shows confirmation dialog and emits ``marker_delete_confirmed``."""
        confirm = QMessageBox.question(
            self,
            "Delete Marker",
            "Remove this marker?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.marker_delete_confirmed.emit(marker_id)
