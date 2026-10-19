"""Detached timeline packing inputs and deterministic first-fit calculation."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineLayoutInput:
    """One GUI-measured interval in lore days, including its trailing gap."""

    event_id: str
    start: float
    end: float
    height: int


def pack_timeline_intervals(
    intervals: Sequence[TimelineLayoutInput],
) -> tuple[dict[str, int], list[int]]:
    """Pack stable start-sorted intervals into the first available lane."""
    ends: list[float] = []
    heights: list[int] = []
    assignments: dict[str, int] = {}
    for interval in sorted(intervals, key=lambda value: value.start):
        lane = next(
            (index for index, end in enumerate(ends) if end <= interval.start),
            len(ends),
        )
        if lane == len(ends):
            ends.append(interval.end)
            heights.append(interval.height)
        else:
            ends[lane] = interval.end
            heights[lane] = max(heights[lane], interval.height)
        assignments[interval.event_id] = lane
    return assignments, heights
