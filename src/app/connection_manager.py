"""
Signal Connection Manager.

Handles all signal/slot connections for the MainWindow,
organizing them by component for better maintainability.
"""

import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages signal/slot connections between UI components.

    Separates connection logic from MainWindow to improve
    maintainability and reduce coupling.
    """

    def __init__(self, main_window):
        """
        Initialize the connection manager.

        Args:
            main_window: Reference to the MainWindow instance.
        """
        self.window = main_window
        logger.debug("ConnectionManager initialized")

    def connect_all(self):
        """Connect all UI signals to their respective slots."""
        self.connect_unified_list()
        self.connect_editors()
        self.connect_timeline()
        self.connect_longform_editor()
        self.connect_map_widget()
        logger.debug("All signal/slot connections established")

    def connect_unified_list(self):
        """Connect signals from the unified list widget."""
        ul = self.window.unified_list
        ul.refresh_requested.connect(self.window.load_data)
        ul.create_event_requested.connect(self.window.create_event)
        ul.create_entity_requested.connect(self.window.create_entity)
        ul.delete_requested.connect(self.window._on_item_delete_requested)
        ul.item_selected.connect(self.window._on_item_selected)

    def connect_editors(self):
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

    def connect_timeline(self):
        """Connect signals from the timeline widget."""
        timeline = self.window.timeline
        timeline.event_selected.connect(self.window.load_event_details)
        timeline.current_time_changed.connect(self.window.on_current_time_changed)
        timeline.playhead_time_changed.connect(self.window.update_playhead_time_label)
        timeline.event_date_changed.connect(self.window._on_event_date_changed)

    def connect_longform_editor(self):
        """Connect signals from the longform editor widget."""
        longform = self.window.longform_editor
        longform.promote_requested.connect(self.window.promote_longform_entry)
        longform.demote_requested.connect(self.window.demote_longform_entry)
        longform.refresh_requested.connect(self.window.load_longform_sequence)
        longform.export_requested.connect(self.window.export_longform_document)
        longform.item_selected.connect(self.window._on_item_selected)
        longform.item_moved.connect(self.window.move_longform_entry)
        longform.link_clicked.connect(self.window.navigate_to_entity)

    def connect_map_widget(self):
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
