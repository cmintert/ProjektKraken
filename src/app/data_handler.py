"""Data Handler Module.

Handles data loading and UI updates for MainWindow. Separates data management logic from
the main window class.
"""

import logging
from typing import Any, Iterable, List, Optional, Tuple, cast

from PySide6.QtCore import QObject, Signal, Slot

from src.commands.base_command import CommandResult
from src.core.entities import Entity
from src.core.events import Event

logger = logging.getLogger(__name__)

_INDEX_COMMANDS = {
    "CreateEventCommand": "event",
    "UpdateEventCommand": "event",
    "CreateEntityCommand": "entity",
    "UpdateEntityCommand": "entity",
}


class DataHandler(QObject):
    """Manages data loading and emits signals for UI updates.

    This class follows the principle of loose coupling by emitting signals
    rather than directly manipulating UI components. The MainWindow is
    responsible for connecting to these signals and updating its own widgets.

    Thread Safety:
        This class runs in the main (GUI) thread. All slot methods are connected
        to worker signals via QueuedConnection, which ensures that slot execution
        happens in the main thread even though signals are emitted from the worker
        thread. The cached data (_cached_events, _cached_entities) is safely
        accessed because:
        1. Slots run in the main thread (via QueuedConnection)
        2. All data access happens within these slots
        3. No concurrent access occurs between threads

        IMPORTANT: This class must remain in the main thread. If ever moved to
        another thread, thread safety guarantees would be violated.

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
    trajectories_ready = Signal(str, list)  # (map_id, trajectory snapshots)
    feature_geometry_states_ready = Signal(str, list)
    entity_state_resolved = Signal(str, dict)  # (entity_id, attributes)
    graph_data_ready = Signal(list, list)  # (nodes, edges)
    graph_metadata_ready = Signal(list, list)  # (tags, rel_types)
    graph_lexicon_ready = Signal(dict, dict)  # (raw_lexicon, resolved_lexicon)

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
    reload_markers_for_current_map = Signal()  # For when map_id is unknown
    reload_event_details = Signal(str)  # (event_id)
    reload_entity_details = Signal(str)  # (entity_id)
    reload_longform = Signal()
    reload_active_editor_relations = Signal()  # Reload relations for active editor

    # Auto-index: emitted when an entity/event is saved and should be re-embedded
    index_object_requested = Signal(str, str)  # (object_type, object_id)

    def __init__(self) -> None:
        """Initialize the data handler.

        Note: No longer requires MainWindow reference - uses signals instead.
        """
        super().__init__()

        # Thread safety assertion: DataHandler must run in the main GUI thread
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            main_thread = app.thread()
            current_thread = QThread.currentThread()
            if current_thread != main_thread:
                raise RuntimeError(
                    f"DataHandler must be created in the main thread. "
                    f"Current thread: {current_thread}, Main thread: {main_thread}"
                )

        self._cached_events: List[Event] = []
        self._cached_entities: List[Entity] = []
        self._pending_select_type: Optional[str] = None
        self._pending_select_id: Optional[str] = None
        self._reload_markers_after_events = False
        self._reload_markers_after_entities = False
        logger.debug("DataHandler initialized")

    @Slot(list)
    def on_events_loaded(self, events: List[Event]) -> None:
        """Processes loaded events and emits signals for UI updates.

        Args:
            events: List of Event objects.

        """
        self._cached_events = events
        self.events_ready.emit(events)
        self.status_message.emit(f"Loaded {len(events)} events.")
        self._update_editor_suggestions()

        if self._reload_markers_after_events:
            self._reload_markers_after_events = False
            self.reload_markers_for_current_map.emit()

        if self._pending_select_type == "event" and self._pending_select_id:
            self.selection_requested.emit("event", self._pending_select_id)
            self._pending_select_type = None
            self._pending_select_id = None

    @Slot(list)
    def on_entities_loaded(self, entities: List[Entity]) -> None:
        """Processes loaded entities and emits signals for UI updates.

        Args:
            entities: List of Entity objects.

        """
        self._cached_entities = entities
        self.entities_ready.emit(entities)
        self.status_message.emit(f"Loaded {len(entities)} entities.")
        self._update_editor_suggestions()

        if self._reload_markers_after_entities:
            self._reload_markers_after_entities = False
            self.reload_markers_for_current_map.emit()

        if self._pending_select_type == "entity" and self._pending_select_id:
            self.selection_requested.emit("entity", self._pending_select_id)
            self._pending_select_type = None
            self._pending_select_id = None

    def _update_editor_suggestions(self) -> None:
        """Update editor completers with Event and Entity names.

        Aggregates all Event and Entity names with IDs and emits signal for the editors'
        completers to be updated. Provides ID-based completion for robust wiki-linking.
        """
        items: List[Tuple[str, str, str]] = []

        # Add entities: (id, name, type)
        if self._cached_entities:
            items.extend(
                (entity.id, entity.name, "entity") for entity in self._cached_entities
            )

        # Add events: (id, name, type)
        if self._cached_events:
            items.extend(
                (event.id, event.name, "event") for event in self._cached_events
            )

        # Sort by name for better UX
        items.sort(key=lambda x: x[1].lower())

        # Emit signal for editors to update
        self.suggestions_update_requested.emit(items)

    @Slot(object, list, list)
    def on_event_details_loaded(
        self, event: Event, relations: List[Any], incoming: List[Any]
    ) -> None:
        """Emits signals for Event Editor to be populated with detailed event data.

        Args:
            event: The event object.
            relations: Outgoing relations.
            incoming: Incoming relations.

        """
        # Dock raising is now handled by the Controller (MainWindow) via user actions,
        # not automatically on data load. This prevents focus stealing during
        # background refreshes.
        self.event_details_ready.emit(event, relations, incoming)

    @Slot(object, list, list)
    def on_entity_details_loaded(
        self, entity: Entity, relations: List[Any], incoming: List[Any]
    ) -> None:
        """Emits signals for Entity Editor to be populated with detailed entity data.

        Args:
            entity: The entity object.
            relations: Outgoing relations.
            incoming: Incoming relations.

        """
        # Dock raising is now handled by the Controller (MainWindow) via user actions.
        self.entity_details_ready.emit(entity, relations, incoming)

    @Slot(list)
    def on_longform_sequence_loaded(self, sequence: List[Any]) -> None:
        """Emits signal for longform editor to be updated with the loaded sequence.

        Args:
            sequence: List of longform items.

        """
        self.longform_sequence_ready.emit(sequence)
        self.status_message.emit(f"Loaded {len(sequence)} longform items.")

    @Slot(list)
    def on_maps_loaded(self, maps: List[Any]) -> None:
        """Emits signal for map widget to be updated with the loaded maps.

        Args:
            maps: List of Map objects.

        """
        self.maps_ready.emit(maps)
        self.status_message.emit(f"Loaded {len(maps)} maps.")

    @Slot(str, list)
    def on_markers_loaded(self, map_id: str, markers: List[Any]) -> None:
        """Emits signal for map widget to be updated with markers for a specific map.

        Args:
            map_id: The map ID.
            markers: List of Marker objects.

        """
        # Process markers to add labels and summaries from cached data
        processed_markers = []
        for marker in markers:
            # Determine label and summary from cached data
            label = "Unknown"
            summary = ""
            lore_date = None

            if marker.object_type == "entity" and self._cached_entities:
                if entity := next(
                    (e for e in self._cached_entities if e.id == marker.object_id),
                    None,
                ):
                    label = getattr(entity, "name", "Unknown Entity")
                    summary = self._marker_summary(entity)
                    # Entities don't have a single specific date usually,
                    # but could check attributes if needed. For now None.
                    lore_date = None

            elif marker.object_type == "event" and self._cached_events:
                if event := next(
                    (e for e in self._cached_events if e.id == marker.object_id),
                    None,
                ):
                    label = getattr(event, "name", "Unknown Event")
                    summary = self._marker_summary(event)
                    lore_date = getattr(event, "lore_date", None)

            # Create marker data dict
            # Prefer ``_v_fill`` over the legacy ``color`` key
            fill_color = marker.attributes.get("_v_fill") or marker.attributes.get(
                "color"
            )
            processed_markers.append(
                {
                    "id": marker.id,
                    "map_id": marker.map_id,
                    "object_id": marker.object_id,
                    "object_type": marker.object_type,
                    "label": label,
                    "summary": summary,
                    "x": marker.x,
                    "y": marker.y,
                    "icon": marker.attributes.get("icon"),
                    "color": fill_color,
                    "lore_date": lore_date,
                    "feature_type": getattr(marker, "feature_type", "point"),
                    "geometry": getattr(marker, "geometry", None),
                    "style": getattr(marker, "style", None),
                    "attributes": marker.attributes,
                    "connection_count": getattr(marker, "connection_count", 0),
                }
            )

        self.markers_ready.emit(map_id, processed_markers)

    @staticmethod
    def _marker_summary(item: Any) -> str:
        """Return an item's stored summary text for use in map tooltips."""
        attributes = getattr(item, "attributes", {})
        if not isinstance(attributes, dict):
            return ""

        summary_data = attributes.get("_summary_data")
        if not isinstance(summary_data, dict):
            return ""

        text = summary_data.get("text")
        return text.strip() if isinstance(text, str) else ""

    def _reload_lore_cache_then_markers(self, object_type: str) -> None:
        """Reload lore data before rebuilding marker tooltip content."""
        if object_type == "event":
            self._reload_markers_after_events = True
            self.reload_events.emit()
        elif object_type == "entity":
            self._reload_markers_after_entities = True
            self.reload_entities.emit()
        else:
            logger.warning("Unknown lore object type for reload: %s", object_type)
            return

        self.reload_longform.emit()

    @Slot(str, list)
    def on_trajectories_loaded(
        self, map_id: str, trajectories: List[Any]
    ) -> None:
        """Forward map-scoped serializable trajectory snapshots."""
        self.trajectories_ready.emit(map_id, trajectories)

    @Slot(str, list)
    def on_feature_geometry_states_loaded(
        self, map_id: str, states: List[Any]
    ) -> None:
        """Forward map-scoped dated geometry snapshots."""
        self.feature_geometry_states_ready.emit(map_id, states)

    @Slot(CommandResult)
    def on_command_finished(self, result: CommandResult) -> None:  # noqa: C901
        """Handles completion of async commands, emitting signals for necessary UI
        refreshes.

        Args:
            result: CommandResult object containing execution status.

        """
        logger.info(
            f"[DataHandler] on_command_finished: {result.command_name} "
            f"success={result.success}"
        )

        if not isinstance(result, CommandResult):
            logger.warning("[DataHandler] Received non-CommandResult object")
            return

        command_name = result.command_name
        success = result.success
        message = result.message

        # Determine what to reload based on command
        if not success:
            logger.warning(f"[DataHandler] Command failed: {message}")
            if message:
                # Emit failure signal for MainWindow to show dialog
                self.command_failed.emit(message)
            return

        try:
            if command_name in {
                "UpdateTrajectoryCommand",
                "Undo_UpdateTrajectoryCommand",
                "Redo_UpdateTrajectoryCommand",
            }:
                # Direct trajectory editing owns one map-scoped reload after
                # persistence; generic undo reloads would duplicate it.
                return

            if command_name == "CreateEventCommand" and result.data.get("id"):
                self._pending_select_type = "event"
                self._pending_select_id = cast(str, result.data["id"])
            elif command_name == "CreateEntityCommand" and result.data.get("id"):
                self._pending_select_type = "entity"
                self._pending_select_id = cast(str, result.data["id"])

            # These layer/map commands only update metadata that is already
            # applied optimistically in the UI — a full map+marker+raster
            # teardown-and-reload would cause a visible blank flash with no
            # benefit, so we skip the reload_maps trigger for them.
            _NO_RELOAD_LAYER_CMDS = {
                "SetLayerOpacityCommand",
                "SaveLayerTreeCommand",
                "SetLayerVisibilityCommand",
                # Raster metadata: visual already updated via update_display /
                # set_blend_mode before the command is emitted.
                "SetRasterBlendModeCommand",
                "SetRasterNotesCommand",
            }
            if (
                "Map" in command_name or "Layer" in command_name
            ) and command_name not in _NO_RELOAD_LAYER_CMDS:
                logger.debug("[DataHandler] Emitting reload_maps")
                self.reload_maps.emit()
            if command_name in {
                "SetRasterSnapshotCommand",
                "RemoveRasterSnapshotCommand",
            }:
                logger.debug("[DataHandler] Reloading dated raster state")
                self.reload_maps.emit()

            if command_name == "RenameLayerCommand":
                logger.debug(
                    "[DataHandler] Emitting lore reloads for RenameLayerCommand"
                )
                self.reload_entities.emit()
                self.reload_events.emit()
                self.reload_markers_for_current_map.emit()

            # Full reload on any UNDO operation to ensure UI consistency
            is_undo_operation = command_name.startswith("Undo_")
            if is_undo_operation:
                logger.debug("[DataHandler] UNDO detected - full reload")
                self.reload_events.emit()
                self.reload_entities.emit()
                self.reload_active_editor_relations.emit()
                self.reload_markers_for_current_map.emit()
                self.reload_maps.emit()
                return  # Skip normal per-command logic for undo

            # Reload markers for creation/deletion (but not normal updates)
            is_update_operation = "Update" in command_name
            if "Marker" in command_name and not is_update_operation:
                logger.debug("[DataHandler] Emitting reload_markers_for_current_map")
                self.reload_markers_for_current_map.emit()

            # Visual attribute/colour changes also need a marker reload
            # so the map re-reads updated attributes from the DB.
            _MARKER_VISUAL_CMDS = {
                "UpdateMarkerAttributeCommand",
                "UpdateMarkerColorCommand",
                "UpdateMarkerIconCommand",
            }
            if command_name in _MARKER_VISUAL_CMDS:
                logger.debug(
                    "[DataHandler] Emitting reload_markers_for_current_map "
                    "(visual update)"
                )
                self.reload_markers_for_current_map.emit()

            if "Event" in command_name:
                logger.debug(
                    "[DataHandler] Reloading event cache before map markers"
                )
                self._reload_lore_cache_then_markers("event")

            if "Entity" in command_name:
                logger.debug(
                    "[DataHandler] Reloading entity cache before map markers"
                )
                self._reload_lore_cache_then_markers("entity")
            if "Relation" in command_name or "WikiLinks" in command_name:
                logger.debug(
                    "[DataHandler] Emitting reload signals (WikiLinks/Relation)"
                )
                self.reload_active_editor_relations.emit()
                self.reload_events.emit()
                self.reload_entities.emit()

            if "Longform" in command_name:
                logger.debug("[DataHandler] Emitting reload_longform")
                self.reload_longform.emit()

            # Re-embed after saves so the semantic index stays fresh
            if command_name in _INDEX_COMMANDS and result.data:
                obj_id = result.data.get("id")
                if obj_id:
                    obj_type = _INDEX_COMMANDS[command_name]
                    self.index_object_requested.emit(obj_type, obj_id)

            # CompositeCommand wraps Update* + ProcessWikiLinksCommand; inspect
            # the worker-produced serializable request. The object fallback is
            # retained only for compatibility with older callers and tests.
            if command_name == "CompositeCommand":
                requests = list(
                    cast(
                        Iterable[dict[str, object]],
                        result.data.get("index_requests", []),
                    )
                )
                if requests:
                    request = requests[0]
                    object_type = str(request["object_type"])
                    self.index_object_requested.emit(
                        object_type,
                        str(request["object_id"]),
                    )
                    self._reload_lore_cache_then_markers(object_type)
                else:
                    cmd_obj = result.data.get("command")
                    for sub in getattr(cmd_obj, "commands", []):
                        sub_name = sub.__class__.__name__
                        if sub_name in _INDEX_COMMANDS:
                            obj_id = getattr(sub, "entity_id", None) or getattr(
                                sub, "event_id", None
                            )
                            if obj_id:
                                object_type = _INDEX_COMMANDS[sub_name]
                                self.index_object_requested.emit(
                                    object_type, obj_id
                                )
                                self._reload_lore_cache_then_markers(object_type)
                                break

            logger.debug(f"[DataHandler] on_command_finished completed: {command_name}")

        except Exception as e:
            logger.error(f"[DataHandler] Exception in on_command_finished: {e}")

    @Slot(str, dict)
    def on_entity_state_resolved(self, entity_id: str, attributes: dict) -> None:
        """Emits signal when entity state is resolved."""
        self.entity_state_resolved.emit(entity_id, attributes)

    @Slot(list, list)
    def on_graph_data_loaded(self, nodes: List[Any], edges: List[Any]) -> None:
        """Emits signal for graph widget to be updated with loaded data.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.

        """
        self.graph_data_ready.emit(nodes, edges)
        self.status_message.emit(f"Loaded {len(nodes)} nodes and {len(edges)} edges.")

    @Slot(list, list)
    def on_graph_metadata_loaded(self, tags: List[str], rel_types: List[str]) -> None:
        """Emits signal for graph widget to be updated with metadata.

        Args:
            tags: List of tag strings.
            rel_types: List of relation type strings.

        """
        self.graph_metadata_ready.emit(tags, rel_types)

    @Slot(dict, dict)
    def on_graph_lexicon_loaded(
        self, raw_lexicon: dict, resolved_lexicon: dict
    ) -> None:
        """Emits signal for graph widget to apply visual lexicon styles.

        Args:
            raw_lexicon: Raw lexicon config with file paths.
            resolved_lexicon: Resolved lexicon with Base64 data URIs.

        """
        self.graph_lexicon_ready.emit(raw_lexicon, resolved_lexicon)
