"""Signal Connection Manager.

Handles all signal/slot connections for the MainWindow, organizing them by component
for better maintainability.

Connections are defined declaratively as tuples and processed in batch, reducing
boilerplate and making it easier to add or remove signal wiring.
"""

import logging
from typing import TYPE_CHECKING, Sequence, Tuple, Union

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from src.core.protocols import MainWindowProtocol

# Connection spec: (source_obj, signal_name, slot, description[, connection_type])
ConnectionSpec = Union[
    Tuple[object, str, callable, str],
    Tuple[object, str, callable, str, Qt.ConnectionType],
]

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages signal/slot connections between UI components.

    Separates connection logic from MainWindow to improve maintainability and reduce
    coupling.
    """

    def __init__(self, main_window: "MainWindowProtocol") -> None:
        """Initialize the connection manager.

        Args:
            main_window: Reference to the MainWindow instance.

        """
        self.window = main_window
        self._connection_stats = {"attempted": 0, "succeeded": 0, "failed": 0}
        logger.debug("ConnectionManager initialized")

    def _connect_signal_safe(
        self,
        obj: object,
        signal_name: str,
        slot: callable,
        obj_description: str = "",
        connection_type: Qt.ConnectionType = Qt.ConnectionType.AutoConnection,
    ) -> bool:
        """Safely connect a signal with validation and error handling.

        Args:
            obj: The object containing the signal.
            signal_name: Name of the signal attribute.
            slot: The slot (callable) to connect to.
            obj_description: Description of the object for logging.
            connection_type: Qt connection type (AutoConnection for same-thread,
                QueuedConnection for cross-thread). Defaults to AutoConnection.

        Returns:
            bool: True if connection successful, False otherwise.

        Note:
            Use Qt.ConnectionType.QueuedConnection for cross-thread connections
            (e.g., GUI widget to worker thread). This ensures thread-safe
            signal delivery via Qt's event queue.

        """
        self._connection_stats["attempted"] += 1

        try:
            # Validate object
            if obj is None:
                logger.warning(f"Cannot connect signal '{signal_name}': object is None")
                self._connection_stats["failed"] += 1
                return False

            # Check if object has the signal
            if not hasattr(obj, signal_name):
                logger.warning(
                    f"{obj_description or obj.__class__.__name__} does not have "
                    f"signal '{signal_name}'"
                )
                self._connection_stats["failed"] += 1
                return False

            # Get the signal
            signal = getattr(obj, signal_name)

            # Validate slot is callable
            if not callable(slot):
                logger.error(
                    f"Slot for {obj_description}.{signal_name} is not callable: "
                    f"{type(slot)}"
                )
                self._connection_stats["failed"] += 1
                return False

            # Attempt connection with specified connection type
            signal.connect(slot, connection_type)
            self._connection_stats["succeeded"] += 1
            logger.debug(
                f"Successfully connected {obj_description or obj.__class__.__name__}."
                f"{signal_name} (type: {connection_type.name})"
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to connect {obj_description}.{signal_name}: {e}")
            self._connection_stats["failed"] += 1
            return False

    def _connect_batch(
        self, specs: Sequence[ConnectionSpec], group_name: str
    ) -> int:
        """Connects a batch of signal/slot pairs from a declarative specification.

        Each spec is a tuple of ``(source, signal_name, slot, description)`` with an
        optional fifth element for ``Qt.ConnectionType``.

        Args:
            specs: Sequence of connection specifications.
            group_name: Human-readable label for logging (e.g., "DataHandler").

        Returns:
            Number of failed connections.

        """
        failed = 0
        for spec in specs:
            obj, signal_name, slot, desc = spec[:4]
            conn_type = (
                spec[4]
                if len(spec) > 4
                else Qt.ConnectionType.AutoConnection
            )
            if not self._connect_signal_safe(obj, signal_name, slot, desc, conn_type):
                failed += 1

        total = len(specs)
        logger.debug(
            f"{group_name} connections: {total - failed}/{total} succeeded, "
            f"{failed} failed"
        )
        return failed

    def connect_all(self) -> dict:
        """Connect all UI signals to their respective slots.

        Returns:
            dict: Connection statistics with keys 'total_attempted', 'total_succeeded',
                  'total_failed'.

        """
        # Reset stats
        self._connection_stats = {"attempted": 0, "succeeded": 0, "failed": 0}

        self.connect_data_handler()
        self.connect_unified_list()
        self.connect_editors()
        self.connect_timeline()
        self.connect_longform_editor()
        self.connect_map_widget()
        self.connect_ai_search_panel()
        self.connect_graph_widget()

        # Log summary
        logger.info(
            f"Signal connections complete: {self._connection_stats['succeeded']} "
            f"succeeded, {self._connection_stats['failed']} failed out of "
            f"{self._connection_stats['attempted']} attempted"
        )

        return {
            "total_attempted": self._connection_stats["attempted"],
            "total_succeeded": self._connection_stats["succeeded"],
            "total_failed": self._connection_stats["failed"],
        }

    def connect_data_handler(self) -> int:
        """Connect signals from the data handler."""
        dh = self.window.data_handler
        dc = self.window.data_coordinator
        return self._connect_batch([
            (dh, "events_ready", dc.on_events_ready, "DataHandler"),
            (dh, "entities_ready", dc.on_entities_ready, "DataHandler"),
            (dh, "suggestions_update_requested", dc.on_suggestions_update, "DataHandler"),
            (dh, "event_details_ready", dc.on_event_details_ready, "DataHandler"),
            (dh, "entity_details_ready", dc.on_entity_details_ready, "DataHandler"),
            (dh, "longform_sequence_ready", self.window.longform_manager.on_longform_sequence_loaded, "DataHandler"),
            (dh, "maps_ready", self.window.map_handler.on_maps_ready, "DataHandler"),
            (dh, "markers_ready", self.window.map_handler.on_markers_ready, "DataHandler"),
            (dh, "trajectories_ready", self.window.map_handler.on_trajectories_ready, "DataHandler"),
            (dh, "entity_state_resolved", self.window.time_coordinator.on_entity_state_resolved, "DataHandler"),
            (dh, "graph_data_ready", dc.on_graph_data_ready, "DataHandler"),
            (dh, "graph_metadata_ready", dc.on_graph_metadata_ready, "DataHandler"),
            (dh, "graph_lexicon_ready", dc.on_graph_lexicon_ready, "DataHandler"),
            (dh, "status_message", self.window.status_bar.showMessage, "DataHandler"),
            (dh, "command_failed", dc.on_command_failed, "DataHandler"),
            (dh, "dock_raise_requested", dc.on_dock_raise_requested, "DataHandler"),
            (dh, "selection_requested", dc.on_selection_requested, "DataHandler"),
            (dh, "reload_events", dc.load_events, "DataHandler"),
            (dh, "reload_entities", dc.load_entities, "DataHandler"),
            (dh, "reload_maps", self.window.load_maps, "DataHandler"),
            (dh, "reload_longform", self.window.longform_manager.load_longform_sequence, "DataHandler"),
            (dh, "reload_active_editor_relations", dc.on_reload_active_editor_relations, "DataHandler"),
            (dh, "reload_markers", self.window.map_handler.reload_markers, "DataHandler"),
            (dh, "reload_markers_for_current_map", self.window.map_handler.reload_markers_for_current_map, "DataHandler"),
        ], "DataHandler")

    def connect_unified_list(self) -> int:
        """Connect signals from the unified list widget."""
        ul = self.window.unified_list
        ec = self.window.editor_coordinator
        dc = self.window.data_coordinator
        specs: list[ConnectionSpec] = [
            (ul, "refresh_requested", dc.load_data, "UnifiedList"),
            (ul, "create_event_requested", ec.create_event, "UnifiedList"),
            (ul, "create_entity_requested", ec.create_entity, "UnifiedList"),
            (ul, "create_map_requested", self.window.map_widget._on_create_map_clicked, "UnifiedList"),
            (ul, "delete_requested", ec.on_item_delete_requested, "UnifiedList"),
            (ul, "item_selected", self.window.navigation_coordinator.on_item_selected, "UnifiedList"),
            (ul, "drag_started", self.window.navigation_coordinator.on_drag_started, "UnifiedList"),
        ]
        if hasattr(ul, "show_filter_dialog_requested"):
            specs.append((ul, "show_filter_dialog_requested", self.window.show_filter_dialog, "UnifiedList"))
        if hasattr(ul, "clear_filter_requested"):
            specs.append((ul, "clear_filter_requested", self.window.clear_filter, "UnifiedList"))
        if hasattr(ul, "status_message_requested"):
            specs.append((ul, "status_message_requested", self.window.status_bar.showMessage, "UnifiedList"))
        if hasattr(ul, "export_obsidian_requested"):
            specs.append((ul, "export_obsidian_requested", self.window.import_coordinator.export_single_obsidian, "UnifiedList"))
        return self._connect_batch(specs, "UnifiedList")

    def connect_editors(self) -> int:
        """Connect signals from event and entity editors."""
        ec = self.window.editor_coordinator
        dc = self.window.data_coordinator
        specs: list[ConnectionSpec] = []
        for editor in [self.window.event_editor, self.window.entity_editor]:
            editor_name = editor.__class__.__name__
            specs.extend([
                (editor, "add_relation_requested", ec.add_relation, editor_name),
                (editor, "remove_relation_requested", ec.remove_relation, editor_name),
                (editor, "update_relation_requested", ec.update_relation, editor_name),
                (editor, "link_clicked", self.window.navigation_coordinator.navigate_to_entity, editor_name),
                (editor, "navigate_to_relation", self.window.navigation_coordinator.navigate_to_entity, editor_name),
            ])
        specs.extend([
            (self.window.event_editor, "save_requested", ec.update_event, "EventEditor"),
            (self.window.entity_editor, "save_requested", ec.update_entity, "EntityEditor"),
            (self.window.entity_editor, "return_to_present_requested", self.window.time_coordinator.on_return_to_present, "EntityEditor"),
            (self.window.event_editor, "current_data_changed", self.window.timeline.update_event_preview, "EventEditor"),
            (self.window.event_editor, "discard_requested", dc.load_event_details, "EventEditor"),
            (self.window.entity_editor, "discard_requested", dc.load_entity_details, "EntityEditor"),
        ])
        return self._connect_batch(specs, "Editors")

    def connect_timeline(self) -> int:
        """Connect signals from the timeline widget."""
        timeline = self.window.timeline
        specs: list[ConnectionSpec] = [
            (timeline, "event_selected", self.window.data_coordinator.load_event_details, "Timeline"),
            (timeline, "create_event_requested", self.window.editor_coordinator.create_event, "Timeline"),
            (timeline, "current_time_changed", self.window.time_coordinator.on_current_time_changed, "Timeline"),
            (timeline, "playhead_time_changed", self.window.time_coordinator.update_playhead_time_label, "Timeline"),
            (timeline, "playhead_time_changed", self.window.time_coordinator.on_playhead_changed, "Timeline"),
            (timeline, "event_date_changed", self.window.editor_coordinator.on_event_date_changed, "Timeline"),
        ]
        if hasattr(timeline, "_band_manager") and timeline._band_manager:
            specs.extend([
                (timeline._band_manager, "tag_color_change_requested", self.window.grouping_manager.on_tag_color_change_requested, "Timeline.BandManager"),
                (timeline._band_manager, "remove_from_grouping_requested", self.window.grouping_manager.on_remove_from_grouping_requested, "Timeline.BandManager"),
            ])
        return self._connect_batch(specs, "Timeline")

    def connect_longform_editor(self) -> int:
        """Connect signals from the longform editor widget."""
        longform = self.window.longform_editor
        lm = self.window.longform_manager
        return self._connect_batch([
            (longform, "promote_requested", lm.promote_longform_entry, "LongformEditor"),
            (longform, "demote_requested", lm.demote_longform_entry, "LongformEditor"),
            (longform, "refresh_requested", lm.load_longform_sequence, "LongformEditor"),
            (longform, "export_requested", lm.export_longform_document, "LongformEditor"),
            (longform, "export_vault_requested", lm.export_as_vault, "LongformEditor"),
            (longform, "item_selected", self.window.navigation_coordinator.on_item_selected, "LongformEditor"),
            (longform, "item_moved", lm.move_longform_entry, "LongformEditor"),
            (longform, "delete_requested", lm.delete_longform_item, "LongformEditor"),
            (longform, "move_up_requested", lm.move_up_longform_entry, "LongformEditor"),
            (longform, "move_down_requested", lm.move_down_longform_entry, "LongformEditor"),
            (longform, "link_clicked", self.window.navigation_coordinator.navigate_to_entity, "LongformEditor"),
            (longform, "show_filter_dialog_requested", lm.show_longform_filter_dialog, "LongformEditor"),
            (longform, "clear_filters_requested", lm.clear_longform_filter, "LongformEditor"),
        ], "LongformEditor")

    def connect_map_widget(self) -> int:
        """Connect signals from the map widget."""
        map_widget = self.window.map_widget
        map_handler = self.window.map_handler
        timeline = self.window.timeline
        queued = Qt.ConnectionType.QueuedConnection
        return self._connect_batch([
            (map_widget, "marker_position_changed", map_handler.on_marker_position_changed, "MapWidget"),
            (map_widget, "map_scale_changed", map_handler.on_map_scale_changed, "MapWidget"),
            (map_widget, "marker_clicked", map_handler.on_marker_clicked, "MapWidget"),
            (map_widget, "map_created", map_handler.create_map, "MapWidget"),
            (map_widget, "map_deleted", map_handler.delete_map, "MapWidget"),
            (map_widget, "map_selected", map_handler.on_map_selected, "MapWidget"),
            (map_widget, "marker_created", map_handler.create_marker, "MapWidget"),
            (map_widget, "marker_delete_confirmed", map_handler.delete_marker, "MapWidget"),
            (map_widget, "change_marker_icon_requested", map_handler.on_marker_icon_changed, "MapWidget"),
            (map_widget, "change_marker_color_requested", map_handler.on_marker_color_changed, "MapWidget"),
            (map_widget, "marker_visual_style_changed", map_handler.on_marker_visual_style_changed, "MapWidget"),
            (map_widget, "marker_drop_requested", map_handler.on_marker_dropped, "MapWidget"),
            (map_widget, "feature_created", map_handler.on_feature_drawn, "MapWidget"),
            (map_widget, "feature_style_changed", map_handler.on_feature_style_changed, "MapWidget"),
            (map_widget, "feature_geometry_changed", map_handler.on_feature_geometry_changed, "MapWidget"),
            (timeline, "playhead_time_changed", map_widget.on_time_changed, "Timeline->MapWidget"),
            (timeline, "current_time_changed", map_widget.on_current_time_changed, "Timeline->MapWidget"),
            (map_widget, "add_keyframe_requested", self.window.worker.add_keyframe, "MapWidget", queued),
            (map_widget, "update_keyframe_time_requested", self.window.worker.update_keyframe_time, "MapWidget", queued),
            (map_widget, "delete_keyframe_requested", self.window.worker.delete_keyframe, "MapWidget", queued),
            (map_widget, "jump_to_time_requested", self.window.timeline.set_playhead_time, "MapWidget"),
            (map_widget, "layer_tree_changed", map_handler.on_layer_tree_changed, "MapWidget"),
            (map_widget, "layer_opacity_change_requested", map_handler.on_layer_opacity_changed, "MapWidget"),
            (map_widget, "layer_rename_requested", map_handler.on_layer_renamed, "MapWidget"),
            (map_widget, "layer_delete_feature_requested", map_handler.on_layer_feature_deleted, "MapWidget"),
            (map_widget, "create_entity_requested", self.window.editor_coordinator.on_map_create_entity, "MapWidget"),
            (map_widget, "create_event_requested", self.window.editor_coordinator.on_map_create_event, "MapWidget"),
        ], "MapWidget")

    def connect_ai_search_panel(self) -> int:
        """Connect signals from the AI search panel widget."""
        panel = self.window.ai_search_panel
        ai = self.window.ai_search_manager
        return self._connect_batch([
            (panel, "search_requested", ai.perform_semantic_search, "AISearchPanel"),
            (panel, "result_selected", ai.on_search_result_selected, "AISearchPanel"),
        ], "AISearchPanel")

    def connect_graph_widget(self) -> int:
        """Connect signals from the graph widget."""
        graph = self.window.graph_widget
        return self._connect_batch([
            (graph, "refresh_requested", self.window.data_coordinator.load_graph_data, "GraphWidget"),
            (graph, "filter_changed", self.window.data_coordinator.load_graph_data, "GraphWidget"),
            (graph, "node_clicked", self.window.navigation_coordinator.on_item_selected, "GraphWidget"),
            (graph, "lexicon_save_requested", self.window.worker.save_graph_lexicon, "GraphWidget"),
        ], "GraphWidget")
