"""Corner-cutting subdivision for open map paths."""

from math import isclose

from src.core.region_geometry import Ring


def is_path_bend(
    before: dict[str, float], corner: dict[str, float], after: dict[str, float]
) -> bool:
    """Return whether both adjacent segments form a non-collinear bend."""
    incoming_x = corner["x"] - before["x"]
    incoming_y = corner["y"] - before["y"]
    outgoing_x = after["x"] - corner["x"]
    outgoing_y = after["y"] - corner["y"]
    return not isclose(incoming_x * outgoing_y, incoming_y * outgoing_x)


def subdivide_path(points: Ring) -> Ring:
    """Replace each bend with two points a quarter of the way to its neighbors."""
    if len(points) <= 1:
        return [dict(point) for point in points]
    softened = [dict(points[0])]
    for before, corner, after in zip(points, points[1:], points[2:], strict=False):
        if not is_path_bend(before, corner, after):
            softened.append(dict(corner))
            continue
        for neighbor in (before, after):
            softened.append(
                {
                    "x": corner["x"] + (neighbor["x"] - corner["x"]) / 4,
                    "y": corner["y"] + (neighbor["y"] - corner["y"]) / 4,
                }
            )
    softened.append(dict(points[-1]))
    return softened
