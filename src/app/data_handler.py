"""
Data Handler Module.

Handles data loading and UI updates for MainWindow.
Separates data management logic from the main window class.
"""

import logging
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QMetaObject, Qt as QtCore_Qt, Q_ARG

from src.commands.base_command import CommandResult

logger = logging.getLogger(__name__)


class DataHandler(QObject):
    """
    Manages data loading and UI updates.
    
    Handles:
    - Loading events, entities, maps, and longform sequences
    - Updating UI components with loaded data
    - Managing pending selections after creation
    - Editor suggestion updates
    """

    def __init__(self, main_window):
        """
        Initialize the data handler.
        
        Args:
            main_window: Reference to the MainWindow instance.
        """
        super().__init__()
        self.window = main_window
        logger.debug("DataHandler initialized")

    @Slot(list)
    def on_events_loaded(self, events):
        """
        Updates the UI with the loaded events.
        
        Args:
            events: List of Event objects.
        """
        self.window._cached_events = events
        self.window.unified_list.set_data(
            self.window._cached_events, 
            self.window._cached_entities
        )
        self.window.timeline.set_events(events)
        self.window.status_bar.showMessage(f"Loaded {len(events)} events.")
        self._update_editor_suggestions()

        if (self.window._pending_select_type == "event" and 
            self.window._pending_select_id):
            self.window.unified_list.select_item(
                "event", 
                self.window._pending_select_id
            )
            self.window._pending_select_type = None
            self.window._pending_select_id = None

    @Slot(list)
    def on_entities_loaded(self, entities):
        """
        Updates the UI with loaded entities.
        
        Args:
            entities: List of Entity objects.
        """
        self.window._cached_entities = entities
        self.window.unified_list.set_data(
            self.window._cached_events, 
            self.window._cached_entities
        )
        self.window.status_bar.showMessage(f"Loaded {len(entities)} entities.")
        self._update_editor_suggestions()

        if (self.window._pending_select_type == "entity" and 
            self.window._pending_select_id):
            self.window.unified_list.select_item(
                "entity", 
                self.window._pending_select_id
            )
            self.window._pending_select_type = None
            self.window._pending_select_id = None

    def _update_editor_suggestions(self):
        """
        Update editor completers with Event and Entity names.

        Aggregates all Event and Entity names with IDs and updates
        the editors' completers. Provides ID-based completion for
        robust wiki-linking.
        """
        items = []

        # Add entities: (id, name, type)
        if self.window._cached_entities:
            for entity in self.window._cached_entities:
                items.append((entity.id, entity.name, "entity"))

        # Add events: (id, name, type)
        if self.window._cached_events:
            for event in self.window._cached_events:
                items.append((event.id, event.name, "event"))

        # Sort by name for better UX
        items.sort(key=lambda x: x[1].lower())

        # Update editors with ID-based completion
        self.window.event_editor.update_suggestions(items=items)
        self.window.entity_editor.update_suggestions(items=items)

    @Slot(object, list, list)
    def on_event_details_loaded(self, event, relations, incoming):
        """
        Populates the Event Editor with detailed event data.

        Args:
            event: The event object.
            relations: Outgoing relations.
            incoming: Incoming relations.
        """
        self.window.ui_manager.docks["event"].raise_()
        self.window.event_editor.load_event(event, relations, incoming)

    @Slot(object, list, list)
    def on_entity_details_loaded(self, entity, relations, incoming):
        """
        Populates the Entity Editor with detailed entity data.

        Args:
            entity: The entity object.
            relations: Outgoing relations.
            incoming: Incoming relations.
        """
        self.window.ui_manager.docks["entity"].raise_()
        self.window.entity_editor.load_entity(entity, relations, incoming)

    @Slot(list)
    def on_longform_sequence_loaded(self, sequence):
        """
        Updates the longform editor with the loaded sequence.

        Args:
            sequence: List of longform items.
        """
        self.window._cached_longform_sequence = sequence
        self.window.longform_editor.load_sequence(sequence)
        self.window.status_bar.showMessage(
            f"Loaded {len(sequence)} longform items."
        )

    @Slot(list)
    def on_maps_loaded(self, maps):
        """
        Updates the map widget with the loaded maps.

        Args:
            maps: List of Map objects.
        """
        self.window.map_widget.set_maps(maps)
        self.window.status_bar.showMessage(f"Loaded {len(maps)} maps.")
        
        # Auto-select first map if none selected
        if maps:
            current_id = self.window.map_widget.map_selector.currentData()
            if not current_id:
                self.window.map_widget.select_map(maps[0].id)

    @Slot(str, list)
    def on_markers_loaded(self, map_id, markers):
        """
        Updates the map widget with markers for a specific map.

        Args:
            map_id: The map ID.
            markers: List of Marker objects.
        """
        # Verify we are still looking at this map
        current_map_id = self.window.map_widget.map_selector.currentData()
        if current_map_id != map_id:
            return

        self.window.map_widget.clear_markers()
        self.window._marker_object_to_id.clear()  # Reset mapping
        
        for marker in markers:
            # Determine label from cached data
            label = "Unknown"
            if marker.object_type == "entity" and self.window._cached_entities:
                entity = next(
                    (e for e in self.window._cached_entities 
                     if e.id == marker.object_id), 
                    None
                )
                if entity:
                    label = entity.name
            elif marker.object_type == "event" and self.window._cached_events:
                event = next(
                    (e for e in self.window._cached_events 
                     if e.id == marker.object_id), 
                    None
                )
                if event:
                    label = event.name
            
            # Add marker to map
            self.window.map_widget.add_marker(
                marker.x,
                marker.y,
                label,
                icon_name=marker.attributes.get("icon"),
                color=marker.attributes.get("color"),
            )
            
            # Store mapping for later updates
            self.window._marker_object_to_id[(marker.object_id, marker.object_type)] = marker.id

    @Slot(object)
    def on_command_finished(self, result):
        """
        Handles completion of async commands, triggering necessary UI refreshes.

        Args:
            result: CommandResult object containing execution status.
        """
        if not isinstance(result, CommandResult):
            return

        command_name = result.command_name
        success = result.success
        message = result.message

        # Determine what to reload based on command
        if not success:
            if message:
                QMessageBox.warning(
                    self.window, 
                    "Command Failed", 
                    message
                )
            return

        if command_name == "CreateEventCommand" and result.data.get("id"):
            self.window._pending_select_type = "event"
            self.window._pending_select_id = result.data["id"]
        elif command_name == "CreateEntityCommand" and result.data.get("id"):
            self.window._pending_select_type = "entity"
            self.window._pending_select_id = result.data["id"]

        if "Map" in command_name:
            self.window.load_maps()

        if "Marker" in command_name and "Update" not in command_name:
            current_map_id = self.window.map_widget.map_selector.currentData()
            if current_map_id:
                QMetaObject.invokeMethod(
                    self.window.worker,
                    "load_markers",
                    QtCore_Qt.QueuedConnection,
                    Q_ARG(str, current_map_id),
                )

        if "Event" in command_name:
            self.window.load_events()
        if "Entity" in command_name:
            self.window.load_entities()
        if "Relation" in command_name:
            if self.window.event_editor._current_event_id:
                self.window.load_event_details(
                    self.window.event_editor._current_event_id
                )
            if self.window.entity_editor._current_entity_id:
                self.window.load_entity_details(
                    self.window.entity_editor._current_entity_id
                )

        if "WikiLinks" in command_name:
            if self.window.event_editor._current_event_id:
                self.window.load_event_details(
                    self.window.event_editor._current_event_id
                )
            if self.window.entity_editor._current_entity_id:
                self.window.load_entity_details(
                    self.window.entity_editor._current_entity_id
                )

        if "Longform" in command_name:
            self.window.load_longform_sequence()
