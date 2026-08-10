"""Persistence for dated path and region geometry states."""

from __future__ import annotations

import copy
import json
import math
from typing import Any, Sequence

from src.core.feature_geometry_state import (
    FeatureGeometryState,
    calculate_feature_anchor,
    validate_feature_geometry,
)
from src.services.repositories.base_repository import BaseRepository


class FeatureGeometryConflictError(RuntimeError):
    """Raised when persisted geometry states changed after editing began."""


class FeatureGeometryRepository(BaseRepository):
    """Read and atomically replace dated geometry states."""

    def get_states(self, marker_id: str) -> list[FeatureGeometryState]:
        """Return one marker's states in effective-date order."""
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT id, marker_id, effective_date, geometry, anchor_x, anchor_y,
                   created_at, modified_at
            FROM feature_geometry_states
            WHERE marker_id = ?
            ORDER BY effective_date, id
            """,
            (marker_id,),
        ).fetchall()
        return [self._state_from_row(row) for row in rows]

    def get_states_for_map(self, map_id: str) -> list[dict[str, Any]]:
        """Return JSON-safe state snapshots for every marker on one map."""
        connection = self._require_connection()
        rows = connection.execute(
            """
            SELECT s.id, s.marker_id, s.effective_date, s.geometry,
                   s.anchor_x, s.anchor_y, s.created_at, s.modified_at
            FROM feature_geometry_states AS s
            JOIN markers AS m ON m.id = s.marker_id
            WHERE m.map_id = ?
            ORDER BY s.marker_id, s.effective_date, s.id
            """,
            (map_id,),
        ).fetchall()
        return [self._state_from_row(row).to_dict() for row in rows]

    def snapshot_by_marker(self, marker_id: str) -> list[dict[str, Any]]:
        """Return an exact JSON-safe snapshot for reversible operations."""
        return [state.to_dict() for state in self.get_states(marker_id)]

    def replace_marker_states(
        self,
        marker_id: str,
        replacement: Sequence[FeatureGeometryState | dict[str, Any]],
        *,
        expected_snapshot: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically replace all states belonging to one marker."""
        connection = self._require_connection()
        marker_row = connection.execute(
            "SELECT feature_type FROM markers WHERE id = ?", (marker_id,)
        ).fetchone()
        if marker_row is None:
            raise ValueError(f"Marker not found: {marker_id}")
        feature_type = str(marker_row["feature_type"])
        prepared: list[FeatureGeometryState] = []
        dates: set[float] = set()
        ids: set[str] = set()
        for raw in replacement:
            state = (
                raw
                if isinstance(raw, FeatureGeometryState)
                else FeatureGeometryState.from_dict(raw)
            )
            if state.marker_id != marker_id:
                raise ValueError("Every state must belong to the replaced marker.")
            if not math.isfinite(state.effective_date):
                raise ValueError("Geometry-state dates must be finite.")
            if state.effective_date in dates:
                raise ValueError("A feature cannot have two states on the same date.")
            if state.id in ids:
                raise ValueError("Geometry-state IDs must be unique.")
            validate_feature_geometry(feature_type, state.geometry)
            anchor_x, anchor_y = calculate_feature_anchor(state.geometry)
            prepared.append(
                FeatureGeometryState(
                    id=state.id,
                    marker_id=marker_id,
                    effective_date=state.effective_date,
                    geometry=copy.deepcopy(state.geometry),
                    anchor_x=anchor_x,
                    anchor_y=anchor_y,
                    created_at=state.created_at,
                    modified_at=state.modified_at,
                )
            )
            dates.add(state.effective_date)
            ids.add(state.id)

        with self.transaction() as conn:
            current = self.snapshot_by_marker(marker_id)
            if expected_snapshot is not None and current != expected_snapshot:
                raise FeatureGeometryConflictError(
                    "Geometry states changed after this edit began."
                )
            conn.execute(
                "DELETE FROM feature_geometry_states WHERE marker_id = ?",
                (marker_id,),
            )
            conn.executemany(
                """
                INSERT INTO feature_geometry_states
                    (id, marker_id, effective_date, geometry, anchor_x, anchor_y,
                     created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        state.id,
                        state.marker_id,
                        state.effective_date,
                        json.dumps(state.geometry),
                        state.anchor_x,
                        state.anchor_y,
                        state.created_at,
                        state.modified_at,
                    )
                    for state in prepared
                ],
            )
        return self.snapshot_by_marker(marker_id)

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore one exact state row after a cascading deletion."""
        state = FeatureGeometryState.from_dict(snapshot)
        connection = self._require_connection()
        connection.execute(
            """
            INSERT INTO feature_geometry_states
                (id, marker_id, effective_date, geometry, anchor_x, anchor_y,
                 created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.id,
                state.marker_id,
                state.effective_date,
                json.dumps(state.geometry),
                state.anchor_x,
                state.anchor_y,
                state.created_at,
                state.modified_at,
            ),
        )

    @staticmethod
    def _state_from_row(row: Any) -> FeatureGeometryState:
        data = dict(row)
        data["geometry"] = json.loads(data["geometry"])
        return FeatureGeometryState.from_dict(data)
