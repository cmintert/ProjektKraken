"""Permanent responsibility boundaries for optional local world sharing."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.ci_fast


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_transport_and_connector_cannot_query_world_or_import_gui():
    for path in (ROOT / "src/integrations/mcp").glob("*.py"):
        assert not any(
            name.startswith(
                (
                    "src.gui",
                    "src.app",
                    "src.commands",
                    "src.services.db_service",
                    "src.services.repositories",
                    "sqlite3",
                )
            )
            for name in imports(path)
        ), path


def test_read_service_is_independent_of_protocol_and_ui():
    names = imports(ROOT / "src/services/mcp_read_service.py")
    assert not any(
        name.startswith(("PySide6", "mcp", "src.app", "src.gui", "src.commands"))
        for name in names
    )


def test_coordinator_has_no_application_facade_dependency():
    source = (ROOT / "src/app/coordinators/mcp_coordinator.py").read_text(
        encoding="utf-8"
    )
    assert "MainWindow" not in source
    assert "main_window" not in source


def test_console_entry_does_not_launch_desktop_or_cli():
    names = imports(ROOT / "mcp_launcher.py")
    assert names == ["src.integrations.mcp.connector"]
