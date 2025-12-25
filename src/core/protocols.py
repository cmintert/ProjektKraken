"""
Protocol Interfaces for Loose Coupling.

This module defines Protocol interfaces (PEP 544) to establish formal contracts
between architectural layers without tight coupling to concrete implementations.

Protocols allow structural subtyping where any class that implements the required
methods automatically satisfies the protocol without explicit inheritance.
"""

from typing import Protocol, runtime_checkable


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
