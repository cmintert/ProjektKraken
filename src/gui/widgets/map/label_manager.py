"""Label Manager for Dynamic GIS-style Label Layout.

Provides a collision-aware label layout engine (Greedy PAL-Lite) that
dynamically positions marker labels to minimize overlap.  Labels are
placed at the best available position from an 8-candidate hierarchy,
and lower-priority labels gracefully hide when no free space exists.
"""

import logging
from typing import List, Optional, Protocol

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsItem


class LabelLayoutItem(Protocol):
    """Device-independent contract consumed by the shared label layout."""

    connection_count: int
    _label_item: QGraphicsItem

    def isVisible(self) -> bool:
        """Return whether the label owner is visible."""
        ...

    def label_anchor_scene_pos(self) -> QPointF:
        """Return the label anchor in scene coordinates."""
        ...

    def label_clearance_px(self, view_scale: float = 1.0) -> float:
        """Return required clearance around the label in pixels."""
        ...

    def label_obstacle_scene_rect(self, view_scale: float = 1.0) -> QRectF:
        """Return actual rendered bounds in scene coordinates."""
        ...

    def apply_label_scene_position(
        self, scene_x: float, scene_y: float, inv_scale: float
    ) -> None:
        """Apply the chosen scene position and inverse scale."""
        ...

    def hide_layout_label(self) -> None:
        """Hide the label when no collision-free placement exists."""
        ...

logger = logging.getLogger(__name__)


class LabelManager:
    """Spatial index and layout calculator for marker labels.

    Tracks occupied rectangles in scene coordinates and assigns
    each marker label to the best free position from an 8-slot
    candidate hierarchy (Bottom, Top, Right, Left, and diagonals).
    Markers are processed in descending ``connection_count`` order
    so that high-priority entities claim the best real estate first.
    """

    # Candidate offsets as (dx_factor, dy_factor) relative to anchor size.
    # Order defines priority: Bottom, Top, Right, Left, then diagonals.
    _CANDIDATE_OFFSETS = [
        (0.0, 1.0),  # Bottom (centered below)
        (0.0, -1.0),  # Top (centered above)
        (1.0, 0.0),  # Right
        (-1.0, 0.0),  # Left
        (0.5, 1.0),  # Bottom-Right
        (-0.5, -1.0),  # Top-Left
        (0.5, -1.0),  # Top-Right
        (-0.5, 1.0),  # Bottom-Left
    ]

    # Small gap (pixels) between anchor and label.
    _PADDING = 2.0

    def __init__(self) -> None:
        """Initializes the LabelManager with an empty spatial index."""
        self._occupied_rects: List[QRectF] = []
        self._placements: dict[int, tuple[float, float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_layout_pass(
        self,
        markers: List[LabelLayoutItem],
        view_scale: float,
        extra_obstacles: Optional[List[QRectF]] = None,
    ) -> None:
        """Runs a full label-layout pass over the given markers.

        1. Clears previously occupied rectangles.
        2. Registers any extra obstacles (e.g. keyframe dots and labels).
        3. Registers every marker icon bounding rect as an obstacle.
        4. Sorts markers by ``connection_count`` (descending) and places
           their labels.

        Args:
            markers: List of MarkerItem instances to lay out.
            view_scale: Current view transform scale factor
                (``transform().m11()``), used to convert label sizes
                from device-independent to scene coordinates.
            extra_obstacles: Optional list of scene-coordinate rects
                to pre-register as occupied (e.g. keyframe dots and
                labels) before placing marker labels.
        """
        self._occupied_rects.clear()
        self._placements.clear()

        # Step 0 – register extra obstacles (keyframe labels, etc.).
        if extra_obstacles:
            self._occupied_rects.extend(extra_obstacles)

        visible_items = [item for item in markers if item.isVisible()]
        for item in markers:
            if not item.isVisible():
                item.hide_layout_label()

        if not visible_items:
            return

        inv_scale = 1.0 / view_scale if view_scale > 0 else 1.0

        # Step 1 – register marker icons as obstacles.
        for marker in visible_items:
            self._occupied_rects.append(
                self._marker_obstacle_rect(marker, inv_scale, view_scale)
            )

        # Step 2 – sort markers by priority and place their labels.
        sorted_markers = sorted(
            visible_items,
            key=lambda m: getattr(m, "connection_count", 0),
            reverse=True,
        )
        for marker in sorted_markers:
            self._place_label(marker, inv_scale, view_scale)

    def refresh_cached_positions(
        self, markers: List[LabelLayoutItem], view_scale: float
    ) -> None:
        """Move labels with zoom while preserving their selected layout slots.

        This lightweight path skips collision detection during active zooming.
        A debounced full layout can then reconsider collisions after input stops.
        """
        inv_scale = 1.0 / view_scale if view_scale > 0 else 1.0
        for marker in markers:
            offset = self._placements.get(id(marker))
            if offset is None or not marker.isVisible():
                continue
            candidate = self._candidate_rect(
                marker, inv_scale, view_scale, *offset
            )
            marker.apply_label_scene_position(
                candidate.x(), candidate.y(), inv_scale
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_label(
        self, marker: LabelLayoutItem, inv_scale: float, view_scale: float
    ) -> None:
        """Tries to place a single marker's label at the best candidate.

        Args:
            marker: The MarkerItem whose label to place.
            inv_scale: Inverse of the current view scale.
        """
        for dx_factor, dy_factor in self._CANDIDATE_OFFSETS:
            candidate = self._candidate_rect(
                marker, inv_scale, view_scale, dx_factor, dy_factor
            )

            if self._is_space_free(candidate):
                marker.apply_label_scene_position(
                    candidate.x(), candidate.y(), inv_scale
                )
                self._occupied_rects.append(candidate)
                self._placements[id(marker)] = (dx_factor, dy_factor)
                return

        # All 8 candidates collided – hide the label.
        marker.hide_layout_label()

    def _candidate_rect(
        self,
        marker: LabelLayoutItem,
        inv_scale: float,
        view_scale: float,
        dx_factor: float,
        dy_factor: float,
    ) -> QRectF:
        """Return one label candidate in scene coordinates."""
        label_rect = marker._label_item.boundingRect()
        label_w = label_rect.width() * inv_scale
        label_h = label_rect.height() * inv_scale
        obstacle = self._marker_obstacle_rect(marker, inv_scale, view_scale)
        padding = self._PADDING * inv_scale

        if dx_factor == 0.0:
            candidate_x = obstacle.center().x() - label_w / 2.0
        elif dx_factor > 0:
            candidate_x = obstacle.right() + padding
        else:
            candidate_x = obstacle.left() - padding - label_w

        if dy_factor > 0:
            candidate_y = obstacle.bottom() + padding
        elif dy_factor < 0:
            candidate_y = obstacle.top() - padding - label_h
        else:
            candidate_y = obstacle.center().y() - label_h / 2.0

        return QRectF(candidate_x, candidate_y, label_w, label_h)

    @staticmethod
    def _marker_obstacle_rect(
        marker: LabelLayoutItem,
        inv_scale: float,
        view_scale: float,
    ) -> QRectF:
        """Resolve actual bounds, with compatibility for geometry labels."""
        obstacle_getter = getattr(marker, "label_obstacle_scene_rect", None)
        if callable(obstacle_getter):
            return QRectF(obstacle_getter(view_scale))
        scene_pos = marker.label_anchor_scene_pos()
        clearance = marker.label_clearance_px(view_scale) * inv_scale
        return QRectF(
            scene_pos.x() - clearance,
            scene_pos.y() - clearance,
            clearance * 2.0,
            clearance * 2.0,
        )

    def _is_space_free(self, candidate: QRectF) -> bool:
        """Checks whether *candidate* overlaps any occupied rectangle.

        Args:
            candidate: The rectangle to test (in scene coordinates).

        Returns:
            True if the candidate does not intersect any occupied rect.
        """
        for occupied in self._occupied_rects:
            if candidate.intersects(occupied):
                return False
        return True
