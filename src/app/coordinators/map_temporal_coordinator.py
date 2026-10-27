"""Publish detached temporal evidence through existing data notifications."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Slot

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext


class MapTemporalCoordinator(QObject):
    """Own snapshot generations without database access or shell dependencies."""

    def __init__(
        self,
        events: Callable[[], list[Event]],
        consumers: list[Callable[[TemporalResolutionContext], None]],
        parent: QObject | None = None,
    ) -> None:
        """Receive narrow providers and presentation callbacks."""
        super().__init__(parent)
        self._events = events
        self._consumers = consumers
        self._converter: CalendarConverter | None = None
        self._revision = 0

    @Slot(object)
    def set_calendar(self, config: CalendarConfig | None) -> None:
        """Replace calendar identity, including an unavailable calendar."""
        self._converter = CalendarConverter(config) if config else None
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        """Publish one complete generation after an accepted lore mutation."""
        self._revision += 1
        context = TemporalResolutionContext.build(
            self._events(), self._converter, self._revision
        )
        for consumer in self._consumers:
            consumer(context)

    @Slot(str, str, str)
    def lore_changed(self, kind: str, _identity: str, _operation: str) -> None:
        """Ignore entity-only changes while refreshing all event dependencies."""
        if kind == "event":
            self.refresh()
