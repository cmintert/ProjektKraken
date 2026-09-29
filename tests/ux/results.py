"""Versioned records for opt-in internal authoring walkthroughs."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.ux.catalog import CATALOG_VERSION, TASKS
from tests.ux.fixture import SCENARIO_VERSION, archive_provenance

SCHEMA_VERSION = 1
_OUTCOMES = {"not_run", "success", "partial", "failure", "blocked"}


def _git(repo: Path, *args: str) -> bytes:
    command = ["git", "-c", f"safe.directory={repo.as_posix()}", *args]
    return subprocess.run(command, cwd=repo, check=True, capture_output=True).stdout


def source_identity(repo: Path) -> dict[str, Any]:
    """Tie a run to the checkout, including uncommitted work."""
    commit = _git(repo, "rev-parse", "HEAD").decode().strip()
    status = _git(repo, "status", "--porcelain", "--untracked-files=normal")
    patch = _git(repo, "diff", "--binary", "HEAD")
    digest = hashlib.sha256(patch)
    for relative in sorted(
        path for path in _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if path
    ):
        digest.update(relative)
        digest.update(hashlib.sha256((repo / relative.decode()).read_bytes()).digest())
    return {
        "commit": commit,
        "dirty": bool(status),
        "status": status.decode(errors="replace"),
        "working_tree_sha256": digest.hexdigest(),
    }


def new_result(run_id: str, repo: Path) -> dict[str, Any]:
    """Create an empty run with explicit unmeasured human ratings."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_version": CATALOG_VERSION,
        "scenario_version": SCENARIO_VERSION,
        "archive": archive_provenance(),
        "source": source_identity(repo),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "tasks": {
            task.id: {
                "scenario": None,
                "completion": "not_run",
                "correctness": None,
                "elapsed_seconds": None,
                "actions": None,
                "errors": None,
                "backtracks": None,
                "help_events": None,
                "decision_points": None,
                "recall_dependencies": None,
                "internal_terms": [],
                "relevant_controls": None,
                "presented_controls": None,
                "seq": None,
                "nasa_tlx": None,
                "ratings_reason": "No human participant in internal walkthrough",
                "notes": "",
                "screenshots": [],
            }
            for task in TASKS
        },
    }


def validate_result(result: dict[str, Any]) -> None:
    """Reject malformed or falsely complete benchmark results."""
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported UX results schema")
    if set(result.get("tasks", {})) != {task.id for task in TASKS}:
        raise ValueError("UX results must contain all versioned task IDs")
    for task_id, row in result["tasks"].items():
        if row.get("completion") not in _OUTCOMES:
            raise ValueError(f"Invalid completion for {task_id}")
        if row["completion"] != "not_run" and not row.get("notes"):
            raise ValueError(f"Attempted task {task_id} requires observation notes")
        if row["completion"] == "success" and row.get("correctness") is not True:
            raise ValueError(f"Successful task {task_id} requires verified correctness")
        for key in ("elapsed_seconds", "actions", "errors", "backtracks", "help_events"):
            value = row.get(key)
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                raise ValueError(f"Invalid {key} for {task_id}")
        relevant, presented = row.get("relevant_controls"), row.get("presented_controls")
        if relevant is not None and presented is not None and not (0 <= relevant <= presented):
            raise ValueError(f"Invalid relevant-control count for {task_id}")


def save_result(path: Path, result: dict[str, Any]) -> None:
    """Write a validated run and derived CSV/Markdown views."""
    validate_result(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = []
    for task in TASKS:
        row = result["tasks"][task.id]
        presented = row["presented_controls"]
        relevant = row["relevant_controls"]
        rows.append(
            {
                "task_id": task.id,
                "completion": row["completion"],
                "correctness": row["correctness"],
                "elapsed_seconds": row["elapsed_seconds"],
                "actions": row["actions"],
                "errors": row["errors"],
                "backtracks": row["backtracks"],
                "help_events": row["help_events"],
                "rcr": relevant / presented if presented else "",
                "notes": row["notes"],
            }
        )
    with path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = [
        f"# Authoring UX baseline {result['run_id']}",
        "",
        f"Archive SHA-256: `{result['archive']['sha256']}`",
        f"Source commit: `{result['source']['commit']}`",
        f"Dirty checkout: `{result['source']['dirty']}`",
        "SEQ and NASA-TLX: unmeasured in this internal walkthrough.",
        "",
        "| Task | Outcome | Correct | Seconds | Actions | Notes |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        notes = str(row["notes"]).replace("|", "\\|").replace("\n", " ")
        summary.append(
            f"| {row['task_id']} | {row['completion']} | {row['correctness']} "
            f"| {row['elapsed_seconds']} | {row['actions']} | {notes} |"
        )
    path.with_suffix(".md").write_text("\n".join(summary) + "\n", encoding="utf-8")
