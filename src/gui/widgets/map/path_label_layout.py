"""Find readable positions beside the visible course of a map path."""

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import pairwise

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTransform

_GAP_PX = 5.0
_SAMPLE_FRACTIONS = (0.5, 0.375, 0.625, 0.25, 0.75, 0.125, 0.875)


@dataclass(frozen=True)
class PathLabelAnchor:
    """A path position, with a local reading angle and a chosen side."""

    point: QPointF
    angle: float
    side: int

    def scene_transform(
        self, label_rect: QRectF, inv_scale: float, stroke_width_px: float
    ) -> QTransform:
        """Map the label's pixel rectangle to scene coordinates."""
        offset = (label_rect.height() + stroke_width_px) / 2 + _GAP_PX
        transform = QTransform()
        transform.translate(self.point.x(), self.point.y())
        transform.rotate(self.angle)
        transform.scale(inv_scale, inv_scale)
        transform.translate(-label_rect.center().x(), -label_rect.center().y())
        transform.translate(0.0, self.side * offset)
        return transform


def path_label_anchors(
    path: QPainterPath,
    points: Sequence[QPointF],
    viewport: QRectF | None,
    label_width: float,
) -> Iterator[PathLabelAnchor]:
    """Sample visible runs by distance and prefer stretches close to horizontal."""
    bounds = path.controlPointRect()
    if viewport is not None and not viewport.intersects(
        bounds.adjusted(-1e-7, -1e-7, 1e-7, 1e-7)
    ):
        return
    length = path.length()
    if length <= 0:
        return

    runs = (
        _visible_runs(points, viewport)
        if viewport is not None and not viewport.contains(bounds)
        else [(0.0, length)]
    )
    for start, end in sorted(runs, key=lambda run: run[0] - run[1])[:4]:
        samples = []
        span = end - start
        for fraction in _SAMPLE_FRACTIONS:
            distance = start + span * fraction
            room = min(label_width / 2, distance - start, end - distance)
            if room <= 0:
                continue
            before = path.pointAtPercent(path.percentAtLength(distance - room))
            after = path.pointAtPercent(path.percentAtLength(distance + room))
            chord = after - before
            direct_length = math.hypot(chord.x(), chord.y())
            if direct_length < room:
                continue
            angle = math.degrees(math.atan2(chord.y(), chord.x()))
            angle = (angle + 90) % 180 - 90
            point = path.pointAtPercent(path.percentAtLength(distance))
            bend = 1 - direct_length / (2 * room)
            score = abs(angle) / 90 + bend + abs(fraction - 0.5)
            samples.append((score, point, angle))

        for _, point, angle in sorted(samples, key=lambda sample: sample[0]):
            yield PathLabelAnchor(point, angle, -1)
            yield PathLabelAnchor(point, angle, 1)


def _visible_runs(
    points: Sequence[QPointF], viewport: QRectF
) -> list[tuple[float, float]]:
    """Return the arc-length intervals of a polyline inside the viewport."""
    runs: list[tuple[float, float]] = []
    distance = 0.0
    for previous, point in pairwise(points):
        dx, dy = point.x() - previous.x(), point.y() - previous.y()
        length = math.hypot(dx, dy)
        interval = _clip_segment(previous.x(), previous.y(), dx, dy, viewport)
        if length > 0 and interval is not None:
            first, last = interval
            start, end = distance + first * length, distance + last * length
            if runs and math.isclose(runs[-1][1], start, rel_tol=0, abs_tol=1e-7):
                runs[-1] = (runs[-1][0], end)
            elif end > start:
                runs.append((start, end))
        distance += length
    return runs


def _clip_segment(
    x: float, y: float, dx: float, dy: float, viewport: QRectF
) -> tuple[float, float] | None:
    """Clip a segment to the rectangle and return its visible fractions."""
    first, last = 0.0, 1.0
    for direction, gap in (
        (-dx, x - viewport.left()),
        (dx, viewport.right() - x),
        (-dy, y - viewport.top()),
        (dy, viewport.bottom() - y),
    ):
        if direction < 0:
            first = max(first, gap / direction)
        elif direction > 0:
            last = min(last, gap / direction)
        elif gap < 0:
            return None
    return (first, last) if first < last else None
