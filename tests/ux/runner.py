"""Opt-in authoring UX fixture and observation command line."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence

from tests.ux.catalog import TASK_BY_ID, TASKS
from tests.ux.fixture import prepare_task
from tests.ux.results import new_result, save_result, source_identity, validate_result

REPO_ROOT = Path(__file__).resolve().parents[2]
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def run_root(run_id: str) -> Path:
    """Confine working copies and settings to ignored UX storage."""
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("Run ID must be 1-80 letters, digits, hyphens or underscores")
    allowed = (REPO_ROOT / "tmp" / "ux").resolve(strict=False)
    candidate = (allowed / run_id).resolve(strict=False)
    if not candidate.is_relative_to(allowed) or candidate == allowed:
        raise ValueError("UX run path escaped tmp/ux")
    return candidate


def _result_path(root: Path) -> Path:
    return root / "results.json"


def _load(root: Path) -> dict[str, Any]:
    result = json.loads(_result_path(root).read_text(encoding="utf-8"))
    validate_result(result)
    return result


def _prepare(root: Path, result: dict[str, Any], task_id: str) -> None:
    if task_id not in TASK_BY_ID:
        raise ValueError(f"Unknown task {task_id}")
    row = result["tasks"][task_id]
    if row["scenario"] is not None:
        raise ValueError(f"Task {task_id} is already prepared")
    scenario = prepare_task(task_id, root / "scenarios" / task_id / "worlds")
    row["scenario"] = scenario
    save_result(_result_path(root), result)


def _open_app(root: Path, result: dict[str, Any], task_id: str) -> int:
    if source_identity(REPO_ROOT) != result["source"]:
        raise ValueError("Checkout changed since the UX run began; start a new run")
    scenario = result["tasks"][task_id]["scenario"]
    if scenario is None:
        raise ValueError("Prepare the task before opening it")
    world_path = Path(scenario["world_path"])
    if not world_path.is_relative_to(root):
        raise ValueError("Scenario world is outside this UX run")
    runtime = root / "runtime" / task_id
    for name in ("appdata", "localappdata", "logs"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["APPDATA"] = str(runtime / "appdata")
    environment["LOCALAPPDATA"] = str(runtime / "localappdata")
    environment["XDG_CONFIG_HOME"] = str(runtime / "appdata")
    environment["PROJEKTKRAKEN_PERFORMANCE_WORLDS_DIR"] = str(world_path.parent)
    environment["PROJEKTKRAKEN_PERFORMANCE_LOG_DIR"] = str(runtime / "logs")
    environment.pop("QT_QPA_PLATFORM", None)
    command = [
        sys.executable,
        "-m",
        "tests.ux.launch",
        "--world",
        str(world_path),
        "--settings",
        str(runtime / "settings"),
    ]
    return subprocess.run(command, cwd=REPO_ROOT, env=environment, check=False).returncode


def _record(result: dict[str, Any], options: argparse.Namespace) -> None:
    row = result["tasks"][options.task]
    if row["scenario"] is None:
        raise ValueError("Prepare the task before recording an observation")
    row.update(
        completion=options.completion,
        correctness={"true": True, "false": False, "unknown": None}[options.correctness],
        elapsed_seconds=options.seconds,
        actions=options.actions,
        errors=options.errors,
        backtracks=options.backtracks,
        help_events=options.help_events,
        decision_points=options.decision_points,
        recall_dependencies=options.recall_dependencies,
        internal_terms=options.internal_term,
        relevant_controls=options.relevant_controls,
        presented_controls=options.presented_controls,
        notes=options.notes,
    )


def build_parser() -> argparse.ArgumentParser:
    """Describe preparation, real-app opening, observation, and publication."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--task", choices=tuple(TASK_BY_ID))
    prepare.add_argument("--all", action="store_true")
    launch = sub.add_parser("open")
    launch.add_argument("--task", required=True, choices=tuple(TASK_BY_ID))
    record = sub.add_parser("record")
    record.add_argument("--task", required=True, choices=tuple(TASK_BY_ID))
    record.add_argument("--completion", required=True, choices=("success", "partial", "failure", "blocked"))
    record.add_argument("--correctness", required=True, choices=("true", "false", "unknown"))
    record.add_argument("--seconds", type=float)
    record.add_argument("--actions", type=int)
    record.add_argument("--errors", type=int)
    record.add_argument("--backtracks", type=int)
    record.add_argument("--help-events", type=int)
    record.add_argument("--decision-points", type=int)
    record.add_argument("--recall-dependencies", type=int)
    record.add_argument("--internal-term", action="append", default=[])
    record.add_argument("--relevant-controls", type=int)
    record.add_argument("--presented-controls", type=int)
    record.add_argument("--notes", required=True)
    screenshot = sub.add_parser("screenshot")
    screenshot.add_argument("--task", required=True, choices=tuple(TASK_BY_ID))
    screenshot.add_argument("--path", required=True, type=Path)
    screenshot.add_argument("--state", required=True)
    screenshot.add_argument("--theme", required=True)
    screenshot.add_argument("--scale", required=True, type=float)
    screenshot.add_argument("--window-size", required=True)
    sub.add_parser("report")
    sub.add_parser("publish")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one opt-in benchmark administration command."""
    options = build_parser().parse_args(argv)
    root = run_root(options.run_id)
    path = _result_path(root)
    if options.command == "new":
        root.mkdir(parents=True, exist_ok=False)
        save_result(path, new_result(options.run_id, REPO_ROOT))
        return 0
    result = _load(root)
    if options.command == "prepare":
        if options.all == bool(options.task):
            raise ValueError("Choose exactly one of --task or --all")
        for task in TASKS if options.all else (TASK_BY_ID[options.task],):
            _prepare(root, result, task.id)
    elif options.command == "open":
        return _open_app(root, result, options.task)
    elif options.command == "record":
        _record(result, options)
        save_result(path, result)
    elif options.command == "screenshot":
        source = options.path.resolve(strict=True)
        if not source.is_relative_to(root) or source.suffix.lower() != ".png":
            raise ValueError("Screenshot must be a PNG inside this UX run")
        result["tasks"][options.task]["screenshots"].append(
            {
                "path": source.relative_to(root).as_posix(),
                "state": options.state,
                "theme": options.theme,
                "scale": options.scale,
                "window_size": options.window_size,
            }
        )
        save_result(path, result)
    elif options.command == "report":
        save_result(path, result)
    elif options.command == "publish":
        if any(row["completion"] == "not_run" for row in result["tasks"].values()):
            raise ValueError("All 40 task attempts must be recorded before publication")
        if not any(row["screenshots"] for row in result["tasks"].values()):
            raise ValueError("Rendered screenshots are required before publication")
        source = result["source"]
        suffix = f"-dirty-{source['working_tree_sha256'][:8]}" if source["dirty"] else ""
        destination = REPO_ROOT / "tests" / "ux" / "results" / f"baseline-{source['commit'][:8]}{suffix}.json"
        save_result(path, result)
        published = deepcopy(result)
        for row in published["tasks"].values():
            for screenshot in row["screenshots"]:
                source_image = root / screenshot["path"]
                target_image = destination.parent / destination.stem / screenshot["path"]
                target_image.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_image, target_image)
                screenshot["path"] = f"{destination.stem}/{screenshot['path']}"
        save_result(destination, published)
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
