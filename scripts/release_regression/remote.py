"""Read-only GitHub approval and release-evidence verification."""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from scripts.release_regression import common

PAGE_SIZE = 100
REPOSITORY_PARTS = 2


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward a GitHub token to signed artifact-storage redirects."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        """Strip authorization when following a redirect to another host."""
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlparse(req.full_url).netloc != (
            urllib.parse.urlparse(newurl).netloc
        ):
            redirected.remove_header("Authorization")
        return redirected


def api(path: str, *, binary: bool = False) -> Any:
    """Read GitHub with scoped workflow credentials; never print credentials."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GH_TOKEN is required for authoritative GitHub verification")
    request = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.build_opener(SafeRedirect()).open(
        request, timeout=60
    ) as response:
        content = response.read()
    return content if binary else json.loads(content)


def pages(path: str, key: str) -> list[dict[str, Any]]:
    """Do not silently truncate older runs, matrix jobs or retained artifacts."""
    result = []
    separator = "&" if "?" in path else "?"
    for page in range(1, 101):
        items = api(f"{path}{separator}per_page={PAGE_SIZE}&page={page}")[key]
        result.extend(items)
        if len(items) < PAGE_SIZE:
            return result
    raise ValueError("GitHub pagination exceeds verification bound")


def github_review(repo: str, run: str, attempt: int, sha: str) -> dict[str, Any]:
    """Require a reviewer comment explicitly naming the current recovery attempt.

    The recovery job waits on a protected environment. An unprotected or newly
    created environment has no approval record and fails closed here.
    """
    reviews = api(f"repos/{repo}/actions/runs/{run}/approvals")
    prefix = f"attempt {attempt}:"
    approved = [
        review
        for review in reviews
        if review["state"] == "approved"
        and review.get("comment", "").lower().startswith(prefix)
        and review["comment"][len(prefix) :].strip()
        and any(
            env["name"] == "release-regression-recovery"
            for env in review["environments"]
        )
    ]
    if not approved:
        raise ValueError(
            f"Approve recovery with comment '{prefix} <failure explanation>'"
        )
    review = approved[-1]
    return {
        "run": run,
        "sha": sha,
        "attempt": attempt,
        "reviewer": review["user"]["login"],
        "explanation": review["comment"],
    }


def extract(content: bytes, target: Path) -> None:
    """Extract only ordinary files confined to the evidence directory."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise ValueError("Artifact contains an unsafe path")
            if member.is_dir():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))


def verify_summary(directory: Path, sha: str, run: dict[str, Any]) -> None:
    """Validate the trusted aggregate's bound plan, ledger and coverage files."""
    from scripts.release_regression.planner import validate

    summary = common.read(directory / "summary.json")
    plan = common.read(directory / "plan.json")
    common.unseal(summary)
    validate(plan)
    if (
        summary["sha"] != sha
        or plan["sha"] != sha
        or summary["status"] != "passed"
        or summary["run"] != str(run["id"])
        or plan["run"] != str(run["id"])
        or summary["plan"] != plan["digest"]
        or summary["errors"]
        or summary["expected"] != len(plan["order"])
        or len(summary["shards"]) != len(plan["shards"])
        or {item["shard"] for item in summary["shards"]}
        != set(range(len(plan["shards"])))
        or {item["shard"] for item in summary["ledger"]}
        != set(range(len(plan["shards"])))
        or summary["environment"] != plan["environment"]
        or any(item["status"] != "passed" for item in summary["shards"])
    ):
        raise ValueError("Aggregate is incomplete or belongs to a different candidate")
    required = {"coverage.combined", "coverage.xml", "coverage.txt"}
    if set(summary["coverage"]) != required:
        raise ValueError("Missing complete coverage")
    for name, checksum in summary["coverage"].items():
        if common.file_hash(directory / name) != checksum:
            raise ValueError(f"Corrupt combined coverage: {name}")


def verify_run(repo: str, sha: str, run: dict[str, Any]) -> None:
    """Trust only this repository's manual workflow and its successful final job."""
    base = f"repos/{repo}/actions/runs/{run['id']}"
    if (
        run["head_sha"] != sha
        or run["event"] != "workflow_dispatch"
        or run["path"].split("@", 1)[0] != ".github/workflows/tests.yml"
        or run["status"] != "completed"
        or run["conclusion"] != "success"
    ):
        raise ValueError("Required manual release workflow has not passed for this SHA")
    jobs = pages(f"{base}/jobs?filter=latest", "jobs")
    final = [job for job in jobs if job["name"] == "Release verification"]
    if len(final) != 1 or final[0]["conclusion"] != "success":
        raise ValueError("Required Release verification check did not succeed")
    name = f"release-summary-{run['id']}-{run['run_attempt']}"
    artifacts = [
        item
        for item in pages(f"{base}/artifacts", "artifacts")
        if item["name"] == name and not item["expired"]
    ]
    if len(artifacts) != 1:
        raise ValueError("Missing or ambiguous authoritative aggregate artifact")
    data = api(f"repos/{repo}/actions/artifacts/{artifacts[0]['id']}/zip", binary=True)
    with tempfile.TemporaryDirectory(
        prefix="kraken-release-verification-"
    ) as temporary:
        directory = Path(temporary)
        extract(data, directory)
        verify_summary(directory, sha, run)


def verify(repo: str, sha: str, run_id: int | None = None) -> int:
    """Resolve matching runs explicitly; successful smoke is insufficient."""
    if not repo or len(repo.split("/")) != REPOSITORY_PARTS:
        raise ValueError("Pass --repo owner/repository")
    if run_id:
        candidates = [api(f"repos/{repo}/actions/runs/{run_id}")]
    else:
        query = urllib.parse.urlencode({"head_sha": sha, "event": "workflow_dispatch"})
        candidates = pages(
            f"repos/{repo}/actions/workflows/tests.yml/runs?{query}", "workflow_runs"
        )
    if not candidates:
        raise ValueError("No release regression exists for the exact candidate SHA")
    # A newer failed or pending release run must not be masked by an older pass.
    latest = max(candidates, key=lambda run: run["id"])
    verify_run(repo, sha, latest)
    return 0


def dispatch(args: argparse.Namespace) -> int:
    """Expose remote verification and approved recovery recording to the CLI."""
    if args.command == "verify":
        return verify(args.repo, args.sha, args.run)
    review = github_review(
        os.environ["GITHUB_REPOSITORY"],
        os.environ["GITHUB_RUN_ID"],
        int(os.environ["GITHUB_RUN_ATTEMPT"]),
        common.git("rev-parse", "HEAD"),
    )
    common.write(args.output, review)
    return 0
