"""Enforce one-way Ruff complexity allowances and improvement on executable edits."""

from __future__ import annotations

import argparse
import ast
import copy
import io
import json
import re
import subprocess
import sys
import tokenize
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = "scripts/complexity_policy_baseline.json"
NORMAL_LIMIT = 15
SCHEMA = 1
NOQA = re.compile(r"#\s*(?:(ruff|flake8):\s*)?noqa\b(?:\s*:\s*([\w, ]+))?", re.I)
METRIC = re.compile(r"\((\d+) > 0\)$")
MEASURE_ARGS = [
    "check",
    "--isolated",
    "--select",
    "C901",
    "--ignore-noqa",
    "--config",
    "lint.mccabe.max-complexity=0",
    "--target-version",
    "py313",
    "--no-cache",
    "--output-format",
    "json",
]


@dataclass(frozen=True)
class Callable:
    """Measured source identity, independent of presentation-only changes."""

    path: str
    symbol: str
    line: int
    executable: str
    complexity: int
    suppressed: bool

    @property
    def key(self) -> tuple[str, str]:
        """Return the current locator, separate from the persistent allowance ID."""
        return self.path, self.symbol


@dataclass(frozen=True)
class Allowance:
    """Reviewed ceiling with an ID carried through file moves and renames."""

    id: str
    path: str
    symbol: str
    ceiling: int
    reason: str

    @property
    def key(self) -> tuple[str, str]:
        """Return the current callable locator."""
        return self.path, self.symbol


class ExecutableAST(ast.NodeTransformer):
    """Discard docstrings while retaining signatures, decorators and executable code."""

    def generic_visit(self, node: ast.AST) -> ast.AST:
        """Normalize docstrings only in scopes where Python treats them as such."""
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
        return super().generic_visit(node)


def executable(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Normalize an outer callable name so pure relocation/rename is not a touch."""
    normalized = copy.deepcopy(node)
    normalized.name = "_callable"
    return ast.dump(ExecutableAST().visit(normalized), include_attributes=False)


def covers_complexity(codes: list[str]) -> bool:
    """Recognize rule prefixes that disable C901."""
    return any("C901".startswith(code.upper()) for code in codes)


def suppression_rows(source: str) -> set[int]:
    """Find explicit C901 comments and reject blanket complexity suppression."""
    rows = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        match = NOQA.search(token.string)
        if match is None:
            continue
        codes = re.findall(r"[A-Za-z]+\d*", match[2] or "")
        if not codes or covers_complexity(codes):
            if match[1] or "C901" not in codes:
                raise ValueError(f"Line {token.start[0]}: blanket C901 suppression")
            rows.add(token.start[0])
    return rows


def callables(source: str, path: str, metrics: dict[int, int]) -> list[Callable]:
    """Resolve Ruff diagnostic rows to qualified AST callables, including nested ones."""
    tree = ast.parse(source, filename=path)
    suppressed = suppression_rows(source)
    result: list[Callable] = []
    claimed = set()

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = f"{scope}.{node.name}".strip(".")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Ruff associates C901 with the definition/header, not arbitrary body lines.
            header_end = node.body[0].lineno if node.body else node.lineno
            rows = suppressed.intersection(range(node.lineno, header_end))
            rows.update(suppressed.intersection({node.lineno}))
            claimed.update(rows)
            if node.lineno not in metrics:
                raise ValueError(f"{path}:{node.lineno}: missing Ruff measurement")
            result.append(
                Callable(
                    path,
                    scope,
                    node.lineno,
                    executable(node),
                    metrics[node.lineno],
                    bool(rows),
                )
            )
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "")
    if suppressed - claimed:
        raise ValueError(
            f"{path}: unbound C901 suppression at {sorted(suppressed - claimed)}"
        )
    counts = Counter(item.key for item in result)
    if any(
        counts[item.key] > 1 and (item.suppressed or item.complexity > NORMAL_LIMIT)
        for item in result
    ):
        raise ValueError(f"{path}: ambiguous callable identity")
    # Conditional local helpers/overloads below the limit need no allowance.
    return [item for item in result if counts[item.key] == 1]


def ruff(arguments: list[str], root: Path, source: str | None = None) -> str:
    """Run the project Ruff module without caches or project suppression settings."""
    process = subprocess.run(
        [sys.executable, "-m", "ruff", *arguments],
        cwd=root,
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode not in (0, 1) or not process.stdout.strip():
        raise ValueError(f"Ruff failed: {process.stderr.strip() or process.returncode}")
    return process.stdout


def measure(sources: dict[str, str], root: Path) -> dict[tuple[str, str], Callable]:
    """Measure source snapshots through Ruff stdin; never materialize historical files."""
    result: dict[tuple[str, str], Callable] = {}
    for path, source in sorted(sources.items()):
        diagnostics = json.loads(
            ruff(
                [*MEASURE_ARGS, "--stdin-filename", path, "-"],
                root,
                source,
            )
        )
        metrics = {}
        for item in diagnostics:
            match = METRIC.search(item["message"])
            if item["code"] != "C901" or match is None:
                raise ValueError(f"Unexpected Ruff diagnostic: {item}")
            metrics[item["location"]["row"]] = int(match[1])
        result.update((item.key, item) for item in callables(source, path, metrics))
    return result


def measure_tree(
    sources: dict[str, str], root: Path
) -> dict[tuple[str, str], Callable]:
    """Batch current production measurements without allowing exclusions to hide debt."""
    diagnostics = json.loads(
        ruff(
            [
                *MEASURE_ARGS,
                "--no-respect-gitignore",
                "--exclude",
                "",
                "--config",
                'include = ["*.py"]',
                str(root / "src"),
            ],
            root,
        )
    )
    metrics: dict[str, dict[int, int]] = {}
    for item in diagnostics:
        match = METRIC.search(item["message"])
        if item["code"] != "C901" or match is None:
            raise ValueError(f"Unexpected Ruff diagnostic: {item}")
        path = Path(item["filename"]).relative_to(root).as_posix()
        metrics.setdefault(path, {})[item["location"]["row"]] = int(match[1])
    return {
        item.key: item
        for path, source in sorted(sources.items())
        for item in callables(source, path, metrics.get(path, {}))
    }


def load_baseline(source: str) -> dict[str, Allowance]:
    """Reject malformed, duplicate, undocumented or unnecessary allowances."""
    data = json.loads(source)
    if (
        not isinstance(data, dict)
        or type(data.get("schema")) is not int
        or data.get("schema") != SCHEMA
        or not isinstance(data.get("allowances"), list)
    ):
        raise ValueError("Unsupported complexity baseline schema")
    entries = {}
    locators = set()
    for raw in data["allowances"]:
        entry = Allowance(**raw)
        if (
            not all(
                isinstance(v, str) and v.strip()
                for v in (
                    entry.id,
                    entry.path,
                    entry.symbol,
                    entry.reason,
                )
            )
            or type(entry.ceiling) is not int
            or entry.ceiling <= NORMAL_LIMIT
            or not entry.path.startswith("src/")
            or ".." in Path(entry.path).parts
            or entry.id in entries
            or entry.key in locators
        ):
            raise ValueError(f"Invalid or duplicate allowance: {raw}")
        entries[entry.id] = entry
        locators.add(entry.key)
    return entries


def configuration_failures(config: dict[str, Any], root: Path) -> list[str]:
    """Prevent project configuration from bypassing the normal C901 standard."""
    settings = config["tool"]["ruff"]
    lint = settings["lint"]
    failures = []
    if not covers_complexity(lint.get("select", []) + lint.get("extend-select", [])):
        failures.append("Ruff must enable C901")
    if covers_complexity(lint.get("ignore", []) + lint.get("extend-ignore", [])):
        failures.append("Ruff cannot ignore C901")
    if lint.get("mccabe", {}).get("max-complexity") != NORMAL_LIMIT:
        failures.append(f"Normal Ruff complexity limit must remain {NORMAL_LIMIT}")
    for option in ("per-file-ignores", "extend-per-file-ignores"):
        for pattern, codes in lint.get(option, {}).items():
            if covers_complexity(codes):
                failures.append(f"C901 per-file bypass is forbidden: {pattern}")
    if settings.get("extend"):
        failures.append(
            "Ruff configuration inheritance requires explicit policy review"
        )
    for directory in (root, *(root / "src").rglob("*")):
        if directory.is_dir():
            for filename in ("ruff.toml", ".ruff.toml", "pyproject.toml"):
                candidate = directory / filename
                if candidate.is_file() and candidate != root / "pyproject.toml":
                    failures.append(f"Nested/alternate Ruff configuration: {candidate}")
    return failures


def git(root: Path, arguments: list[str], optional: bool = False) -> str | None:
    """Read repository history with a scoped safe-directory setting."""
    process = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode:
        if optional and process.returncode == 1:
            return None
        raise ValueError(
            f"Cannot read Git comparison history: {process.stderr.strip()}"
        )
    return process.stdout


def historical_sources(root: Path, revision: str, paths: set[str]) -> dict[str, str]:
    """Read requested paths only after verifying they exist in the comparison tree."""
    available = set(
        (
            git(root, ["ls-tree", "-r", "--name-only", revision, "--", "src"]) or ""
        ).splitlines()
    )
    return {
        path: git(root, ["show", f"{revision}:{path}"]) or ""
        for path in sorted(paths & available)
    }


def compare(
    current: dict[tuple[str, str], Callable],
    previous: dict[tuple[str, str], Callable],
    entries: dict[str, Allowance],
    old_entries: dict[str, Allowance] | None,
) -> dict[str, Any]:
    """Evaluate identity, strict touch improvement, and exact ceiling requirements."""
    failures: list[str] = []
    adjustments: list[str] = []
    rows: list[dict[str, Any]] = []
    proposed = dict(entries)
    if old_entries is None:
        old_entries = {
            identifier: Allowance(
                entry.id,
                entry.path,
                entry.symbol,
                previous[entry.key].complexity,
                entry.reason,
            )
            for identifier, entry in entries.items()
            if entry.key in previous and previous[entry.key].suppressed
        }
    for identifier in entries.keys() - old_entries.keys():
        failures.append(f"{identifier}: unreviewed allowance or identity reset")
    for identifier, old in old_entries.items():
        new = entries.get(identifier)
        before = previous.get(old.key)
        after = current.get(new.key if new else old.key)
        if before is None:
            failures.append(f"{identifier}: previous reviewed callable is missing")
            continue
        if not before.suppressed or before.complexity != old.ceiling:
            failures.append(f"{identifier}: invalid previous reviewed allowance")
        row = {
            "id": identifier,
            "path": new.path if new else old.path,
            "symbol": new.symbol if new else old.symbol,
            "previous": before.complexity,
            "previous_ceiling": old.ceiling,
            "current": after.complexity if after else None,
            "current_ceiling": new.ceiling if new else None,
            "touched": bool(after and after.executable != before.executable),
            "action": "none",
        }
        rows.append(row)
        check_transition(old, new, before, after, row, failures, adjustments, proposed)
    reviewed = {entry.key for entry in entries.values()}
    for item in current.values():
        if item.key not in reviewed and (
            item.suppressed or item.complexity > NORMAL_LIMIT
        ):
            failures.append(
                f"{item.path}:{item.line} {item.symbol}: unreviewed C901 debt "
                f"({item.complexity}); reduce to {NORMAL_LIMIT}, remove suppression"
            )
    return {
        "schema": SCHEMA,
        "failures": failures,
        "adjustments": adjustments,
        "hotspots": rows,
        "proposed": proposed,
    }


def check_transition(
    old: Allowance,
    new: Allowance | None,
    before: Callable,
    after: Callable | None,
    row: dict[str, Any],
    failures: list[str],
    adjustments: list[str],
    proposed: dict[str, Allowance],
) -> None:
    """Validate one reviewed transition and suggest only safe allowance tightening."""
    label = f"{old.id} {row['path']}:{row['symbol']}"
    if new and new.ceiling > old.ceiling:
        failures.append(f"{label}: ceiling increased {old.ceiling} -> {new.ceiling}")
    if after is None:
        if new:
            adjustments.append(f"{label}: remove allowance for deleted callable")
            proposed.pop(old.id, None)
        row["action"] = "remove allowance"
        return
    if after.complexity > min(old.ceiling, before.complexity):
        row["action"] = "reduce regression"
        failures.append(
            f"{label}: complexity increased; previous {before.complexity}, "
            f"reviewed ceiling {old.ceiling}, current {after.complexity}; reduce regression"
        )
    if row["touched"] and after.complexity >= before.complexity:
        row["action"] = "refactor touched hotspot"
        failures.append(
            f"{label}: executable edit requires strict improvement "
            f"({before.complexity} -> {after.complexity}); refactor the touched hotspot"
        )
    if after.complexity <= NORMAL_LIMIT:
        row["action"] = "remove suppression and allowance"
        if after.suppressed:
            failures.append(f"{label}: obsolete C901 suppression; remove it")
        if new:
            adjustments.append(f"{label}: remove obsolete allowance")
            proposed.pop(old.id, None)
        return
    if new is None or not after.suppressed:
        failures.append(
            f"{label}: reviewed debt still exceeds {NORMAL_LIMIT}; retain identity"
        )
        return
    if new.ceiling != after.complexity:
        row["action"] = "lower ceiling"
        adjustments.append(
            f"{label}: record exact improved ceiling {new.ceiling} -> {after.complexity}"
        )
        if after.complexity < new.ceiling:
            proposed[old.id] = Allowance(
                new.id,
                new.path,
                new.symbol,
                after.complexity,
                new.reason,
            )
        else:
            failures.append(f"{label}: measurement exceeds current allowance")


def check(root: Path = ROOT, base_ref: str = "HEAD") -> dict[str, Any]:
    """Inspect current sources and a resolved historical baseline without mutations."""
    revision = (
        git(
            root,
            [
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{base_ref}^{{commit}}",
            ],
        )
        or ""
    ).strip()
    config = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))
    failures = configuration_failures(config, root)
    pin = next(
        value
        for value in config["project"]["optional-dependencies"]["dev"]
        if value.startswith("ruff==")
    )
    if ruff(["--version"], root).strip() != pin.replace("==", " "):
        failures.append(f"Use project-pinned {pin} to measure complexity")
    entries = load_baseline((root / BASELINE_PATH).read_text("utf-8"))
    available = set(
        (git(root, ["ls-tree", "-r", "--name-only", revision]) or "").splitlines()
    )
    old_entries = None
    if BASELINE_PATH in available:
        old_entries = load_baseline(
            git(root, ["show", f"{revision}:{BASELINE_PATH}"]) or ""
        )
        paths = {entry.path for entry in old_entries.values()}
    else:
        matches = git(
            root, ["grep", "-l", "noqa", revision, "--", "src"], optional=True
        )
        paths = {
            line.removeprefix(f"{revision}:")
            for line in (matches or "").splitlines()
            if line.endswith(".py")
        }
    previous = measure(historical_sources(root, revision, paths), root)
    sources = {
        path.relative_to(root).as_posix(): path.read_text("utf-8-sig")
        for path in (root / "src").rglob("*.py")
    }
    report = compare(measure_tree(sources, root), previous, entries, old_entries)
    report["failures"][:0] = failures
    report["base_ref"] = revision
    return report


def baseline_text(entries: dict[str, Allowance]) -> str:
    """Serialize allowances deterministically for explicit reviewed tightening."""
    return (
        json.dumps(
            {
                "schema": SCHEMA,
                "allowances": [asdict(entry) for _, entry in sorted(entries.items())],
            },
            indent=2,
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Report policy results; optionally apply only verified allowance reductions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--tighten", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check(root=ROOT, base_ref=args.base_ref)
        proposed = report.pop("proposed")
        if args.tighten and not report["failures"] and report["adjustments"]:
            (ROOT / BASELINE_PATH).write_text(baseline_text(proposed), encoding="utf-8")
            report["adjustments"] = []
        errors = report["failures"] + report["adjustments"]
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        SyntaxError,
        StopIteration,
        tokenize.TokenError,
    ) as error:
        report = {
            "schema": SCHEMA,
            "failures": [str(error)],
            "hotspots": [],
            "adjustments": [],
        }
        errors = report["failures"]
    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        for row in report["hotspots"]:
            sys.stdout.write(
                f"{row['id']} {row['path']}:{row['symbol']}: "
                f"{row['previous']} -> {row['current']} "
                f"(touched={row['touched']}, action={row['action']})\n"
            )
        for message in errors:
            sys.stderr.write(message + "\n")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
