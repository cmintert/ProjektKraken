"""Publish detached temporal evidence through existing data notifications."""

import json
from collections.abc import Callable

from PySide6.QtCore import QObject, Slot

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_context import TemporalResolutionContext


class MapTemporalCoordinator(QObject):
    """Own snapshot generations without database access or shell dependencies."""

    MAX_PREPARED_RESOLUTIONS = 4

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
        self._prepared: dict[str, str] = {}

    @Slot(str)
    def prime_resolution(self, payload: str) -> None:
        """Cache detached calculations; only matching saved facts can publish them."""
        fingerprint = json.loads(payload)["fingerprint"]
        self._prepared[fingerprint] = payload
        while len(self._prepared) > self.MAX_PREPARED_RESOLUTIONS:
            self._prepared.pop(next(iter(self._prepared)))

    @Slot(object)
    def set_calendar(self, config: CalendarConfig | None) -> None:
        """Replace calendar identity, including an unavailable calendar."""
        self._converter = CalendarConverter(config) if config else None
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        """Publish one complete generation after an accepted lore mutation."""
        self._revision += 1
        from src.core.event_timing.compiler import fingerprint

        events = self._events()
        prepared = self._prepared.get(fingerprint(events, self._converter))
        context = TemporalResolutionContext.build(
            events, self._converter, self._revision, prepared
        )
        for consumer in self._consumers:
            consumer(context)

    @Slot(str, str, str)
    def lore_changed(self, kind: str, _identity: str, _operation: str) -> None:
        """Ignore entity-only changes while refreshing all event dependencies."""
        if kind == "event":
            self.refresh()
