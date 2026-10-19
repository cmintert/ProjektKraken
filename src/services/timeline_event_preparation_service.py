"""Stateless event reconciliation; scene ownership stays with the timeline GUI."""

from collections.abc import Sequence
from dataclasses import dataclass

from src.core.command import LoreMutationEffect
from src.core.events import Event


@dataclass(frozen=True)
class PreparedTimelineEvents:
    """GUI-local reconciliation plan, retaining surviving Event identities."""

    events: tuple[Event, ...]
    upserts: tuple[Event, ...]
    removed_ids: frozenset[str]
    layout_changed: bool


class TimelineEventPreparationService:
    """Prepare replacement and ordered effects without Qt or persistence."""

    @staticmethod
    def layout_signature(event: Event | None) -> tuple[object, ...] | None:
        """Return fields that affect measured geometry or group membership."""
        if event is None:
            return None
        return (
            event.lore_date,
            event.lore_duration,
            event.name,
            event.type,
            tuple(event.tags),
            repr(event.attributes.get("_temporal_v2")),
        )

    @staticmethod
    def replace(
        events: Sequence[Event], existing_ids: set[str]
    ) -> PreparedTimelineEvents:
        """Prepare a full replacement with stable ordering of equal dates."""
        ordered = tuple(sorted(events, key=lambda event: event.lore_date))
        return PreparedTimelineEvents(
            ordered,
            ordered,
            frozenset(existing_ids - {event.id for event in ordered}),
            True,
        )

    @classmethod
    def apply_effects(
        cls, current: Sequence[Event], effects: Sequence[LoreMutationEffect]
    ) -> PreparedTimelineEvents:
        """Apply effects in order, retaining every geometry invalidation."""
        events = list(current)
        upserts: dict[str, Event] = {}
        removed: set[str] = set()
        layout_changed = False
        for effect in effects:
            event_id = effect["object_id"]
            previous = next((event for event in events if event.id == event_id), None)
            events = [event for event in events if event.id != event_id]
            if effect["operation"] == "delete":
                removed.add(event_id)
                upserts.pop(event_id, None)
                layout_changed = layout_changed or previous is not None
                continue
            snapshot = effect["snapshot"]
            assert snapshot is not None
            event = Event.from_dict(snapshot)
            events.append(event)
            events.sort(key=lambda value: value.lore_date)
            upserts[event_id] = event
            removed.discard(event_id)
            layout_changed = layout_changed or (
                cls.layout_signature(previous) != cls.layout_signature(event)
            )
        return PreparedTimelineEvents(
            tuple(events), tuple(upserts.values()), frozenset(removed), layout_changed
        )
