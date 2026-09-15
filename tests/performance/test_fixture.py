import json
import sqlite3
from pathlib import Path

from src.performance.fixture import generate_fixture
from src.performance.models import FixtureProfile


def _rows(database: Path, table: str) -> list[tuple]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    finally:
        connection.close()


def test_fixture_is_deterministic_and_records_exact_counts(tmp_path: Path) -> None:
    profile = FixtureProfile(
        "tiny", event_count=7, entity_count=11, relation_count=13, tag_count=3
    )
    first = generate_fixture(tmp_path / "first", profile, seed=42)
    second = generate_fixture(tmp_path / "second", profile, seed=42)

    first_db = Path(first["database_path"])
    second_db = Path(second["database_path"])
    assert _rows(first_db, "events") == _rows(second_db, "events")
    assert _rows(first_db, "entities") == _rows(second_db, "entities")
    assert _rows(first_db, "relations") == _rows(second_db, "relations")
    assert len(_rows(first_db, "events")) == 7
    assert len(_rows(first_db, "entities")) == 11
    assert len(_rows(first_db, "relations")) == 13
    manifest = json.loads((tmp_path / "first" / "world.json").read_text())
    assert manifest["db_filename"] == "measurement.kraken"


def test_temporal_map_fixture_populates_temporal_tables(tmp_path: Path) -> None:
    profile = FixtureProfile(
        "temporal-tiny",
        event_count=4,
        entity_count=8,
        relation_count=5,
        tag_count=2,
        marker_count=6,
        moving_marker_count=3,
        geometry_state_count=2,
    )

    manifest = generate_fixture(tmp_path / "world", profile, seed=7)
    database = Path(manifest["database_path"])

    assert len(_rows(database, "markers")) == 6
    assert len(_rows(database, "moving_features")) == 3
    assert len(_rows(database, "feature_geometry_states")) == 2

