"""
Unit tests for TrajectoryRepository.
"""

import json
import math
import sqlite3

import pytest

from src.core.trajectory import Keyframe
from src.services.repositories.trajectory_repository import (
    AmbiguousTrajectoryError,
    TrajectoryConflictError,
    TrajectoryRepository,
)

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

    def test_add_keyframe_creates_new_trajectory(self, repo, setup_data):
        """Test adding a keyframe to a marker with no existing trajectory."""
        marker_id = setup_data["marker_id"]
        # Ensure no trajectory exists initially
        assert len(repo.get_by_marker_db_id(marker_id)) == 0

        kf = Keyframe(t=15.0, x=0.2, y=0.2)
        repo.add_keyframe("map1", marker_id, kf)

        results = repo.get_by_marker_db_id(marker_id)
        assert len(results) == 1
        fetched_traj = results[0][1]
        assert len(fetched_traj) == 1
        assert fetched_traj[0].t == 15.0

    def test_add_keyframe_raises_error_for_missing_marker(self, repo):
        """Test that adding a keyframe for a non-existent marker fails."""
        kf = Keyframe(t=10.0, x=0.5, y=0.5)
        # Repo logic apparently checks for marker existence explicitly
        with pytest.raises(ValueError, match="Marker not found"):
            repo.add_keyframe("map1", "non_existent_marker", kf)

    def test_backward_compat_parses_old_format(self, repo, db_connection, setup_data):
        """Test that old [[t,x,y],...] format is correctly parsed."""
        marker_id = setup_data["marker_id"]
        # Insert old-format trajectory directly into DB
        old_format = [[10.0, 0.1, 0.1], [50.0, 0.5, 0.5]]
        db_connection.execute(
            """
            INSERT INTO moving_features (id, marker_id, t_start, t_end, trajectory, properties)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("old-traj-id", marker_id, 10.0, 50.0, json.dumps(old_format), "{}"),
        )
        db_connection.commit()

        # Verify repo can parse it
        results = repo.get_by_marker_db_id(marker_id)
        assert len(results) == 1
        traj_id, keyframes = results[0]
        assert traj_id == "old-traj-id"
        assert len(keyframes) == 2
        assert keyframes[0].t == 10.0
        assert keyframes[0].x == 0.1
        assert keyframes[1].t == 50.0
        assert keyframes[1].x == 0.5

    def test_insert_does_not_sort_or_reuse_caller_values(self, repo, setup_data):
        """Repository insertion owns an independent sorted snapshot."""
        first = Keyframe(t=20.0, x=0.8, y=0.8)
        second = Keyframe(t=10.0, x=0.2, y=0.2)
        supplied = [first, second]

        repo.insert(setup_data["marker_id"], supplied)
        first.x = 0.1

        assert supplied == [first, second]
        assert [keyframe.t for keyframe in supplied] == [20.0, 10.0]
        persisted = repo.get_by_marker_db_id(setup_data["marker_id"])[0][1]
        assert [(keyframe.t, keyframe.x) for keyframe in persisted] == [
            (10.0, 0.2),
            (20.0, 0.8),
        ]

    def test_complete_replacement_preserves_row_metadata(
        self, repo, db_connection, setup_data
    ):
        """Atomic replacement preserves row identity and opaque metadata."""
        trajectory_id = repo.insert(
            setup_data["marker_id"],
            [
                Keyframe(t=0.0, x=0.1, y=0.1),
                Keyframe(t=10.0, x=0.9, y=0.9),
            ],
            properties={"stroke": "dashed"},
        )
        db_connection.execute(
            "UPDATE moving_features SET created_at = ? WHERE id = ?",
            (1234.5, trajectory_id),
        )
        db_connection.commit()
        before = repo.get_marker_trajectory_snapshot("map1", "marker1")
        assert before is not None

        supplied = [
            Keyframe(t=30.0, x=0.7, y=0.8),
            Keyframe(t=20.0, x=0.3, y=0.4),
        ]
        after = repo.set_marker_trajectory(
            "map1",
            "marker1",
            supplied,
            expected_snapshot=before,
        )

        assert after is not None
        assert after["id"] == before["id"]
        assert after["marker_id"] == before["marker_id"]
        assert after["properties"] == before["properties"]
        assert after["created_at"] == before["created_at"]
        assert after["t_start"] == 20.0
        assert after["t_end"] == 30.0
        assert [keyframe.t for keyframe in supplied] == [30.0, 20.0]

    def test_complete_replacement_preserves_one_keyframe(self, repo, setup_data):
        """A one-point trajectory remains a persisted domain state."""
        repo.insert(
            setup_data["marker_id"],
            [Keyframe(t=0.0, x=0.1, y=0.1), Keyframe(t=10.0, x=0.9, y=0.9)],
        )
        before = repo.get_marker_trajectory_snapshot("map1", "marker1")

        after = repo.set_marker_trajectory(
            "map1",
            "marker1",
            [Keyframe(t=5.0, x=0.4, y=0.6)],
            expected_snapshot=before,
        )

        assert after is not None
        assert after["t_start"] == 5.0
        assert after["t_end"] == 5.0
        persisted = repo.get_by_marker_db_id(setup_data["marker_id"])
        assert len(persisted) == 1
        assert persisted[0][1] == [Keyframe(t=5.0, x=0.4, y=0.6)]

    def test_complete_replacement_deletes_only_at_zero(self, repo, setup_data):
        """An empty complete state deletes the trajectory row."""
        repo.insert(
            setup_data["marker_id"], [Keyframe(t=5.0, x=0.4, y=0.6)]
        )
        before = repo.get_marker_trajectory_snapshot("map1", "marker1")

        after = repo.set_marker_trajectory(
            "map1", "marker1", [], expected_snapshot=before
        )

        assert after is None
        assert repo.get_marker_trajectory_snapshot("map1", "marker1") is None

    def test_granular_delete_preserves_one_remaining_keyframe(
        self, repo, setup_data
    ):
        """Legacy deletion follows the corrected one-keyframe contract."""
        trajectory_id = repo.insert(
            setup_data["marker_id"],
            [Keyframe(t=0.0, x=0.1, y=0.1), Keyframe(t=10.0, x=0.9, y=0.9)],
        )

        result = repo.delete_keyframe("map1", "marker1", 10.0)

        assert result == trajectory_id
        persisted = repo.get_by_marker_db_id(setup_data["marker_id"])
        assert persisted[0][1] == [Keyframe(t=0.0, x=0.1, y=0.1)]

    @pytest.mark.parametrize(
        "invalid_keyframes",
        [
            [Keyframe(t=0.0, x=-0.1, y=0.5)],
            [Keyframe(t=0.0, x=0.5, y=math.inf)],
            [
                Keyframe(t=0.0, x=0.1, y=0.1),
                Keyframe(t=0.01, x=0.9, y=0.9),
            ],
        ],
    )
    def test_complete_replacement_rejects_invalid_data(
        self, repo, setup_data, invalid_keyframes
    ):
        """Repository validation rejects invalid complete states."""
        with pytest.raises(ValueError, match="Invalid trajectory"):
            repo.set_marker_trajectory(
                "map1",
                "marker1",
                invalid_keyframes,
                expected_snapshot=None,
            )

        assert repo.get_marker_trajectory_snapshot("map1", "marker1") is None

    def test_stale_expected_snapshot_rejects_replacement(
        self, repo, db_connection, setup_data
    ):
        """A concurrent row change cannot be overwritten silently."""
        trajectory_id = repo.insert(
            setup_data["marker_id"], [Keyframe(t=1.0, x=0.1, y=0.1)]
        )
        expected = repo.get_marker_trajectory_snapshot("map1", "marker1")
        db_connection.execute(
            "UPDATE moving_features SET properties = ? WHERE id = ?",
            ('{"external": true}', trajectory_id),
        )
        db_connection.commit()

        with pytest.raises(TrajectoryConflictError, match="changed"):
            repo.set_marker_trajectory(
                "map1",
                "marker1",
                [Keyframe(t=2.0, x=0.2, y=0.2)],
                expected_snapshot=expected,
            )

        current = repo.get_marker_trajectory_snapshot("map1", "marker1")
        assert current is not None
        assert current["properties"] == '{"external": true}'

    def test_duplicate_rows_raise_explicit_ambiguity(
        self, repo, db_connection, setup_data
    ):
        """Single-trajectory operations never choose a duplicate row."""
        repo.insert(
            setup_data["marker_id"], [Keyframe(t=1.0, x=0.1, y=0.1)]
        )
        db_connection.execute(
            """
            INSERT INTO moving_features
                (id, marker_id, t_start, t_end, trajectory, properties)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "duplicate-trajectory",
                setup_data["marker_id"],
                2.0,
                2.0,
                json.dumps(
                    {
                        "type": "MovingPoint",
                        "coordinates": [[0.2, 0.2]],
                        "datetimes": [2.0],
                    }
                ),
                "{}",
            ),
        )
        db_connection.commit()

        with pytest.raises(AmbiguousTrajectoryError, match="2 trajectory rows"):
            repo.get_marker_trajectory_snapshot("map1", "marker1")
        with pytest.raises(AmbiguousTrajectoryError, match="2 trajectory rows"):
            repo.add_keyframe(
                "map1", "marker1", Keyframe(t=3.0, x=0.3, y=0.3)
            )

    def test_failed_update_rolls_back_exact_prior_row(
        self, repo, db_connection, setup_data
    ):
        """A database failure leaves the complete prior row untouched."""
        repo.insert(
            setup_data["marker_id"], [Keyframe(t=1.0, x=0.1, y=0.1)]
        )
        before = repo.get_marker_trajectory_snapshot("map1", "marker1")
        db_connection.execute(
            """
            CREATE TRIGGER reject_trajectory_update
            BEFORE UPDATE ON moving_features
            BEGIN
                SELECT RAISE(ABORT, 'blocked by test');
            END
            """
        )
        db_connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="blocked by test"):
            repo.set_marker_trajectory(
                "map1",
                "marker1",
                [Keyframe(t=2.0, x=0.2, y=0.2)],
                expected_snapshot=before,
            )

        assert repo.get_marker_trajectory_snapshot("map1", "marker1") == before
