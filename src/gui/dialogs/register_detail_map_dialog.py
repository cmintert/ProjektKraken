"""Register Detail Map Dialog.

Phase-1 entry point for marking a map as a detail child of another map.
The user picks a parent (the world's master, or another already-registered
detail map) and confirms.  The dialog produces a default centred,
aspect-locked-affine registration payload — Phase 3 replaces the
default with canvas-driven placement.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.map import Map
from src.gui.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER

logger = logging.getLogger(__name__)


# Phase-1 default footprint: centred, quarter-width, no rotation.
# Phase 3 overrides every value via the canvas placement tool.
_DEFAULT_CENTER = (0.5, 0.5)
_DEFAULT_SCALE = 0.25
_DEFAULT_ROTATION_DEG = 0.0


class RegisterDetailMapDialog(QDialog):
    """Modal dialog that collects (parent_id, registration) for a detail map.

    Args:
        detail_map: The map that will be registered as a detail child.
        candidate_parents: Maps eligible to act as the parent.  Already
            filtered by the caller — must contain only master / detail
            maps and must exclude ``detail_map`` itself.
        resolve_image_path: Callable that turns a stored ``image_path``
            (which may be relative to the world directory) into an
            absolute path on disk.  Used to read the detail map's
            intrinsic aspect ratio without forcing the dialog to know
            where the world root lives.
        parent: Parent widget.

    """

    def __init__(
        self,
        detail_map: Map,
        candidate_parents: List[Map],
        resolve_image_path: Optional[Callable[[str], str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize detail-map registration controls."""
        super().__init__(parent)
        self._detail_map = detail_map
        self._candidates = candidate_parents
        self._resolve_image_path = resolve_image_path
        self._selected_parent_id: Optional[str] = None
        self._registration: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Register as Detail Map")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        intro = QLabel(
            f"Register <b>{detail_map.name}</b> as a detail map nested "
            "inside another map.  A default footprint is placed at the "
            "centre of the parent — drag handles will let you adjust "
            "placement on the parent canvas (later phase)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel("Parent map:"))
        self._parent_combo = QComboBox(self)
        for m in candidate_parents:
            role = (m.attributes or {}).get("map_role", "")
            label = f"{m.name}  ({role})" if role else m.name
            self._parent_combo.addItem(label, m.id)
        layout.addWidget(self._parent_combo)

        if not candidate_parents:
            warn = QLabel(
                "No eligible parent maps exist yet.  Designate a master "
                "map first."
            )
            warn.setWordWrap(True)
            warn.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(warn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(bool(candidate_parents))
        layout.addWidget(buttons)

    def _accept(self) -> None:
        """Build the registration payload and close with Accepted."""
        parent_id = self._parent_combo.currentData()
        if not parent_id:
            self.reject()
            return
        self._selected_parent_id = parent_id

        # Effective aspect ratio = intrinsic * (parent_h / parent_w).
        # This makes the footprint polygon have the correct visual shape on
        # the specific parent map regardless of its pixel aspect ratio.
        intrinsic = self._read_image_aspect(self._detail_map.image_path or "")
        parent_size = self._read_parent_pixel_size(parent_id)
        if parent_size and parent_size[0] > 0:
            effective = intrinsic * parent_size[1] / parent_size[0]
        else:
            effective = intrinsic

        self._registration = {
            "mode": "aspect_locked_affine",
            "version": 1,
            "master_center_norm": {
                "x": _DEFAULT_CENTER[0],
                "y": _DEFAULT_CENTER[1],
            },
            "scale_norm": _DEFAULT_SCALE,
            "rotation_deg": _DEFAULT_ROTATION_DEG,
            "aspect_ratio": effective,
            "confidence": "user_confirmed",
        }
        self.accept()

    def _read_image_size(self, image_path: str) -> Optional[Tuple[int, int]]:
        """Return ``(width, height)`` in pixels for ``image_path``, or ``None``.

        Resolves relative paths via ``_resolve_image_path`` when available.

        Args:
            image_path: Raw path (may be relative) to the image file.

        Returns:
            ``(w, h)`` tuple, or ``None`` if the image cannot be read.

        """
        if self._resolve_image_path is not None:
            try:
                image_path = self._resolve_image_path(image_path)
            except Exception:
                logger.exception("Failed to resolve image path")
                return None
        try:
            reader = QImageReader(image_path)
            size = reader.size()
            if size.isValid() and size.width() > 0 and size.height() > 0:
                return (size.width(), size.height())
        except Exception:
            logger.exception("Failed to read image dimensions for %s", image_path)
        return None

    def _read_image_aspect(self, image_path: str) -> float:
        """Return ``width / height`` for ``image_path``, or ``1.0`` on failure.

        Args:
            image_path: Raw path (may be relative) to the image file.

        Returns:
            Positive float pixel aspect ratio.

        """
        size = self._read_image_size(image_path)
        return float(size[0]) / float(size[1]) if size else 1.0

    def _read_parent_pixel_size(self, parent_id: str) -> Optional[Tuple[int, int]]:
        """Return ``(width, height)`` in pixels for the selected parent map.

        Args:
            parent_id: ID of the candidate parent map.

        Returns:
            ``(w, h)`` tuple, or ``None`` if the image cannot be read.

        """
        parent_map = next((m for m in self._candidates if m.id == parent_id), None)
        if parent_map is None:
            return None
        return self._read_image_size(parent_map.image_path or "")

    def selected_parent_id(self) -> Optional[str]:
        """Return the chosen parent map ID after accept (else ``None``)."""
        return self._selected_parent_id

    def registration(self) -> Optional[Dict[str, Any]]:
        """Return the constructed registration payload after accept."""
        return self._registration

    @staticmethod
    def filter_candidate_parents(
        all_maps: List[Map], detail_map_id: str
    ) -> List[Map]:
        """Return maps eligible to act as a parent.

        Args:
            all_maps: Every map in the current world.
            detail_map_id: ID of the map being registered (excluded
                from the result).

        Returns:
            Maps whose ``map_role`` is master or detail, minus the
            detail map itself.

        """
        out: List[Map] = []
        for m in all_maps:
            if m.id == detail_map_id:
                continue
            role = (m.attributes or {}).get("map_role")
            if role in (MAP_ROLE_MASTER, MAP_ROLE_DETAIL):
                out.append(m)
        return out
