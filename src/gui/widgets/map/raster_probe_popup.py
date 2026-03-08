"""Raster Probe Popup — floating label showing sampled raster values.

Displayed as a small overlay inside the MapGraphicsView whenever the
sample / probe tool fires a ``raster_value_probed`` signal.  Auto-hides
after a short timeout.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

logger = logging.getLogger(__name__)

_AUTO_HIDE_MS = 3000  # milliseconds before auto-hide


class RasterProbePopup(QLabel):
    """Floating read-out label for raster probe results.

    Placed as a child of the view widget, positioned in the top-left
    corner of the viewport with a small margin.  Shows the raw value,
    optional label, and optional entity name.

    Args:
        parent: Parent widget (typically the ``MapGraphicsView``).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("RasterProbePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWordWrap(False)
        self.setStyleSheet(
            "QLabel#RasterProbePopup {"
            "  background: rgba(20, 20, 20, 210);"
            "  color: #E8E8E8;"
            "  border: 1px solid rgba(255,255,255,60);"
            "  border-radius: 6px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "}"
        )
        self.hide()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_result)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_result(
        self,
        node_id: str,
        value: int,
        entity_name: Optional[str],
        label: Optional[str],
        mode: str = "",
    ) -> None:
        """Display a probe result and start the auto-hide timer.

        Args:
            node_id: Raster layer node ID (for debug/display context).
            value: Raw 16-bit cell value.
            entity_name: Entity name resolved from mapping, or ``None``.
            label: Human-readable palette label, or ``None``.
            mode: Layer mode — ``"discrete"`` or ``"continuous"`` (shown as hint).
        """
        lines = []
        if mode:
            icon = "📊" if mode == "discrete" else "📈"
            mode_label = "Discrete" if mode == "discrete" else "Continuous"
            lines.append(f"{icon} {mode_label}")
        lines.append(f"Value: {value}")
        if label:
            lines.append(f"Label: {label}")
        if entity_name:
            lines.append(f"Entity: {entity_name}")
        self.setText("  |  ".join(lines))
        self.adjustSize()
        self._position_in_parent()
        self.show()
        self.raise_()
        self._timer.start(_AUTO_HIDE_MS)
        logger.debug(
            "RasterProbePopup: node_id=%s value=%d entity=%s label=%s",
            node_id,
            value,
            entity_name,
            label,
        )

    def hide_result(self) -> None:
        """Hide the popup immediately."""
        self._timer.stop()
        self.hide()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _position_in_parent(self) -> None:
        """Place the popup in the top-left corner of the parent widget."""
        parent = self.parentWidget()
        if parent is not None:
            self.move(12, 12)
