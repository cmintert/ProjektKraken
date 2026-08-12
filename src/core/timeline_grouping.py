"""Pure helpers for building timeline grouping snapshots in memory."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from src.core.events import Event

ALL_EVENTS_GROUP_NAME = "All events"
ALL_EVENTS_GROUP_COLOR = "#808080"


def events_for_group(
    events: Iterable[Event],
    tag_name: str,
    date_range: tuple[float, float] | None = None,
) -> list[Event]:
    """Return cached events belonging to a timeline group.

    Args:
        events: Current immutable event snapshots.
        tag_name: Stored tag name to match.
        date_range: Optional inclusive lore-date bounds.

    Returns:
        Matching events ordered by lore date.

    """
    start_date, end_date = date_range or (float("-inf"), float("inf"))
    matching = [
        event
        for event in events
        if start_date <= event.lore_date <= end_date
        and tag_name in set(event.tags)
    ]
    return sorted(matching, key=lambda event: event.lore_date)


def build_group_metadata(
    events: Sequence[Event],
    tag_order: Sequence[str],
    colors: Mapping[str, str],
    date_range: tuple[float, float] | None = None,
) -> list[dict[str, Any]]:
    """Build timeline band metadata from cached event snapshots.

    Args:
        events: Current immutable event snapshots.
        tag_order: Group names in display order.
        colors: Worker-loaded tag colors keyed by tag name.
        date_range: Optional inclusive lore-date bounds.

    Returns:
        Metadata dictionaries matching ``TagRepository.get_group_metadata``.
        The legacy ``All events`` pseudo-group is appended last and ignores
        the optional range for metadata, preserving the existing provider
        contract.

    """
    metadata: list[dict[str, Any]] = []
    regular_tags = [
        tag_name for tag_name in tag_order if tag_name != ALL_EVENTS_GROUP_NAME
    ]
    for tag_name in regular_tags:
        grouped_events = events_for_group(events, tag_name, date_range)
        dates = [event.lore_date for event in grouped_events]
        metadata.append(
            {
                "tag_name": tag_name,
                "color": colors.get(tag_name, ALL_EVENTS_GROUP_COLOR),
                "count": len(grouped_events),
                "earliest_date": min(dates) if dates else None,
                "latest_date": max(dates) if dates else None,
            }
        )
    if ALL_EVENTS_GROUP_NAME in tag_order:
        all_dates = [event.lore_date for event in events]
        metadata.append(
            {
                "tag_name": ALL_EVENTS_GROUP_NAME,
                "color": ALL_EVENTS_GROUP_COLOR,
                "count": len(events),
                "earliest_date": min(all_dates, default=0.0),
                "latest_date": max(all_dates, default=0.0),
            }
        )
    return metadata
