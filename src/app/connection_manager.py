"""Signal Connection Manager.

Handles all signal/slot connections for the MainWindow, organizing them by component
for better maintainability.

Connections are defined declaratively as tuples and processed in batch, reducing
boilerplate and making it easier to add or remove signal wiring.
"""

import logging
from typing import TYPE_CHECKING, Callable, Sequence, Tuple, Union, cast

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from src.core.protocols import MainWindowProtocol

# Connection spec: (source_obj, signal_name, slot, description[, connection_type])
ConnectionSpec = Union[
    Tuple[object, str, Callable, str],
    Tuple[object, str, Callable, str, Qt.ConnectionType],
]

logger = logging.getLogger(__name__)

_CONNECTION_SPEC_BASE_FIELD_COUNT = 4


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
        slot: Callable,
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

    def _connect_batch(self, specs: Sequence[ConnectionSpec], group_name: str) -> int:
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
            if len(spec) == _CONNECTION_SPEC_BASE_FIELD_COUNT:
                short_spec = cast(Tuple[object, str, Callable, str], spec)
                obj, signal_name, slot, desc = short_spec
                conn_type = Qt.ConnectionType.AutoConnection
            else:
                long_spec = cast(
                    Tuple[object, str, Callable, str, Qt.ConnectionType], spec
                )
                obj, signal_name, slot, desc, conn_type = long_spec
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
        self.connect_analysis_panel()

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
        refresh_context = (
            self.window.app_coordinator.authoring_context.schedule_refresh
        )
        refresh_entity_context = (
            self.window.app_coordinator.authoring_context.schedule_entity_refresh
        )
        return self._connect_batch(
            [
                (dh, "events_ready", dc.on_events_ready, "DataHandler"),
                (
                    dh,
                    "events_ready",
                    lambda _events: refresh_context(),
                    "DataHandler",
                ),
                (
                    dh,
                    "events_ready",
                    lambda _events: refresh_entity_context(),
                    "DataHandler",
                ),
                (dh, "entities_ready", dc.on_entities_ready, "DataHandler"),
                (
                    dh,
                    "entities_ready",
                    lambda _entities: refresh_context(),
                    "DataHandler",
                ),
                (
                    dh,
                    "entities_ready",
                    lambda _entities: refresh_entity_context(),
                    "DataHandler",
                ),
                (
                    dh,
                    "suggestions_update_requested",
                    dc.on_suggestions_update,
                    "DataHandler",
                ),
                (dh, "event_details_ready", dc.on_event_details_ready, "DataHandler"),
                (dh, "entity_details_ready", dc.on_entity_details_ready, "DataHandler"),
                (
                    dh,
                    "longform_sequence_ready",
                    self.window.longform_manager.on_longform_sequence_loaded,
                    "DataHandler",
                ),
                (
                    dh,
                    "maps_ready",
                    self.window.map_handler.on_maps_ready,
                    "DataHandler",
                ),
                (
                    dh,
                    "maps_ready",
                    lambda _maps: refresh_context(),
                    "DataHandler",
                ),
                (
                    dh,
                    "maps_ready",
                    lambda _maps: refresh_entity_context(),
                    "DataHandler",
                ),
                (
                    dh,
                    "markers_ready",
                    self.window.map_handler.on_markers_ready,
                    "DataHandler",
                ),
                (
                    dh,
                    "markers_ready",
                    lambda _markers: refresh_entity_context(),
                    "DataHandler",
                ),
                (
                    self.window.worker,
                    "attachments_loaded",
                    lambda owner_type, _owner_id, _items: (
                        refresh_entity_context()
                        if owner_type == "entity"
                        else None
                    ),
                    "DatabaseWorker",
                    Qt.ConnectionType.QueuedConnection,
                ),
                (
                    dh,
                    "trajectories_ready",
                    self.window.app_coordinator.trajectory_edit.on_trajectories_ready,
                    "DataHandler",
                ),
                (
                    dh,
                    "entity_state_resolved",
                    self.window.time_coordinator.on_entity_state_resolved,
                    "DataHandler",
                ),
                (dh, "graph_data_ready", dc.on_graph_data_ready, "DataHandler"),
                (dh, "graph_metadata_ready", dc.on_graph_metadata_ready, "DataHandler"),
                (dh, "graph_lexicon_ready", dc.on_graph_lexicon_ready, "DataHandler"),
                (
                    dh,
                    "status_message",
                    self.window.status_bar.showMessage,
                    "DataHandler",
                ),
                (dh, "command_failed", dc.on_command_failed, "DataHandler"),
                (dh, "dock_raise_requested", dc.on_dock_raise_requested, "DataHandler"),
                (dh, "selection_requested", dc.on_selection_requested, "DataHandler"),
                (dh, "reload_events", dc.load_events, "DataHandler"),
                (dh, "reload_entities", dc.load_entities, "DataHandler"),
                (dh, "reload_maps", self.window.load_maps, "DataHandler"),
                (
                    dh,
                    "reload_longform",
                    self.window.longform_manager.load_longform_sequence,
                    "DataHandler",
                ),
                (
                    dh,
                    "reload_active_editor_relations",
                    dc.on_reload_active_editor_relations,
                    "DataHandler",
                ),
                (
                    dh,
                    "reload_active_editor_relations",
                    refresh_context,
                    "DataHandler",
                ),
                (
                    dh,
                    "reload_active_editor_relations",
                    refresh_entity_context,
                    "DataHandler",
                ),
                (
                    dh,
                    "reload_markers",
                    self.window.map_handler.reload_markers,
                    "DataHandler",
                ),
                (
                    dh,
                    "reload_markers_for_current_map",
                    self.window.map_handler.reload_markers_for_current_map,
                    "DataHandler",
                ),
            ],
            "DataHandler",
        )

    def connect_unified_list(self) -> int:
        """Connect signals from the unified list widget."""
        ul = self.window.unified_list
        ec = self.window.editor_coordinator
        dc = self.window.data_coordinator
        context = self.window.app_coordinator.context_tags
        specs: list[ConnectionSpec] = [
            (ul, "refresh_requested", dc.load_data, "UnifiedList"),
            (ul, "create_event_requested", ec.create_event, "UnifiedList"),
            (ul, "create_entity_requested", ec.create_entity, "UnifiedList"),
            (
                ul,
                "create_map_requested",
                self.window.map_widget._on_create_map_clicked,
                "UnifiedList",
            ),
            (ul, "delete_requested", ec.on_item_delete_requested, "UnifiedList"),
            (
                ul,
                "context_tags_edit_requested",
                context.show_editor,
                "UnifiedList",
            ),
            (
                ul,
                "context_tags_enable_requested",
                context.enable,
                "UnifiedList",
            ),
            (
                ul,
                "context_tags_disable_requested",
                context.disable,
                "UnifiedList",
            ),
            (
                ul,
                "context_tags_review_requested",
                context.show_review,
                "UnifiedList",
            ),
            (
                ul,
                "item_selected",
                self.window.navigation_coordinator.on_item_selected,
                "UnifiedList",
            ),
            (
                ul,
                "drag_started",
                self.window.navigation_coordinator.on_drag_started,
                "UnifiedList",
            ),
        ]
        if hasattr(ul, "show_filter_dialog_requested"):
            specs.append(
                (
                    ul,
                    "show_filter_dialog_requested",
                    self.window.show_filter_dialog,
                    "UnifiedList",
                )
            )
        if hasattr(ul, "clear_filter_requested"):
            specs.append(
                (ul, "clear_filter_requested", self.window.clear_filter, "UnifiedList")
            )
        if hasattr(ul, "status_message_requested"):
            specs.append(
                (
                    ul,
                    "status_message_requested",
                    self.window.status_bar.showMessage,
                    "UnifiedList",
                )
            )
        if hasattr(ul, "export_obsidian_requested"):
            specs.append(
                (
                    ul,
                    "export_obsidian_requested",
                    self.window.import_coordinator.export_single_obsidian,
                    "UnifiedList",
                )
            )
        return self._connect_batch(specs, "UnifiedList")

    def connect_editors(self) -> int:
        """Connect signals from event and entity editors."""
        ec = self.window.editor_coordinator
        dc = self.window.data_coordinator
        specs: list[ConnectionSpec] = []
        for editor in [self.window.event_editor, self.window.entity_editor]:
            editor_name = editor.__class__.__name__
            specs.extend(
                [
                    (editor, "add_relation_requested", ec.add_relation, editor_name),
                    (
                        editor,
                        "remove_relation_requested",
                        ec.remove_relation,
                        editor_name,
                    ),
                    (
                        editor,
                        "update_relation_requested",
                        ec.update_relation,
                        editor_name,
                    ),
                    (
                        editor,
                        "link_clicked",
                        self.window.navigation_coordinator.navigate_to_entity,
                        editor_name,
                    ),
                (
                    editor,
                    "navigate_to_relation",
                    self.window.navigation_coordinator.navigate_to_entity,
                    editor_name,
                ),
                    (
                        editor,
                        "completion_prefix_changed",
                        dc.request_semantic_completions,
                        editor_name,
                    ),
                ]
            )
        specs.extend(
            [
                (
                    self.window.entity_editor,
                    "navigate_to_map",
                    self.window.map_widget.select_map,
                    "EntityEditor",
                ),
                (
                    self.window.event_editor,
                    "save_requested",
                    ec.update_event,
                    "EventEditor",
                ),
                (
                    self.window.entity_editor,
                    "save_requested",
                    ec.update_entity,
                    "EntityEditor",
                ),
                (
                    self.window.entity_editor,
                    "return_to_present_requested",
                    self.window.time_coordinator.on_return_to_present,
                    "EntityEditor",
                ),
                (
                    self.window.event_editor,
                    "current_data_changed",
                    self.window.timeline.update_event_preview,
                    "EventEditor",
                ),
                (
                    self.window.event_editor,
                    "discard_requested",
                    dc.load_event_details,
                    "EventEditor",
                ),
                (
                    self.window.entity_editor,
                    "discard_requested",
                    dc.load_entity_details,
                    "EntityEditor",
                ),
                (
                    self.window.event_editor,
                    "create_new_requested",
                    ec.create_event,
                    "EventEditor",
                ),
                (
                    self.window.event_editor,
                    "authoring_context_refresh_requested",
                    self.window.app_coordinator.authoring_context.schedule_refresh,
                    "EventEditor",
                ),
                (
                    self.window.entity_editor,
                    "create_new_requested",
                    ec.create_entity,
                    "EntityEditor",
                ),
                (
                    self.window.entity_editor,
                    "authoring_context_refresh_requested",
                    self.window.app_coordinator.authoring_context.schedule_entity_refresh,
                    "EntityEditor",
                ),
            ]
        )
        return self._connect_batch(specs, "Editors")

    def connect_timeline(self) -> int:
        """Connect signals from the timeline widget."""
        timeline = self.window.timeline
        specs: list[ConnectionSpec] = [
            (
                timeline,
                "event_selected",
                self.window.data_coordinator.load_event_details,
                "Timeline",
            ),
            (
                timeline,
                "create_event_requested",
                self.window.editor_coordinator.create_event,
                "Timeline",
            ),
            (
                timeline,
                "current_time_changed",
                self.window.time_coordinator.on_current_time_changed,
                "Timeline",
            ),
            (
                timeline,
                "playhead_time_changed",
                self.window.time_coordinator.update_playhead_time_label,
                "Timeline",
            ),
            (
                timeline,
                "playhead_time_changed",
                self.window.time_coordinator.on_playhead_changed,
                "Timeline",
            ),
            (
                timeline,
                "playhead_time_changed",
                self.window.map_handler.on_playhead_changed,
                "Timeline",
            ),
            (
                timeline,
                "event_date_changed",
                self.window.editor_coordinator.on_event_date_changed,
                "Timeline",
            ),
        ]
        if hasattr(timeline, "_band_manager") and timeline._band_manager:
            specs.extend(
                [
                    (
                        timeline._band_manager,
                        "tag_color_change_requested",
                        self.window.grouping_manager.on_tag_color_change_requested,
                        "Timeline.BandManager",
                    ),
                    (
                        timeline._band_manager,
                        "remove_from_grouping_requested",
                        self.window.grouping_manager.on_remove_from_grouping_requested,
                        "Timeline.BandManager",
                    ),
                ]
            )
        return self._connect_batch(specs, "Timeline")

    def connect_longform_editor(self) -> int:
        """Connect signals from the longform editor widget."""
        longform = self.window.longform_editor
        lm = self.window.longform_manager
        return self._connect_batch(
            [
                (
                    longform,
                    "promote_requested",
                    lm.promote_longform_entry,
                    "LongformEditor",
                ),
                (
                    longform,
                    "demote_requested",
                    lm.demote_longform_entry,
                    "LongformEditor",
                ),
                (
                    longform,
                    "refresh_requested",
                    lm.load_longform_sequence,
                    "LongformEditor",
                ),
                (
                    longform,
                    "export_requested",
                    lm.export_longform_document,
                    "LongformEditor",
                ),
                (
                    longform,
                    "export_vault_requested",
                    lm.export_as_vault,
                    "LongformEditor",
                ),
                (
                    longform,
                    "item_selected",
                    self.window.navigation_coordinator.on_item_selected,
                    "LongformEditor",
                ),
                (longform, "item_moved", lm.move_longform_entry, "LongformEditor"),
                (
                    longform,
                    "delete_requested",
                    lm.delete_longform_item,
                    "LongformEditor",
                ),
                (
                    longform,
                    "move_up_requested",
                    lm.move_up_longform_entry,
                    "LongformEditor",
                ),
                (
                    longform,
                    "move_down_requested",
                    lm.move_down_longform_entry,
                    "LongformEditor",
                ),
                (
                    longform,
                    "link_clicked",
                    self.window.navigation_coordinator.navigate_to_entity,
                    "LongformEditor",
                ),
                (
                    longform,
                    "show_filter_dialog_requested",
                    lm.show_longform_filter_dialog,
                    "LongformEditor",
                ),
                (
                    longform,
                    "clear_filters_requested",
                    lm.clear_longform_filter,
                    "LongformEditor",
                ),
                (
                    lm,
                    "export_vault_requested",
                    self.window.worker.run_obsidian_vault_export,
                    "LongformManager",
                    Qt.ConnectionType.QueuedConnection,
                ),
                (
                    self.window.worker,
                    "obsidian_vault_export_finished",
                    lm.on_vault_export_finished,
                    "DatabaseWorker",
                    Qt.ConnectionType.QueuedConnection,
                ),
            ],
            "LongformEditor",
        )

    def connect_map_widget(self) -> int:
        """Connect signals from the map widget."""
        map_widget = self.window.map_widget
        map_handler = self.window.map_handler
        timeline = self.window.timeline
        return self._connect_batch(
            [
                (
                    map_widget,
                    "marker_position_changed",
                    map_handler.on_marker_position_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "map_settings_changed",
                    map_handler.on_map_settings_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "marker_clicked",
                    map_handler.on_marker_clicked,
                    "MapWidget",
                ),
                (map_widget, "map_created", map_handler.create_map, "MapWidget"),
                (map_widget, "map_deleted", map_handler.delete_map, "MapWidget"),
                (map_widget, "map_selected", map_handler.on_map_selected, "MapWidget"),
                (
                    map_widget,
                    "map_selected",
                    self.window.app_coordinator.authoring_context.schedule_refresh,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "set_master_map_requested",
                    map_handler.on_set_master_map_requested,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "register_detail_map_requested",
                    map_handler.on_register_detail_map_requested,
                    "MapWidget",
                ),
                (
                    map_widget.view,
                    "footprint_edit_confirmed",
                    map_handler.on_footprint_edit_confirmed,
                    "MapGraphicsView",
                ),
                (
                    map_widget.view,
                    "detail_map_clicked",
                    map_handler.on_detail_map_clicked,
                    "MapGraphicsView",
                ),
                (map_widget, "marker_created", map_handler.create_marker, "MapWidget"),
                (
                    map_widget,
                    "marker_delete_confirmed",
                    map_handler.delete_marker,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "change_marker_color_requested",
                    map_handler.on_marker_color_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "marker_visual_style_changed",
                    map_handler.on_marker_visual_style_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "marker_appearance_changed",
                    map_handler.on_marker_appearance_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "marker_drop_requested",
                    map_handler.on_marker_dropped,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "feature_created",
                    map_handler.on_feature_drawn,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "feature_style_changed",
                    map_handler.on_feature_style_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "feature_geometry_changed",
                    map_handler.on_feature_geometry_changed,
                    "MapWidget",
                ),
                (
                    timeline,
                    "playhead_time_changed",
                    map_widget.on_time_changed,
                    "Timeline->MapWidget",
                ),
                (
                    timeline,
                    "current_time_changed",
                    map_widget.on_current_time_changed,
                    "Timeline->MapWidget",
                ),
                (
                    map_widget,
                    "jump_to_time_requested",
                    self.window.timeline.set_playhead_time,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "layer_tree_changed",
                    map_handler.on_layer_tree_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "layer_opacity_change_requested",
                    map_handler.on_layer_opacity_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "layer_rename_requested",
                    map_handler.on_layer_renamed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "layer_properties_changed",
                    map_handler.on_layer_properties_changed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "layer_delete_feature_requested",
                    map_handler.on_layer_feature_deleted,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "create_raster_layer_requested",
                    map_handler.create_raster_layer,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "raster_stroke_completed",
                    map_handler.on_raster_stroke_completed,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "raster_palette_edit_requested",
                    map_handler.on_raster_palette_edit,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "raster_value_probed",
                    map_handler.on_raster_value_probed,
                    "MapWidget",
                ),
                (
                    map_handler,
                    "raster_save_state_changed",
                    map_widget.layer_panel.set_raster_save_state,
                    "MapHandler",
                ),
                (
                    map_widget.layer_panel,
                    "raster_snapshot_requested",
                    map_handler.on_raster_snapshot_requested,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_snapshot_edit_requested",
                    map_handler.on_raster_snapshot_edit_requested,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_base_edit_requested",
                    map_handler.on_raster_base_edit_requested,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_query_requested",
                    map_handler.on_raster_query_requested,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_query_cleared",
                    map_handler.on_raster_query_cleared,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_gradient_sub_mode_changed",
                    map_handler.on_raster_gradient_sub_mode_changed,
                    "MapLayerPanel",
                ),
                (
                    map_widget.layer_panel,
                    "raster_notes_requested",
                    map_handler.on_raster_notes_requested,
                    "MapLayerPanel",
                ),
                (
                    map_widget,
                    "create_entity_requested",
                    self.window.editor_coordinator.on_map_create_entity,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "create_event_requested",
                    self.window.editor_coordinator.on_map_create_event,
                    "MapWidget",
                ),
                (
                    map_widget,
                    "marker_object_creation_requested",
                    self.window.editor_coordinator.on_map_create_marker_object,
                    "MapWidget",
                ),
            ],
            "MapWidget",
        )

    def connect_ai_search_panel(self) -> int:
        """Connect signals from the AI search panel widget."""
        panel = self.window.ai_search_panel
        ai = self.window.ai_search_manager
        worker = self.window.worker
        queued = Qt.ConnectionType.QueuedConnection
        return self._connect_batch(
            [
                (
                    panel,
                    "search_requested",
                    ai.perform_semantic_search,
                    "AISearchPanel",
                ),
                (
                    panel,
                    "result_selected",
                    ai.on_search_result_selected,
                    "AISearchPanel",
                ),
                (
                    worker,
                    "index_rebuild_progress",
                    ai.on_index_rebuild_progress,
                    "Worker→AISearchManager",
                    queued,
                ),
                (
                    worker,
                    "index_rebuild_finished",
                    ai.on_index_rebuild_finished,
                    "Worker→AISearchManager",
                    queued,
                ),
                (
                    worker,
                    "embedding_stats_loaded",
                    ai.on_embedding_stats_loaded,
                    "Worker→AISearchManager",
                    queued,
                ),
                (
                    self.window.data_handler,
                    "index_object_requested",
                    self.window.worker_manager._on_index_object_requested,
                    "DataHandler→WorkerManager",
                ),
            ],
            "AISearchPanel",
        )

    def connect_graph_widget(self) -> int:
        """Connect signals from the graph widget."""
        graph = self.window.graph_widget
        return self._connect_batch(
            [
                (
                    graph,
                    "refresh_requested",
                    self.window.data_coordinator.load_graph_data,
                    "GraphWidget",
                ),
                (
                    graph,
                    "filter_changed",
                    self.window.data_coordinator.load_graph_data,
                    "GraphWidget",
                ),
                (
                    graph,
                    "node_clicked",
                    self.window.navigation_coordinator.on_item_selected,
                    "GraphWidget",
                ),
                (
                    graph,
                    "lexicon_save_requested",
                    self.window.worker.save_graph_lexicon,
                    "GraphWidget",
                    Qt.ConnectionType.QueuedConnection,
                ),
            ],
            "GraphWidget",
        )

    def connect_analysis_panel(self) -> int:
        """Connect signals between the analysis panel, worker, and coordinator.

        Wires worker report signals to the panel's display slots (queued, cross-
        thread) and each trigger button to the matching coordinator action.

        Returns:
            Number of failed connections.
        """
        panel = self.window.analysis_panel
        worker = self.window.worker
        coord = self.window.app_coordinator
        intelligence_manager = self.window.intelligence_analysis_manager
        return self._connect_batch(
            [
                # Worker → panel (cross-thread, must be queued)
                (
                    worker,
                    "validation_complete",
                    panel.on_validation_complete,
                    "AnalysisPanel",
                    Qt.ConnectionType.QueuedConnection,
                ),
                (
                    worker,
                    "temporal_analysis_complete",
                    panel.on_temporal_complete,
                    "AnalysisPanel",
                    Qt.ConnectionType.QueuedConnection,
                ),
                (
                    worker,
                    "analysis_failed",
                    panel.on_standard_analysis_failed,
                    "AnalysisPanel",
                    Qt.ConnectionType.QueuedConnection,
                ),
                # Dedicated AI manager → panel.
                (
                    intelligence_manager,
                    "started",
                    panel.on_intelligence_analysis_started,
                    "AnalysisPanel",
                ),
                (
                    intelligence_manager,
                    "partial_result",
                    panel.on_intelligence_partial,
                    "AnalysisPanel",
                ),
                (
                    intelligence_manager,
                    "completed",
                    panel.on_intelligence_complete,
                    "AnalysisPanel",
                ),
                (
                    intelligence_manager,
                    "failed",
                    panel.on_intelligence_failed,
                    "AnalysisPanel",
                ),
                (
                    intelligence_manager,
                    "cancelling",
                    panel.on_intelligence_cancelling,
                    "AnalysisPanel",
                ),
                (
                    intelligence_manager,
                    "cancelled",
                    panel.on_intelligence_cancelled,
                    "AnalysisPanel",
                ),
                (
                    panel.intelligence_panel,
                    "open_source_requested",
                    self.window.navigation_coordinator.navigate_to_entity,
                    "AnalysisPanel",
                ),
                (
                    panel.validation_panel,
                    "open_source_requested",
                    self.window.navigation_coordinator.navigate_to_entity,
                    "AnalysisPanel",
                ),
                (
                    panel.temporal_panel,
                    "open_source_requested",
                    self.window.navigation_coordinator.navigate_to_entity,
                    "AnalysisPanel",
                ),
                (
                    getattr(self.window, "command_coordinator", panel),
                    "history_changed",
                    lambda _undo, _redo: panel.intelligence_panel.mark_stale(),
                    "AnalysisPanel",
                ),
                (
                    worker,
                    "initialized",
                    panel.on_world_initialized,
                    "AnalysisPanel",
                ),
                (
                    worker,
                    "import_finished",
                    lambda result: (
                        panel.intelligence_panel.mark_stale()
                        if getattr(result, "success", False)
                        else None
                    ),
                    "AnalysisPanel",
                ),
                (
                    worker,
                    "events_loaded",
                    lambda _events: panel.intelligence_panel.mark_stale(),
                    "AnalysisPanel",
                ),
                (
                    worker,
                    "entities_loaded",
                    lambda _entities: panel.intelligence_panel.mark_stale(),
                    "AnalysisPanel",
                ),
                (
                    worker,
                    "calendar_config_loaded",
                    lambda _config: panel.intelligence_panel.mark_stale(),
                    "AnalysisPanel",
                ),
                # Buttons → coordinator (main thread).
                # Each lambda fires on_analysis_started first so the panel
                # immediately shows a busy state before the async worker call.
                (
                    panel.validate_btn,
                    "clicked",
                    lambda _checked: panel.on_analysis_started(
                        "Validating world\u2026",
                        "validation",
                        coord.validate_world(panel.editorial_checks.isChecked()),
                    ),
                    "AnalysisPanel",
                ),
                (
                    panel.temporal_btn,
                    "clicked",
                    lambda _checked: panel.on_analysis_started(
                        "Analyzing timeline\u2026",
                        "temporal",
                        coord.analyze_temporal(),
                    ),
                    "AnalysisPanel",
                ),
                (
                    panel.intelligence_btn,
                    "clicked",
                    self._show_analysis_run_dialog,
                    "AnalysisPanel",
                ),
                (
                    panel.cancel_intelligence_btn,
                    "clicked",
                    lambda _checked: coord.cancel_intelligence_analysis(),
                    "AnalysisPanel",
                ),
            ],
            "AnalysisPanel",
        )

    def _show_analysis_run_dialog(self, _checked: bool = False) -> None:
        """Collect an explicit AI scope before dispatching the snapshot job."""
        from PySide6.QtWidgets import QDialog

        from src.gui.dialogs.analysis_run_dialog import AnalysisRunDialog

        navigation = self.window.navigation_coordinator
        current_item_id = getattr(navigation, "selected_id", None)
        selection_ids = self.window.unified_list.get_checked_item_ids()
        dialog = AnalysisRunDialog(
            current_item_id=current_item_id,
            selection_ids=selection_ids,
            parent=self.window.analysis_panel,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.window.app_coordinator.run_intelligence_analysis(
            "all", dialog.run_options()
        )
