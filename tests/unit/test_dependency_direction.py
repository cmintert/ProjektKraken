"""Regression guards for ProjektKraken's one-way source dependencies."""

import ast
from pathlib import Path

import pytest

_SOURCE_ROOT = Path(__file__).parents[2] / "src"
_FORBIDDEN_IMPORT_ROOTS = {
    "core": {"app", "gui", "commands", "services"},
    "services": {"app", "gui", "commands"},
    "commands": {"app", "gui"},
    "gui": {"app"},
}


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """Return absolute modules imported by a Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
    return imports


@pytest.mark.parametrize("layer", sorted(_FORBIDDEN_IMPORT_ROOTS))
def test_source_layers_do_not_import_upward(layer: str) -> None:
    """Prevent lower source layers from importing higher application layers."""
    forbidden = _FORBIDDEN_IMPORT_ROOTS[layer]
    violations: list[str] = []
    for path in (_SOURCE_ROOT / layer).rglob("*.py"):
        for line, module in _imported_modules(path):
            parts = module.split(".")
            if len(parts) > 1 and parts[0] == "src" and parts[1] in forbidden:
                relative_path = path.relative_to(_SOURCE_ROOT.parent)
                violations.append(f"{relative_path}:{line} imports {module}")
    assert not violations, "Upward source dependencies:\n" + "\n".join(violations)


def test_gui_and_app_do_not_import_database_service() -> None:
    """Keep the worker-owned database service out of main-thread layers."""
    violations: list[str] = []
    for layer in ("app", "gui"):
        for path in (_SOURCE_ROOT / layer).rglob("*.py"):
            for line, module in _imported_modules(path):
                if module == "src.services.db_service":
                    relative_path = path.relative_to(_SOURCE_ROOT.parent)
                    violations.append(f"{relative_path}:{line}")
    assert not violations, "Main-thread DatabaseService imports:\n" + "\n".join(
        violations
    )


def _private_connection_lines(source: str) -> list[int]:
    """Find private connection access regardless of receiver name."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "_connection":
            lines.append(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr", "setattr", "delattr"}
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "_connection"
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


@pytest.mark.ci_fast
def test_private_connections_stay_in_persistence_internals() -> None:
    """Prevent a second persistence API outside approved connection owners."""
    violations = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        relative = path.relative_to(_SOURCE_ROOT).as_posix()
        if relative == "services/db_service.py" or relative.startswith(
            "services/repositories/"
        ):
            continue
        for line in _private_connection_lines(path.read_text(encoding="utf-8")):
            violations.append(f"src/{relative}:{line}")
    assert not violations, "Private connection access:\n" + "\n".join(violations)


@pytest.mark.ci_fast
@pytest.mark.parametrize(
    "source",
    [
        "db._connection.execute('SELECT 1')",
        "alias = db\nalias._connection",
        "getattr(db, '_connection')",
        "hasattr(db, '_connection')",
        "setattr(db, '_connection', None)",
        "delattr(db, '_connection')",
    ],
)
def test_connection_guard_detects_aliases_and_reflection(source: str) -> None:
    assert _private_connection_lines(source)


@pytest.mark.ci_fast
def test_connection_guard_allows_public_access() -> None:
    assert not _private_connection_lines("db.require_connection().execute('SELECT 1')")
