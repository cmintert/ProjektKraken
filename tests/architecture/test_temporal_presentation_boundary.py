"""Rendering consumers receive classified meaning rather than reinterpreting dates."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.ci_fast
ROOT = Path(__file__).parents[2]


def test_retired_temporal_renderers_cannot_return():
    retired = {"temporal_display", "temporal_presentation"}
    retired_calls = {
        "event_temporal_display",
        "event_temporal_presentation",
        "projection_display",
    }
    for name in retired:
        assert not (ROOT / "src/core" / f"{name}.py").exists()
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {f"src.core.{name}" for name in retired}, path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in retired_calls, path


def test_screen_geometry_and_repeat_glyphs_cannot_classify_authored_dates():
    for name in ("temporal_geometry", "occurrence_marker"):
        source = (ROOT / "src/gui/widgets/timeline" / f"{name}.py").read_text("utf-8")
        tree = ast.parse(source)
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert not attributes & {"precision", "qualifier", "explicit_window"}
        if name == "occurrence_marker":
            assert 'TemporalGeometry("exact"' not in source
