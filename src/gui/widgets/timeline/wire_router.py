"""Ordered node-editor wires: smooth side tangents and rounded obstacle routes."""

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker

WIRE_GAP = 8.0
CORNER_RADIUS = 24.0
BEND_COST = 24.0
CROSSING_COST = 48.0
OVERLAP_COST = 160.0
MIN_FORWARD_GAP = 32.0
MIN_POLYLINE_POINTS = 2
LOCAL_ROUTE_SPAN = 1024.0
WIRE_CLEARANCE = 1.75


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


def _best_spline(
    wire: Wire, obstacles: list[QRectF], previous: list[QPainterPath]
) -> QPainterPath | None:
    """Prefer one smooth, non-self-intersecting cubic over routed bends."""
    vertical = abs(wire.target.y() - wire.source.y())
    forward = (wire.target.x() - wire.source.x()) * wire.source_side
    if vertical < MIN_FORWARD_GAP and forward < MIN_FORWARD_GAP:
        return None
    distance = abs(wire.target.x() - wire.source.x())
    handles = sorted(
        {
            max(16.0, min(120.0, distance / 2)),
            32.0,
            64.0,
            96.0,
            144.0,
            216.0,
            324.0,
            486.0,
        }
    )
    stroker = QPainterPathStroker()
    stroker.setWidth(3.0)
    sockets = QPainterPath()
    sockets.addEllipse(wire.source, 24, 24)
    sockets.addEllipse(wire.target, 24, 24)
    default = smooth_wire(wire)
    default_stroke = stroker.createStroke(default)
    if not any(default_stroke.intersects(rect) for rect in obstacles) and not any(
        earlier.intersects(default_stroke.subtracted(sockets)) for earlier in previous
    ):
        return default
    best: tuple[float, QPainterPath] | None = None
    for outgoing in handles:
        for incoming in handles:
            if (
                forward > 0
                and wire.target_side == -wire.source_side
                and outgoing + incoming > distance
            ):
                continue
            path = QPainterPath(wire.source)
            path.cubicTo(
                wire.source + QPointF(wire.source_side * outgoing, 0),
                wire.target + QPointF(wire.target_side * incoming, 0),
                wire.target,
            )
            stroke = stroker.createStroke(path)
            if any(stroke.intersects(rect) for rect in obstacles):
                continue
            cost = path.length() + (outgoing + incoming) * 0.05
            away_from_sockets = stroke.subtracted(sockets)
            cost += CROSSING_COST * sum(
                earlier.intersects(away_from_sockets) for earlier in previous
            )
            if best is None or cost < best[0]:
                best = cost, path
    return best[1] if best is not None else None


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
    for dx, dy, axis in ((-1, 0, 1), (1, 0, 1), (0, -1, 2), (0, 1, 2)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
            continue
        if direction == 0 and (dy or dx != wire.source_side):
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


def route_wires(
    wires: list[Wire], obstacles: list[QRectF], minimum_y: float | None = None
) -> list[QPainterPath]:
    """Route in caller's stable branch order, separating overlapping wire tracks."""
    reserved: list[tuple[QPointF, QPointF]] = []
    paths = []
    previous: list[QPainterPath] = []
    stroker = QPainterPathStroker()
    stroker.setWidth(3.0)
    intervals: list[tuple[float, float]] = []
    for wire in wires:
        # Offscreen endpoints may legitimately be above the sticky ruler. Their
        # path stays world-relative; viewport clipping then hides only that part.
        floor = minimum_y
        if floor is not None and min(wire.source.y(), wire.target.y()) < floor:
            floor = None
        direct = _best_spline(wire, obstacles, previous)
        if direct is not None:
            paths.append(direct)
            previous.append(stroker.createStroke(direct))
            continue
        lower, upper = sorted((wire.source.y(), wire.target.y()))
        track = sum(not (end < lower or start > upper) for start, end in intervals) % 8
        intervals.append((lower, upper))
        region = (
            QRectF(wire.source, wire.target).normalized().adjusted(-160, -80, 160, 80)
        )
        nearby = [rect for rect in obstacles if rect.intersects(region)]
        points = _orthogonal_route(wire, nearby, track, reserved, floor)
        if points:
            path = _safe_rounding(points, obstacles)
            if path.isEmpty():
                points = _orthogonal_route(wire, obstacles, track, reserved, floor)
                path = _safe_rounding(points, obstacles) if points else QPainterPath()
            reserved.extend(zip(points, points[1:]))
            paths.append(path)
            previous.append(stroker.createStroke(path))
        else:
            # Overlapping node bodies can close a port. Leave that wire absent
            # rather than painting a false loop or cutting through authored text.
            paths.append(QPainterPath())
    return paths
