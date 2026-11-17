"""CPU-only projection calculation with no database or GUI dependencies."""

import json
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.services.map_projection import MapProjector, ProjectionSnapshot


class MapProjectionCalculation(QObject):
    """Cache source topology and chronology on a dedicated computation thread."""

    completed = Signal(dict)

    def __init__(self) -> None:
        """Start empty; no live model references arrive from other threads."""
        super().__init__()
        self._identity: tuple[str, int] | None = None
        self._projector: MapProjector | None = None

    @Slot(dict)
    def run(self, payload: dict[str, Any]) -> None:
        """Resolve a serializable capture into a serializable display frame."""
        request = payload["request"]
        result = {
            "token": request["token"],
            "points": [],
            "geometries": [],
            "issues": [],
        }
        try:
            identity = request["world"], request["revision"]
            if identity != self._identity:
                self._projector = MapProjector(
                    ProjectionSnapshot.from_dict(json.loads(payload["snapshot"]))
                )
                self._identity = identity
            assert self._projector is not None
            result.update(
                self._projector.frame(
                    request["target"],
                    request["date"],
                    zoom=request["zoom"],
                    include_detail=request["include_detail"],
                    fit_ratio=request.get("fit_ratio"),
                    pixel_size=request.get("pixel_size"),
                )
            )
        except Exception as exc:
            result["issues"] = [f"Connected features unavailable: {exc}"]
            self._identity = None
            self._projector = None
        self.completed.emit(result)
