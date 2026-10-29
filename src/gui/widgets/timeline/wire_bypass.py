"""Broad, tangent-continuous bypass candidates for compact blocking clusters."""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform

from src.gui.widgets.timeline.wire_geometry import STROKE_WIDTH, WIRE_GAP

if TYPE_CHECKING:
    from src.gui.widgets.timeline.wire_router import Wire

MAX_BYPASS_TRACKS = 64  # Bounded 512 px detour on each side; never modulo reuse.
CLUSTER_GAP = WIRE_GAP * 2
FAN_TRANSITION = 32.0


def blocking_envelope(
    wire: Wire, direct: QPainterPath, obstacles: list[QRectF]
) -> QRectF | None:
    """Merge only painted blockers near the obstructed trajectory, not empty rows."""
    if (wire.target.x() - wire.source.x()) * wire.source_side <= WIRE_GAP * 4:
        return None
    if wire.target_side != -wire.source_side:
        return None
    stroker = QPainterPathStroker()
    stroker.setWidth(STROKE_WIDTH)
    stroke = stroker.createStroke(direct)
    blockers = [rect for rect in obstacles if stroke.intersects(rect)]
    if not blockers:
        return None
    envelope = QRectF(blockers[0])
    for rect in blockers[1:]:
        envelope = envelope.united(rect)
    remaining = [rect for rect in obstacles if rect not in blockers]
    while remaining:
        nearby = [
            rect
            for rect in remaining
            if envelope.adjusted(
                -CLUSTER_GAP, -CLUSTER_GAP, CLUSTER_GAP, CLUSTER_GAP
            ).intersects(rect)
        ]
        if not nearby:
            break
        for rect in nearby:
            envelope = envelope.united(rect)
            remaining.remove(rect)
    return envelope


def _smooth_bypass(wire: Wire, envelope: QRectF, y: float) -> QPainterPath:
    """Three C1-connected cubics, with a monotone, horizontal central corridor."""
    direction = wire.source_side
    transform = QTransform.fromScale(direction, 1)
    start, target = transform.map(wire.source), transform.map(wire.target)
    bounds = transform.mapRect(envelope)
    left, right = bounds.left() - WIRE_GAP, bounds.right() + WIRE_GAP
    if left <= start.x() + WIRE_GAP or right >= target.x() - WIRE_GAP:
        return QPainterPath()
    before, across, after = left - start.x(), right - left, target.x() - right
    entry_handle = min(before / 2, across / 3)
    exit_handle = min(after / 2, across / 3)
    entry, exit_point = QPointF(left, y), QPointF(right, y)
    path = QPainterPath(start)
    path.cubicTo(
        start + QPointF(before / 2, 0), entry - QPointF(entry_handle, 0), entry
    )
    path.cubicTo(
        entry + QPointF(entry_handle, 0),
        exit_point - QPointF(exit_handle, 0),
        exit_point,
    )
    path.cubicTo(
        exit_point + QPointF(exit_handle, 0), target - QPointF(after / 2, 0), target
    )
    return transform.map(path)


def bypass_candidates(
    wire: Wire, envelope: QRectF, rank: int, population: int
) -> list[QPainterPath]:
    """Try ordered separated tracks on both sides, with a fixed maximum extent."""
    half = ceil(population / 2)
    above = max(1, half - rank) if rank < half else rank - half + 1
    below = rank + 1 if rank < half else rank - half + 1
    # The preferred half preserves endpoint order through a common corridor.
    sides = (-1, 1) if rank < half else (1, -1)
    paths = []
    for side in sides:
        track = min(MAX_BYPASS_TRACKS, above if side < 0 else below)
        boundary = envelope.top() if side < 0 else envelope.bottom()
        paths.append(_smooth_bypass(wire, envelope, boundary + side * track * WIRE_GAP))
    return paths


def extra_bypasses(wire: Wire, envelope: QRectF) -> list[QPainterPath]:
    """Bounded alternatives when ordered tracks are blocked or already occupied."""
    return [
        _smooth_bypass(wire, envelope, boundary + side * track * WIRE_GAP)
        for track in range(1, MAX_BYPASS_TRACKS + 1)
        for side, boundary in ((-1, envelope.top()), (1, envelope.bottom()))
    ]


def fan_candidates(wire: Wire) -> list[QPainterPath]:
    """Separate a branch/merge just outside its shared terminal neighbourhood."""
    direction = wire.source_side
    source_x, target_x = wire.source.x() * direction, wire.target.x() * direction
    if wire.target_side != -direction or target_x - source_x <= FAN_TRANSITION * 2:
        return []
    # These are guide positions for wire separation, not invented event bodies.
    left = source_x + FAN_TRANSITION + WIRE_GAP
    right = target_x - FAN_TRANSITION - WIRE_GAP
    guide = QTransform.fromScale(direction, 1).mapRect(QRectF(left, 0, right - left, 0))
    return [
        _smooth_bypass(wire, guide, y + sign * WIRE_GAP * track)
        for track in (1, 2, 3, 4)
        for y in sorted({wire.source.y(), wire.target.y()})
        for sign in (-1, 1)
    ]


def side_candidates(wire: Wire) -> list[QPainterPath]:
    """Small smooth return from a duration start's outward-facing side socket."""
    forward = -wire.target_side
    distance = (wire.target.x() - wire.source.x()) * forward
    if wire.source_side != wire.target_side or distance <= WIRE_GAP * 8:
        return []
    handle = WIRE_GAP * 2
    entry_x = wire.source.x() + wire.source_side * handle
    exit_x = wire.target.x() + wire.target_side * handle * 2
    paths = []
    for offset in (-handle, handle, -handle * 2, handle * 2):
        y = wire.source.y() + offset
        entry, exit_point = QPointF(entry_x, y), QPointF(exit_x, y)
        path = QPainterPath(wire.source)
        path.cubicTo(
            wire.source + QPointF(wire.source_side * handle, 0),
            entry - QPointF(forward * handle, 0),
            entry,
        )
        path.cubicTo(
            entry + QPointF(forward * handle, 0),
            exit_point - QPointF(forward * handle, 0),
            exit_point,
        )
        path.cubicTo(
            exit_point + QPointF(forward * handle, 0),
            wire.target + QPointF(wire.target_side * handle, 0),
            wire.target,
        )
        paths.append(path)
    return paths


def compact_corridor(
    wire: Wire, envelope: QRectF, rank: int, population: int
) -> list[QPointF]:
    """Ordered nested elbows when broad sweeps cannot fit the entry corridor.

    This is the existing rounded-orthogonal representation, with coordinated
    turning columns rather than repeated tracks. It is only a crowded fallback.
    """
    direction = wire.source_side
    transform = QTransform.fromScale(direction, 1)
    source, target = transform.map(wire.source), transform.map(wire.target)
    bounds = transform.mapRect(envelope)
    half = ceil(population / 2)
    gap = STROKE_WIDTH + 0.5
    available = min(bounds.left() - source.x(), target.x() - bounds.right()) - WIRE_GAP
    if half * gap <= available / 2 or half * gap >= available:
        return []
    if rank < half:
        column = rank + 1
        y = bounds.top() - (half - rank) * WIRE_GAP
    else:
        column = population - rank
        y = bounds.bottom() + (rank - half + 1) * WIRE_GAP
    left, right = source.x() + column * gap, target.x() - column * gap
    return [
        transform.map(point)
        for point in (
            source,
            QPointF(left, source.y()),
            QPointF(left, y),
            QPointF(right, y),
            QPointF(right, target.y()),
            target,
        )
    ]
