"""
Unit tests for Temporal Database Schema.
Verifies the existence and functionality of the moving_features table.
"""

import sqlite3
import pytest
from src.services.db_service import DatabaseService


@pytest.fixture
def db_service():
    """Provides an in-memory database service."""
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()


def test_moving_features_table_exists(db_service):
    """Test that the moving_features table is created."""
    cursor = db_service._connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='moving_features';"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result["name"] == "moving_features"


def test_insert_moving_feature(db_service):
    """Test inserting a row into moving_features."""
    cursor = db_service._connection.cursor()

    # 1. Create a map and marker first (foreign key constraint)
    cursor.execute(
        "INSERT INTO maps (id, name, image_path, created_at) VALUES (?, ?, ?, ?)",
        ("map1", "Test Map", "/path/to/img.png", 0.0),
    )
    cursor.execute(
        "INSERT INTO markers (id, map_id, object_id, object_type, x, y, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("marker1", "map1", "obj1", "entity", 0.5, 0.5, 0.0),
    )

    # 2. Insert moving feature
    trajectory_json = "[[0, 0.5, 0.5], [10, 0.6, 0.6]]"
    cursor.execute(
        """
        INSERT INTO moving_features (id, marker_id, t_start, t_end, trajectory, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        ("mf1", "marker1", 0.0, 10.0, trajectory_json, 0.0),
    )

    # 3. Verify insertion
    cursor.execute("SELECT * FROM moving_features WHERE id='mf1'")
    row = cursor.fetchone()
    assert row is not None
    assert row["marker_id"] == "marker1"
    assert row["trajectory"] == trajectory_json
