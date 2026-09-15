"""Manual command-line runner for the read-only measurement suite."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.performance.database_metrics import measure_database
from src.performance.fixture import generate_fixture
from src.performance.models import PROFILES
from src.performance.reporting import write_reports
from src.performance.resources import environment_metadata
from src.performance.safety import (
    capture_integrity,
    compare_integrity,
    validate_run_root,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the public, manually invoked suite interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate isolated large worlds and measure ProjektKraken. "
            "MEASUREMENT ONLY: this command never applies optimizations."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true", help="Run the standard profile")
    mode.add_argument("--full", action="store_true", help="Run every workload profile")
    parser.add_argument("--target", choices=("source", "packaged"), required=True)
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--seed", type=int, default=20_260_914)
    parser.add_argument("--keep-fixture", action="store_true")
    parser.add_argument("--compare", type=Path)
    parser.add_argument(
        "--packaged-executable",
        type=Path,
        help="Override dist/ProjektKraken/ProjektKraken.exe",
    )
    parser.add_argument("--trace", action="store_true", help="Retain detailed samples")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-profile watchdog in seconds (default: quick 600, full 1200)",
    )
    parser.add_argument(
        "--playback-seconds",
        type=float,
        default=60.0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--scrub-positions",
        type=int,
        default=300,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected profiles and preserve a report even after interruption."""
    options = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    mode = "full" if options.full else "quick"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_root = validate_run_root(
        repo_root, repo_root / "tmp" / "performance" / run_id
    )
    run_root.mkdir(parents=True, exist_ok=False)
    partial_path = run_root / "partial-run.json"
    profiles = list(PROFILES) if options.full else ["standard"]
    repetitions = 5 if options.full else 2
    timeout = options.timeout or (1200.0 if options.full else 600.0)
    manifest: dict[str, Any] = {
        "label": "MEASUREMENT ONLY",
        "schema_version": 1,
        "run_id": run_id,
        "mode": mode,
        "target": options.target,
        "seed": options.seed,
        "profiles": profiles,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment_metadata(),
        "status": "running",
    }
    raw_metrics: dict[str, Any] = {}
    generated_fixture_roots: list[Path] = []
    before = capture_integrity(repo_root)
    exit_code = 0
    try:
        for index, profile_name in enumerate(profiles):
            profile_root = run_root / profile_name
            profile_root.mkdir()
            world_root = profile_root / "fixture" / "world"
            generated_fixture_roots.append(profile_root / "fixture")
            fixture_manifest = generate_fixture(
                world_root, PROFILES[profile_name], options.seed + index
            )
            manifest.setdefault("fixtures", []).append(fixture_manifest)
            _merge_metrics(
                raw_metrics,
                profile_name,
                measure_database(Path(fixture_manifest["database_path"]), repetitions),
            )
            probe_report, process_metrics = _run_probe(
                repo_root=repo_root,
                run_root=profile_root,
                world_root=world_root,
                profile=profile_name,
                target=options.target,
                packaged_executable=options.packaged_executable,
                repetitions=repetitions,
                visible=options.visible,
                scrub_positions=options.scrub_positions,
                playback_seconds=options.playback_seconds,
                timeout=timeout,
                trace=options.trace,
            )
            _merge_metrics(raw_metrics, profile_name, process_metrics)
            _merge_metrics(raw_metrics, profile_name, probe_report.get("metrics", {}))
            manifest.setdefault("warnings", []).extend(
                probe_report.get("warnings", [])
            )
            if not probe_report.get("success", False):
                exit_code = 1
                manifest.setdefault("errors", []).extend(probe_report.get("errors", []))
            partial_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    except KeyboardInterrupt:
        exit_code = 130
        manifest.setdefault("errors", []).append("Run interrupted by user.")
    except subprocess.TimeoutExpired as exc:
        exit_code = 2
        manifest.setdefault("errors", []).append(
            f"Profile process exceeded {exc.timeout} seconds."
        )
    except Exception as exc:
        exit_code = 1
        manifest.setdefault("errors", []).append(
            f"Suite failed: {type(exc).__name__}: {exc}"
        )
    finally:
        if not options.keep_fixture:
            for fixture_root in generated_fixture_roots:
                _remove_generated_fixture(run_root, fixture_root)
        after = capture_integrity(repo_root)
        integrity = compare_integrity(before, after)
        manifest["integrity"] = integrity
        if not integrity["success"]:
            exit_code = 1
        manifest["status"] = "complete" if exit_code == 0 else "failed"
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["exit_code"] = exit_code
        write_reports(
            run_root,
            manifest,
            raw_metrics,
            compare_path=options.compare.resolve() if options.compare else None,
        )
        partial_path.unlink(missing_ok=True)
    print(f"Measurement report: {run_root / 'summary.md'}")
    return exit_code


def _run_probe(
    *,
    repo_root: Path,
    run_root: Path,
    world_root: Path,
    profile: str,
    target: str,
    packaged_executable: Path | None,
    repetitions: int,
    visible: bool,
    scrub_positions: int,
    playback_seconds: float,
    timeout: float,
    trace: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report_path = run_root / "probe.json"
    settings_path = run_root / "runtime" / "settings"
    if target == "source":
        command = [sys.executable, str(repo_root / "launcher.py")]
    else:
        executable = (
            packaged_executable.resolve()
            if packaged_executable
            else repo_root / "dist" / "ProjektKraken" / "ProjektKraken.exe"
        )
        if not executable.is_file():
            raise FileNotFoundError(
                f"Packaged executable not found: {executable}. Build it first or pass "
                "--packaged-executable."
            )
        command = [str(executable)]
    command.extend(
        [
            "--performance-probe-report",
            str(report_path),
            "--performance-probe-world",
            str(world_root),
            "--performance-probe-settings",
            str(settings_path),
            "--performance-probe-profile",
            profile,
            "--performance-probe-repetitions",
            str(repetitions),
            "--performance-probe-scrub-positions",
            str(scrub_positions),
            "--performance-probe-playback-seconds",
            str(playback_seconds),
            "--performance-probe-timeout",
            str(timeout),
        ]
    )
    if visible:
        command.append("--performance-probe-visible")
    if trace:
        command.extend(
            ["--performance-probe-trace", str(run_root / "profile.pstats")]
        )

    runtime_root = run_root / "runtime"
    environment = os.environ.copy()
    environment["APPDATA"] = str(runtime_root / "appdata")
    environment["LOCALAPPDATA"] = str(runtime_root / "localappdata")
    environment["PROJEKTKRAKEN_PERFORMANCE_WORLDS_DIR"] = str(
        runtime_root / "worlds"
    )
    environment["PROJEKTKRAKEN_PERFORMANCE_LOG_DIR"] = str(runtime_root / "logs")
    if not visible:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    started = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout + 5,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        return_code = 124
        stdout = _timeout_text(exc.stdout)
        stderr = _timeout_text(exc.stderr)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    (run_root / "process.stdout.log").write_text(stdout, encoding="utf-8")
    (run_root / "process.stderr.log").write_text(stderr, encoding="utf-8")
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = {
            "success": False,
            "errors": [
                f"Probe exited with code {return_code} without a report."
            ],
            "metrics": {},
        }
    if timed_out:
        report["success"] = False
        report.setdefault("errors", []).append(
            f"External probe watchdog expired after {timeout + 5:.1f} seconds."
        )
    process_metrics = {
        "process.wall_total": {"unit": "ms", "samples": [elapsed_ms]},
        "process.exit_code": {"unit": "count", "samples": [return_code]},
    }
    return report, process_metrics


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _remove_generated_fixture(run_root: Path, fixture_root: Path) -> None:
    """Remove one suite-created fixture after verifying its exact location."""
    resolved_run_root = run_root.resolve(strict=True)
    resolved_fixture = fixture_root.resolve(strict=False)
    if (
        resolved_fixture.name != "fixture"
        or not resolved_fixture.is_relative_to(resolved_run_root)
    ):
        raise ValueError(f"Refusing to remove unsafe fixture path: {resolved_fixture}")
    if resolved_fixture.is_dir():
        shutil.rmtree(resolved_fixture)


def _merge_metrics(
    destination: dict[str, Any], profile: str, metrics: dict[str, Any]
) -> None:
    for name, metric in metrics.items():
        destination[f"{profile}.{name}"] = metric


if __name__ == "__main__":
    raise SystemExit(main())
