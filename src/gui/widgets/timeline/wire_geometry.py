"""Hard wire clearance and bounded comparisons of complete painted candidates."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, sqrt
from typing import TYPE_CHECKING

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker

if TYPE_CHECKING:
    from src.gui.widgets.timeline.wire_router import Wire

WIRE_GAP = 8.0
STROKE_WIDTH = 3.0  # Includes the 2.5 px selected pen and antialiasing clearance.
SOCKET_RADIUS = 24.0
PARALLEL_COSINE = 0.985
GEOMETRY_EPSILON = 1e-6
MIN_PATH_ELEMENTS = 2


def path_point(path: QPainterPath, index: int) -> QPointF:
    """Read an element through Qt's runtime implicit QPointF conversion."""
    # PySide6 6.10.1 accepts Element at runtime, but QtCore.pyi omits the overload.
    return QPointF(path.elementAt(index))  # type: ignore[call-overload]


def path_segments(path: QPainterPath) -> list[QLineF]:
    """Flatten without joining separate subpaths or closing an open wire."""
    return [
        QLineF(a, b)
        for polygon in path.toSubpathPolygons()
        for index in range(polygon.size() - 1)
        for a, b in [(polygon.at(index), polygon.at(index + 1))]
        if a != b
    ]


def self_intersects(segments: list[QLineF]) -> bool:
    """Reject nonadjacent crossings, including a loop created by smoothing."""
    for index, segment in enumerate(segments):
        for other in segments[: max(0, index - 1)]:
            kind, _ = segment.intersects(other)
            if kind == QLineF.IntersectionType.BoundedIntersection:
                return True
    return False


def endpoint_decoration(wire: Wire) -> QPainterPath:
    """Mirror the painter's socket and arrow, including the selected pen."""
    arrow = QPainterPath(wire.target + QPointF(wire.target_side * 6, -4))
    arrow.lineTo(wire.target)
    arrow.lineTo(wire.target + QPointF(wire.target_side * 6, 4))
    stroker = QPainterPathStroker()
    stroker.setWidth(STROKE_WIDTH)
    return stroker.createStroke(arrow)


def _decorations_clear(wire: Wire, obstacles: list[QRectF]) -> bool:
    arrow = endpoint_decoration(wire)
    socket = QPainterPath()
    socket.addEllipse(wire.source, 2 + STROKE_WIDTH / 2, 2 + STROKE_WIDTH / 2)
    for rect in obstacles:
        if arrow.intersects(rect):
            return False
        edge = rect.right() if wire.source_side > 0 else rect.left()
        own_contact = (
            abs(edge + wire.source_side * 2 - wire.source.x()) < GEOMETRY_EPSILON
            and rect.top() <= wire.source.y() <= rect.bottom()
        )
        if socket.intersects(rect) and not own_contact:
            return False
    return True


@dataclass
class _Run:
    """Premeasured flattened segment for inexpensive corridor comparisons."""

    x: float
    y: float
    length: float
    ux: float
    uy: float
    bounds: tuple[float, float, float, float]

    @classmethod
    def from_line(cls, line: QLineF) -> _Run:
        length = line.length()
        return cls(
            line.x1(),
            line.y1(),
            length,
            line.dx() / length,
            line.dy() / length,
            (
                min(line.x1(), line.x2()),
                min(line.y1(), line.y2()),
                max(line.x1(), line.x2()),
                max(line.y1(), line.y2()),
            ),
        )

    def portion(self, lower: float, upper: float) -> _Run:
        """Retain a measured part after removing a shared terminal circle."""
        x, y = self.x + self.ux * lower, self.y + self.uy * lower
        end_x, end_y = self.x + self.ux * upper, self.y + self.uy * upper
        return _Run(
            x,
            y,
            upper - lower,
            self.ux,
            self.uy,
            (min(x, end_x), min(y, end_y), max(x, end_x), max(y, end_y)),
        )


@dataclass
class Candidate:
    """One validated route with reusable geometry for reservations and ranking."""

    wire: Wire
    path: QPainterPath
    stroke: QPainterPath
    segments: list[QLineF]
    runs: list[_Run]


def valid_candidate(
    wire: Wire,
    path: QPainterPath,
    obstacles: list[QRectF],
    minimum_y: float | None,
) -> Candidate | None:
    """Validate ports, complete selected stroke and decorations before ranking."""
    if path.isEmpty() or path.elementCount() < MIN_PATH_ELEMENTS:
        return None
    first = path_point(path, 1)
    last = path_point(path, path.elementCount() - 2)
    if (
        path.pointAtPercent(0) != wire.source
        or path.pointAtPercent(1) != wire.target
        or abs(first.y() - wire.source.y()) > GEOMETRY_EPSILON
        or abs(last.y() - wire.target.y()) > GEOMETRY_EPSILON
        or (first.x() - wire.source.x()) * wire.source_side <= 0
        or (last.x() - wire.target.x()) * wire.target_side <= 0
    ):
        return None
    if (
        minimum_y is not None
        and path.boundingRect().top() < minimum_y + STROKE_WIDTH / 2
    ):
        return None
    stroker = QPainterPathStroker()
    stroker.setWidth(STROKE_WIDTH)
    stroke = stroker.createStroke(path)
    if any(stroke.intersects(rect) for rect in obstacles) or not _decorations_clear(
        wire, obstacles
    ):
        return None
    segments = path_segments(path)
    xs = [
        path_point(path, i).x() * wire.source_side for i in range(path.elementCount())
    ]
    monotone = all(a <= b for a, b in zip(xs, xs[1:]))
    if not monotone and self_intersects(segments):
        return None
    return Candidate(
        wire, path, stroke, segments, [_Run.from_line(s) for s in segments]
    )


def _parallel_overlap(first: _Run, second: _Run) -> float:
    """Length of near-parallel, insufficiently separated runs, not point crossings."""
    a, b, c, d = first.bounds
    e, f, g, h = second.bounds
    clearance = STROKE_WIDTH + 1
    if c + clearance < e or g + clearance < a or d + clearance < f or h + clearance < b:
        return 0.0
    cosine = abs(first.ux * second.ux + first.uy * second.uy)
    if cosine < PARALLEL_COSINE:
        return 0.0
    x, y = second.x - first.x, second.y - first.y
    across = x * first.uy - y * first.ux
    end_across = across + second.length * (second.ux * first.uy - second.uy * first.ux)
    if min(abs(across), abs(end_across)) >= clearance:
        return 0.0
    along = x * first.ux + y * first.uy
    end_along = along + second.length * (second.ux * first.ux + second.uy * first.uy)
    lower, upper = sorted((along, end_along))
    return max(0.0, min(first.length, upper) - max(0.0, lower))


def _outside_shared_sockets(candidate: Candidate, previous: Candidate) -> QPainterPath:
    sockets = QPainterPath()
    for point in (candidate.wire.source, candidate.wire.target):
        if point in (previous.wire.source, previous.wire.target):
            sockets.addEllipse(point, SOCKET_RADIUS, SOCKET_RADIUS)
    return sockets


def route_conflicts(
    candidate: Candidate, previous: list[Candidate]
) -> tuple[bool, int]:
    """Forbid shared runs; count remaining, potentially unavoidable point crossings."""
    crossings = 0
    for earlier in previous:
        # Stroke overlap is a cheap broad phase; separated tracks need no sampling.
        if not candidate.stroke.intersects(earlier.stroke):
            continue
        sockets = _outside_shared_sockets(candidate, earlier)
        current = candidate.stroke.subtracted(sockets)
        other = earlier.stroke.subtracted(sockets)
        if not current.intersects(other):
            continue
        crossings += 1
        shared = _shared_run(candidate, earlier, sockets)
        if shared >= WIRE_GAP:
            return True, crossings
    return False, crossings


def _shared_run(
    candidate: Candidate, earlier: Candidate, sockets: QPainterPath
) -> float:
    total = 0.0
    common = (
        [
            p
            for p in (candidate.wire.source, candidate.wire.target)
            if p in (earlier.wire.source, earlier.wire.target)
        ]
        if not sockets.isEmpty()
        else []
    )
    # Clip at the circle boundary, rather than exempting a whole flattened
    # segment that happens to start inside it (which could be hundreds of px).
    for segment in _trim_runs(candidate.runs, common):
        for other in _trim_runs(earlier.runs, common):
            total += _parallel_overlap(segment, other)
            if total >= WIRE_GAP:
                return total
    return total


def _trim_runs(runs: list[_Run], centers: list[QPointF]) -> list[_Run]:
    for center in centers:
        runs = [part for run in runs for part in _outside_circle(run, center)]
    return runs


def _outside_circle(run: _Run, center: QPointF) -> list[_Run]:
    dx, dy = run.x - center.x(), run.y - center.y()
    along = dx * run.ux + dy * run.uy
    discriminant = SOCKET_RADIUS**2 - (dx * dx + dy * dy - along * along)
    if discriminant <= 0:
        return [run]
    radius = sqrt(discriminant)
    lower, upper = max(0.0, -along - radius), min(run.length, -along + radius)
    if upper <= lower:
        return [run]
    return [
        run.portion(a, b)
        for a, b in ((0.0, lower), (upper, run.length))
        if b - a > GEOMETRY_EPSILON
    ]


def candidate_rank(candidate: Candidate, crossings: int) -> tuple[float, ...]:
    """Correctness precedes this lexicographic readability/compactness preference."""
    direct = hypot(
        candidate.wire.target.x() - candidate.wire.source.x(),
        candidate.wire.target.y() - candidate.wire.source.y(),
    )
    return (
        crossings,
        candidate.path.elementCount(),
        candidate.path.length() - direct,
        candidate.path.boundingRect().height(),
        candidate.path.boundingRect().top(),
    )
