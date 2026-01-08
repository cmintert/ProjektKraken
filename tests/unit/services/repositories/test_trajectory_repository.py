"""
Unit tests for TrajectoryRepository.
"""

import sqlite3

import pytest

from src.core.trajectory import Keyframe
from src.services.repositories.trajectory_repository import TrajectoryRepository

# Schema needed for testing (moving_features + markers + maps)
TEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS maps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS markers (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    object_id TEXT NOT NULL DEFAULT 'unknown',
    FOREIGN KEY(map_id) REFERENCES maps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS moving_features (
    id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    trajectory JSON NOT NULL,
    properties JSON DEFAULT '{}',
    created_at REAL,
    FOREIGN KEY(marker_id) REFERENCES markers(id) ON DELETE CASCADE
);
"""


@pytest.fixture
def db_connection():
    """Provides an in-memory SQLite connection with the necessary schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(TEST_SCHEMA)
    yield conn
    conn.close()


@pytest.fixture
def repo(db_connection):
    """Provides a TrajectoryRepository instance connected to the test DB."""
    repo = TrajectoryRepository()
    repo.set_connection(db_connection)
    return repo


@pytest.fixture
def setup_data(db_connection):
    """Inserts a test map and marker."""
    db_connection.execute("INSERT INTO maps (id, name) VALUES ('map1', 'Test Map')")
    # 'marker1' serves as both internal DB ID and object_id for simplicity here
    db_connection.execute(
        "INSERT INTO markers (id, map_id, object_id) "
        "VALUES ('marker1', 'map1', 'marker1')"
    )
    db_connection.commit()
    return {"map_id": "map1", "marker_id": "marker1"}


class TestTrajectoryRepository:
    def test_insert_and_get_by_marker_id(self, repo, setup_data):
        marker_id = setup_data["marker_id"]
        trajectory = [
            Keyframe(t=0.0, x=0.1, y=0.1),
            Keyframe(t=100.0, x=0.9, y=0.9),
        ]

        traj_id = repo.insert(marker_id, trajectory)
        assert traj_id is not None

        results = repo.get_by_marker_db_id(marker_id)
        assert len(results) == 1
        fetched_id, fetched_traj = results[0]

        assert fetched_id == traj_id
        assert len(fetched_traj) == 2
        assert fetched_traj[0].t == 0.0
        assert fetched_traj[0].x == 0.1
        assert fetched_traj[1].t == 100.0

    def test_insert_empty_trajectory_raises_error(self, repo, setup_data):
        marker_id = setup_data["marker_id"]
        with pytest.raises(ValueError, match="empty trajectory"):
            repo.insert(marker_id, [])

    def test_get_by_map_id(self, repo, setup_data):
        map_id = setup_data["map_id"]
        marker_id = setup_data["marker_id"]
        trajectory = [Keyframe(t=0, x=0, y=0), Keyframe(t=10, x=1, y=1)]

        repo.insert(marker_id, trajectory)

        # Create another map and marker/trajectory to ensure filtering works
        repo._connection.execute(
            "INSERT INTO maps (id, name) VALUES ('map2', 'Other Map')"
        )
        repo._connection.execute(
            "INSERT INTO markers (id, map_id, object_id) "
            "VALUES ('marker2', 'map2', 'marker2')"
        )
        repo.insert("marker2", trajectory)

        results = repo.get_by_map_id(map_id)
        assert len(results) == 1
        fetched_marker_id, _, fetched_traj = results[0]

        assert fetched_marker_id == marker_id
        assert len(fetched_traj) == 2

    def test_trajectory_columns_populated_correctly(self, repo, setup_data):
        """Verify t_start and t_end are stored correctly in DB columns."""
        marker_id = setup_data["marker_id"]
        trajectory = [
            Keyframe(t=10.0, x=0.0, y=0.0),
            Keyframe(t=50.0, x=1.0, y=1.0),
        ]

        traj_id = repo.insert(marker_id, trajectory)

        row = repo._connection.execute(
            "SELECT t_start, t_end FROM moving_features WHERE id = ?", (traj_id,)
        ).fetchone()

        assert row["t_start"] == 10.0
        assert row["t_start"] == 10.0
        assert row["t_end"] == 50.0

    def test_update_keyframe_time_and_resort(self, repo, setup_data):
        """Test updating a keyframe time and verifying re-sort."""
        marker_id = setup_data["marker_id"]
        # Initial: t=10, t=50, t=90
        trajectory = [
            Keyframe(t=10.0, x=0.1, y=0.1),
            Keyframe(t=50.0, x=0.5, y=0.5),
            Keyframe(t=90.0, x=0.9, y=0.9),
        ]
        repo.insert(marker_id, trajectory)

        # Move middle keyframe (t=50) to t=5 (should become first)
        repo.update_keyframe_time("map1", marker_id, 50.0, 5.0)

        # Verify new order
        fetched = repo.get_by_marker_db_id(marker_id)[0][1]
        assert len(fetched) == 3
        # Should be sorted: 5.0, 10.0, 90.0
        assert fetched[0].t == 5.0
        assert fetched[0].x == 0.5  # Moved item
        assert fetched[1].t == 10.0
        assert fetched[2].t == 90.0

    def test_update_keyframe_time_not_found(self, repo, setup_data):
        """Test updating a non-existent keyframe raises ValueError."""
        marker_id = setup_data["marker_id"]
        trajectory = [Keyframe(t=10.0, x=0.0, y=0.0)]
        repo.insert(marker_id, trajectory)

        # Try to update t=999 (doesn't exist)
        with pytest.raises(ValueError, match="Keyframe at t=999.0 not found"):
            repo.update_keyframe_time("map1", marker_id, 999.0, 50.0)

        fetched = repo.get_by_marker_db_id(marker_id)[0][1]
        assert len(fetched) == 1
        assert fetched[0].t == 10.0
