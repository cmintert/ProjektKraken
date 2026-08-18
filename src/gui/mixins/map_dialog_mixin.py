"""Map dialog and user-input helpers for :class:`MapWidget`."""

import logging
import uuid
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import SignalInstance, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from src.gui.constants import IMAGE_FILE_FILTER
from src.gui.dialogs.map_object_picker_dialog import (
    MapObjectChoice,
    MapObjectPickerDialog,
)

logger = logging.getLogger(__name__)


class MapDialogMixin:
    """Provide map CRUD and linked-object selection dialogs."""

    if TYPE_CHECKING:
        map_selector: QComboBox
        map_created: SignalInstance
        map_deleted: SignalInstance
        marker_created: SignalInstance
        marker_delete_confirmed: SignalInstance
        create_entity_requested: SignalInstance
        create_event_requested: SignalInstance
        marker_object_creation_requested: SignalInstance
        _cached_entities: list[Any]
        _cached_events: list[Any]

        def get_selected_map_id(self) -> str | None:
            """Return the active map identifier."""
            ...

    def set_cached_items(self, entities: list[Any], events: list[Any]) -> None:
        """Store entity and event snapshots for map object pickers."""
        self._cached_entities = entities
        self._cached_events = events

    def _choose_map_object(self, title: str) -> MapObjectChoice | None:
        """Open the purpose-built picker and return its accepted choice."""
        dialog = MapObjectPickerDialog(
            getattr(self, "_cached_entities", []),
            getattr(self, "_cached_events", []),
            cast(QWidget, self),
            title,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.choice()

    def _select_or_create_object(
        self, dialog_title: str, dialog_label: str
    ) -> tuple[str, str, str] | None:
        """Select or create an object for path and region feature workflows."""
        del dialog_label
        choice = self._choose_map_object(dialog_title)
        if choice is None:
            return None
        if choice.action == "existing":
            return choice.object_id, choice.object_type, choice.name

        new_id = str(uuid.uuid4())
        if choice.object_type == "entity":
            self.create_entity_requested.emit(
                new_id, choice.name, choice.entity_type
            )
        else:
            self.create_event_requested.emit(new_id, choice.name)
        return new_id, choice.object_type, choice.name

    @Slot()
    def _on_create_map_clicked(self) -> None:
        """Show file and name dialogs, then emit ``map_created``."""
        file_path, _ = QFileDialog.getOpenFileName(
            cast(QWidget, self), "Select Map Image", "", IMAGE_FILE_FILTER
        )
        if not file_path:
            return
        name, ok = QInputDialog.getText(
            cast(QWidget, self), "New Map", "Map Name:"
        )
        if ok and name.strip():
            self.map_created.emit(file_path, name.strip())

    @Slot()
    def _on_delete_map_clicked(self) -> None:
        """Confirm deletion and emit ``map_deleted``."""
        map_id = self.map_selector.currentData()
        if not map_id:
            return
        confirm = QMessageBox.question(
            cast(QWidget, self),
            "Delete Map",
            "Are you sure you want to delete this map and all its markers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.map_deleted.emit(map_id)

    @Slot(float, float)
    def _on_create_marker_requested(self, x: float, y: float) -> None:
        """Place an existing object or request atomic object-marker creation."""
        map_id = self.get_selected_map_id()
        if not map_id:
            QMessageBox.warning(
                cast(QWidget, self),
                "No Map",
                "Please create or select a map first.",
            )
            return

        choice = self._choose_map_object("Add Marker Here")
        if choice is None:
            return
        if choice.action == "existing":
            self.marker_created.emit(
                map_id,
                choice.object_id,
                choice.object_type,
                choice.name,
                x,
                y,
            )
            return

        new_id = str(uuid.uuid4())
        self.marker_object_creation_requested.emit(
            map_id,
            new_id,
            choice.object_type,
            choice.name,
            choice.entity_type,
            x,
            y,
        )
        logger.info(
            "Requested atomic %s and marker creation for '%s' (%s)",
            choice.object_type,
            choice.name,
            new_id,
        )

    @Slot(str)
    def _on_delete_marker_requested(self, marker_id: str) -> None:
        """Confirm marker removal and emit ``marker_delete_confirmed``."""
        confirm = QMessageBox.question(
            cast(QWidget, self),
            "Delete Marker",
            "Remove this marker?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.marker_delete_confirmed.emit(marker_id)
