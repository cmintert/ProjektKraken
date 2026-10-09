"""Run comprehensive checks locally before pushing or releasing Kraken."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUSH_REF_FIELDS = 4


def git_output(*arguments: str) -> str:
    """Read repository state, failing closed when Git cannot inspect it."""
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Cannot inspect Git state")
    return result.stdout.strip()


def validate_push(refs: str) -> bool:
    """Require every non-deletion update to send the clean checked-out commit."""
    updates = []
    for line in refs.splitlines():
        fields = line.split()
        if len(fields) != PUSH_REF_FIELDS:
            raise RuntimeError("Invalid Git pre-push input; expected four fields")
        local_ref, local_sha, _, _ = fields
        if set(local_sha) != {"0"}:
            updates.append((local_ref, local_sha))
    if not updates:
        return False
    if git_output("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError(
            "Push requires a clean checkout. Commit, stash or remove local changes "
            "before pushing; staged fixes cannot validate an older commit."
        )
    head = git_output("rev-parse", "HEAD")
    for local_ref, local_sha in updates:
        commit = git_output(
            "rev-parse", "--verify", "--end-of-options", f"{local_sha}^{{commit}}"
        )
        if commit != head:
            raise RuntimeError(
                f"Push of {local_ref} does not match HEAD. Check out the commit "
                "being pushed and push it separately."
            )
    return True


def resolve_base_ref(explicit: str | None) -> str:
    """Use the remote main merge-base; HEAD alone misses committed changes."""
    if explicit:
        return explicit
    try:
        base = git_output("merge-base", "HEAD", "refs/remotes/origin/main")
    except RuntimeError as error:
        raise RuntimeError(
            "Cannot find origin/main merge-base. Run 'git fetch origin main' or "
            "pass --base-ref <commit>. Never silently compare against HEAD."
        ) from error
    return base


def make_steps(mode: str, base_ref: str) -> list[tuple[str, list[str]]]:
    """Return the auditable, non-mutating quality steps."""
    py = sys.executable
    steps = [
        ("Dependency contracts", [py, "-m", "scripts.check_dependencies"]),
        ("Repository-wide Ruff", [py, "-m", "ruff", "check"]),
        ("Type check", [py, "-m", "mypy", "src"]),
        (
            "Complexity contract",
            [py, "-m", "scripts.check_complexity_policy", "--base-ref", base_ref],
        ),
        (
            "Visual contract",
            [py, "-m", "scripts.check_visual_policy", "--base-ref", base_ref],
        ),
        ("Reviewed test inventory", [py, "-m", "scripts.check_test_policy"]),
        ("Generated schema", [py, "docs/generate_schema_docs.py", "--check"]),
        (
            "Strict documentation",
            [
                py,
                "-m",
                "sphinx",
                "-n",
                "-W",
                "--keep-going",
                "-b",
                "html",
                "docs",
                "docs/_build/html",
            ],
        ),
    ]
    if mode == "release":
        steps.append(
            (
                "Full regression and coverage",
                [
                    py,
                    "-m",
                    "pytest",
                    "--maxfail=1",
                    "--durations=30",
                    "--cov=src",
                    "--cov-report=term-missing",
                ],
            )
        )
    else:
        steps.append(
            (
                "Fast regression",
                [py, "-m", "pytest", "-m", "smoke or ci_fast", "-q", "--maxfail=1"],
            )
        )
    return steps


def main(argv: list[str] | None = None) -> int:
    """Stop an ordinary Git push as soon as a required local check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("push", "release"))
    parser.add_argument("--base-ref", help="Override origin/main merge-base")
    parser.add_argument(
        "--pre-push", action="store_true", help="Validate all Git updates from stdin"
    )
    args = parser.parse_args(argv)
    pushed_refs: str | None = None
    try:
        if os.environ.get("PRE_COMMIT"):
            raise RuntimeError(
                "Reinstall the push hook with 'python -m scripts.install_hooks'. "
                "The pre-commit wrapper cannot validate every pushed ref."
            )
        if args.pre_push:
            if args.mode != "push":
                raise RuntimeError("--pre-push requires push mode")
            pushed_refs = sys.stdin.read()
            if not validate_push(pushed_refs):
                return 0
        base = resolve_base_ref(args.base_ref)
    except RuntimeError as error:
        parser.error(str(error))

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_OPENGL", "software")
    steps = make_steps(args.mode, base)
    print(
        f"Kraken {args.mode} preflight: {len(steps)} checks (base {base[:12]})",
        flush=True,
    )
    for index, (name, command) in enumerate(steps, start=1):
        print(f"\n[{index}/{len(steps)}] {name}: {shlex.join(command)}", flush=True)
        start = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        except OSError as error:
            print(f"Cannot run {name}: {error}", file=sys.stderr)
            return 1
        if result.returncode:
            print(
                f"FAILED {name} (exit {result.returncode}); push blocked.",
                file=sys.stderr,
            )
            return 1
        print(f"PASS {name} ({time.monotonic() - start:.1f}s)", flush=True)
    if pushed_refs is not None:
        try:
            validate_push(pushed_refs)
        except RuntimeError as error:
            print(f"Push state changed during verification: {error}", file=sys.stderr)
            return 1
    print(f"PASS all {len(steps)} local checks", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
