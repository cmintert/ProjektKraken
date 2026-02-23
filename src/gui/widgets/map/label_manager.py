"""Label Manager for Dynamic GIS-style Label Layout.

Provides a collision-aware label layout engine (Greedy PAL-Lite) that
dynamically positions marker labels and keyframe labels to minimize
overlap.  Labels are placed at the best available position from an
8-candidate hierarchy, and lower-priority labels gracefully hide
when no free space exists.
"""

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsObject

if TYPE_CHECKING:
    from src.gui.widgets.map.marker_item import MarkerItem
    from src.gui.widgets.map.trajectory_renderer import KeyframeLabelItem

logger = logging.getLogger(__name__)


class LabelManager:
    """Spatial index and layout calculator for marker and keyframe labels.

    Tracks occupied rectangles in scene coordinates and assigns
    each label to the best free position from an 8-slot candidate
    hierarchy (Bottom, Top, Right, Left, and diagonals).
    Markers are processed in descending ``connection_count`` order
    so that high-priority entities claim the best real estate first.
    Keyframe labels are placed after marker labels.
    """

    # Candidate offsets as (dx_factor, dy_factor) relative to anchor size.
    # Order defines priority: Bottom, Top, Right, Left, then diagonals.
    _CANDIDATE_OFFSETS = [
        (0.0, 1.0),    # Bottom (centered below)
        (0.0, -1.0),   # Top (centered above)
        (1.0, 0.0),    # Right
        (-1.0, 0.0),   # Left
        (0.5, 1.0),    # Bottom-Right
        (-0.5, -1.0),  # Top-Left
        (0.5, -1.0),   # Top-Right
        (-0.5, 1.0),   # Bottom-Left
    ]

    # Small gap (pixels) between anchor and label.
    _PADDING = 2.0

    def __init__(self) -> None:
        """Initializes the LabelManager with an empty spatial index."""
        self._occupied_rects: List[QRectF] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_layout_pass(
        self,
        markers: List["MarkerItem"],
        view_scale: float,
        extra_obstacles: Optional[List[QRectF]] = None,
        keyframe_pairs: Optional[
            List[Tuple[QGraphicsObject, "KeyframeLabelItem"]]
        ] = None,
    ) -> None:
        """Runs a full label-layout pass over markers and keyframe labels.

        1. Clears previously occupied rectangles.
        2. Registers any extra obstacles (e.g. keyframe dots).
        3. Registers every marker icon bounding rect as an obstacle.
        4. Sorts markers by ``connection_count`` (descending) and places
           their labels.
        5. Registers keyframe dot bounding rects and places keyframe
           labels.

        Args:
            markers: List of MarkerItem instances to lay out.
            view_scale: Current view transform scale factor
                (``transform().m11()``), used to convert label sizes
                from device-independent to scene coordinates.
            extra_obstacles: Optional list of scene-coordinate rects
                to pre-register as occupied before placing any labels.
            keyframe_pairs: Optional list of ``(dot, label)`` tuples
                where *dot* is a ``KeyframeItem`` (the anchor) and
                *label* is the corresponding ``KeyframeLabelItem``.
        """
        self._occupied_rects.clear()

        # Step 0 – register extra obstacles.
        if extra_obstacles:
            self._occupied_rects.extend(extra_obstacles)

        inv_scale = 1.0 / view_scale if view_scale > 0 else 1.0

        # Step 1 – register marker icons as obstacles.
        for marker in markers:
            icon_rect = marker.boundingRect()
            scene_pos = marker.scenePos()
            # Icon rect is in local coords centered on (0,0).
            # Map to scene by shifting by the marker's scene position,
            # then scaling by inv_scale (since ItemIgnoresTransformations).
            obstacle = QRectF(
                scene_pos.x() + icon_rect.x() * inv_scale,
                scene_pos.y() + icon_rect.y() * inv_scale,
                icon_rect.width() * inv_scale,
                icon_rect.height() * inv_scale,
            )
            self._occupied_rects.append(obstacle)

        # Step 2 – sort markers by priority and place their labels.
        sorted_markers = sorted(
            markers,
            key=lambda m: getattr(m, "connection_count", 0),
            reverse=True,
        )
        for marker in sorted_markers:
            self._place_label(marker, inv_scale)

        # Step 3 – place keyframe labels.
        if keyframe_pairs:
            for dot, kf_label in keyframe_pairs:
                if not dot.isVisible():
                    kf_label.setVisible(False)
                    continue
                # Register the dot as an obstacle.
                dr = dot.boundingRect()
                dsp = dot.scenePos()
                self._occupied_rects.append(
                    QRectF(
                        dsp.x() + dr.x(),
                        dsp.y() + dr.y(),
                        dr.width(),
                        dr.height(),
                    )
                )
                self._place_keyframe_label(dot, kf_label, inv_scale)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_label(
        self, marker: "MarkerItem", inv_scale: float
    ) -> None:
        """Tries to place a single marker's label at the best candidate.

        Args:
            marker: The MarkerItem whose label to place.
            inv_scale: Inverse of the current view scale.
        """
        label_item = marker._label_item
        label_rect = label_item.boundingRect()
        label_w = label_rect.width() * inv_scale
        label_h = label_rect.height() * inv_scale

        scene_pos = marker.scenePos()
        size = marker.resolved_size * inv_scale
        half_size = size / 2.0
        padding = self._PADDING * inv_scale

        for dx_factor, dy_factor in self._CANDIDATE_OFFSETS:
            # Compute candidate centre offset from the marker centre.
            if dx_factor == 0.0:
                cx = scene_pos.x() - label_w / 2.0
            elif dx_factor > 0:
                cx = scene_pos.x() + half_size + padding
            else:
                cx = scene_pos.x() - half_size - padding - label_w

            if dy_factor > 0:
                cy = scene_pos.y() + half_size + padding
            elif dy_factor < 0:
                cy = scene_pos.y() - half_size - padding - label_h
            else:
                cy = scene_pos.y() - label_h / 2.0

            candidate = QRectF(cx, cy, label_w, label_h)

            if self._is_space_free(candidate):
                # Convert scene position back to local coords.
                local_x = (cx - scene_pos.x()) / inv_scale
                local_y = (cy - scene_pos.y()) / inv_scale
                marker.apply_label_position(local_x, local_y, True)
                self._occupied_rects.append(candidate)
                return

        # All 8 candidates collided – hide the label.
        marker.apply_label_position(0.0, 0.0, False)

    def _place_keyframe_label(
        self,
        dot: QGraphicsObject,
        label: "KeyframeLabelItem",
        inv_scale: float,
    ) -> None:
        """Tries to place a keyframe label at the best candidate.

        Args:
            dot: The keyframe dot (anchor graphics item).
            label: The ``KeyframeLabelItem`` to position.
            inv_scale: Inverse of the current view scale.
        """
        label_rect = label.boundingRect()
        scale = getattr(label, "_label_scale", 1.0)
        label_w = label_rect.width() * scale * inv_scale
        label_h = label_rect.height() * scale * inv_scale

        scene_pos = dot.scenePos()
        dot_rect = dot.boundingRect()
        half_w = dot_rect.width() / 2.0
        half_h = dot_rect.height() / 2.0
        padding = self._PADDING * inv_scale

        for dx_factor, dy_factor in self._CANDIDATE_OFFSETS:
            if dx_factor == 0.0:
                cx = scene_pos.x() - label_w / 2.0
            elif dx_factor > 0:
                cx = scene_pos.x() + half_w + padding
            else:
                cx = scene_pos.x() - half_w - padding - label_w

            if dy_factor > 0:
                cy = scene_pos.y() + half_h + padding
            elif dy_factor < 0:
                cy = scene_pos.y() - half_h - padding - label_h
            else:
                cy = scene_pos.y() - label_h / 2.0

            candidate = QRectF(cx, cy, label_w, label_h)

            if self._is_space_free(candidate):
                # Offset in device pixels (before scene scaling).
                offset_x = (cx - scene_pos.x()) / inv_scale / scale
                offset_y = (cy - scene_pos.y()) / inv_scale / scale
                label.apply_label_position(offset_x, offset_y, True)
                self._occupied_rects.append(candidate)
                return

        # All 8 candidates collided – hide the label.
        label.apply_label_position(0.0, 0.0, False)

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
