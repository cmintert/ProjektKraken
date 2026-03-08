"""Editor Coordinator Module.

Manages all editor-related operations extracted from MainWindow:
- CRUD operations for events, entities, and relations
- Unsaved changes prompts and dirty state tracking
- Inline creation from map widgets
- Toast notifications for drag-drop relations
"""

import logging
from typing import TYPE_CHECKING, Dict, Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget

from src.app.coordinators.base_coordinator import BaseCoordinator
from src.commands.composite_command import CompositeCommand
from src.commands.entity_commands import (
    CreateEntityCommand,
    DeleteEntityCommand,
    UpdateEntityCommand,
)
from src.commands.event_commands import (
    CreateEventCommand,
    DeleteEventCommand,
    UpdateEventCommand,
)
from src.commands.relation_commands import (
    AddRelationCommand,
    RemoveRelationCommand,
    UpdateRelationCommand,
)
from src.commands.wiki_commands import ProcessWikiLinksCommand

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class EditorCoordinator(BaseCoordinator):
    """Coordinates editor CRUD operations and relation management.

    Handles:
    - Creating, updating, and deleting events and entities
    - Adding, removing, and updating relations
    - Unsaved changes prompts
    - Editor dirty state tracking (dock title asterisk)
    - Inline creation from map widgets
    - Toast notifications for relation creation
    """

    command_requested = Signal(object)

    def __init__(self, main_window: "MainWindow") -> None:
        """Initialize the editor coordinator.

        Args:
            main_window: The main window instance.

        """
        super().__init__(main_window)
        self._last_drag_drop_command_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Create Operations
    # ------------------------------------------------------------------

    def create_event(self) -> None:
        """Creates a new event by prompting for a name and emitting a command."""
        if not self.check_unsaved_changes(self.main_window.event_editor):
            return

        name, ok = QInputDialog.getText(self.main_window, "New Event", "Event Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEventCommand({"name": name.strip(), "lore_date": 0.0})
        self.command_requested.emit(cmd)

    def create_entity(self) -> None:
        """Creates a new entity by prompting for a name and emitting a command."""
        if not self.check_unsaved_changes(self.main_window.entity_editor):
            return

        name, ok = QInputDialog.getText(self.main_window, "New Entity", "Entity Name:")
        if not ok or not name.strip():
            return

        cmd = CreateEntityCommand({"name": name.strip(), "type": "Concept"})
        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Delete Operations
    # ------------------------------------------------------------------

    def delete_event(self, event_id: str) -> None:
        """Deletes an event by emitting a delete command.

        Args:
            event_id: The ID of the event to delete.

        """
        cmd = DeleteEventCommand(event_id)
        self.command_requested.emit(cmd)

    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity, warning if it has raster layer references.

        Checks the in-memory ``maps_data`` for any raster layer mappings
        that reference *entity_id*.  If found, shows a warning dialog with
        three options: remove references and delete, delete anyway, or cancel.

        Args:
            entity_id: The ID of the entity to delete.

        """
        from src.commands.raster_commands import SetRasterMappingCommand
        from src.gui.dialogs.raster_orphan_warning_dialog import (
            RasterOrphanWarningDialog,
        )
        from src.gui.widgets.map.raster_mapping import check_entity_raster_refs

        maps_data = []
        try:
            maps_data = self.main_window.map_handler._map_widget.maps_data or []
        except AttributeError:
            pass

        refs = check_entity_raster_refs(entity_id, maps_data)

        if refs:
            map_names: Dict[str, str] = {
                m.id: getattr(m, "name", m.id) for m in maps_data
            }
            dlg = RasterOrphanWarningDialog(
                entity_name=entity_id,
                refs=refs,
                map_names=map_names,
                parent=self.main_window,
            )
            dlg.exec()

            if dlg.result_action == "cancel":
                return

            if dlg.result_action == "remove_and_delete":
                processed_nodes: set = set()
                for ref in refs:
                    if ref.node_id in processed_nodes:
                        continue
                    processed_nodes.add(ref.node_id)
                    map_obj = next(
                        (m for m in maps_data if m.id == ref.map_id), None
                    )
                    if map_obj is None:
                        continue
                    raster_layers = (map_obj.attributes or {}).get(
                        "raster_layers", []
                    )
                    layer = next(
                        (
                            la
                            for la in raster_layers
                            if la.get("node_id") == ref.node_id
                        ),
                        None,
                    )
                    if layer is None:
                        continue
                    old_vem = layer.get("value_entity_map", {})
                    new_vem = {
                        "mode": old_vem.get("mode", "exact") if isinstance(old_vem, dict) else "exact",
                        "mappings": [
                            m
                            for m in (old_vem.get("mappings", []) if isinstance(old_vem, dict) else [])
                            if m.get("entity_id") != entity_id
                        ],
                    }
                    cmd = SetRasterMappingCommand(
                        map_id=ref.map_id,
                        node_id=ref.node_id,
                        new_mapping=new_vem,
                        old_mapping=old_vem if isinstance(old_vem, dict) else {},
                    )
                    self.command_requested.emit(cmd)

        cmd = DeleteEntityCommand(entity_id)
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_item_delete_requested(self, item_type: str, item_id: str) -> None:
        """Routes deletion request to the appropriate delete method.

        Args:
            item_type: Type of item ("event" or "entity").
            item_id: ID of the item to delete.

        """
        if item_type == "event":
            self.delete_event(item_id)
        elif item_type == "entity":
            self.delete_entity(item_id)

    # ------------------------------------------------------------------
    # Update Operations
    # ------------------------------------------------------------------

    def update_event(self, event_data: dict) -> None:
        """Updates an event with the provided data.

        Automatically creates a CompositeCommand with wiki link processing
        if the data includes a description field.

        Args:
            event_data: Dictionary containing event data including 'id'.

        """
        event_id = event_data.get("id")
        logger.info(
            f"[EditorCoordinator] update_event: id={event_id}, "
            f"name='{event_data.get('name', '?')}'"
        )
        if not event_id:
            logger.error("[EditorCoordinator] update_event aborted - no ID")
            return

        cmds = []
        cmds.append(UpdateEventCommand(event_id, event_data))

        if "description" in event_data:
            wiki_cmd = ProcessWikiLinksCommand(event_id, event_data["description"])
            cmds.append(wiki_cmd)

        if len(cmds) > 1:
            desc = f"Update Event '{event_data.get('name', '?')}'"
            cmd = CompositeCommand(cmds, description=desc)
            logger.debug("[EditorCoordinator] Emitting CompositeCommand (Update+Wiki)")
        else:
            cmd = cmds[0]
            logger.debug(
                f"[EditorCoordinator] Emitting {cmd.__class__.__name__}"
            )

        self.command_requested.emit(cmd)

    def update_entity(self, entity_data: dict) -> None:
        """Updates an entity with the provided data.

        Automatically creates a CompositeCommand with wiki link processing
        if the data includes a description field.

        Args:
            entity_data: Dictionary containing entity data including 'id'.

        """
        entity_id = entity_data.get("id")
        logger.info(
            f"[EditorCoordinator] update_entity: id={entity_id}, "
            f"name='{entity_data.get('name', '?')}'"
        )
        if not entity_id:
            logger.error("[EditorCoordinator] update_entity aborted - no ID")
            return

        cmds = []
        cmds.append(UpdateEntityCommand(entity_id, entity_data))

        if "description" in entity_data:
            wiki_cmd = ProcessWikiLinksCommand(entity_id, entity_data["description"])
            cmds.append(wiki_cmd)

        if len(cmds) > 1:
            desc = f"Update Entity '{entity_data.get('name', '?')}'"
            cmd = CompositeCommand(cmds, description=desc)
            logger.debug(
                "[EditorCoordinator] Emitting CompositeCommand (Update+Wiki)"
            )
        else:
            cmd = cmds[0]
            logger.debug(
                f"[EditorCoordinator] Emitting {cmd.__class__.__name__}"
            )

        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Relation Operations
    # ------------------------------------------------------------------

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        attributes: dict = None,
        bidirectional: bool = False,
    ) -> None:
        """Adds a relation between entities.

        Args:
            source_id: The ID of the source entity.
            target_id: The ID of the target entity.
            rel_type: The type of relation.
            attributes: Optional attributes for the relation.
            bidirectional: Whether the relation is bidirectional.

        """
        cmd = AddRelationCommand(
            source_id,
            target_id,
            rel_type,
            attributes=attributes,
            bidirectional=bidirectional,
        )

        # Track for toast notification
        self._last_drag_drop_command_id = id(cmd)

        self.command_requested.emit(cmd)

    def remove_relation(self, rel_id: str) -> None:
        """Removes a relation by its ID.

        Args:
            rel_id: The ID of the relation to remove.

        """
        cmd = RemoveRelationCommand(rel_id)
        self.command_requested.emit(cmd)

    def update_relation(
        self, rel_id: str, target_id: str, rel_type: str, attributes: dict = None
    ) -> None:
        """Updates an existing relation.

        Args:
            rel_id: The ID of the relation to update.
            target_id: The new target entity ID.
            rel_type: The new relation type.
            attributes: Optional new attributes.

        """
        cmd = UpdateRelationCommand(rel_id, target_id, rel_type, attributes=attributes)
        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Editor State Management
    # ------------------------------------------------------------------

    def check_unsaved_changes(self, editor: QWidget) -> bool:
        """Checks if the editor has unsaved changes and prompts the user.

        Args:
            editor: The editor widget to check.

        Returns:
            True if safe to proceed (Saved, Discarded, or Clean).
            False if User Cancelled.

        """
        if (
            not hasattr(editor, "has_unsaved_changes")
            or not editor.has_unsaved_changes()
        ):
            return True

        # Determine readable name
        editor_name = "Item"
        if editor == self.main_window.event_editor:
            editor_name = "Event"
        elif editor == self.main_window.entity_editor:
            editor_name = "Entity"

        reply = QMessageBox.warning(
            self.main_window,
            "Unsaved Changes",
            f"You have unsaved changes in the {editor_name} Editor.\n"
            "Do you want to save them before proceeding?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Save:
            if hasattr(editor, "_on_save"):
                editor._on_save()
            return True
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def on_editor_dirty_changed(self, editor: QWidget, dirty: bool) -> None:
        """Updates the dock title with an asterisk if dirty.

        Args:
            editor: The editor widget that changed state.
            dirty: True if editor has unsaved changes.

        """
        dock_key = None
        base_title = ""

        if editor == self.main_window.event_editor:
            dock_key = "event"
            base_title = "Event Inspector"
        elif editor == self.main_window.entity_editor:
            dock_key = "entity"
            base_title = "Entity Inspector"

        if dock_key:
            if dock := self.main_window.ui_manager.docks.get(dock_key):
                new_title = base_title + (" *" if dirty else "")
                dock.setWindowTitle(new_title)

    # ------------------------------------------------------------------
    # Timeline / Map Integration
    # ------------------------------------------------------------------

    @Slot(str, float)
    def on_event_date_changed(self, event_id: str, new_lore_date: float) -> None:
        """Handles event date changes from timeline dragging.

        Args:
            event_id: The ID of the event that was dragged.
            new_lore_date: The new lore_date value.

        """
        logger.debug(f"Event {event_id} date changed to {new_lore_date}")
        cmd = UpdateEventCommand(event_id, {"lore_date": new_lore_date})
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_map_create_entity(self, new_id: str, name: str) -> None:
        """Handle inline entity creation from the map.

        Args:
            new_id: Pre-generated UUID for the new entity.
            name: Name of the new entity.

        """
        cmd = CreateEntityCommand({"id": new_id, "name": name, "type": "Location"})
        self.command_requested.emit(cmd)

    @Slot(str, str)
    def on_map_create_event(self, new_id: str, name: str) -> None:
        """Handle inline event creation from the map.

        Args:
            new_id: Pre-generated UUID for the new event.
            name: Name of the new event.

        """
        cmd = CreateEventCommand({"id": new_id, "name": name, "lore_date": 0.0})
        self.command_requested.emit(cmd)

    # ------------------------------------------------------------------
    # Toast Notifications
    # ------------------------------------------------------------------

    @Slot(object)
    def on_command_finished_check_toast(self, result: object) -> None:
        """Check if completed command was a drag-drop relation and show toast.

        Args:
            result: CommandResult object from worker.

        """
        if not result.success:
            return

        command = result.data.get("command")
        if command is None:
            return

        if id(command) == self._last_drag_drop_command_id:
            self._show_relation_created_toast()
            self._last_drag_drop_command_id = None

    def _show_relation_created_toast(self) -> None:
        """Show toast notification for successful relation creation."""
        from src.gui.widgets.auto_closing_message_box import AutoClosingMessageBox

        msg = "Relation created.\n\n(Ctrl+Z to Undo)"
        popup = AutoClosingMessageBox("Success", msg, 1500, parent=self.main_window)
        popup.exec()

        logger.debug("Drag-drop relation toast displayed")
