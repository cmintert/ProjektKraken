"""
Data Handler Module.

Handles data loading and UI updates for MainWindow.
Separates data management logic from the main window class.
"""

import logging

from PySide6.QtCore import QObject, Signal, Slot

from src.commands.base_command import CommandResult

logger = logging.getLogger(__name__)


class DataHandler(QObject):
    """
    Manages data loading and emits signals for UI updates.

    This class follows the principle of loose coupling by emitting signals
    rather than directly manipulating UI components. The MainWindow is
    responsible for connecting to these signals and updating its own widgets.

    Handles:
    - Processing loaded data (events, entities, maps, longform)
    - Emitting signals for UI updates
    - Managing pending selections after creation
    - Coordinating editor suggestion updates
    """

    # Signals for data updates
    events_ready = Signal(list)  # Emitted when events are processed
    entities_ready = Signal(list)  # Emitted when entities are processed
    suggestions_update_requested = Signal(list)  # (items: list of tuples)
    event_details_ready = Signal(object, list, list)  # (event, relations, incoming)
    entity_details_ready = Signal(object, list, list)  # (entity, relations, incoming)
    longform_sequence_ready = Signal(list)  # Emitted when longform data is processed
    maps_ready = Signal(list)  # Emitted when maps are processed
    markers_ready = Signal(str, list)  # (map_id, markers)

    # Signals for UI actions
    status_message = Signal(str)  # Status bar message updates
    command_failed = Signal(str)  # Command failure message
    dock_raise_requested = Signal(str)  # Request to raise a dock ("event", "entity")
    selection_requested = Signal(str, str)  # (item_type, item_id)

    # Signals for command-driven reloads
    reload_events = Signal()
    reload_entities = Signal()
    reload_maps = Signal()
    reload_markers = Signal(str)  # (map_id)
    reload_event_details = Signal(str)  # (event_id)
    reload_entity_details = Signal(str)  # (entity_id)
    reload_longform = Signal()
    reload_active_editor_relations = Signal()  # Reload relations for active editor

    def __init__(self):
        """
        Initialize the data handler.

        Note: No longer requires MainWindow reference - uses signals instead.
        """
        super().__init__()
        self._cached_events = []
        self._cached_entities = []
        self._pending_select_type = None
        self._pending_select_id = None
        logger.debug("DataHandler initialized")

    @Slot(list)
    def on_events_loaded(self, events):
        """
        Processes loaded events and emits signals for UI updates.

        Args:
            events: List of Event objects.
        """
        self._cached_events = events
        self.events_ready.emit(events)
        self.status_message.emit(f"Loaded {len(events)} events.")
        self._update_editor_suggestions()

        if self._pending_select_type == "event" and self._pending_select_id:
            self.selection_requested.emit("event", self._pending_select_id)
            self._pending_select_type = None
            self._pending_select_id = None

    @Slot(list)
    def on_entities_loaded(self, entities):
        """
        Processes loaded entities and emits signals for UI updates.

        Args:
            entities: List of Entity objects.
        """
        self._cached_entities = entities
        self.entities_ready.emit(entities)
        self.status_message.emit(f"Loaded {len(entities)} entities.")
        self._update_editor_suggestions()

        if self._pending_select_type == "entity" and self._pending_select_id:
            self.selection_requested.emit("entity", self._pending_select_id)
            self._pending_select_type = None
            self._pending_select_id = None

    def _update_editor_suggestions(self):
        """
        Update editor completers with Event and Entity names.

        Aggregates all Event and Entity names with IDs and emits
        signal for the editors' completers to be updated.
        Provides ID-based completion for robust wiki-linking.
        """
        items = []

        # Add entities: (id, name, type)
        if self._cached_entities:
            for entity in self._cached_entities:
                items.append((entity.id, entity.name, "entity"))

        # Add events: (id, name, type)
        if self._cached_events:
            for event in self._cached_events:
                items.append((event.id, event.name, "event"))

        # Sort by name for better UX
        items.sort(key=lambda x: x[1].lower())

        # Emit signal for editors to update
        self.suggestions_update_requested.emit(items)

    @Slot(object, list, list)
    def on_event_details_loaded(self, event, relations, incoming):
        """
        Emits signals for Event Editor to be populated with detailed event data.

        Args:
            event: The event object.
            relations: Outgoing relations.
            incoming: Incoming relations.
        """
        self.dock_raise_requested.emit("event")
        self.event_details_ready.emit(event, relations, incoming)

    @Slot(object, list, list)
    def on_entity_details_loaded(self, entity, relations, incoming):
        """
        Emits signals for Entity Editor to be populated with detailed entity data.

        Args:
            entity: The entity object.
            relations: Outgoing relations.
            incoming: Incoming relations.
        """
        self.dock_raise_requested.emit("entity")
        self.entity_details_ready.emit(entity, relations, incoming)

    @Slot(list)
    def on_longform_sequence_loaded(self, sequence):
        """
        Emits signal for longform editor to be updated with the loaded sequence.

        Args:
            sequence: List of longform items.
        """
        self.longform_sequence_ready.emit(sequence)
        self.status_message.emit(f"Loaded {len(sequence)} longform items.")

    @Slot(list)
    def on_maps_loaded(self, maps):
        """
        Emits signal for map widget to be updated with the loaded maps.

        Args:
            maps: List of Map objects.
        """
        self.maps_ready.emit(maps)
        self.status_message.emit(f"Loaded {len(maps)} maps.")

    @Slot(str, list)
    def on_markers_loaded(self, map_id, markers):
        """
        Emits signal for map widget to be updated with markers for a specific map.

        Args:
            map_id: The map ID.
            markers: List of Marker objects.
        """
        # Process markers to add labels from cached data
        processed_markers = []
        for marker in markers:
            # Determine label from cached data
            label = "Unknown"
            if marker.object_type == "entity" and self._cached_entities:
                entity = next(
                    (e for e in self._cached_entities if e.id == marker.object_id),
                    None,
                )
                if entity:
                    label = entity.name
            elif marker.object_type == "event" and self._cached_events:
                event = next(
                    (e for e in self._cached_events if e.id == marker.object_id),
                    None,
                )
                if event:
                    label = event.name

            # Create marker data dict
            processed_markers.append(
                {
                    "id": marker.id,
                    "object_id": marker.object_id,
                    "object_type": marker.object_type,
                    "label": label,
                    "x": marker.x,
                    "y": marker.y,
                    "icon": marker.attributes.get("icon"),
                    "color": marker.attributes.get("color"),
                }
            )

        self.markers_ready.emit(map_id, processed_markers)

    @Slot(object)
    def on_command_finished(self, result):
        """
        Handles completion of async commands, emitting signals for necessary UI refreshes.

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
                # Emit failure signal for MainWindow to show dialog
                self.command_failed.emit(message)
            return

        if command_name == "CreateEventCommand" and result.data.get("id"):
            self._pending_select_type = "event"
            self._pending_select_id = result.data["id"]
        elif command_name == "CreateEntityCommand" and result.data.get("id"):
            self._pending_select_type = "entity"
            self._pending_select_id = result.data["id"]

        if "Map" in command_name:
            self.reload_maps.emit()

        if "Marker" in command_name and "Update" not in command_name:
            # Emit signal to reload markers - MainWindow will determine current map
            # This is intentionally left as a pass - MainWindow handles it
            pass

        if "Event" in command_name:
            self.reload_events.emit()
        if "Entity" in command_name:
            self.reload_entities.emit()
        if "Relation" in command_name or "WikiLinks" in command_name:
            # Signal to reload editor relations if an editor is active
            self.reload_active_editor_relations.emit()

        if "Longform" in command_name:
            self.reload_longform.emit()
