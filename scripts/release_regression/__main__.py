"""Plan, execute, recover and verify an exhaustive release regression."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from scripts.release_regression import aggregation, common, execution, planner


def parser() -> argparse.ArgumentParser:
    """Expose one contract for local and GitHub execution."""
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--shards", type=int, default=6)
    plan.add_argument(
        "--durations",
        type=Path,
        default=common.ROOT / "scripts/release_regression/durations.json",
    )
    plan.add_argument(
        "--run", default=os.environ.get("GITHUB_RUN_ID", str(uuid.uuid4()))
    )
    for command in ("run-shard", "resume", "aggregate"):
        child = commands.add_parser(command)
        child.add_argument("--plan", type=Path, required=True)
        child.add_argument("--output", type=Path, required=True)
        if command != "aggregate":
            child.add_argument("--shard", type=int, required=True)
            child.add_argument("--attempt", type=int, default=1)
            child.add_argument("--module-timeout", type=float, default=600)
            child.add_argument("--shard-timeout", type=float, default=1500)
        if command in {"resume", "aggregate"}:
            child.add_argument("--evidence", type=Path, required=True)
            child.add_argument("--explanation", default="")
        if command == "aggregate":
            child.add_argument("--review", type=Path)
            child.add_argument(
                "--upstream-result",
                default="success",
                choices=("success", "failure", "cancelled", "skipped"),
            )
    local = commands.add_parser("local")
    local.add_argument(
        "--output", type=Path, default=common.ROOT / "artifacts/release-runs"
    )
    local.add_argument("--plan", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--sha", required=True)
    verify.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    verify.add_argument("--run", type=int)
    review = commands.add_parser("github-review")
    review.add_argument("--output", type=Path, required=True)
    export = commands.add_parser("durations")
    export.add_argument("--log", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    return result


def create_plan(args: argparse.Namespace) -> dict[str, Any]:
    """Collect only once and persist the exact candidate's complete inventory."""
    from scripts import check_test_policy

    sha = common.source_sha()
    env = common.environment()
    start = time.monotonic()
    recorder = check_test_policy.collect_reviewed()
    result = planner.build(
        recorder.result,
        recorder.order,
        sha=sha,
        environment=env,
        run=args.run,
        durations=common.read(args.durations),
        shards=args.shards,
        collection_skips=recorder.skips,
        configuration=common.configuration(),
    )
    common.provenance(result)
    if args.output.exists():
        raise ValueError("Plan already exists; reuse it or start a new run directory")
    common.write(args.output, result)
    common.write(
        args.output.with_name("planning-metrics.json"),
        {
            "collection_seconds": time.monotonic() - start,
            "expected": len(result["order"]),
            "estimated_shard_seconds": result["estimated_shard_seconds"],
        },
    )
    return result


def local_run(output: Path, existing: Path | None = None) -> int:
    """Execute all shards sequentially and never call this from a push hook."""
    run = str(uuid.uuid4())
    directory = existing.resolve().parent if existing else output / run
    plan = (
        common.read(existing)
        if existing
        else create_plan(
            argparse.Namespace(
                output=directory / "plan.json",
                shards=6,
                run=run,
                durations=common.ROOT / "scripts/release_regression/durations.json",
            )
        )
    )
    for shard in range(len(plan["shards"])):
        execution.run_shard(plan, shard, directory)
    report = aggregation.aggregate(plan, directory, directory / "aggregate")
    sys.stdout.write(f"Release evidence: {directory}\n")
    return int(report["status"] != "passed")


def local_review(
    plan: dict[str, Any], root: Path, explanation: str
) -> dict[str, Any] | None:
    """Bind an operator's reviewed recovery explanation to retained attempts."""
    if not explanation.strip():
        return None
    versions = [
        int(p.name.rsplit("-", 1)[1])
        for p in root.rglob("shard-*-attempt-*")
        if p.is_dir()
    ]
    return {
        "run": plan["run"],
        "sha": plan["sha"],
        "attempt": max(versions, default=1),
        "explanation": explanation,
        "reviewer": getpass.getuser(),
    }


def dispatch(args: argparse.Namespace) -> int:
    """Dispatch without hiding a failed runner behind successful orchestration."""
    if args.command == "plan":
        create_plan(args)
        return 0
    if args.command == "local":
        return local_run(args.output.resolve(), args.plan)
    if args.command == "durations":
        common.write(
            args.output, planner.durations_from_log(args.log.read_text("utf-8"))
        )
        return 0
    if args.command in {"verify", "github-review"}:
        from scripts.release_regression import remote

        return remote.dispatch(args)
    plan = common.read(args.plan)
    planner.validate(plan)
    if args.command == "aggregate":
        review = (
            common.read(args.review)
            if args.review
            else local_review(plan, args.evidence, args.explanation)
        )
        report = aggregation.aggregate(
            plan, args.evidence, args.output, review, args.upstream_result
        )
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(aggregation.render_summary(report))
                stream.write(
                    f"\n[Run artifacts]({os.environ.get('GITHUB_SERVER_URL', '')}/"
                    f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/"
                    f"{plan['run']})\n"
                )
        return int(report["status"] != "passed")
    if args.command == "resume":
        if not args.explanation.strip():
            raise ValueError("Recovery requires a reviewed failure explanation")
        history = aggregation.attempts(args.evidence, args.shard)
        if not history:
            raise ValueError("No previous shard attempt to recover")
        args.attempt = int(history[-1].name.rsplit("-", 1)[1]) + 1
    if min(args.module_timeout, args.shard_timeout) <= 0:
        raise ValueError("Timeouts must be positive")
    directory = execution.run_shard(
        plan,
        args.shard,
        args.output.resolve(),
        attempt=args.attempt,
        explanation=getattr(args, "explanation", ""),
        module_timeout=args.module_timeout,
        shard_timeout=args.shard_timeout,
    )
    return int(common.read(directory / "shard.json")["status"] != "passed")


def main(argv: list[str] | None = None) -> int:
    """Return a nonzero gate result for malformed or incomplete evidence."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_OPENGL", "software")
    args = parser().parse_args(argv)
    try:
        return dispatch(args)
    except (OSError, ValueError, KeyError) as error:
        sys.stderr.write(f"Release verification failed: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
