"""Tests for GUI-safe timeline grouping over cached event snapshots."""

from src.core.events import Event
from src.core.timeline_grouping import build_group_metadata, events_for_group


def _event(name: str, lore_date: float, tags: list[str]) -> Event:
    """Create an event snapshot with normalized cached tags."""
    event = Event(name=name, lore_date=lore_date)
    event.tags = tags
    return event


def test_cached_group_events_match_tag_and_inclusive_date_range() -> None:
    """Cached group lookup preserves tag filtering, bounds, and ordering."""
    events = [
        _event("late", 20.0, ["alpha"]),
        _event("other", 15.0, ["beta"]),
        _event("early", 10.0, ["alpha"]),
    ]

    result = events_for_group(events, "alpha", (10.0, 20.0))

    assert [event.name for event in result] == ["early", "late"]


def test_cached_metadata_preserves_legacy_all_events_contract() -> None:
    """The pseudo-group remains last, unfiltered, and neutral-coloured."""
    events = [
        _event("inside", 10.0, ["alpha"]),
        _event("outside", 30.0, []),
    ]

    metadata = build_group_metadata(
        events,
        ["All events", "alpha"],
        {"alpha": "#123456"},
        (0.0, 20.0),
    )

    assert metadata == [
        {
            "tag_name": "alpha",
            "color": "#123456",
            "count": 1,
            "earliest_date": 10.0,
            "latest_date": 10.0,
        },
        {
            "tag_name": "All events",
            "color": "#808080",
            "count": 2,
            "earliest_date": 10.0,
            "latest_date": 30.0,
        },
    ]


def test_empty_all_events_metadata_uses_zero_date_bounds() -> None:
    """An empty pseudo-group retains the repository's zero-date sentinel."""
    metadata = build_group_metadata([], ["All events"], {})

    assert metadata[0]["earliest_date"] == 0.0
    assert metadata[0]["latest_date"] == 0.0
