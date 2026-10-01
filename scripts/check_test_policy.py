"""Check canonical test discovery and reviewed critical-suite membership."""

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests/collection_baseline.json"
SUITES = ("smoke", "ci_fast", "slow", "performance")
EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "build",
    "dist",
    "_build",
    "tmp",
    ".cache",
    ".eggs",
    "__pypackages__",
    "artifacts",
}


def hidden_tests(root: Path) -> list[str]:
    """Find misplaced source tests, including files not tracked by Git."""
    found = []

    def raise_scan_error(error: OSError) -> None:
        raise error

    for directory, directories, files in os.walk(root, onerror=raise_scan_error):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED)
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root)
            if (
                name.startswith("test_")
                and name.endswith(".py")
                and relative.parts[0] != "tests"
            ):
                found.append(relative.as_posix())
    return sorted(found)


def snapshot(items: list[pytest.Item]) -> dict[str, Any]:
    """Record stable node identities and overlapping suite counts."""
    tests = {
        item.nodeid: sorted(suite for suite in SUITES if item.get_closest_marker(suite))
        for item in items
    }
    counts = {
        suite: sum(suite in marks for marks in tests.values()) for suite in SUITES
    }
    counts["full"] = len(tests)
    counts["full_only"] = sum(
        not {"smoke", "ci_fast"}.intersection(marks) for marks in tests.values()
    )
    categories: dict[str, int] = {}
    for nodeid in tests:
        relative = nodeid.split("::", 1)[0].removeprefix("tests/")
        category = relative.split("/", 1)[0] if "/" in relative else "root"
        categories[category] = categories.get(category, 0) + 1
    return {
        "schema": 1,
        "counts": counts,
        "categories": dict(sorted(categories.items())),
        "tests": dict(sorted(tests.items())),
    }


def regressions(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Report removals and critical marker loss, allowing new coverage."""
    if baseline.get("schema") != 1:
        raise ValueError("Unsupported collection baseline schema")
    failures = []
    for nodeid, marks in baseline["tests"].items():
        if nodeid not in current["tests"]:
            failures.append(f"Removed test: {nodeid}")
            continue
        for suite in ("smoke", "ci_fast"):
            if suite in marks and suite not in current["tests"][nodeid]:
                failures.append(f"Lost {suite} membership: {nodeid}")
    return failures


class CollectionRecorder:
    """Capture the complete collection without altering normal local pytest."""

    def __init__(self) -> None:
        """Initialize an empty snapshot until collection completes."""
        self.result: dict[str, Any] = {}

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Record the finished full collection."""
        self.result = snapshot(session.items)


def main() -> int:
    """Collect all tests and check or deliberately update the reviewed baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args()
    misplaced = hidden_tests(ROOT)
    if misplaced:
        parser.exit(1, "Tests outside tests/:\n" + "\n".join(misplaced) + "\n")
    recorder = CollectionRecorder()
    # Explicit root and empty addopts prevent selectors from making a partial baseline.
    output = io.StringIO()
    environment_options = os.environ.pop("PYTEST_ADDOPTS", None)
    try:
        with contextlib.redirect_stdout(output):
            exit_code = pytest.main(
                [str(ROOT / "tests"), "--collect-only", "-q", "-o", "addopts="],
                plugins=[recorder],
            )
    finally:
        if environment_options is not None:
            os.environ["PYTEST_ADDOPTS"] = environment_options
    if exit_code != pytest.ExitCode.OK:
        sys.stderr.write(output.getvalue())
        return int(exit_code)
    current = recorder.result
    if args.update:
        args.baseline.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    else:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        failures = regressions(baseline, current)
        if failures:
            parser.exit(
                1, "\n".join(failures) + "\nReview intentional baseline changes.\n"
            )
        added = set(current["tests"]) - set(baseline["tests"])
        sys.stdout.write(f"Added tests: {len(added)}\n")
        for nodeid in sorted(added):
            sys.stdout.write(f"  {nodeid}\n")
    sys.stdout.write(json.dumps(current["counts"], sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
