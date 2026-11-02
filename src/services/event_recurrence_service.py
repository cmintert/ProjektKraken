"""Worker-side recurrence validation without adding database responsibilities."""

from typing import Any

from src.core.calendar import CalendarConverter
from src.core.event_timing.definitions import EventTimingDefinition
from src.core.events import Event
from src.core.recurrence import RECURRENCE_ATTRIBUTE, validate_recurrence


def validate_expected_recurrence(current: Event, update: dict[str, Any]) -> None:
    """Reject stale explicit schedule saves while allowing independent prose saves."""
    if "__expected_recurrence" in update and update[
        "__expected_recurrence"
    ] != current.attributes.get(RECURRENCE_ATTRIBUTE):
        raise ValueError(
            "The recurrence changed since this Event was loaded. Reload before saving."
        )


def validate_recurrence_change(
    previous: Event | None, updated: Event, converter: CalendarConverter | None
) -> None:
    """Validate new schedule/timing intent, allowing opaque unchanged content.

    Old/unknown recurrence survives unrelated edits and historical replay. An
    explicit removal is always possible without revalidating the old schedule.
    """
    if RECURRENCE_ATTRIBUTE not in updated.attributes:
        return
    data = updated.attributes[RECURRENCE_ATTRIBUTE]
    if previous is not None and data == previous.attributes.get(RECURRENCE_ATTRIBUTE):
        if (
            updated.lore_date == previous.lore_date
            and updated.lore_duration == previous.lore_duration
            and updated.attributes.get("_temporal_v2")
            == previous.attributes.get("_temporal_v2")
        ):
            return
        if EventTimingDefinition.from_event(
            previous
        ) == EventTimingDefinition.from_event(updated):
            return
    validate_recurrence(updated, converter)
