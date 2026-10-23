"""Detached timeline inputs and chronology-constrained minimum lane packing."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineLayoutInput:
    """Measured collision bounds and an independent saved chronological anchor."""

    event_id: str
    start: float
    end: float
    height: int
    anchor: float | None = None


@dataclass(frozen=True)
class TimelineLayoutSnapshot:
    """Detached accepted assignments and row heights."""

    lanes: tuple[tuple[str, int], ...] = ()
    heights: tuple[int, ...] = ()


def pack_timeline_intervals(
    intervals: Sequence[TimelineLayoutInput],
) -> tuple[dict[str, int], list[int]]:
    """Assign each event its highest legal row in chronological order.

    Every earlier overlapping item must be strictly above the current item.
    Thus its earliest legal row is one below the deepest such predecessor.
    This longest-path recurrence minimizes each row and the total row count
    under chronological precedence, rather than unconstrained interval coloring.
    Bounds include the measured trailing gap. Anchor and ID break chronology
    ties independently of zoom-dependent visual starts. Work is O(n squared)
    with O(n) storage and no materialized adjacency graph.
    """
    ordered = sorted(
        intervals,
        key=lambda item: (
            item.start if item.anchor is None else item.anchor,
            item.event_id,
        ),
    )
    placed: list[tuple[TimelineLayoutInput, int]] = []
    assignments: dict[str, int] = {}
    heights: list[int] = []
    for item in ordered:
        lane = max(
            (
                row + 1
                for other, row in placed
                if other.start < item.end and item.start < other.end
            ),
            default=0,
        )
        if lane == len(heights):
            heights.append(item.height)
        else:
            heights[lane] = max(heights[lane], item.height)
        assignments[item.event_id] = lane
        placed.append((item, lane))
    return assignments, heights


def pack_stable_timeline_intervals(
    intervals: Sequence[TimelineLayoutInput],
    previous: TimelineLayoutSnapshot = TimelineLayoutSnapshot(),
) -> tuple[dict[str, int], list[int]]:
    """Use the canonical highest legal rows, superseding incompatible history.

    Previous placements cannot override chronology or leave avoidable row gaps.
    Identical bounds and anchors yield identical assignments regardless of input
    order or prior zoom history. Kept as the shared sync/grouped API boundary.
    """
    return pack_timeline_intervals(intervals)
