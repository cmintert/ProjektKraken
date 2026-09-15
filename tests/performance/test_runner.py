import json
import subprocess
from pathlib import Path

import pytest

from src.performance import runner
from src.performance.runner import _remove_generated_fixture, _run_probe
from src.performance.safety import IntegritySnapshot


def test_probe_timeout_preserves_checkpoint_report(
    monkeypatch, tmp_path: Path
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    checkpoint = {
        "status": "running",
        "success": False,
        "errors": [],
        "metrics": {"completed.phase": {"unit": "ms", "samples": [12.0]}},
    }
    (run_root / "probe.json").write_text(json.dumps(checkpoint), encoding="utf-8")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("probe", 6.0, output="partial output")

    monkeypatch.setattr(subprocess, "run", timeout)

    report, metrics = _run_probe(
        repo_root=tmp_path,
        run_root=run_root,
        world_root=tmp_path / "fixture",
        profile="tiny",
        target="source",
        packaged_executable=None,
        repetitions=1,
        visible=False,
        scrub_positions=1,
        playback_seconds=0.0,
        timeout=1.0,
        trace=False,
    )

    assert report["metrics"] == checkpoint["metrics"]
    assert "watchdog expired" in report["errors"][-1]
    assert metrics["process.exit_code"]["samples"] == [124]
    assert (run_root / "process.stdout.log").read_text() == "partial output"


def test_generated_fixture_cleanup_is_contained_to_run_root(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    fixture_root = run_root / "standard" / "fixture"
    fixture_root.mkdir(parents=True)
    (fixture_root / "measurement.kraken").write_bytes(b"fixture")
    outside = tmp_path / "fixture"
    outside.mkdir()

    _remove_generated_fixture(run_root, fixture_root)

    assert not fixture_root.exists()
    with pytest.raises(ValueError, match="unsafe fixture path"):
        _remove_generated_fixture(run_root, outside)
    assert outside.is_dir()


def test_interruption_writes_report_and_removes_fixture(
    monkeypatch, tmp_path: Path
) -> None:
    run_root = tmp_path / "performance-run"
    snapshot = IntegritySnapshot(tracked={}, world_databases={}, git_status="")

    monkeypatch.setattr(runner, "validate_run_root", lambda *_args: run_root)
    monkeypatch.setattr(runner, "capture_integrity", lambda *_args: snapshot)
    monkeypatch.setattr(runner, "environment_metadata", lambda: {})

    def interrupting_fixture(world_root, *_args):
        world_root.mkdir(parents=True)
        (world_root / "measurement.kraken").write_bytes(b"partial")
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "generate_fixture", interrupting_fixture)

    exit_code = runner.main(["--quick", "--target", "source"])

    manifest = json.loads((run_root / "run-manifest.json").read_text())
    assert exit_code == 130
    assert manifest["status"] == "failed"
    assert manifest["errors"] == ["Run interrupted by user."]
    assert manifest["integrity"]["success"] is True
    assert not (run_root / "standard" / "fixture").exists()
    assert (run_root / "summary.md").is_file()
