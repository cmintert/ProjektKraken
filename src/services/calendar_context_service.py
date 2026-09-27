"""Establish a durable calendar identity before enabling temporal authoring."""

from typing import Protocol

from src.core.calendar import CalendarConfig


class CalendarStore(Protocol):
    """The worker-owned persistence operations needed for calendar bootstrap."""

    def get_active_calendar_config(self) -> CalendarConfig | None:
        """Read the current world's active calendar."""
        ...

    def insert_calendar_config(self, config: CalendarConfig) -> None:
        """Persist a calendar before publishing its identity."""
        ...


def ensure_active_calendar(store: CalendarStore) -> CalendarConfig:
    """Persist the existing Gregorian fallback once, preserving custom calendars.

    Call only on the database worker. A failed write propagates so the UI never
    receives an ephemeral ID that cannot be used in an event assertion.
    """
    config = store.get_active_calendar_config()
    if config is None:
        config = CalendarConfig.create_default()
        config.is_active = True
        store.insert_calendar_config(config)
    return config
