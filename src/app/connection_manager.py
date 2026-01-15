"""
Signal Connection Manager.

Handles all signal/slot connections for the MainWindow,
organizing them by component for better maintainability.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.protocols import MainWindowProtocol

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages signal/slot connections between UI components.

    Separates connection logic from MainWindow to improve
    maintainability and reduce coupling.
    """

    def __init__(self, main_window: "MainWindowProtocol") -> None:
        """
        Initialize the connection manager.

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
    ) -> bool:
        """
        Safely connect a signal with validation and error handling.

        Args:
            obj: The object containing the signal.
            signal_name: Name of the signal attribute.
            slot: The slot (callable) to connect to.
            obj_description: Description of the object for logging.

        Returns:
            bool: True if connection successful, False otherwise.
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

            # Attempt connection
            signal.connect(slot)
            self._connection_stats["succeeded"] += 1
            logger.debug(
                f"Successfully connected {obj_description or obj.__class__.__name__}."
                f"{signal_name}"
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to connect {obj_description}.{signal_name}: {e}")
            self._connection_stats["failed"] += 1
            return False

    def connect_all(self) -> dict:
        """
        Connect all UI signals to their respective slots.

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
        """
        Connect signals from the data handler.

        Returns:
            int: Number of failed connections.
        """
        dh = self.window.data_handler
        failed_count = 0

        # Data ready signals
        if not self._connect_signal_safe(
            dh, "events_ready", self.window._on_events_ready, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "entities_ready", self.window._on_entities_ready, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "suggestions_update_requested",
            self.window._on_suggestions_update,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "event_details_ready",
            self.window._on_event_details_ready,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "entity_details_ready",
            self.window._on_entity_details_ready,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "longform_sequence_ready",
            self.window.longform_manager.on_longform_sequence_loaded,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "maps_ready", self.window.map_handler.on_maps_ready, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "markers_ready", self.window.map_handler.on_markers_ready, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "trajectories_ready",
            self.window.map_handler.on_trajectories_ready,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "entity_state_resolved",
            self.window._on_entity_state_resolved,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "graph_data_ready", self.window._on_graph_data_ready, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "graph_metadata_ready",
            self.window._on_graph_metadata_ready,
            "DataHandler",
        ):
            failed_count += 1

        # UI action signals
        if not self._connect_signal_safe(
            dh, "status_message", self.window.status_bar.showMessage, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "command_failed", self.window._on_command_failed, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "dock_raise_requested",
            self.window._on_dock_raise_requested,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "selection_requested",
            self.window._on_selection_requested,
            "DataHandler",
        ):
            failed_count += 1

        # Reload signals
        if not self._connect_signal_safe(
            dh, "reload_events", self.window.load_events, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "reload_entities", self.window.load_entities, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh, "reload_maps", self.window.load_maps, "DataHandler"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "reload_longform",
            self.window.load_longform_sequence,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "reload_active_editor_relations",
            self.window._on_reload_active_editor_relations,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "reload_markers",
            self.window.map_handler.reload_markers,
            "DataHandler",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            dh,
            "reload_markers_for_current_map",
            self.window.map_handler.reload_markers_for_current_map,
            "DataHandler",
        ):
            failed_count += 1

        logger.debug(
            f"DataHandler connections: {23 - failed_count}/23 succeeded, "
            f"{failed_count} failed"
        )
        return failed_count

    def connect_unified_list(self) -> int:
        """
        Connect signals from the unified list widget.

        Returns:
            int: Number of failed connections.
        """
        ul = self.window.unified_list
        failed_count = 0

        if not self._connect_signal_safe(
            ul, "refresh_requested", self.window.load_data, "UnifiedList"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            ul, "create_event_requested", self.window.create_event, "UnifiedList"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            ul, "create_entity_requested", self.window.create_entity, "UnifiedList"
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            ul,
            "delete_requested",
            self.window._on_item_delete_requested,
            "UnifiedList",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            ul, "item_selected", self.window._on_item_selected, "UnifiedList"
        ):
            failed_count += 1

        # Optional signals
        if hasattr(ul, "show_filter_dialog_requested"):
            if not self._connect_signal_safe(
                ul,
                "show_filter_dialog_requested",
                self.window.show_filter_dialog,
                "UnifiedList",
            ):
                failed_count += 1

        if hasattr(ul, "clear_filter_requested"):
            if not self._connect_signal_safe(
                ul, "clear_filter_requested", self.window.clear_filter, "UnifiedList"
            ):
                failed_count += 1

        logger.debug(
            f"UnifiedList connections: {7 - failed_count}/7 succeeded, "
            f"{failed_count} failed"
        )
        return failed_count

    def connect_editors(self) -> int:
        """
        Connect signals from event and entity editors.

        Returns:
            int: Number of failed connections.
        """
        failed_count = 0

        # Generic connections for both editors
        for editor in [self.window.event_editor, self.window.entity_editor]:
            editor_name = editor.__class__.__name__

            if not self._connect_signal_safe(
                editor, "add_relation_requested", self.window.add_relation, editor_name
            ):
                failed_count += 1

            if not self._connect_signal_safe(
                editor,
                "remove_relation_requested",
                self.window.remove_relation,
                editor_name,
            ):
                failed_count += 1

            if not self._connect_signal_safe(
                editor,
                "update_relation_requested",
                self.window.update_relation,
                editor_name,
            ):
                failed_count += 1

            if not self._connect_signal_safe(
                editor, "link_clicked", self.window.navigate_to_entity, editor_name
            ):
                failed_count += 1

            if not self._connect_signal_safe(
                editor,
                "navigate_to_relation",
                self.window.navigate_to_entity,
                editor_name,
            ):
                failed_count += 1

        # Specific connections for each editor
        if not self._connect_signal_safe(
            self.window.event_editor,
            "save_requested",
            self.window.update_event,
            "EventEditor",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            self.window.entity_editor,
            "save_requested",
            self.window.update_entity,
            "EntityEditor",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            self.window.entity_editor,
            "return_to_present_requested",
            self.window.on_return_to_present,
            "EntityEditor",
        ):
            failed_count += 1

        # Live preview for Timeline
        if not self._connect_signal_safe(
            self.window.event_editor,
            "current_data_changed",
            self.window.timeline.update_event_preview,
            "EventEditor",
        ):
            failed_count += 1

        # Discard signals - reload from database
        if not self._connect_signal_safe(
            self.window.event_editor,
            "discard_requested",
            self.window.load_event_details,
            "EventEditor",
        ):
            failed_count += 1

        if not self._connect_signal_safe(
            self.window.entity_editor,
            "discard_requested",
            self.window.load_entity_details,
            "EntityEditor",
        ):
            failed_count += 1

        logger.debug(
            f"Editor connections: {12 - failed_count}/12 succeeded, "
            f"{failed_count} failed"
        )
        return failed_count

    def connect_timeline(self) -> None:
        """Connect signals from the timeline widget."""
        timeline = self.window.timeline
        timeline.event_selected.connect(self.window.load_event_details)
        timeline.current_time_changed.connect(self.window.on_current_time_changed)
        timeline.playhead_time_changed.connect(self.window.update_playhead_time_label)
        timeline.playhead_time_changed.connect(self.window._on_playhead_changed)
        timeline.event_date_changed.connect(self.window._on_event_date_changed)

        # Band manager signals (for timeline grouping)
        if hasattr(timeline, "_band_manager") and timeline._band_manager:
            timeline._band_manager.tag_color_change_requested.connect(
                self.window._on_tag_color_change_requested
            )
            timeline._band_manager.remove_from_grouping_requested.connect(
                self.window._on_remove_from_grouping_requested
            )

    def connect_longform_editor(self) -> None:
        """Connect signals from the longform editor widget."""
        longform = self.window.longform_editor
        longform.promote_requested.connect(self.window.promote_longform_entry)
        longform.demote_requested.connect(self.window.demote_longform_entry)
        longform.refresh_requested.connect(self.window.load_longform_sequence)
        longform.export_requested.connect(self.window.export_longform_document)
        longform.item_selected.connect(self.window._on_item_selected)
        longform.item_moved.connect(self.window.move_longform_entry)
        longform.link_clicked.connect(self.window.navigate_to_entity)
        longform.show_filter_dialog_requested.connect(
            self.window.show_longform_filter_dialog
        )
        longform.clear_filters_requested.connect(self.window.clear_longform_filter)

    def connect_map_widget(self) -> None:
        """Connect signals from the map widget."""
        map_widget = self.window.map_widget
        map_widget.marker_position_changed.connect(
            self.window._on_marker_position_changed
        )
        map_widget.marker_clicked.connect(self.window._on_marker_clicked)
        map_widget.create_map_requested.connect(self.window.create_map)
        map_widget.delete_map_requested.connect(self.window.delete_map)
        map_widget.map_selected.connect(self.window.on_map_selected)
        map_widget.create_marker_requested.connect(self.window.create_marker)
        map_widget.delete_marker_requested.connect(self.window.delete_marker)
        map_widget.change_marker_icon_requested.connect(
            self.window._on_marker_icon_changed
        )
        map_widget.change_marker_color_requested.connect(
            self.window._on_marker_color_changed
        )
        map_widget.marker_drop_requested.connect(self.window._on_marker_dropped)

        # Wire Timeline playhead to Map for temporal synchronization
        timeline = self.window.timeline
        timeline.playhead_time_changed.connect(map_widget.on_time_changed)
        timeline.current_time_changed.connect(map_widget.on_current_time_changed)

        # Connect keyframe request
        map_widget.add_keyframe_requested.connect(self.window.worker.add_keyframe)
        map_widget.update_keyframe_time_requested.connect(
            self.window.worker.update_keyframe_time
        )
        map_widget.delete_keyframe_requested.connect(self.window.worker.delete_keyframe)
        map_widget.jump_to_time_requested.connect(
            self.window.timeline.set_playhead_time
        )

    def connect_ai_search_panel(self) -> None:
        """Connect signals from the AI search panel widget."""
        panel = self.window.ai_search_panel

        # Search and index operations
        panel.search_requested.connect(self.window.perform_semantic_search)
        panel.result_selected.connect(self.window._on_search_result_selected)

    def connect_graph_widget(self) -> None:
        """Connect signals from the graph widget."""
        graph = self.window.graph_widget
        graph.refresh_requested.connect(self.window.load_graph_data)
        graph.filter_changed.connect(self.window.load_graph_data)
        graph.node_clicked.connect(self.window._on_item_selected)
