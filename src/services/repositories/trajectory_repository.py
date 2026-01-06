"""
Trajectory Repository Module.

Handles database operations for the `moving_features` table,
managing temporal trajectories for map markers.
"""

import json
import logging
import uuid
from typing import List, Optional, Tuple

from src.core.trajectory import Keyframe
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
            marker_id: The ID of the marker this trajectory belongs to.
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

    def get_by_marker_id(self, marker_id: str) -> List[Tuple[str, List[Keyframe]]]:
        """
        Retrieves all trajectories associated with a marker.

        Args:
            marker_id: The UUID of the marker.

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
        cursor = self._connection.execute(sql, (marker_id,))
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
            List of tuples (marker_id, trajectory_id, List[Keyframe]).
        """
        if not self._connection:
            raise RuntimeError("Database connection not initialized")

        sql = """
            SELECT mf.id as traj_id, mf.marker_id, mf.trajectory
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
