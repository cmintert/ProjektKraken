"""Fail-closed evidence reconciliation and coverage publication."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from scripts.release_regression import common, execution, planner


def verify_module(directory: Path, expected: list[str]) -> Path:
    """Recompute progress and checksums instead of trusting a green status field."""
    report = common.read(directory / "module.json")
    common.unseal(report)
    required = {
        "selection.json",
        "progress.jsonl",
        "stdout.log",
        "stderr.log",
        "coverage.data",
        "junit.xml",
    }
    if not required.issubset(report["files"]):
        raise ValueError(f"Missing module evidence: {directory}")
    for name, checksum in report["files"].items():
        if Path(name).name != name or common.file_hash(directory / name) != checksum:
            raise ValueError(f"Corrupt module artifact: {directory / name}")
    if common.read(directory / "selection.json") != expected:
        raise ValueError("Module selection changed")
    actual = execution.outcomes(directory, expected)
    if execution.module_status({**report, **actual}) != "passed" or actual != {
        key: report[key] for key in actual
    }:
        raise ValueError(f"Incomplete or failed module: {directory}")
    junit = ElementTree.parse(directory / "junit.xml").getroot()
    cases = list(junit.iter("testcase"))
    if (
        len(cases) != len(expected)
        or list(junit.iter("failure"))
        or list(junit.iter("error"))
    ):
        raise ValueError("JUnit count/outcome mismatch")
    return directory / "coverage.data"


def verify_shard(
    plan: dict[str, Any], directory: Path
) -> tuple[dict[str, Any], list[Path]]:
    """Require a complete successful attempt from the exact frozen plan."""
    report = common.read(directory / "shard.json")
    common.unseal(report)
    if directory.name != f"shard-{report['shard']}-attempt-{report['attempt']}":
        raise ValueError("Shard directory identity mismatch")
    for key, expected in (
        ("plan", plan["digest"]),
        ("sha", plan["sha"]),
        ("run", plan["run"]),
        ("environment", plan["environment"]),
    ):
        if report[key] != expected:
            raise ValueError(f"Shard provenance mismatch: {key}")
    if (
        report["status"] != "passed"
        or report["unstarted"]
        or report.get("source_error")
    ):
        failures = [item for item in report["modules"] if item["status"] != "passed"]
        raise ValueError(
            f"Shard {report['shard']}: {failures}; "
            f"unstarted={report['unstarted']}; {report.get('source_error', '')}"
        )
    if [item["module"] for item in report["modules"]] != plan["shards"][
        report["shard"]
    ]:
        raise ValueError("Shard module assignment mismatch")
    coverage = []
    for index, item in enumerate(report["modules"]):
        if item["directory"] != str(index):
            raise ValueError("Invalid module directory")
        coverage.append(
            verify_module(directory / str(index), plan["modules"][item["module"]])
        )
    return report, coverage


def attempts(root: Path, shard: int) -> list[Path]:
    """Include attempts with only a start record; never fall back past a crash."""
    found = [p for p in root.rglob(f"shard-{shard}-attempt-*") if p.is_dir()]
    numbers = [int(p.name.rsplit("-", 1)[1]) for p in found]
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"Conflicting shard attempts: {shard}")
    return sorted(found, key=lambda p: int(p.name.rsplit("-", 1)[1]))


def verify_history(plan: dict[str, Any], history: list[Path]) -> None:
    """Retain initial-attempt provenance instead of accepting expired history."""
    if int(history[0].name.rsplit("-", 1)[1]) != 1:
        raise ValueError("Missing initial attempt; start a fresh complete run")
    for directory in history:
        started = common.read(directory / "started.json")
        for key, expected in (
            ("plan", plan["digest"]),
            ("sha", plan["sha"]),
            ("run", plan["run"]),
            ("environment", plan["environment"]),
        ):
            if started[key] != expected:
                raise ValueError("Attempt history contains mismatched provenance")


def diagnostics(directory: Path) -> dict[str, Any]:
    """Keep named failures and unfinished cases visible in a red aggregate."""
    path = directory / "shard.json"
    if not path.exists():
        path = directory / "checkpoint.json"
    if not path.exists():
        return {"evidence": directory.name}
    report = common.read(path)
    return {
        key: report[key]
        for key in ("counts", "failures", "skips", "unfinished", "unstarted", "seconds")
        if key in report
    } | {"evidence": directory.name}


def merge_coverage(files: list[Path], output: Path) -> dict[str, str]:
    """Reject empty/corrupt databases before publishing complete XML."""
    with contextlib.chdir(common.ROOT):
        return _merge_coverage(files, output)


def _merge_coverage(files: list[Path], output: Path) -> dict[str, str]:
    """Resolve portable coverage paths against the candidate checkout."""
    from coverage import Coverage, CoverageData

    for path in files:
        data = CoverageData(basename=str(path))
        data.read()
        if not data.measured_files() or any(
            not name.replace("\\", "/").startswith("src/")
            for name in data.measured_files()
        ):
            raise ValueError(f"Empty or nonportable coverage: {path}")
    coverage = Coverage(
        data_file=str(output / "coverage.combined"),
        config_file=str(common.ROOT / "scripts/release_regression/coverage.ini"),
    )
    coverage.combine(data_paths=[str(path) for path in files], strict=True, keep=True)
    coverage.save()
    # Write to a temporary name; an interrupted merge must not advertise complete XML.
    temporary = output / "coverage.pending.xml"
    coverage.xml_report(outfile=str(temporary))
    with (output / "coverage.txt").open("w", encoding="utf-8") as stream:
        coverage.report(file=stream)
    temporary.replace(output / "coverage.xml")
    return {
        name: common.file_hash(output / name)
        for name in ("coverage.combined", "coverage.xml", "coverage.txt")
    }


def aggregate(
    plan: dict[str, Any],
    root: Path,
    output: Path,
    review: dict[str, Any] | None = None,
    upstream_result: str = "success",
) -> dict[str, Any]:
    """Always emit a summary, but publish coverage only from complete evidence."""
    planner.validate(plan)
    root, output = root.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    summary: dict[str, Any] = {
        "schema": 1,
        "sha": plan["sha"],
        "run": plan["run"],
        "plan": plan["digest"],
        "expected": len(plan["order"]),
        "environment": plan["environment"],
        "collection_skips": plan["collection_skips"],
        "shards": [],
        "errors": []
        if upstream_result == "success"
        else [f"Required workflow jobs did not succeed: {upstream_result}"],
        "review": review,
        "coverage": {},
        "ledger": [],
        "skips": [],
    }
    try:
        if (
            common.source_sha() != plan["sha"]
            or common.configuration() != plan["configuration"]
        ):
            summary["errors"].append(
                "Aggregator source/configuration differs from candidate"
            )
    except (OSError, ValueError) as error:
        summary["errors"].append(f"Aggregator source cannot be verified: {error}")
    files: list[Path] = []
    for shard in range(len(plan["shards"])):
        detail: dict[str, Any] = {}
        try:
            history = attempts(root, shard)
            if not history:
                raise ValueError(f"Missing shard {shard}")
            detail = diagnostics(history[-1])
            summary["ledger"].append(
                {
                    "shard": shard,
                    "attempts": [p.name for p in history],
                    "selected": history[-1].name,
                }
            )
            verify_history(plan, history)
            report, data = verify_shard(plan, history[-1])
            if len(history) > 1 or report["attempt"] > 1:
                validate_review(review, report["attempt"], plan)
            summary["shards"].append(
                {
                    "shard": shard,
                    "status": "passed",
                    "attempt": report["attempt"],
                    "seconds": report["seconds"],
                    **detail,
                }
            )
            for item in report["modules"]:
                module = common.read(history[-1] / item["directory"] / "module.json")
                summary["skips"].extend(module["skips"])
            files.extend(data)
        except (
            OSError,
            ValueError,
            KeyError,
            IndexError,
            ElementTree.ParseError,
        ) as error:
            summary["errors"].append(f"Shard {shard}: {error}")
            summary["shards"].append({"shard": shard, "status": "failed", **detail})
    if not summary["errors"]:
        try:
            summary["coverage"] = merge_coverage(files, output)
        except Exception as error:
            # coverage exposes several database/parser exception types. Preserve a
            # red aggregate and diagnostic summary for all of them.
            summary["errors"].append(
                f"Coverage merge failed: {type(error).__name__}: {error}"
            )
    summary["status"] = "failed" if summary["errors"] else "passed"
    summary["merge_seconds"] = time.monotonic() - start
    result = common.seal(summary)
    common.write(output / "summary.json", result)
    common.write(output / "plan.json", plan)
    text = render_summary(result)
    (output / "summary.md").write_text(text, encoding="utf-8")
    return result


def validate_review(
    review: dict[str, Any] | None, attempt: int, plan: dict[str, Any]
) -> None:
    """A recovered run needs an explicit explanation bound to its identity."""
    if (
        not review
        or not review.get("explanation", "").strip()
        or not review.get("reviewer")
        or review.get("run") != plan["run"]
        or review.get("sha") != plan["sha"]
        or review.get("attempt", 0) < attempt
    ):
        raise ValueError("Recovered attempt requires an explicit matching review")


def render_summary(summary: dict[str, Any]) -> str:
    """Show incomplete shards and retained artifacts without implying coverage."""
    lines = [
        f"# Release verification: {summary['status']}",
        f"Candidate: `{summary['sha']}`; run: `{summary['run']}`; "
        f"expected tests: {summary['expected']}.",
        "",
        "| Shard | Result | Attempt | Seconds |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {s['shard']} | {s['status']} | {s.get('attempt', '')} | "
        f"{s.get('seconds', '')} |"
        for s in summary["shards"]
    )
    for shard in summary["shards"]:
        for failure in shard.get("failures", []):
            lines.append(f"\nFailed: `{failure['nodeid']}` ({failure['phase']}).")
        if shard.get("unfinished") or shard.get("unstarted"):
            lines.append(
                f"\nShard {shard['shard']}: "
                f"{len(shard.get('unfinished', []))} unfinished cases; "
                f"{len(shard.get('unstarted', []))} unstarted modules."
            )
    lines.extend(
        [
            "",
            *summary["errors"],
            "",
            f"Execution skips: {len(summary['skips'])}; "
            f"collection skips: {len(summary['collection_skips'])}.",
            "Skip reasons, attempt ledger and environment: summary.json.",
            "Complete coverage published."
            if summary["status"] == "passed"
            else "INCOMPLETE: no complete coverage is certified.",
        ]
    )
    return "\n".join(lines) + "\n"
