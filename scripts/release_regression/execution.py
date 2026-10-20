"""Supervise fresh module interpreters and retain evidence after native faults."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.release_regression import common, planner, process_tree

PYTEST_MAX_EXIT = 5


def launch(
    command: list[str], directory: Path, env: dict[str, str], timeout: float
) -> dict[str, Any]:
    """Execute without a shell and let the parent survive aborts and hangs."""
    start = time.monotonic()
    result: dict[str, Any] = {"command": command, "exit": None, "timed_out": False}
    options: dict[str, Any] = {}
    if sys.platform == "win32":
        # Suspend before assigning the job: a native venv redirector can otherwise
        # start its real interpreter before Popen returns and escape containment.
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
    else:
        options["start_new_session"] = True
    with (
        (directory / "stdout.log").open("wb") as stdout,
        (directory / "stderr.log").open("wb") as stderr,
    ):
        try:
            process = subprocess.Popen(
                command,
                cwd=common.ROOT,
                env=env,
                stdout=stdout,
                stderr=stderr,
                **options,
            )
            job = None
            try:
                if sys.platform == "win32":
                    job = process_tree.WindowsJob(process)
                    process_tree.resume(process.pid)
                try:
                    result["exit"] = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    result["timed_out"] = True
            finally:
                process_tree.cleanup(process, job)
            result["exit"] = process.returncode
        except OSError as error:
            result["error"] = str(error)
    result["seconds"] = time.monotonic() - start
    return result


def outcomes(directory: Path, expected: list[str]) -> dict[str, Any]:
    """Reconcile durable progress, including setup skips and teardown failures."""
    path = directory / "progress.jsonl"
    records = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    collections = [r["nodeids"] for r in records if r["event"] == "collection"]
    started = [r["nodeid"] for r in records if r["event"] == "start"]
    finished = [r["nodeid"] for r in records if r["event"] == "finish"]
    reports = [r for r in records if r["event"] == "report"]
    cases = {node: [r for r in reports if r["nodeid"] == node] for node in expected}
    terminal = {node: case_outcome(parts) for node, parts in cases.items()}
    sessions = [r for r in records if r["event"] == "session_finish"]
    complete = (
        collections == [expected]
        and started == expected
        and finished == expected
        and len(sessions) == 1
        and sessions[0]["exitstatus"] == 0
        and all(r["nodeid"] in cases for r in reports)
        and all(valid_phases(parts) for parts in cases.values())
    )
    return {
        "complete": complete,
        "counts": dict(Counter(terminal.values())),
        "outcomes": terminal,
        "failures": [r for r in reports if r["outcome"] == "failed" or r["xfail"]],
        "skips": [r for r in reports if r["outcome"] == "skipped"],
        "unfinished": [node for node in expected if node not in finished],
        "last_event": records[-1] if records else None,
        "started": len(started),
        "completed": len(finished),
    }


def valid_phases(parts: list[dict[str, Any]]) -> bool:
    """Require each phase exactly once, allowing setup skips without a call."""
    phases = [part["phase"] for part in parts]
    if phases == ["setup", "call", "teardown"]:
        return True
    return phases == ["setup", "teardown"] and parts[0]["outcome"] in {
        "skipped",
        "failed",
    }


def case_outcome(parts: list[dict[str, Any]]) -> str:
    """Never allow a successful call to hide teardown failure or xfail."""
    if any(r["outcome"] == "failed" or r["xfail"] for r in parts):
        return "failed"
    if any(r["outcome"] == "skipped" for r in parts):
        return "skipped"
    return "passed" if valid_phases(parts) else "incomplete"


def run_module(
    module: str, expected: list[str], directory: Path, timeout: float
) -> dict[str, Any]:
    """Run one module and seal every available artifact even after failure."""
    directory.mkdir(parents=True, exist_ok=False)
    common.write(directory / "selection.json", expected)
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONFAULTHANDLER": "1",
            "PK_RELEASE_SELECTION": str(directory / "selection.json"),
            "PK_RELEASE_PROGRESS": str(directory / "progress.jsonl"),
            "COVERAGE_FILE": str(directory / "coverage.data"),
        }
    )
    command = [
        sys.executable,
        "-X",
        "faulthandler",
        "-m",
        "pytest",
        module,
        "-p",
        "scripts.release_regression.plugin",
        "-o",
        "addopts=",
        "--strict-markers",
        "--durations=30",
        "--cov=src",
        "--cov-report=",
        f"--cov-config={common.ROOT / 'scripts/release_regression/coverage.ini'}",
        f"--junitxml={directory / 'junit.xml'}",
    ]
    result = launch(command, directory, env, timeout)
    try:
        result.update(outcomes(directory, expected))
    except (OSError, ValueError) as error:
        result.update(complete=False, error=str(error), unfinished=expected)
    result["module"] = module
    result["status"] = module_status(result)
    result["files"] = {
        path.name: common.file_hash(path)
        for path in directory.iterdir()
        if path.is_file()
    }
    common.write(directory / "module.json", common.seal({"schema": 1, **result}))
    return result


def module_status(result: dict[str, Any]) -> str:
    """Distinguish timeout, native crash, pytest failure and missing evidence."""
    if result["timed_out"]:
        return "timeout"
    if result["exit"] is None:
        return "infrastructure_failure"
    if result["exit"] < 0 or result["exit"] > PYTEST_MAX_EXIT:
        return "crash"
    if result["exit"]:
        return "test_failure" if result["exit"] == 1 else "collection_or_pytest_error"
    if not result["complete"]:
        return "incomplete"
    if result.get("counts", {}).get("failed", 0):
        return "test_failure"
    return "passed"


def run_shard(
    plan: dict[str, Any],
    shard: int,
    output: Path,
    *,
    attempt: int = 1,
    explanation: str = "",
    module_timeout: float = 600,
    shard_timeout: float = 1500,
) -> Path:
    """Continue other modules after failure and write immutable shard attempts."""
    planner.validate(plan)
    common.provenance(plan)
    if not 0 <= shard < len(plan["shards"]) or attempt < 1:
        raise ValueError("Invalid shard or attempt")
    directory = output / f"shard-{shard}-attempt-{attempt}"
    directory.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report: dict[str, Any] = {
        "schema": 1,
        "plan": plan["digest"],
        "sha": plan["sha"],
        "run": plan["run"],
        "shard": shard,
        "attempt": attempt,
        "explanation": explanation,
        "environment": common.environment(),
        "modules": [],
        "unstarted": [],
        "counts": {},
        "failures": [],
        "skips": [],
        "unfinished": [],
    }
    common.write(directory / "started.json", report)
    for index, module in enumerate(plan["shards"][shard]):
        remaining = shard_timeout - (time.monotonic() - start)
        if remaining <= 0:
            report["unstarted"] = plan["shards"][shard][index:]
            break
        result = run_module(
            module,
            plan["modules"][module],
            directory / str(index),
            min(module_timeout, remaining),
        )
        for outcome, count in result.get("counts", {}).items():
            report["counts"][outcome] = report["counts"].get(outcome, 0) + count
        for key in ("failures", "skips", "unfinished"):
            report[key].extend(result.get(key, []))
        report["modules"].append(
            {"module": module, "directory": str(index), "status": result["status"]}
        )
        common.write(directory / "checkpoint.json", report)
        sys.stdout.write(f"{module}: {result['status']} ({result['seconds']:.1f}s)\n")
        sys.stdout.flush()
    report["seconds"] = time.monotonic() - start
    try:
        common.provenance(plan)
    except ValueError as error:
        report["source_error"] = str(error)
    report["status"] = (
        "passed"
        if not report["unstarted"]
        and not report.get("source_error")
        and all(item["status"] == "passed" for item in report["modules"])
        else "failed"
    )
    common.write(directory / "shard.json", common.seal(report))
    return directory
