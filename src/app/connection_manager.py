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
        logger.debug("ConnectionManager initialized")

    def connect_all(self) -> None:
        """Connect all UI signals to their respective slots."""
        self.connect_data_handler()
        self.connect_unified_list()
        self.connect_editors()
        self.connect_timeline()
        self.connect_longform_editor()
        self.connect_map_widget()
        self.connect_ai_search_panel()
        logger.debug("All signal/slot connections established")

    def connect_data_handler(self) -> None:
        """Connect signals from the data handler."""
        dh = self.window.data_handler

        # Data ready signals
        dh.events_ready.connect(self.window._on_events_ready)
        dh.entities_ready.connect(self.window._on_entities_ready)
        dh.suggestions_update_requested.connect(self.window._on_suggestions_update)
        dh.event_details_ready.connect(self.window._on_event_details_ready)
        dh.entity_details_ready.connect(self.window._on_entity_details_ready)
        dh.longform_sequence_ready.connect(
            self.window.longform_manager.on_longform_sequence_loaded
        )
        dh.maps_ready.connect(self.window.map_handler.on_maps_ready)
        dh.markers_ready.connect(self.window.map_handler.on_markers_ready)

        # UI action signals
        dh.status_message.connect(self.window.status_bar.showMessage)
        dh.command_failed.connect(self.window._on_command_failed)
        dh.dock_raise_requested.connect(self.window._on_dock_raise_requested)
        dh.selection_requested.connect(self.window._on_selection_requested)

        # Reload signals
        dh.reload_events.connect(self.window.load_events)
        dh.reload_entities.connect(self.window.load_entities)
        dh.reload_maps.connect(self.window.load_maps)
        dh.reload_longform.connect(self.window.load_longform_sequence)
        dh.reload_active_editor_relations.connect(
            self.window._on_reload_active_editor_relations
        )
        dh.reload_markers.connect(self.window.map_handler.reload_markers)
        dh.reload_markers_for_current_map.connect(
            self.window.map_handler.reload_markers_for_current_map
        )

    def connect_unified_list(self) -> None:
        """Connect signals from the unified list widget."""
        ul = self.window.unified_list
        ul.refresh_requested.connect(self.window.load_data)
        ul.create_event_requested.connect(self.window.create_event)
        ul.create_entity_requested.connect(self.window.create_entity)
        ul.delete_requested.connect(self.window._on_item_delete_requested)
        ul.item_selected.connect(self.window._on_item_selected)
        if hasattr(ul, "show_filter_dialog_requested"):
            ul.show_filter_dialog_requested.connect(self.window.show_filter_dialog)
        if hasattr(ul, "clear_filter_requested"):
            ul.clear_filter_requested.connect(self.window.clear_filter)

    def connect_editors(self) -> None:
        """Connect signals from event and entity editors."""
        # Generic connections for both editors
        for editor in [self.window.event_editor, self.window.entity_editor]:
            editor.add_relation_requested.connect(self.window.add_relation)
            editor.remove_relation_requested.connect(self.window.remove_relation)
            editor.update_relation_requested.connect(self.window.update_relation)
            editor.link_clicked.connect(self.window.navigate_to_entity)
            editor.navigate_to_relation.connect(self.window.navigate_to_entity)

        # Specific connections for each editor
        self.window.event_editor.save_requested.connect(self.window.update_event)
        self.window.entity_editor.save_requested.connect(self.window.update_entity)

        # Live preview for Timeline
        self.window.event_editor.current_data_changed.connect(
            self.window.timeline.update_event_preview
        )

        # Discard signals - reload from database
        self.window.event_editor.discard_requested.connect(
            self.window.load_event_details
        )
        self.window.entity_editor.discard_requested.connect(
            self.window.load_entity_details
        )

    def connect_timeline(self) -> None:
        """Connect signals from the timeline widget."""
        timeline = self.window.timeline
        timeline.event_selected.connect(self.window.load_event_details)
        timeline.current_time_changed.connect(self.window.on_current_time_changed)
        timeline.playhead_time_changed.connect(self.window.update_playhead_time_label)
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

    def connect_ai_search_panel(self) -> None:
        """Connect signals from the AI search panel widget."""
        panel = self.window.ai_search_panel

        # Search and index operations
        panel.search_requested.connect(self.window.perform_semantic_search)
        panel.result_selected.connect(self.window._on_search_result_selected)
