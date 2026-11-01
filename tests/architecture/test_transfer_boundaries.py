"""The feature-owned transfer boundary is the only production materializer caller."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.ci_fast
ROOT = Path(__file__).resolve().parents[2]


def test_private_materialization_does_not_escape_transfer_preparation():
    callers = set()
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_materialize_batch"
            for node in ast.walk(tree)
        ):
            callers.add(path.relative_to(ROOT).as_posix())
    assert callers == {"src/services/transfer_import.py"}


def test_obsolete_worker_import_routes_are_retired():
    retired = {"run_import", "run_markdown_import", "run_markdown_batch_import"}
    for path in (
        ROOT / "src/services/worker.py",
        ROOT / "src/app/coordinators/import_coordinator.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        methods = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert not methods & retired
    text = (ROOT / "src/app/worker_manager.py").read_text(encoding="utf-8")
    assert not any(name + "_requested" in text for name in retired)
