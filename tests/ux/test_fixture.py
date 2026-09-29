"""The authoring benchmark never changes its source package or real worlds."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from tests.ux.catalog import TASK_BY_ID, TASKS
from tests.ux.fixture import ARCHIVE, archive_provenance, prepare_task


def test_catalog_has_forty_stable_tasks() -> None:
    """Every tier has ten or twenty independently addressable tasks."""
    assert len(TASKS) == len(TASK_BY_ID) == 40
    assert {tier: sum(task.tier == tier for task in TASKS) for tier in "ABC"} == {
        "A": 20,
        "B": 10,
        "C": 10,
    }


def test_archive_provenance_and_isolated_repeatability(tmp_path: Path) -> None:
    """Two imports keep the package intact and start from equal logical data."""
    before = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    provenance = archive_provenance()
    first = prepare_task("KA-07", tmp_path / "first")
    second = prepare_task("KA-07", tmp_path / "second")
    assert provenance["sha256"] == before
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == before
    assert first["fingerprint"] == second["fingerprint"]
    for scenario in (first, second):
        world_path = Path(scenario["world_path"])
        assert world_path.is_relative_to(tmp_path)
        assert (world_path / "assets/maps/rhine_tribunal_benchmark.png").is_file()
        with sqlite3.connect(world_path / "world.kraken") as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute(
                "SELECT COUNT(*) FROM entities WHERE name IN ('Tasgillia', 'House Tytalus')"
            ).fetchone()[0] == 2


@pytest.mark.parametrize(
    "task_id", [task.id for task in TASKS if task.id not in {"KC-01", "KC-02"}]
)
def test_representative_scenarios_prepare(task_id: str, tmp_path: Path) -> None:
    """Every ordinary core, advanced, and edge scenario imports cleanly."""
    scenario = prepare_task(task_id, tmp_path / task_id)
    world_path = Path(scenario["world_path"])
    assert world_path.is_dir()
    assert len(scenario["fingerprint"]) == 64
    with sqlite3.connect(world_path / "world.kraken") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


@pytest.mark.performance
@pytest.mark.parametrize(
    ("task_id", "minimum_relations"),
    [("KC-01", 40_000), ("KC-02", 200_000)],
)
def test_large_scenarios_extend_archive(
    task_id: str, minimum_relations: int, tmp_path: Path
) -> None:
    """Large profiles preserve the named source data and reach their target scale."""
    scenario = prepare_task(task_id, tmp_path / task_id)
    with sqlite3.connect(Path(scenario["world_path"]) / "world.kraken") as connection:
        assert connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] >= (
            minimum_relations
        )
        assert connection.execute("SELECT COUNT(*) FROM maps").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM entities WHERE name = 'Rhine Tribunal'"
        ).fetchone()[0] == 1
