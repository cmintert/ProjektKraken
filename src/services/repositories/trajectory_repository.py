"""
Trajectory Repository Module.

Handles database operations for the `moving_features` table,
managing temporal trajectories for map markers.
"""

import json
import logging
import uuid
from typing import List, Optional, Tuple

from src.core.trajectory import KEYFRAME_TIME_EPSILON, Keyframe
from src.services.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TrajectoryRepository(BaseRepository):
    """
    Repository for managing temporal trajectory data in `moving_features`.
    """

    def insert(
        self,
        marker_id: str,
        trajectory: List[Keyframe],
        properties: Optional[dict] = None,
    ) -> str:
        """
        Inserts a new trajectory or updates if one exists for the marker.
        (Note: Current schema allows multiple trajectories per marker,
         but for now we might treat it as one active trajectory or multiple segments).

        For this implementation, we insert a new row.

        Args:
            marker_id: The ID of the marker (DB ID) this trajectory belongs to.
            trajectory: List of Keyframe objects.
            properties: Optional JSON properties (e.g., color, style changes).

        Returns:
            The ID of the inserted trajectory record.
        """
        if not trajectory:
            raise ValueError("Cannot insert empty trajectory")

        # Sort trajectory by time to ensure t_start/t_end are correct
        trajectory.sort(key=lambda kf: kf.t)
        t_start = trajectory[0].t
        t_end = trajectory[-1].t

        # Serialize trajectory to list of [t, x, y] lists for JSON storage
        traj_data = [[kf.t, kf.x, kf.y] for kf in trajectory]
        traj_json = json.dumps(traj_data)
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

    def get_by_marker_db_id(
        self, marker_db_id: str
    ) -> List[Tuple[str, List[Keyframe]]]:
        """
        Retrieves all trajectories associated with a marker (by DB ID).

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
                traj_list = json.loads(traj_json)
                # Convert back to Keyframe objects
                keyframes = [
                    Keyframe(t=item[0], x=item[1], y=item[2]) for item in traj_list
                ]
                results.append((traj_id, keyframes))
            except (json.JSONDecodeError, IndexError, TypeError) as e:
                logger.error(f"Failed to parse trajectory {traj_id}: {e}")

        return results

    def get_by_map_id(self, map_id: str) -> List[Tuple[str, str, List[Keyframe]]]:
        """
        Retrieves all trajectories for all markers on a specific map.

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
                traj_list = json.loads(traj_json)
                keyframes = [
                    Keyframe(t=item[0], x=item[1], y=item[2]) for item in traj_list
                ]
                results.append((marker_id, traj_id, keyframes))
            except (json.JSONDecodeError, IndexError, TypeError) as e:
                logger.error(f"Failed to parse trajectory {traj_id}: {e}")

        return results

    def add_keyframe(self, map_id: str, object_id: str, keyframe: Keyframe) -> str:
        """
        Adds or updates a keyframe for the given marker (identified by map+object).
        Resolves the internal markers.id first.

        Args:
            map_id: ID of the map.
            object_id: The object ID (Entity/Event ID).
            keyframe: The Keyframe to add.

        Returns:
            The ID of the trajectory updated or created.
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # 1. Resolve markers.id
        row = self._connection.execute(
            "SELECT id FROM markers WHERE map_id = ? AND object_id = ?",
            (map_id, object_id),
        ).fetchone()

        if not row:
            logger.error(f"No marker found for map_id={map_id}, object_id={object_id}")
            raise ValueError(f"Marker not found: map={map_id}, obj={object_id}")

        marker_db_id = row["id"]

        # 2. Get existing trajectories
        trajectories = self.get_by_marker_db_id(marker_db_id)

        if trajectories:
            # Update existing (pick the last one based on t_start if multiple, or just first)
            traj_id, keyframes = trajectories[0]

            # Remove any existing keyframe at exactly this time (or within small epsilon)
            keyframes = [
                k for k in keyframes if abs(k.t - keyframe.t) > KEYFRAME_TIME_EPSILON
            ]

            keyframes.append(keyframe)
            keyframes.sort(key=lambda k: k.t)

            # Persist update
            self._update_trajectory_record(traj_id, keyframes)
            return traj_id
        else:
            return self.insert(marker_db_id, [keyframe])

    def update_keyframe_time(
        self, map_id: str, object_id: str, old_t: float, new_t: float
    ) -> str:
        """
        Updates the timestamp of a specific keyframe (Clock Mode editing).
        Finds keyframe at old_t, changes its t to new_t, re-sorts trajectory.

        Args:
            map_id: ID of the map.
            object_id: The object ID (Entity/Event ID).
            old_t: Original timestamp to find the keyframe.
            new_t: New timestamp to assign.

        Returns:
            The ID of the trajectory updated.

        Raises:
            ValueError: If marker or keyframe not found.
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # 1. Resolve markers.id
        row = self._connection.execute(
            "SELECT id FROM markers WHERE map_id = ? AND object_id = ?",
            (map_id, object_id),
        ).fetchone()

        if not row:
            logger.error(f"No marker found for map_id={map_id}, object_id={object_id}")
            raise ValueError(f"Marker not found: map={map_id}, obj={object_id}")

        marker_db_id = row["id"]

        # 2. Get existing trajectories
        trajectories = self.get_by_marker_db_id(marker_db_id)

        if not trajectories:
            raise ValueError(f"No trajectory found for marker {object_id}")

        traj_id, keyframes = trajectories[0]

        # 3. Find keyframe at old_t (within epsilon)
        target_kf = None
        for kf in keyframes:
            if abs(kf.t - old_t) < KEYFRAME_TIME_EPSILON:
                target_kf = kf
                break

        if not target_kf:
            raise ValueError(f"Keyframe at t={old_t} not found")

        # 4. Update timestamp
        target_kf.t = new_t

        # 5. Re-sort keyframes (natural reordering)
        keyframes.sort(key=lambda k: k.t)

        # 6. Persist update
        self._update_trajectory_record(traj_id, keyframes)
        logger.info(f"Updated keyframe time: {old_t:.2f} → {new_t:.2f} for {object_id}")
        return traj_id

    def delete_keyframe(self, map_id: str, object_id: str, t: float) -> Optional[str]:
        """
        Deletes a keyframe at a specific time from a trajectory.

        Args:
            map_id: ID of the map.
            object_id: The object ID (Entity/Event ID).
            t: The timestamp of the keyframe to delete.

        Returns:
            The ID of the trajectory updated, or None if trajectory is now empty.

        Raises:
            ValueError: If marker or keyframe not found.
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        # 1. Resolve markers.id
        row = self._connection.execute(
            "SELECT id FROM markers WHERE map_id = ? AND object_id = ?",
            (map_id, object_id),
        ).fetchone()

        if not row:
            logger.error(f"No marker found for map_id={map_id}, object_id={object_id}")
            raise ValueError(f"Marker not found: map={map_id}, obj={object_id}")

        marker_db_id = row["id"]

        # 2. Get existing trajectories
        trajectories = self.get_by_marker_db_id(marker_db_id)

        if not trajectories:
            raise ValueError(f"No trajectory found for marker {object_id}")

        traj_id, keyframes = trajectories[0]

        # 3. Find and remove keyframe at t (within epsilon)
        original_count = len(keyframes)
        keyframes = [kf for kf in keyframes if abs(kf.t - t) > KEYFRAME_TIME_EPSILON]

        if len(keyframes) == original_count:
            raise ValueError(f"Keyframe at t={t} not found")

        logger.info(f"Deleted keyframe at t={t:.2f} for {object_id}")

        # 4. If trajectory now has less than 2 keyframes, delete the entire trajectory
        if len(keyframes) < 2:
            logger.info(
                f"Trajectory {traj_id} has <2 keyframes, deleting entire trajectory"
            )
            with self.transaction() as conn:
                conn.execute("DELETE FROM moving_features WHERE id = ?", (traj_id,))
            return None

        # 5. Persist update
        self._update_trajectory_record(traj_id, keyframes)
        return traj_id

    def _update_trajectory_record(
        self, traj_id: str, keyframes: List[Keyframe]
    ) -> None:
        """Updates the trajectory JSON in the database."""
        if not keyframes:
            return

        t_start = keyframes[0].t
        t_end = keyframes[-1].t
        traj_data = [[kf.t, kf.x, kf.y] for kf in keyframes]
        traj_json = json.dumps(traj_data)

        sql = """
            UPDATE moving_features
            SET t_start = ?, t_end = ?, trajectory = ?
            WHERE id = ?
        """
        with self.transaction() as conn:
            conn.execute(sql, (t_start, t_end, traj_json, traj_id))
