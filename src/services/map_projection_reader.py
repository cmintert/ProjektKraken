"""Feature-owned, read-only projection adapter on the existing database thread."""

import json
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.calendar import CalendarConverter
from src.core.temporal_context import TemporalResolutionContext
from src.core.trajectory import apply_trajectory_metadata, mfjson_to_keyframes
from src.services.db_service import DatabaseService
from src.services.map_projection import MapProjector, ProjectionSnapshot

DatabaseProvider = Callable[[], DatabaseService | None]


def read_projection(db: DatabaseService) -> MapProjector:
    """Read authored inputs without repairing, pruning or writing any saved row."""
    maps = db.get_all_maps()
    markers = [m for record in maps for m in db.get_markers_for_map(record.id)]
    config = db.get_active_calendar_config()
    snapshot = ProjectionSnapshot(
        maps,
        markers,
        context=TemporalResolutionContext.build(
            db.get_all_events(), CalendarConverter(config) if config else None
        ),
    )
    snapshot.labels = {
        (kind, item.id): item.name
        for kind, items in (
            ("entity", db.get_all_entities()),
            ("event", db.get_all_events()),
        )
        for item in items
    }
    rows = (
        db.require_connection()
        .execute(
            "SELECT marker_id, trajectory, properties FROM moving_features ORDER BY id"
        )
        .fetchall()
    )
    for row in rows:
        try:
            points = mfjson_to_keyframes(json.loads(row["trajectory"]))
            points, modes, _ = apply_trajectory_metadata(
                points, json.loads(row["properties"] or "{}")
            )
            snapshot.tracks.setdefault(row["marker_id"], []).append((points, modes))
        except (ValueError, TypeError, KeyError):
            # Ambiguous/invalid tracks must not silently fall back to static data.
            snapshot.tracks[row["marker_id"]] = [([], {}), ([], {})]
    return MapProjector(snapshot)


class MapProjectionReader(QObject):
    """Serve coalesced serializable frame requests with worker-owned cached inputs."""

    completed = Signal(dict)

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Retain a provider called exclusively after queued worker delivery."""
        super().__init__()
        self.database = database
        self._projector: MapProjector | None = None
        self._identity: tuple[int, str, int] | None = None

    @Slot(dict)
    def run(self, request: dict[str, Any]) -> None:
        """Build one dated frame; never emit database objects across threads."""
        result = {"token": request["token"], "points": [], "issues": []}
        try:
            db = self.database()
            if db is None or str(db.db_path) != request["world"]:
                raise ValueError(
                    "The active world changed; refresh connected features."
                )
            identity = id(db), str(db.db_path), request["revision"]
            if identity != self._identity:
                self._projector = read_projection(db)
                self._identity = identity
            assert self._projector is not None
            result.update(
                self._projector.frame(
                    request["target"],
                    request["date"],
                    zoom=request["zoom"],
                    fit_ratio=request.get("fit_ratio"),
                    include_detail=request["include_detail"],
                )
            )
        except Exception as exc:
            result["issues"] = [f"Connected features unavailable: {exc}"]
            self._projector = None
            self._identity = None
        self.completed.emit(result)
