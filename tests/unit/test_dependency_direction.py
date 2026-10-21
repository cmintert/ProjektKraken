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
pytestmark = pytest.mark.ci_fast


def test_semantic_index_has_one_service_owner_and_thin_worker_slots():
    """KRT-101 keeps indexing state below the public Qt worker boundary."""
    service_path = _SOURCE_ROOT / "services/worker_semantic_index_service.py"
    service_tree = ast.parse(service_path.read_text(encoding="utf-8"))
    assert all(
        module.split(".")[1] in {"core", "services"}
        for _, module in _imported_modules(service_path)
        if module.startswith("src.")
    )
    assert not any(
        isinstance(node, ast.Name) and node.id in {"QObject", "QThread"}
        for node in ast.walk(service_tree)
    )

    tree = ast.parse((_SOURCE_ROOT / "services/worker.py").read_text("utf-8"))
    worker = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DatabaseWorker"
    )
    owned_state = {
        "_search_service",
        "_pending_embeddings",
        "_embedding_in_progress",
        "_semantic_probe_ran",
        "_semantic_probe_ok",
    }
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr in owned_state
        for node in ast.walk(worker)
    )
    for name in (
        "index_object",
        "rebuild_search_index",
        "query_semantic_suggestions",
    ):
        method = next(
            node
            for node in worker.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [
            node
            for statement in method.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
        ]
        assert len(calls) == 1
        assert ast.unparse(calls[0].func) == f"self._semantic_index.{name}"


def test_simple_load_reporter_cannot_execute_operations():
    """KRT-38 reporting may only log safe context and emit an error."""
    tree = ast.parse((_SOURCE_ROOT / "services/worker.py").read_text("utf-8"))
    worker = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DatabaseWorker"
    )
    reporter = next(
        node
        for node in worker.body
        if isinstance(node, ast.FunctionDef) and node.name == "_report_load_failure"
    )
    allowed_calls = {"logger.error", "type", "safe_stack", "self.error_occurred.emit"}
    for node in ast.walk(reporter):
        if isinstance(node, ast.Call):
            assert ast.unparse(node.func) in allowed_calls, (
                "Load failure reporting cannot execute or dispatch operations"
            )
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            assert node.attr == "error_occurred", (
                "Load failure reporting cannot access database or success signals"
            )


def test_spell_check_capability_has_one_narrow_gui_owner():
    """KRT-39 keeps scheduling and workers out of the authoring view."""
    path = _SOURCE_ROOT / "gui/widgets/spell_check_controller.py"
    allowed = {
        "src.core.theme_manager",
        "src.gui.utils.help_context",
        "src.services.language_tool_service",
    }
    modules = {module for _, module in _imported_modules(path)}
    assert all(
        any(m == root or m.startswith(root + ".") for root in allowed)
        for m in modules
        if m.startswith("src.")
    )
    view = _SOURCE_ROOT / "gui/widgets/wiki_text_edit.py"
    tree = ast.parse(view.read_text("utf-8"))
    assert not any(
        isinstance(node, ast.Attribute) and node.attr.startswith("_lt_")
        for node in ast.walk(tree)
    ), "Spelling state belongs to SpellCheckController"
    assert not any(
        isinstance(node, ast.Name) and node.id in {"QThread", "LanguageToolWorker"}
        for node in ast.walk(tree)
    ), "WikiTextEdit must delegate spelling worker ownership"
    assert not any(
        "wiki_text_edit" in module
        for _, module in _imported_modules(
            _SOURCE_ROOT / "gui/dialogs/spell_check_settings_dialog.py"
        )
    )


def test_temporal_entity_preparation_is_independent_of_ui_and_persistence():
    """Keep the KRT-40 preparation seam limited to pure data transformations."""
    path = _SOURCE_ROOT / "services/temporal_entity_draft_service.py"
    allowed_roots = {"copy", "dataclasses", "typing"}
    assert all(
        module.split(".")[0] in allowed_roots for _, module in _imported_modules(path)
    ), "Preparation must not acquire Qt, app, GUI, commands or persistence dependencies"


def test_temporal_entity_edit_planning_is_independent_of_ui_and_persistence():
    """Keep KRT-42 mutation planning independent of storage and side effects."""
    path = _SOURCE_ROOT / "services/temporal_entity_edit_planner.py"
    assert all(
        module.split(".")[0] in {"copy", "dataclasses", "typing"}
        for _, module in _imported_modules(path)
    ), "Planning must not acquire Qt, app, GUI, commands or persistence dependencies"
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "exec", "eval", "__import__"}
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    ), "Preparation must not open files or bypass the import boundary"


@pytest.mark.parametrize("filename", ["relation_presentation.py", "relation_policy.py"])
def test_relation_preparation_has_only_pure_standard_library_dependencies(filename):
    """Keep wording and assessment reusable below GUI and persistence owners."""
    path = _SOURCE_ROOT / "core" / filename
    assert all(
        module.split(".")[0] in {"collections", "dataclasses", "typing"}
        for _, module in _imported_modules(path)
    ), "Relation preparation must not acquire Qt, SQL, filesystem or lifecycle APIs"
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "exec", "eval", "__import__"}
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    ), "Pure relation preparation must not open files or bypass the import boundary"


def _source_imports(source: str, module: str) -> list[tuple[int, str]]:
    """Resolve absolute and relative imports, including imported child modules."""
    tree = ast.parse(source)
    package = module.split(".")[:-1]
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parents = len(package) - node.level + 1
                if parents <= 0:
                    raise ValueError(f"Import escapes source package: {module}")
                prefix = ".".join(package[:parents] + ([prefix] if prefix else []))
            imports.append((node.lineno, prefix))
            imports.extend(
                (node.lineno, f"{prefix}.{alias.name}")
                for alias in node.names
                if alias.name != "*"
            )
        elif isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
    return imports


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """Read and resolve source imports under the canonical source package."""
    module = ".".join(path.relative_to(_SOURCE_ROOT.parent).with_suffix("").parts)
    return _source_imports(path.read_text(encoding="utf-8"), module)


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


@pytest.mark.parametrize(
    "source,module,expected",
    [
        ("from .. import app", "src.core.events", "src.app"),
        ("from ...gui import widgets", "src.services.repositories.event", "src.gui"),
        (
            "from ..services import db_service",
            "src.app.worker",
            "src.services.db_service",
        ),
        (
            "from src.services import db_service",
            "src.gui.editor",
            "src.services.db_service",
        ),
        ("from . import events", "src.core.__init__", "src.core.events"),
        ("from ..core import events", "src.gui.editor", "src.core.events"),
    ],
)
def test_dependency_guard_resolves_import_forms(source, module, expected):
    assert expected in {name for _, name in _source_imports(source, module)}


def test_dependency_guard_rejects_import_outside_package():
    with pytest.raises(ValueError, match="escapes source package"):
        _source_imports("from ... import app", "src.core.events")


def test_authored_relation_service_stays_below_facade_and_owns_no_sql():
    """Keep the extracted policy independent of lifecycle and SQL owners."""
    path = _SOURCE_ROOT / "services/authored_relation_service.py"
    assert not any(
        module.startswith("src.services.db_service")
        for _, module in _imported_modules(path)
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_calls = {
        "connect",
        "execute",
        "executemany",
        "commit",
        "rollback",
        "transaction",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_calls
        for node in ast.walk(tree)
    ), "Authored relation policy must leave SQL, lifecycle and transactions to owners"


@pytest.mark.parametrize(
    "method,capability",
    [
        ("_validate_relation_endpoint", "validate_endpoint"),
        ("insert_relation", "create"),
        ("update_relation", "update"),
    ],
)
def test_authored_relation_facade_only_delegates(method, capability):
    """Prevent policy or mutation preparation drifting back into the facade."""
    tree = ast.parse(
        (_SOURCE_ROOT / "services/db_service.py").read_text(encoding="utf-8")
    )
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    function = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method
    )
    body = function.body[1:]  # Exclude the method docstring.
    assert len(body) == 1 and isinstance(body[0], (ast.Expr, ast.Return))
    call = body[0].value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    assert call.func.attr == capability
    assert isinstance(call.func.value, ast.Attribute)
    assert call.func.value.attr == "_authored_relations"


def test_relation_commands_use_authored_service_without_parallel_policy():
    """Commands own intent/history; authored persistence owns endpoint policy."""
    path = _SOURCE_ROOT / "commands/relation_commands.py"
    assert not any(
        module.startswith("src.services.repositories")
        for _, module in _imported_modules(path)
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        in {"insert", "get_entity", "get_event", "UUID", "update_relation"}
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "_relation_repo"
        for node in ast.walk(tree)
    ), "Commands must not bypass authored policy through the facade repository"
    assert not any(
        isinstance(node, ast.Constant) and node.value == "mentions"
        for node in ast.walk(tree)
    ), "System-managed type policy belongs to AuthoredRelationService"


def test_connection_browser_has_no_editor_or_persistence_dependencies():
    """Keep the extracted browser independent of editor and mutation owners."""
    for filename in ("connections_overview.py", "connection_presentation.py"):
        modules = _imported_modules(_SOURCE_ROOT / "gui/widgets" / filename)
        assert not any(
            module.startswith(
                (
                    "src.services",
                    "src.commands",
                    "src.app",
                    "src.gui.widgets.entity_editor",
                    "src.gui.widgets.event_editor",
                    "src.gui.widgets.relation_authoring",
                )
            )
            for _, module in modules
        )


@pytest.mark.ci_fast
@pytest.mark.parametrize(
    "relative,allowed",
    [
        (
            "services/timeline_event_preparation_service.py",
            {"src.core.command", "src.core.events"},
        ),
        ("core/timeline_layout.py", set()),
        (
            "gui/workers/layout_worker.py",
            {"src.core.timeline_layout"},
        ),
    ],
)
def test_timeline_preparation_and_worker_dependencies(relative, allowed):
    """Preparation owns data; workers consume no events, calendar or GUI layout."""
    modules = {module for _, module in _imported_modules(_SOURCE_ROOT / relative)}
    assert all(
        any(module == root or module.startswith(root + ".") for root in allowed)
        for module in modules
        if module.startswith("src.")
    )
    if not relative.startswith("gui/"):
        assert not any(module.startswith("PySide6") for module in modules)
        assert all(
            module.split(".")[0] in {"src", "collections", "dataclasses"}
            for module in modules
        ), "Pure timeline preparation must not acquire persistence or lifecycle APIs"
    else:
        assert all(
            module == "PySide6.QtCore" or module.startswith("PySide6.QtCore.")
            for module in modules
            if module.startswith("PySide6")
        ), "Layout workers must not measure or manipulate GUI objects"
