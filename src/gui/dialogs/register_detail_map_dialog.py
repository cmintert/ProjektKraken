"""Collect parent intent for exact placement or a suggested manual preview."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.map import Map
from src.gui.utils.help_context import declare_inspection
from src.gui.widgets.responsive_dialog_buttons import (
    ResponsiveDialogButtonBox as QDialogButtonBox,
)
from src.gui.widgets.wrapping_choices import WrappingCheckBox
from src.services.map_hierarchy_options import candidate_parents

logger = logging.getLogger(__name__)


# Suggested placement, reviewed on the canvas before persistence.
_DEFAULT_CENTER = (0.5, 0.5)
_DEFAULT_SCALE = 0.25
_DEFAULT_ROTATION_DEG = 0.0


class RegisterDetailMapDialog(QDialog):
    """Modal dialog that collects (parent_id, registration) for a detail map.

    Args:
        detail_map: The map that will be registered as a detail child.
        candidate_parents: Maps eligible to act as the parent.  Already
            filtered by the caller using canonical subtree validation.
        resolve_image_path: Callable that turns a stored ``image_path``
            (which may be relative to the world directory) into an
            absolute path on disk.  Used to read the detail map's
            intrinsic aspect ratio without forcing the dialog to know
            where the world root lives.
        parent: Parent widget.
        preservation_options: Target IDs mapped to an unavailable reason or None
            when the application service can preserve geographic placement.

    """

    def __init__(
        self,
        detail_map: Map,
        candidate_parents: List[Map],
        resolve_image_path: Optional[Callable[[str], str]] = None,
        parent: Optional[QWidget] = None,
        *,
        preservation_options: dict[str, str | None] | None = None,
    ) -> None:
        """Initialize detail-map registration controls."""
        super().__init__(parent)
        self._detail_map = detail_map
        self._candidates = candidate_parents
        self._resolve_image_path = resolve_image_path
        self._selected_parent_id: Optional[str] = None
        self._registration: Optional[Dict[str, Any]] = None
        self._preservation_options = preservation_options or {}

        self.setWindowTitle("Choose Parent Map")
        self.resize(440, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        intro = QLabel(
            f"Choose a parent for {detail_map.name}. Keep placement from saved "
            "alignments, or place the image manually."
        )
        intro.setTextFormat(Qt.TextFormat.PlainText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel("Parent map:"))
        self._parent_combo = declare_inspection(
            QComboBox(self),
            "src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-self-parent-combo|map.features|help-inspect-src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-self-parent-combo",
        )
        for m in candidate_parents:
            role = (
                "Detail map"
                if (m.attributes or {}).get("parent_map_id")
                else "Independent"
            )
            label = f"{m.name}  ({role})"
            self._parent_combo.addItem(label, m.id)
        layout.addWidget(self._parent_combo)

        self._keep_position = declare_inspection(
            WrappingCheckBox("Keep geographic placement", self),
            "map.parent.keep-placement|map.features|help-map-parent-keep-placement",
        )
        layout.addWidget(self._keep_position)
        self._placement_explanation = QLabel(self)
        self._placement_explanation.setTextFormat(Qt.TextFormat.PlainText)
        self._placement_explanation.setWordWrap(True)
        layout.addWidget(self._placement_explanation)

        if not candidate_parents:
            warn = QLabel(
                "No parent can accept this map and its descendants within five levels."
            )
            warn.setWordWrap(True)
            warn.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(warn)

        buttons = declare_inspection(
            QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel,
                parent=self,
            ),
            "src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-buttons|map.features|help-inspect-src-gui-dialogs-register-detail-map-dialog-registerdetailmapdialog-init-buttons",
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._apply_button = ok_btn
        if ok_btn is not None:
            ok_btn.setText("Place on parent map")
            ok_btn.setEnabled(bool(candidate_parents))
        layout.addWidget(buttons)
        self._parent_combo.currentIndexChanged.connect(self._update_preservation)
        self._keep_position.toggled.connect(self._update_action)
        self._update_preservation()

    def _update_preservation(self) -> None:
        parent_id = self._parent_combo.currentData()
        explanation = self._preservation_options.get(
            parent_id, "No shared saved alignment is available. Place the map manually."
        )
        self._keep_position.setEnabled(explanation is None)
        self._keep_position.setChecked(explanation is None)
        self._placement_explanation.setText(explanation or "")
        self._update_action()

    def _update_action(self) -> None:
        if self._apply_button is None:
            return
        keep = self.preserves_position()
        same_parent = self._parent_combo.currentData() == (
            self._detail_map.attributes or {}
        ).get("parent_map_id")
        self._apply_button.setText("Change parent" if keep else "Place on parent map")
        self._apply_button.setEnabled(
            bool(self._parent_combo.currentData()) and not (keep and same_parent)
        )
        if self._keep_position.isEnabled():
            self._placement_explanation.setText(
                "This is already the parent. Clear Keep geographic placement to "
                "edit its placement manually."
                if keep and same_parent
                else "Change parent saves one reversible change using the saved "
                "alignments."
                if keep
                else "Next, adjust the image on the parent map. Nothing is saved "
                "until you apply the placement."
            )

    def preserves_position(self) -> bool:
        """Return the explicit, available position-preservation intent."""
        return self._keep_position.isEnabled() and self._keep_position.isChecked()

    def _accept(self) -> None:
        """Accept preserved intent or build a suggested manual registration."""
        parent_id = self._parent_combo.currentData()
        if not parent_id:
            self.reject()
            return
        self._selected_parent_id = parent_id
        if self.preserves_position():
            self.accept()
            return

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
            "confidence": "suggested",
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
    def filter_candidate_parents(all_maps: List[Map], detail_map_id: str) -> List[Map]:
        """Return maps eligible to act as a parent.

        Args:
            all_maps: Every map in the current world.
            detail_map_id: ID of the map being registered (excluded
                from the result).

        Returns:
            Structurally valid parent maps, including independent roots.

        """
        return candidate_parents(all_maps, detail_map_id)
