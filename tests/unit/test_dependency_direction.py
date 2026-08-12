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
