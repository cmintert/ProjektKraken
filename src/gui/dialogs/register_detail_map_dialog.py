"""Register Detail Map Dialog.

Phase-1 entry point for marking a map as a detail child of another map.
The user picks a parent (the world's master, or another already-registered
detail map) and confirms.  The dialog produces a default centred,
aspect-locked-affine registration payload — Phase 3 replaces the
default with canvas-driven placement.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

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

from src.app.constants import MAP_ROLE_DETAIL, MAP_ROLE_MASTER
from src.core.map import Map

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
        aspect = self._compute_aspect_ratio()
        self._registration = {
            "mode": "aspect_locked_affine",
            "version": 1,
            "master_center_norm": {
                "x": _DEFAULT_CENTER[0],
                "y": _DEFAULT_CENTER[1],
            },
            "scale_norm": _DEFAULT_SCALE,
            "rotation_deg": _DEFAULT_ROTATION_DEG,
            "aspect_ratio": aspect,
            "confidence": "user_confirmed",
        }
        self.accept()

    def _compute_aspect_ratio(self) -> float:
        """Read the detail map image and return ``width / height``.

        Falls back to ``1.0`` when the image cannot be read — the
        registration validator only requires the value to be positive
        and finite.

        """
        image_path = self._detail_map.image_path or ""
        if self._resolve_image_path is not None:
            try:
                image_path = self._resolve_image_path(image_path)
            except Exception:
                logger.exception("Failed to resolve detail-map image path")
        try:
            reader = QImageReader(image_path)
            size = reader.size()
            if size.isValid() and size.height() > 0:
                return float(size.width()) / float(size.height())
        except Exception:
            logger.exception("Failed to read detail-map image dimensions")
        return 1.0

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
