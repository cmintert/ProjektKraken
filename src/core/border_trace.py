"""Copy either route between two locations on a closed ring."""

import math
from dataclasses import dataclass

from src.core.region_geometry import Point
from src.core.spatial_geometry import segment_intersection

_TRACE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class RingPosition:
    """Location along an implicitly closed ring in stored order."""

    segment: int
    fraction: float

    def offset(self, size: int) -> float:
        """Return the cyclic position, treating edge endpoints as vertices."""
        return (self.segment + self.fraction) % size


def border_routes(
    ring: tuple[Point, ...],
    first: RingPosition,
    last: RingPosition,
    width: float,
    height: float,
) -> tuple[tuple[Point, ...], ...]:
    """Return the two arcs in order of image distance, with stored order first on ties."""
    start, end = first.offset(len(ring)), last.offset(len(ring))
    if abs(start - end) <= _TRACE_TOLERANCE:
        return ()
    forward = _forward(ring, start, end)
    backward = _forward(ring, end, start)[::-1]
    if forward[0] == forward[-1]:
        return ()

    def length(route: tuple[Point, ...]) -> float:
        return math.fsum(
            math.hypot((b[0] - a[0]) * width, (b[1] - a[1]) * height)
            for a, b in zip(route, route[1:])
        )

    if length(forward) <= length(backward):
        return forward, backward
    return backward, forward


def _forward(ring: tuple[Point, ...], start: float, end: float) -> tuple[Point, ...]:
    size = len(ring)

    def point(offset: float) -> Point:
        index = int(offset)
        fraction = offset - index
        a, b = ring[index % size], ring[(index + 1) % size]
        return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)

    stop = end if end > start else end + size
    points = (
        point(start),
        *(ring[i % size] for i in range(int(start) + 1, math.ceil(stop))),
        point(end),
    )
    return tuple(p for i, p in enumerate(points) if i == 0 or p != points[i - 1])


def simple_draft(points: tuple[Point, ...], *, closed: bool = False) -> bool:
    """Check for crossings, backtracking, and repeated vertices in a draft."""
    if len(set(points)) != len(points):
        return False
    ends = points[1:] + points[:1] if closed else points[1:]
    segments = tuple(zip(points, ends))
    for i, (a, b) in enumerate(segments):
        for j, (c, d) in enumerate(segments[i + 1 :], i + 1):
            adjacent = j == i + 1 or (closed and i == 0 and j == len(segments) - 1)
            hit = segment_intersection(a, b, c, d, _TRACE_TOLERANCE)
            if hit and (hit[2] or not adjacent):
                return False
    return True
