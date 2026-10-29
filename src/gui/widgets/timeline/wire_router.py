"""Ordered node-editor wires: smooth side tangents and rounded obstacle routes."""

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker

from src.gui.widgets.timeline.wire_bypass import (
    blocking_envelope,
    bypass_candidates,
    compact_corridor,
    extra_bypasses,
    fan_candidates,
    side_candidates,
)
from src.gui.widgets.timeline.wire_geometry import (
    WIRE_GAP,
    Candidate,
    candidate_rank,
    path_point,
    route_conflicts,
    valid_candidate,
)

CORNER_RADIUS = 24.0
BEND_COST = 24.0
CROSSING_COST = 48.0
OVERLAP_COST = 160.0
MIN_FORWARD_GAP = 32.0
MIN_POLYLINE_POINTS = 2
LOCAL_ROUTE_SPAN = 1024.0
WIRE_CLEARANCE = 1.75
MAX_BYPASS_ALTERNATIVES = 8
SINGLE_CUBIC_ELEMENTS = 4


@dataclass(frozen=True)
class Wire:
    """Explicit source/output and target/input side sockets in display space."""

    source: QPointF
    target: QPointF
    source_side: float
    target_side: float


def smooth_wire(wire: Wire) -> QPainterPath:
    """Use the conventional cubic with collinear horizontal endpoint handles."""
    distance = abs(wire.target.x() - wire.source.x())
    vertical = abs(wire.target.y() - wire.source.y())
    reach = min(160.0, max(40.0, distance / 2, vertical * 0.35))
    if (wire.target.x() - wire.source.x()) * wire.source_side > 0:
        reach = min(reach, distance / 2)
    path = QPainterPath(wire.source)
    path.cubicTo(
        wire.source + QPointF(wire.source_side * reach, 0),
        wire.target + QPointF(wire.target_side * reach, 0),
        wire.target,
    )
    return path


def _blocked(first: QPointF, second: QPointF, obstacles: list[QRectF]) -> bool:
    """Test axis-aligned visibility against actual node bodies."""
    left, right = sorted((first.x(), second.x()))
    top, bottom = sorted((first.y(), second.y()))
    for obstacle in obstacles:
        rect = obstacle.adjusted(
            -WIRE_CLEARANCE, -WIRE_CLEARANCE, WIRE_CLEARANCE, WIRE_CLEARANCE
        )
        if first.y() == second.y():
            if (
                rect.top() < top < rect.bottom()
                and left < rect.right()
                and right > rect.left()
            ):
                return True
        elif (
            rect.left() < left < rect.right()
            and top < rect.bottom()
            and bottom > rect.top()
        ):
            return True
    return False


def _reservation_cost(
    first: QPointF, second: QPointF, reserved: list[tuple[QPointF, QPointF]]
) -> float:
    horizontal = first.y() == second.y()
    cost = 0.0
    for start, end in reserved:
        other_horizontal = start.y() == end.y()
        if horizontal == other_horizontal:
            axis = first.y() if horizontal else first.x()
            other_axis = start.y() if horizontal else start.x()
            first_span = sorted(
                (first.x(), second.x()) if horizontal else (first.y(), second.y())
            )
            second_span = sorted(
                (start.x(), end.x()) if horizontal else (start.y(), end.y())
            )
            if abs(axis - other_axis) < WIRE_GAP and max(
                first_span[0], second_span[0]
            ) < min(first_span[1], second_span[1]):
                cost += OVERLAP_COST
        else:
            across = start.x() if horizontal else start.y()
            axis = first.y() if horizontal else first.x()
            along = sorted(
                (first.x(), second.x()) if horizontal else (first.y(), second.y())
            )
            other = sorted((start.y(), end.y()) if horizontal else (start.x(), end.x()))
            if along[0] < across < along[1] and other[0] < axis < other[1]:
                cost += CROSSING_COST
    return cost


def _axes(
    wire: Wire, obstacles: list[QRectF], track: int, minimum_y: float | None
) -> tuple[list[float], list[float]]:
    gap = CORNER_RADIUS + track * WIRE_GAP
    xs = {wire.source.x(), wire.target.x()}
    ys = {wire.source.y(), wire.target.y()}
    # Let forks separate near their shared socket instead of following the
    # first wire as far as the next obstacle-derived grid line.
    port_gap = WIRE_GAP * (track + 1)
    for port in (wire.source, wire.target):
        xs.update((port.x() - port_gap, port.x() + port_gap))
        ys.update((port.y() - port_gap, port.y() + port_gap))
    # A long cross-world wire needs local port corridors and outside gutters,
    # not a quadratic grid of every intervening event's label corners.
    critical = [
        rect
        for rect in obstacles
        if any(
            rect.top() - 96 <= point.y() <= rect.bottom() + 96
            for point in (wire.source, wire.target)
        )
    ]
    if abs(wire.source.y() - wire.target.y()) <= LOCAL_ROUTE_SPAN:
        critical = obstacles
    for rect in critical:
        xs.update((rect.left() - gap, rect.right() + gap))
        ys.update((rect.top() - gap, rect.bottom() + gap))
    if obstacles:
        xs.update(
            (
                min(rect.left() for rect in obstacles) - gap,
                max(rect.right() for rect in obstacles) + gap,
            )
        )
        ys.update(
            (
                min(rect.top() for rect in obstacles) - gap,
                max(rect.bottom() for rect in obstacles) + gap,
            )
        )
    xs.update((min(xs) - gap, max(xs) + gap))
    ys.update((min(ys) - gap, max(ys) + gap))
    if minimum_y is not None:
        ys = {y for y in ys if y >= minimum_y}
    return sorted(xs), sorted(ys)


def _neighbors(
    node: tuple[int, int, int],
    xs: list[float],
    ys: list[float],
    obstacles: list[QRectF],
    wire: Wire,
    destination: tuple[int, int],
) -> list[tuple[int, int, int]]:
    x, y, direction = node
    result = []
    for dx, dy, axis in ((-1, 0, -1), (1, 0, 1), (0, -1, -2), (0, 1, 2)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
            continue
        if direction == 0 and (dy or dx != wire.source_side):
            continue
        if direction == -axis:
            # A search must not satisfy its initial side with an out-and-back
            # stub, which simplification would turn into a false vertical port.
            continue
        if (nx, ny) == destination and (dy or dx != -wire.target_side):
            continue
        if not _blocked(QPointF(xs[x], ys[y]), QPointF(xs[nx], ys[ny]), obstacles):
            result.append((nx, ny, axis))
    return result


def _orthogonal_route(
    wire: Wire,
    obstacles: list[QRectF],
    track: int,
    reserved: list[tuple[QPointF, QPointF]],
    minimum_y: float | None,
) -> list[QPointF]:
    xs, ys = _axes(wire, obstacles, track, minimum_y)
    start = (xs.index(wire.source.x()), ys.index(wire.source.y()), 0)
    destination = (xs.index(wire.target.x()), ys.index(wire.target.y()))
    queue = [(0.0, 0, start)]
    serial = count(1)
    costs = {start: 0.0}
    previous: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    while queue:
        _, _, node = heappop(queue)
        if node[:2] == destination:
            path = [QPointF(xs[node[0]], ys[node[1]])]
            while node in previous:
                node = previous[node]
                path.append(QPointF(xs[node[0]], ys[node[1]]))
            return list(reversed(path))
        first = QPointF(xs[node[0]], ys[node[1]])
        for neighbor in _neighbors(node, xs, ys, obstacles, wire, destination):
            second = QPointF(xs[neighbor[0]], ys[neighbor[1]])
            distance = abs(second.x() - first.x()) + abs(second.y() - first.y())
            turn = BEND_COST if node[2] and node[2] != neighbor[2] else 0.0
            cost = (
                costs[node]
                + distance
                + turn
                + _reservation_cost(first, second, reserved)
            )
            if cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = cost
                previous[neighbor] = node
                heuristic = abs(second.x() - wire.target.x()) + abs(
                    second.y() - wire.target.y()
                )
                heappush(queue, (cost + heuristic, next(serial), neighbor))
    return []


def _simplify(points: list[QPointF]) -> list[QPointF]:
    result: list[QPointF] = []
    for point in points:
        if len(result) >= MIN_POLYLINE_POINTS:
            first, second = result[-2:]
            if (first.x() == second.x() == point.x()) or (
                first.y() == second.y() == point.y()
            ):
                result.pop()
        result.append(point)
    return result


def rounded_route(
    points: list[QPointF], corner_radius: float = CORNER_RADIUS
) -> QPainterPath:
    """Round a small number of routing bends, keeping port tangents horizontal."""
    points = _simplify(points)
    path = QPainterPath(points[0])
    for index in range(1, len(points) - 1):
        previous, corner, following = points[index - 1 : index + 2]
        incoming, outgoing = corner - previous, following - corner
        before = abs(incoming.x()) + abs(incoming.y())
        after = abs(outgoing.x()) + abs(outgoing.y())
        radius = min(corner_radius, before / 2, after / 2)
        entry = corner - incoming * (radius / before)
        exit_point = corner + outgoing * (radius / after)
        path.lineTo(entry)
        path.quadTo(corner, exit_point)
    path.lineTo(points[-1])
    return path


def _safe_rounding(points: list[QPointF], obstacles: list[QRectF]) -> QPainterPath:
    """Keep the complete stroked curve clear after rounding routing corners."""
    stroker = QPainterPathStroker()
    stroker.setWidth(3.0)
    for radius in (CORNER_RADIUS, CORNER_RADIUS / 2, 4.0, 1.0):
        path = rounded_route(points, radius)
        stroke = stroker.createStroke(path)
        if not any(stroke.intersects(rect) for rect in obstacles):
            return path
    return QPainterPath()


def _select_candidate(
    wire: Wire,
    paths: list[QPainterPath],
    obstacles: list[QRectF],
    previous: list[Candidate],
    floor: float | None,
) -> Candidate | None:
    candidates = []
    for path in paths:
        candidate = valid_candidate(wire, path, obstacles, floor)
        if candidate is None:
            continue
        overlapping, crossings = route_conflicts(candidate, previous)
        if not overlapping:
            candidates.append((candidate_rank(candidate, crossings), candidate))
    return min(candidates, key=lambda entry: entry[0])[1] if candidates else None


def _fallback(
    wire: Wire,
    obstacles: list[QRectF],
    reserved: list[tuple[QPointF, QPointF]],
    previous: list[Candidate],
    floor: float | None,
) -> Candidate | None:
    region = QRectF(wire.source, wire.target).normalized().adjusted(-160, -80, 160, 80)
    nearby = [rect for rect in obstacles if rect.intersects(region)]
    for blockers in [nearby, obstacles] if nearby != obstacles else [obstacles]:
        for track in (0, 1, 2):
            points = _orthogonal_route(wire, blockers, track, reserved, floor)
            if points:
                selected = _select_candidate(
                    wire,
                    [_safe_rounding(points, obstacles)],
                    obstacles,
                    previous,
                    floor,
                )
                if selected is not None:
                    return selected
    return None


def _first_bypass(
    wire: Wire,
    envelope: QRectF,
    obstacles: list[QRectF],
    previous: list[Candidate],
    floor: float | None,
) -> Candidate | None:
    """Stop at a separated alternative instead of evaluating every outer track."""
    occupied = {
        line.y1()
        for earlier in previous
        for line in earlier.segments
        if line.dy() == 0 and line.length() >= envelope.width()
    }
    attempts = 0
    for path in extra_bypasses(wire, envelope):
        if path.isEmpty() or path_point(path, 3).y() in occupied:
            continue
        attempts += 1
        selected = _select_candidate(wire, [path], obstacles, previous, floor)
        if selected is not None:
            return selected
        if attempts >= MAX_BYPASS_ALTERNATIVES:
            break
    return None


def _ordered_envelopes(
    wires: list[Wire], obstacles: list[QRectF]
) -> tuple[list[QRectF | None], list[tuple[int, int]]]:
    envelopes = [
        blocking_envelope(wire, smooth_wire(wire), obstacles) for wire in wires
    ]
    groups: dict[tuple[float, ...], list[int]] = {}
    for index, envelope in enumerate(envelopes):
        if envelope is not None:
            key = (envelope.x(), envelope.y(), envelope.width(), envelope.height())
            groups.setdefault(key, []).append(index)
    order = [(0, 1)] * len(wires)
    for indices in groups.values():
        for rank, index in enumerate(indices):
            order[index] = (rank, len(indices))
    return envelopes, order


def _reduce_crossings(
    wire: Wire,
    selected: Candidate,
    obstacles: list[QRectF],
    previous: list[Candidate],
    floor: float | None,
) -> Candidate:
    """Compare bounded alternatives when an otherwise clear cubic crosses a wire."""
    if not route_conflicts(selected, previous)[1]:
        return selected
    return (
        _select_candidate(
            wire, [selected.path, *fan_candidates(wire)], obstacles, previous, floor
        )
        or selected
    )


def route_wires(
    wires: list[Wire], obstacles: list[QRectF], minimum_y: float | None = None
) -> list[QPainterPath]:
    """Keep direct cubics; bypass clusters on ordered tracks without shared runs."""
    obstacles = sorted(obstacles, key=lambda r: (r.x(), r.y(), r.width(), r.height()))
    envelopes, order = _ordered_envelopes(wires, obstacles)
    reserved: list[tuple[QPointF, QPointF]] = []
    previous: list[Candidate] = []
    paths = []
    for index, wire in enumerate(wires):
        floor = minimum_y
        if floor is not None and min(wire.source.y(), wire.target.y()) < floor:
            floor = None
        selected = _select_candidate(
            wire, [smooth_wire(wire)], obstacles, previous, floor
        )
        envelope = envelopes[index]
        if selected is None and envelope is not None:
            points = compact_corridor(wire, envelope, *order[index])
            if points:
                selected = _select_candidate(
                    wire, [rounded_route(points, 1.0)], obstacles, previous, floor
                )
        if selected is None and envelope is not None:
            selected = _select_candidate(
                wire,
                bypass_candidates(wire, envelope, *order[index]),
                obstacles,
                previous,
                floor,
            )
            if selected is None:
                selected = _first_bypass(wire, envelope, obstacles, previous, floor)
        if selected is None:
            selected = _select_candidate(
                wire,
                [*fan_candidates(wire), *side_candidates(wire)],
                obstacles,
                previous,
                floor,
            )
        if selected is None:
            selected = _fallback(wire, obstacles, reserved, previous, floor)
        elif selected.path.elementCount() == SINGLE_CUBIC_ELEMENTS:
            selected = _reduce_crossings(wire, selected, obstacles, previous, floor)
        path = selected.path if selected is not None else QPainterPath()
        paths.append(path)
        if selected is not None:
            previous.append(selected)
            reserved.extend(
                (line.p1(), line.p2())
                for line in selected.segments
                if line.dx() == 0 or line.dy() == 0
            )
    return paths
