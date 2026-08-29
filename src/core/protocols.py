"""Protocol Interfaces for Loose Coupling.

This module defines Protocol interfaces (PEP 544) to establish formal contracts between
architectural layers without tight coupling to concrete implementations.

Protocols allow structural subtyping where any class that implements the required
methods automatically satisfies the protocol without explicit inheritance.
"""

from typing import Any, Protocol, runtime_checkable


class SignalProtocol(Protocol):
    """Minimal contract shared by bound Qt signals used across app layers."""

    def emit(self, *args: Any) -> None:
        """Emit the signal with the supplied arguments."""
        ...


class DatabaseWorkerProtocol(Protocol):
    """Worker operations invoked directly by application coordinators."""

    def load_calendar_config(self) -> None:
        """Load the active calendar configuration."""
        ...

    def save_graph_lexicon(self, config: dict) -> None:
        """Persist the graph lexicon configuration."""
        ...

    def run_obsidian_vault_export(self, output_dir: str) -> None:
        """Export the active world as an Obsidian vault."""
        ...


@runtime_checkable
class MainWindowProtocol(Protocol):
    """Contract used by the app-layer managers that collaborate with MainWindow."""

    def toggle_auto_relation_setting(self) -> None:
        """Toggle the auto-relation setting."""
        ...

    def toggle_longform_auto_refresh(self) -> None:
        """Toggle automatic Longform refresh."""
        ...

    def load_maps(self) -> None:
        """Request the current world's maps."""
        ...

    def show_filter_dialog(self) -> None:
        """Show the global filter dialog."""
        ...

    def clear_filter(self) -> None:
        """Clear the active global filter."""
        ...

    def close(self) -> bool:
        """Close the window."""
        ...

    def addAction(self, action: Any) -> None:
        """Add an action to the main window."""
        ...

    @property
    def worker(self) -> DatabaseWorkerProtocol:
        """Return the database worker owned by the worker thread."""
        ...

    @property
    def command_requested(self) -> SignalProtocol:
        """Return the command-dispatch signal."""
        ...

    ai_search_manager: Any
    ai_search_panel: Any
    analysis_panel: Any
    app_coordinator: Any
    backup_coordinator: Any
    command_coordinator: Any
    coordinator: Any
    data_coordinator: Any
    data_handler: Any
    editor_coordinator: Any
    entity_editor: Any
    event_editor: Any
    grouping_manager: Any
    graph_widget: Any
    import_coordinator: Any
    intelligence_analysis_manager: Any
    longform_editor: Any
    longform_manager: Any
    map_handler: Any
    map_widget: Any
    navigation_coordinator: Any
    status_bar: Any
    time_coordinator: Any
    timeline: Any
    unified_list: Any
    workspace: Any
    worker_manager: Any


@runtime_checkable
class TimelineDataProvider(Protocol):
    """Protocol for providing timeline data without direct database access.

    This interface allows UI components to request data without violating architectural
    boundaries by directly accessing the DatabaseService.

    The provider acts as a mediator, receiving data requests via method calls and
    returning the requested data.
    """

    def get_group_metadata(
        self, tag_order: list[str], date_range: tuple[float, float] | None = None
    ) -> list[dict]:
        """Get metadata for timeline grouping tags.

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
        """Get events that belong to a specific tag group.

        Args:
            tag_name: Name of the tag to filter by.
            date_range: Optional (start_date, end_date) tuple for filtering.

        Returns:
            List of Event objects with the specified tag.

        """
        ...
