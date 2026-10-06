"""Reject new presentation color decisions and incomplete semantic theme mappings.

Legacy exceptions are exact, reviewed source fingerprints, not directory exclusions.
This checker deliberately has no baseline-generation or update option.
"""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.visual_roles import contrast_failures, validate_visual_roles

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts/visual_policy_baseline.json"
COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{6,8}\b|#[0-9a-fA-F]{3}\b|\b(?:rgba?|hsla?)\s*\(",
)
NAMED_QSS_COLOR = re.compile(
    r"(?:color|background|border[^:;{}]*)\s*:[^;{}]*\b"
    r"(?:white|black|red|blue|green|orange|gray|grey|yellow)\b",
    re.I,
)
DERIVATIONS = {"lighter", "darker", "setAlpha", "setAlphaF", "_blend_hex"}
COLOR_CONSTRUCTORS = {"QColor", "QBrush", "QPen"}
COLOR_FACTORIES = {"fromRgb", "fromRgbF", "fromHsv", "fromHsvF", "fromCmyk"}


@dataclass(frozen=True)
class Violation:
    """Stable source identity plus a human-readable location."""

    path: str
    symbol: str
    rule: str
    fingerprint: str
    line: int

    @property
    def key(self) -> str:
        """Identify the exact expression, independent of line-number shifts."""
        return "|".join((self.path, self.symbol, self.rule, self.fingerprint))


def scan_source(source: str, path: str) -> list[Violation]:
    """Find color literals/variants without mistaking docstrings for UI code."""
    violations: list[Violation] = []

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = f"{scope}.{node.name}".strip(".")
        rule = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if COLOR_LITERAL.search(node.value) or NAMED_QSS_COLOR.search(node.value):
                rule = "literal-color"
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Attribute)
                and node.value.attr == "GlobalColor"
                and node.attr != "transparent"
            ):
                rule = "literal-color"
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name in DERIVATIONS:
                rule = "local-color-derivation"
            factory = (
                name in COLOR_FACTORIES
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "QColor"
            )
            if (name in COLOR_CONSTRUCTORS or factory) and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and (
                    isinstance(first.value, (int, float))
                    or (
                        isinstance(first.value, str)
                        and first.value != "transparent"
                        and not COLOR_LITERAL.search(first.value)
                    )
                ):
                    rule = "literal-color"
        if rule:
            assert isinstance(node, (ast.Constant, ast.Attribute, ast.Call))
            fingerprint = hashlib.sha256(ast.dump(node).encode()).hexdigest()[:16]
            violations.append(Violation(path, scope, rule, fingerprint, node.lineno))
        children = list(ast.iter_child_nodes(node))
        if hasattr(node, "body") and isinstance(node.body, list) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                children = [child for child in children if child is not first]
        for child in children:
            visit(child, scope)

    visit(ast.parse(source, filename=path), "")
    return violations


def scan_tree(root: Path) -> list[Violation]:
    """Scan all application and GUI Python presentation paths."""
    violations = [
        violation
        for directory in ("src/gui", "src/app")
        for path in sorted((root / directory).rglob("*.py"))
        for violation in scan_source(
            path.read_text(encoding="utf-8-sig"), path.relative_to(root).as_posix()
        )
    ]
    for path in sorted((root / "src/resources").rglob("*.qss")):
        violations.extend(
            scan_stylesheet(
                path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()
            )
        )
    return violations


def scan_stylesheet(source: str, path: str) -> list[Violation]:
    """Scan template declarations without confusing token braces with blocks."""
    source = re.sub(
        r"/\*.*?\*/", lambda match: "\n" * match[0].count("\n"), source, flags=re.S
    )
    source = re.sub(r"\{[a-zA-Z_]\w*\}", "theme_token", source)
    violations = []
    for block in re.finditer(r"[^{}]+\{+([^{}]*)\}+", source):
        for declaration in re.finditer(r"[^;]+", block[1]):
            expression = declaration[0].strip()
            if COLOR_LITERAL.search(expression) or NAMED_QSS_COLOR.search(expression):
                fingerprint = hashlib.sha256(expression.encode()).hexdigest()[:16]
                start = block.start(1) + declaration.start()
                start += len(declaration[0]) - len(declaration[0].lstrip())
                violations.append(
                    Violation(
                        path,
                        "stylesheet",
                        "literal-color",
                        fingerprint,
                        source[:start].count("\n") + 1,
                    )
                )
    return violations


def baseline_failures(
    violations: list[Violation],
    baseline: dict[str, Any],
) -> list[str]:
    """Reject new expressions, duplicate growth and stale or vague exceptions."""
    failures = []
    if baseline.get("schema") != 1:
        return ["Unsupported visual policy baseline schema"]
    current = Counter(v.key for v in violations)
    entries = baseline.get("exceptions", [])
    reviewed: dict[str, int] = {}
    for entry in entries:
        key = entry["key"]
        if key in reviewed or not entry.get("reason", "").strip():
            failures.append(f"Duplicate or undocumented exception: {key}")
        reviewed[key] = entry["count"]
        if current[key] < entry["count"]:
            failures.append(f"Stale exception; remove/reduce explicitly: {key}")
    for violation in violations:
        if current[violation.key] > reviewed.get(violation.key, 0):
            failures.append(
                f"{violation.path}:{violation.line} "
                f"{violation.symbol}: {violation.rule}"
            )
    return sorted(set(failures))


def source_scopes(source: str) -> dict[str, str]:
    """Fingerprint callable/class-constant scopes, ignoring formatting and imports."""
    scopes: dict[str, str] = {}

    def visit(
        node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        scope: str,
    ) -> None:
        statements = [
            item
            for item in node.body
            if not isinstance(item, (ast.Import, ast.ImportFrom))
        ]
        if isinstance(node, (ast.Module, ast.ClassDef)):
            statements = [
                item
                for item in statements
                if not isinstance(
                    item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
            ]
        scopes[scope] = "\n".join(ast.dump(item) for item in statements)
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, f"{scope}.{child.name}".strip("."))

    visit(ast.parse(source), "")
    return scopes


def legacy_touch_failures(
    violations: list[Violation],
    baseline: dict[str, Any],
    touched: set[tuple[str, str]],
) -> list[str]:
    """Expire legacy exemptions when their containing presentation scope changes."""
    legacy = {
        entry["key"]
        for entry in baseline["exceptions"]
        if entry.get("category", "legacy") == "legacy"
    }
    return [
        f"{v.path}:{v.line} {v.symbol}: legacy styling touched; "
        "unify/correct this presentation path before committing"
        for v in violations
        if v.key in legacy and (v.path, v.symbol) in touched
    ]


def touched_scopes(root: Path, base_ref: str) -> set[tuple[str, str]]:
    """Compare working/staged source with HEAD locally, or the CI change baseline."""
    git = ["git", "-c", f"safe.directory={root.as_posix()}"]
    if not base_ref or set(base_ref) == {"0"}:
        base_ref = "HEAD^"
    # Resolve to a commit before constructing object paths; never interpret a
    # caller's revision as a Git command option.
    revision = subprocess.run(
        git + ["rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    changed = subprocess.run(
        git
        + [
            "diff",
            "--name-only",
            revision,
            "--",
            "src/gui",
            "src/app",
            "src/resources",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    touched = set()
    for path in changed:
        current = root / path
        if not current.is_file() or current.suffix not in (".py", ".qss"):
            continue
        previous = subprocess.run(
            git + ["show", f"{revision}:{path}"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if current.suffix == ".qss":
            touched.add((path, "stylesheet"))
            continue
        before = source_scopes(previous.stdout) if previous.returncode == 0 else {}
        after = source_scopes(current.read_text(encoding="utf-8-sig"))
        touched.update(
            (path, symbol)
            for symbol, value in after.items()
            if before.get(symbol) != value
        )
    return touched


def check(root: Path = ROOT, base_ref: str | None = "HEAD") -> list[str]:
    """Validate theme contracts and reviewed source policy exceptions."""
    violations = scan_tree(root)
    baseline = json.loads((root / "scripts/visual_policy_baseline.json").read_text())
    failures = baseline_failures(violations, baseline)
    if base_ref is not None:
        try:
            failures.extend(
                legacy_touch_failures(
                    violations, baseline, touched_scopes(root, base_ref)
                )
            )
        except (OSError, subprocess.CalledProcessError) as error:
            failures.append(
                f"Cannot verify next-touch policy against {base_ref}: {error}"
            )
    themes = json.loads((root / "themes.json").read_text())
    for name, theme in themes.items():
        try:
            validate_visual_roles(name, theme)
            failures.extend(f"{name}: {error}" for error in contrast_failures(theme))
        except ValueError as error:
            failures.append(str(error))
    return failures


def main() -> int:
    """Print actionable CI diagnostics without changing source or exemptions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref", default="HEAD", help="Change baseline (default: HEAD)"
    )
    failures = check(base_ref=parser.parse_args().base_ref)
    for failure in failures:
        sys.stderr.write(failure + "\n")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
