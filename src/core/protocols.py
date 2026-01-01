"""
Protocol Interfaces for Loose Coupling.

This module defines Protocol interfaces (PEP 544) to establish formal contracts
between architectural layers without tight coupling to concrete implementations.

Protocols allow structural subtyping where any class that implements the required
methods automatically satisfies the protocol without explicit inheritance.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MainWindowProtocol(Protocol):
    """
    Protocol defining the interface that UIManager expects from MainWindow.

    This formalizes the contract between UIManager and MainWindow, making the
    coupling explicit and checkable at runtime.
    """

    def _on_configure_grouping_requested(self) -> None:
        """Handle timeline grouping configuration request."""
        ...

    def _on_clear_grouping_requested(self) -> None:
        """Handle timeline grouping clear request."""
        ...

    def _request_calendar_config(self) -> None:
        """Request loading of calendar configuration."""
        ...

    def show_database_manager(self) -> None:
        """Show the database manager dialog."""
        ...

    def show_ai_settings_dialog(self) -> None:
        """Show the AI settings dialog."""
        ...

    def toggle_auto_relation_setting(self) -> None:
        """Toggle the auto-relation setting."""
        ...

    def close(self) -> bool:
        """Close the window."""
        ...

    # QMainWindow methods
    def setDockOptions(self, options: Any) -> None: ...
    def setTabPosition(self, areas: Any, places: Any) -> None: ...
    def setCorner(self, corner: Any, area: Any) -> None: ...
    def addDockWidget(self, area: Any, dockwidget: Any) -> None: ...
    def tabifyDockWidget(self, first: Any, second: Any) -> None: ...
    def addToolBar(self, toolbar: Any) -> None: ...
    def removeDockWidget(self, dockwidget: Any) -> None: ...

    def saveState(self, version: int = 0) -> bytes:
        """Save the current window state (docks/toolbars)."""
        ...

    def restoreState(self, state: bytes, version: int = 0) -> bool:
        """Restore the window state."""
        ...

    def saveGeometry(self) -> bytes:
        """Save the current window geometry."""
        ...

    def restoreGeometry(self, geometry: bytes) -> bool:
        """Restore the window geometry."""
        ...

    worker: object  # Worker instance for background operations
    command_requested: object  # Signal for emitting commands

    # Missing Attributes identified by Pyright (Typed as Any for flexibility)
    _on_command_failed: Any
    _on_dock_raise_requested: Any
    _on_entities_ready: Any
    _on_entity_details_ready: Any
    _on_event_date_changed: Any
    _on_event_details_ready: Any
    _on_events_ready: Any
    _on_item_delete_requested: Any
    _on_item_selected: Any
    _on_longform_sequence_ready: Any
    _on_maps_ready: Any
    _on_marker_clicked: Any
    _on_marker_color_changed: Any
    _on_marker_dropped: Any
    _on_marker_icon_changed: Any
    _on_marker_position_changed: Any
    _on_markers_ready: Any
    _on_reload_active_editor_relations: Any
    _on_remove_from_grouping_requested: Any
    _on_search_result_selected: Any
    _on_selection_requested: Any
    _on_suggestions_update: Any
    _on_tag_color_change_requested: Any
    add_relation: Any
    ai_search_panel: Any
    clear_filter: Any
    clear_longform_filter: Any
    create_entity: Any
    create_event: Any
    create_map: Any
    create_marker: Any
    data_handler: Any
    delete_map: Any
    delete_marker: Any
    demote_longform_entry: Any
    entity_editor: Any
    event_editor: Any
    export_longform_document: Any
    load_data: Any
    load_entities: Any
    load_entity_details: Any
    load_event_details: Any
    load_events: Any
    load_longform_sequence: Any
    load_maps: Any
    longform_editor: Any
    map_widget: Any
    move_longform_entry: Any
    navigate_to_entity: Any
    on_current_time_changed: Any
    on_map_selected: Any
    perform_semantic_search: Any
    promote_longform_entry: Any
    remove_relation: Any
    show_filter_dialog: Any
    show_longform_filter_dialog: Any
    status_bar: Any
    timeline: Any
    unified_list: Any
    update_entity: Any
    update_event: Any
    update_playhead_time_label: Any
    update_relation: Any


@runtime_checkable
class TimelineDataProvider(Protocol):
    """
    Protocol for providing timeline data without direct database access.

    This interface allows UI components to request data without violating
    architectural boundaries by directly accessing the DatabaseService.

    The provider acts as a mediator, receiving data requests via method calls
    and returning the requested data.
    """

    def get_group_metadata(
        self, tag_order: list[str], date_range: tuple[float, float] | None = None
    ) -> list[dict]:
        """
        Get metadata for timeline grouping tags.

        Args:
            tag_order: List of tag names to get metadata for.
            date_range: Optional (start_date, end_date) tuple for filtering.

        Returns:
            List of dicts containing tag metadata:
                - tag_name: str
                - color: str (hex color)
                - count: int (number of events)
                - earliest_date: float
                - latest_date: float
        """
        ...

    def get_events_for_group(
        self, tag_name: str, date_range: tuple[float, float] | None = None
    ) -> list:
        """
        Get events that belong to a specific tag group.

        Args:
            tag_name: Name of the tag to filter by.
            date_range: Optional (start_date, end_date) tuple for filtering.

        Returns:
            List of Event objects with the specified tag.
        """
        ...
