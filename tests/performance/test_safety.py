from pathlib import Path

import pytest

from src.performance.safety import (
    IntegritySnapshot,
    UnsafePerformancePathError,
    compare_integrity,
    validate_run_root,
)


def test_validate_run_root_accepts_only_unique_performance_child(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    accepted = validate_run_root(repo, repo / "tmp" / "performance" / "run-1")

    assert accepted == (repo / "tmp" / "performance" / "run-1").resolve()
    with pytest.raises(UnsafePerformancePathError):
        validate_run_root(repo, repo / "tmp" / "performance")
    with pytest.raises(UnsafePerformancePathError):
        validate_run_root(repo, repo / "worlds" / "performance")


def test_compare_integrity_names_tracked_and_world_changes() -> None:
    before = IntegritySnapshot(
        tracked={"src/a.py": "old"},
        world_databases={"worlds/a/a.kraken": "same"},
        git_status="",
    )
    after = IntegritySnapshot(
        tracked={"src/a.py": "new"},
        world_databases={"worlds/a/a.kraken": "same"},
        git_status=" M src/a.py\n",
    )

    result = compare_integrity(before, after)

    assert result["success"] is False
    assert result["tracked_changes"] == ["src/a.py"]
    assert result["world_database_changes"] == []

