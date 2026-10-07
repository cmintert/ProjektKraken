"""Explicit, non-mutating relation-drop affordance shared by both inspectors."""

import json
from typing import Any

from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.gui.utils.style_helper import StyleHelper


class RelationDropTarget(QFrame):
    """Validate a stable inspector target before staging a connection draft."""

    def __init__(self, authoring: Any) -> None:
        """Install a labeled, theme-owned target inside Connections."""
        super().__init__(authoring)
        self.authoring = authoring
        self._target_id = ""
        self.setObjectName("TemporalSnapshotBanner")
        self.label = QLabel("Drop an entry here to prepare a connection", self)
        self.label.setObjectName("TemporalSnapshotLabel")
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setAcceptDrops(True)
        self.setToolTip(
            "Drop previews a connection. Connect saves it; Cancel discards it."
        )
        self.apply_theme()

    def setText(self, text: str) -> None:
        """Update the named mode-information label inside the shared frame."""
        self.label.setText(text)

    def apply_theme(self) -> None:
        """Use shared neutral mode information rather than identity emphasis."""
        self.setStyleSheet(StyleHelper.get_temporal_snapshot_banner_style())

    def _payload(self, event: Any) -> dict[str, str] | None:
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        try:
            payload = json.loads(bytes(event.mimeData().data(KRAKEN_ITEM_MIME_TYPE)))
        except (ValueError, TypeError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        item_id, kind = payload.get("id"), payload.get("type")
        if (
            not isinstance(item_id, str)
            or not isinstance(kind, str)
            or kind not in {"entity", "event"}
        ):
            return None
        return self.authoring.resolve_drop(item_id, kind)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Capture the inspected identity only for an eligible drag."""
        self._target_id = ""
        payload = self._payload(event)
        if payload is None:
            event.ignore()
            return
        self._target_id = self.authoring._current_id()
        self.setText(
            f"Prepare connection: {payload['name']} → "
            f"{self.authoring.editor.name_edit.text()}"
        )
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Reject a changed target or an unavailable inspector."""
        if (
            self._target_id != self.authoring._current_id()
            or self._payload(event) is None
        ):
            event.ignore()
        else:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Clear only transient drag feedback."""
        self._reset()
        event.accept()

    def _reset(self) -> None:
        self._target_id = ""
        self.setText("Drop an entry here to prepare a connection")

    def dropEvent(self, event: QDropEvent) -> None:
        """Stage, never persist, a drop that still targets the same inspector."""
        target_id = self._target_id
        payload = self._payload(event)
        self._reset()
        if (
            not target_id
            or target_id != self.authoring._current_id()
            or payload is None
        ):
            event.ignore()
            return
        if self.authoring.stage_drop(payload):
            event.acceptProposedAction()
        else:
            event.ignore()
