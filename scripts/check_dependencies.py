"""Generate dependency projections and validate startup and Windows lock coverage."""

import argparse
import ast
import logging
import re
import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
HEADER = "# Generated from pyproject.toml; run python -m scripts.check_dependencies --write.\n"
logger = logging.getLogger(__name__)


def projections(project: dict[str, Any]) -> dict[str, str]:
    """Render secondary pip inputs from project metadata without resolving packages."""
    runtime = project["dependencies"]
    extras = project["optional-dependencies"]
    files = {"requirements/runtime.txt": HEADER + "\n".join(runtime) + "\n"}
    for group in ("dev", "docs", "semantic-search", "windows-build"):
        files[f"requirements/{group}.txt"] = (
            HEADER + "-r runtime.txt\n" + "\n".join(extras[group]) + "\n"
        )
    files["requirements.txt"] = (
        HEADER
        + "# Complete source-development environment (including local embeddings).\n"
        + "-r requirements/dev.txt\n-r requirements/docs.txt\n"
        + "-r requirements/semantic-search.txt\n"
    )
    windows = runtime + extras["semantic-search"] + extras["windows-build"]
    files["packaging/windows/requirements.in"] = (
        HEADER
        + "# Full Windows package; compile on Windows x64 / Python 3.13.\n"
        + "\n".join(sorted(windows, key=str.casefold))
        + "\n"
    )
    return files


def validate_contracts(root: Path, project: dict[str, Any]) -> list[str]:
    """Require complete preflight coverage and compatible hashed release pins."""
    errors: list[str] = []
    module = ast.parse((root / "src/app/startup_check.py").read_text("utf-8"))
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "REQUIRED_MODULES" for t in node.targets
        )
    )
    checked = [
        canonicalize_name(label) for label, _ in ast.literal_eval(assignment.value)
    ]
    declared = {canonicalize_name(Requirement(s).name) for s in project["dependencies"]}
    if set(checked) != declared or len(checked) != len(set(checked)):
        errors.append(
            f"Startup coverage drift: missing={sorted(declared - set(checked))}, "
            f"unexpected={sorted(set(checked) - declared)} (duplicates also forbidden)"
        )
    extras = project["optional-dependencies"]
    direct = (
        project["dependencies"] + extras["semantic-search"] + extras["windows-build"]
    )
    lock = (root / "packaging/windows/requirements.lock").read_text("utf-8")
    # Join pip-compile continuations to retain each requirement's hash block.
    blocks = lock.replace("\\\n", " ").splitlines()
    locked: dict[str, tuple[str, bool]] = {}
    for block in blocks:
        match = re.match(r"^([\w.-]+)==([^\s;]+)", block)
        if match:
            locked[canonicalize_name(match[1])] = (match[2], "--hash=sha256:" in block)
    for raw in direct:
        requirement = Requirement(raw)
        name = canonicalize_name(requirement.name)
        pin = locked.get(name)
        if pin is None or not pin[1] or not requirement.specifier.contains(pin[0]):
            errors.append(f"Windows lock missing/incompatible/unhashed pin: {raw}")
    return errors


def check(root: Path = ROOT, *, write: bool = False) -> list[str]:
    """Check generated files and contracts, optionally rewriting projections."""
    project = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]
    errors = []
    for relative, content in projections(project).items():
        path = root / relative
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        elif not path.exists() or path.read_text("utf-8") != content:
            errors.append(f"Stale generated dependency file: {relative}")
    return errors + validate_contracts(root, project)


def main() -> int:
    """Expose dependency checks as a CI-friendly command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate pip inputs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    errors = check(write=args.write)
    for error in errors:
        logger.error(error)
    if not errors:
        logger.info("Dependency projections, startup coverage and Windows pins agree.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
