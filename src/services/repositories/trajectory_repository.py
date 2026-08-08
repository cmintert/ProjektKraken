"""Trajectory Repository Module.

Handles database operations for the `moving_features` table,
managing temporal trajectories for map markers.
"""

import json
import logging
import sqlite3
import time
import uuid
from typing import Final, List, Optional, Tuple, TypedDict, cast

from src.core.trajectory import (
    Keyframe,
    clone_keyframes,
    keyframes_to_mfjson,
    mfjson_to_keyframes,
    validate_keyframes,
)
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AmbiguousTrajectoryError(ValueError):
    """Raised when a marker has more than one trajectory row."""


class TrajectoryConflictError(ValueError):
    """Raised when persisted trajectory state differs from an expected snapshot."""


class TrajectorySnapshot(TypedDict):
    """JSON-safe, exact snapshot of one ``moving_features`` row."""

    id: str
    marker_id: str
    t_start: float
    t_end: float
    trajectory: str
    properties: str | None
    created_at: float | None


class _ExpectedSnapshotUnset:
    """Sentinel type for callers that do not request conflict detection."""


_EXPECTED_SNAPSHOT_UNSET: Final = _ExpectedSnapshotUnset()
_SNAPSHOT_COLUMNS: Final = (
    "id, marker_id, t_start, t_end, trajectory, properties, created_at"
)
_QUALIFIED_SNAPSHOT_COLUMNS: Final = (
    "mf.id AS id, mf.marker_id AS marker_id, mf.t_start AS t_start, "
    "mf.t_end AS t_end, mf.trajectory AS trajectory, "
    "mf.properties AS properties, mf.created_at AS created_at"
)


class TrajectoryRepository(BaseRepository):
    """Repository for managing temporal trajectory data in `moving_features`."""

    def insert(
        self,
        marker_id: str,
        trajectory: List[Keyframe],
        properties: Optional[dict] = None,
    ) -> str:
        """Inserts a new trajectory or updates if one exists for the marker. (Note:
        Current schema allows multiple trajectories per marker, but for now we might
        treat it as one active trajectory or multiple segments).

        For this implementation, we insert a new row.

        Args:
            marker_id: The ID of the marker (DB ID) this trajectory belongs to.
            trajectory: List of Keyframe objects.
            properties: Optional JSON properties (e.g., color, style changes).

        Returns:
            The ID of the inserted trajectory record.

        """
        keyframes = clone_keyframes(trajectory)
        if not keyframes:
            raise ValueError("Cannot insert empty trajectory")

        self._validate_complete_trajectory(keyframes)
        keyframes.sort(key=lambda kf: kf.t)
        t_start = keyframes[0].t
        t_end = keyframes[-1].t

        # Serialize trajectory to MF-JSON format
        traj_json = json.dumps(keyframes_to_mfjson(keyframes))
        props_json = self._serialize_json(properties or {})

        feature_id = str(uuid.uuid4())

        sql = """
            INSERT INTO moving_features (id, marker_id, t_start, t_end, trajectory, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, strftime('%J', 'now'))
        """

        with self.transaction() as conn:
            conn.execute(
                sql, (feature_id, marker_id, t_start, t_end, traj_json, props_json)
            )

        logger.info(f"Inserted trajectory {feature_id} for marker {marker_id}")
        return feature_id

    def get_marker_trajectory_snapshot(
        self, map_id: str, object_id: str
    ) -> TrajectorySnapshot | None:
        """Return the marker's one exact trajectory row, if present.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.

        Returns:
            An independent JSON-safe row snapshot, or ``None``.

        Raises:
            ValueError: If the marker does not exist.
            AmbiguousTrajectoryError: If more than one trajectory row exists.

        """
        connection = self._require_connection()
        marker_db_id = self._resolve_marker_db_id(connection, map_id, object_id)
        return self._get_single_snapshot(connection, marker_db_id, object_id)

    def set_marker_trajectory(
        self,
        map_id: str,
        object_id: str,
        keyframes: list[Keyframe],
        *,
        expected_snapshot: (
            TrajectorySnapshot | None | _ExpectedSnapshotUnset
        ) = _EXPECTED_SNAPSHOT_UNSET,
    ) -> TrajectorySnapshot | None:
        """Atomically replace a marker's complete trajectory.

        Existing row identity, properties, and creation time are preserved.
        One-keyframe trajectories remain stored; only an empty replacement
        deletes the row.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.
            keyframes: Complete desired trajectory state.
            expected_snapshot: Exact state the caller expects to replace. Pass
                ``None`` to require that no row exists. Omitting this argument
                disables conflict detection for compatibility callers.

        Returns:
            The exact persisted row snapshot, or ``None`` after deletion.

        Raises:
            ValueError: If the marker or replacement data is invalid.
            AmbiguousTrajectoryError: If more than one trajectory row exists.
            TrajectoryConflictError: If the current row is not the expected row.

        """
        replacement = clone_keyframes(keyframes)
        self._validate_complete_trajectory(replacement)
        replacement.sort(key=lambda keyframe: keyframe.t)

        trajectory_json = (
            json.dumps(keyframes_to_mfjson(replacement)) if replacement else None
        )

        with self.transaction() as connection:
            marker_db_id = self._resolve_marker_db_id(
                connection, map_id, object_id
            )
            current = self._get_single_snapshot(
                connection, marker_db_id, object_id
            )
            self._check_expected_snapshot(current, expected_snapshot)

            if not replacement:
                if current is not None:
                    connection.execute(
                        "DELETE FROM moving_features WHERE id = ?", (current["id"],)
                    )
                return None

            if current is None:
                trajectory_id = str(uuid.uuid4())
                properties = "{}"
                created_at = time.time()
                connection.execute(
                    f"""
                    INSERT INTO moving_features ({_SNAPSHOT_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trajectory_id,
                        marker_db_id,
                        replacement[0].t,
                        replacement[-1].t,
                        trajectory_json,
                        properties,
                        created_at,
                    ),
                )
            else:
                trajectory_id = current["id"]
                connection.execute(
                    """
                    UPDATE moving_features
                    SET t_start = ?, t_end = ?, trajectory = ?
                    WHERE id = ?
                    """,
                    (
                        replacement[0].t,
                        replacement[-1].t,
                        trajectory_json,
                        trajectory_id,
                    ),
                )

            row = connection.execute(
                f"SELECT {_SNAPSHOT_COLUMNS} FROM moving_features WHERE id = ?",
                (trajectory_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Trajectory replacement did not persist a row")
            return self._snapshot_from_row(row)

    def restore_marker_trajectory_snapshot(
        self,
        map_id: str,
        object_id: str,
        snapshot: TrajectorySnapshot | None,
        *,
        expected_snapshot: TrajectorySnapshot | None,
    ) -> TrajectorySnapshot | None:
        """Atomically restore an exact row snapshot for undo or redo.

        Args:
            map_id: ID of the containing map.
            object_id: Entity or event ID associated with the marker.
            snapshot: Exact row to restore, or ``None`` to delete the row.
            expected_snapshot: Exact state that must currently be persisted.

        Returns:
            An independent copy of the restored snapshot, or ``None``.

        Raises:
            ValueError: If the marker or snapshot is invalid.
            AmbiguousTrajectoryError: If more than one trajectory row exists.
            TrajectoryConflictError: If persisted state changed unexpectedly.

        """
        replacement = self._copy_snapshot(snapshot) if snapshot is not None else None
        expected = (
            self._copy_snapshot(expected_snapshot)
            if expected_snapshot is not None
            else None
        )

        with self.transaction() as connection:
            marker_db_id = self._resolve_marker_db_id(
                connection, map_id, object_id
            )
            current = self._get_single_snapshot(
                connection, marker_db_id, object_id
            )
            self._check_expected_snapshot(current, expected)

            if replacement is not None and replacement["marker_id"] != marker_db_id:
                raise ValueError("Trajectory snapshot belongs to a different marker")

            if current is not None:
                connection.execute(
                    "DELETE FROM moving_features WHERE id = ?", (current["id"],)
                )

            if replacement is not None:
                connection.execute(
                    f"""
                    INSERT INTO moving_features ({_SNAPSHOT_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        replacement["id"],
                        replacement["marker_id"],
                        replacement["t_start"],
                        replacement["t_end"],
                        replacement["trajectory"],
                        replacement["properties"],
                        replacement["created_at"],
                    ),
                )

            return self._copy_snapshot(replacement) if replacement is not None else None

    @staticmethod
    def _snapshot_keys() -> tuple[str, ...]:
        """Return snapshot keys in database column order."""
        return (
            "id",
            "marker_id",
            "t_start",
            "t_end",
            "trajectory",
            "properties",
            "created_at",
        )

    @classmethod
    def _snapshot_from_row(cls, row: sqlite3.Row) -> TrajectorySnapshot:
        """Create an independent typed snapshot from a SQLite row."""
        return cast(
            TrajectorySnapshot,
            {key: row[key] for key in cls._snapshot_keys()},
        )

    @classmethod
    def _copy_snapshot(cls, snapshot: TrajectorySnapshot) -> TrajectorySnapshot:
        """Validate and copy a snapshot received across a command boundary."""
        missing = [key for key in cls._snapshot_keys() if key not in snapshot]
        if missing:
            raise ValueError(
                f"Trajectory snapshot is missing fields: {', '.join(missing)}"
            )
        return TrajectorySnapshot(
            id=snapshot["id"],
            marker_id=snapshot["marker_id"],
            t_start=snapshot["t_start"],
            t_end=snapshot["t_end"],
            trajectory=snapshot["trajectory"],
            properties=snapshot["properties"],
            created_at=snapshot["created_at"],
        )

    @staticmethod
    def _resolve_marker_db_id(
        connection: sqlite3.Connection, map_id: str, object_id: str
    ) -> str:
        """Resolve one marker database ID from its map and object identity."""
        rows = connection.execute(
            "SELECT id FROM markers WHERE map_id = ? AND object_id = ?",
            (map_id, object_id),
        ).fetchall()
        if not rows:
            raise ValueError(f"Marker not found: map={map_id}, obj={object_id}")
        if len(rows) > 1:
            raise ValueError(
                f"Multiple markers found: map={map_id}, obj={object_id}"
            )
        return str(rows[0]["id"])

    def _get_single_snapshot(
        self,
        connection: sqlite3.Connection,
        marker_db_id: str,
        object_id: str,
    ) -> TrajectorySnapshot | None:
        """Return one exact row or report unsupported duplicate rows."""
        rows = connection.execute(
            f"""
            SELECT {_SNAPSHOT_COLUMNS}
            FROM moving_features
            WHERE marker_id = ?
            ORDER BY t_start, id
            """,
            (marker_db_id,),
        ).fetchall()
        if len(rows) > 1:
            raise AmbiguousTrajectoryError(
                f"Marker {object_id} has {len(rows)} trajectory rows"
            )
        return self._snapshot_from_row(rows[0]) if rows else None

    @staticmethod
    def _check_expected_snapshot(
        current: TrajectorySnapshot | None,
        expected: TrajectorySnapshot | None | _ExpectedSnapshotUnset,
    ) -> None:
        """Reject replacement when the persisted row changed after capture."""
        if isinstance(expected, _ExpectedSnapshotUnset):
            return
        if current != expected:
            raise TrajectoryConflictError(
                "Trajectory changed after the edit snapshot was captured"
            )

    @staticmethod
    def _validate_complete_trajectory(keyframes: list[Keyframe]) -> None:
        """Raise one stable repository error for invalid trajectory values."""
        errors = validate_keyframes(keyframes)
        if errors:
            raise ValueError("Invalid trajectory: " + " ".join(errors))

    @staticmethod
    def _require_single_trajectory(
        trajectories: List[Tuple[str, List[Keyframe]]], object_id: str
    ) -> Tuple[str, List[Keyframe]] | None:
        """Return one legacy trajectory tuple without silently picking a row."""
        if len(trajectories) > 1:
            raise AmbiguousTrajectoryError(
                f"Marker {object_id} has {len(trajectories)} trajectory rows"
            )
        return trajectories[0] if trajectories else None

    def get_by_marker_db_id(
        self, marker_db_id: str
    ) -> List[Tuple[str, List[Keyframe]]]:
        """Retrieves all trajectories associated with a marker (by DB ID).

        Args:
            marker_db_id: The UUID of the marker in markers table.

        Returns:
            List of tuples (trajectory_id, List[Keyframe]).

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        sql = """
            SELECT id, trajectory FROM moving_features
            WHERE marker_id = ?
            ORDER BY t_start
        """
        cursor = self._connection.execute(sql, (marker_db_id,))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            traj_id = row["id"]
            traj_json = row["trajectory"]
            try:
                traj_data = json.loads(traj_json)
                # Backward compatibility: detect old [[t,x,y],...] format
                keyframes = self._parse_trajectory_json(traj_data)
                results.append((traj_id, keyframes))
            except (json.JSONDecodeError, IndexError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse trajectory {traj_id}: {e}")

        return results

    def snapshot_by_marker(self, marker_db_id: str) -> List[dict]:
        """Return JSON-safe trajectory rows for reversible marker deletion."""
        if not self._connection:
            raise RuntimeError("Database connection not initialized")
        rows = self._connection.execute(
            """
            SELECT id, marker_id, t_start, t_end, trajectory, properties, created_at
            FROM moving_features
            WHERE marker_id = ?
            ORDER BY t_start
            """,
            (marker_db_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def restore_snapshot(self, snapshot: dict) -> None:
        """Restore an exact trajectory row captured by :meth:`snapshot_by_marker`."""
        sql = """
            INSERT INTO moving_features
                (id, marker_id, t_start, t_end, trajectory, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.transaction() as conn:
            conn.execute(
                sql,
                (
                    snapshot["id"],
                    snapshot["marker_id"],
                    snapshot["t_start"],
                    snapshot["t_end"],
                    snapshot["trajectory"],
                    snapshot["properties"],
                    snapshot["created_at"],
                ),
            )

    def get_by_map_id(self, map_id: str) -> List[Tuple[str, str, List[Keyframe]]]:
        """Retrieves all trajectories for all markers on a specific map.

        Args:
            map_id: The UUID of the map.

        Returns:
            List of tuples (object_id, trajectory_id, List[Keyframe]).
            Note: Returns object_id as 'marker_id' for UI compatibility.

        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        sql = """
            SELECT mf.id as traj_id, m.object_id as marker_id, mf.trajectory
            FROM moving_features mf
            JOIN markers m ON mf.marker_id = m.id
            WHERE m.map_id = ?
            ORDER BY mf.t_start
        """
        cursor = self._connection.execute(sql, (map_id,))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            marker_id = row["marker_id"]
            traj_id = row["traj_id"]
            traj_json = row["trajectory"]
            try:
                traj_data = json.loads(traj_json)
                # Backward compatibility: detect old [[t,x,y],...] format
                keyframes = self._parse_trajectory_json(traj_data)
                results.append((marker_id, traj_id, keyframes))
            except (json.JSONDecodeError, IndexError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse trajectory {traj_id}: {e}")

        return results

    def get_snapshots_by_map_id(self, map_id: str) -> list[dict[str, object]]:
        """Return map-scoped, JSON-safe trajectory snapshots for the GUI.

        Args:
            map_id: ID of the map whose trajectories should be loaded.

        Returns:
            Serializable dictionaries containing public marker identity,
            keyframe values, and the exact persistence row snapshot.

        """
        connection = self._require_connection()
        rows = connection.execute(
            f"""
            SELECT m.object_id, {_QUALIFIED_SNAPSHOT_COLUMNS}
            FROM moving_features AS mf
            JOIN markers AS m ON mf.marker_id = m.id
            WHERE m.map_id = ?
            ORDER BY mf.t_start, mf.id
            """,
            (map_id,),
        ).fetchall()

        snapshots: list[dict[str, object]] = []
        for row in rows:
            trajectory_id = str(row["id"])
            try:
                keyframes = self._parse_trajectory_json(
                    json.loads(row["trajectory"])
                )
            except (json.JSONDecodeError, IndexError, TypeError, ValueError) as exc:
                logger.error("Failed to parse trajectory %s: %s", trajectory_id, exc)
                continue
            snapshots.append(
                {
                    "marker_id": str(row["object_id"]),
                    "trajectory_id": trajectory_id,
                    "keyframes": [
                        {"t": keyframe.t, "x": keyframe.x, "y": keyframe.y}
                        for keyframe in keyframes
                    ],
                    "row_snapshot": self._snapshot_from_row(row),
                }
            )
        return snapshots

    def _update_trajectory_record(
        self, traj_id: str, keyframes: List[Keyframe]
    ) -> None:
        """Updates the trajectory JSON in the database."""
        if not keyframes:
            return

        replacement = clone_keyframes(keyframes)
        self._validate_complete_trajectory(replacement)
        replacement.sort(key=lambda keyframe: keyframe.t)
        t_start = replacement[0].t
        t_end = replacement[-1].t
        traj_json = json.dumps(keyframes_to_mfjson(replacement))

        sql = """
            UPDATE moving_features
            SET t_start = ?, t_end = ?, trajectory = ?
            WHERE id = ?
        """
        with self.transaction() as conn:
            conn.execute(sql, (t_start, t_end, traj_json, traj_id))

    def _parse_trajectory_json(self, data: dict | list) -> List[Keyframe]:
        """Parse trajectory data, supporting both old and new formats.

        Args:
            data: Either MF-JSON dict or old [[t,x,y],...] list.

        Returns:
            List of Keyframe objects.

        """
        # New MF-JSON format: {'type': 'MovingPoint', 'coordinates': [...], 'datetimes': [...]}
        if isinstance(data, dict) and data.get("type") == "MovingPoint":
            return mfjson_to_keyframes(data)

        # Old format: [[t, x, y], ...]
        if isinstance(data, list):
            return [Keyframe(t=item[0], x=item[1], y=item[2]) for item in data]

        raise ValueError(f"Unknown trajectory format: {type(data)}")
