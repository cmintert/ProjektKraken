"""Results remain explicit about incomplete and unmeasured tasks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from tests.ux.inspector import capture_widget, inspect_widget
from tests.ux.results import new_result, save_result, validate_result
from tests.ux.runner import REPO_ROOT, run_root


def test_result_schema_and_derived_reports(tmp_path: Path) -> None:
    """A partial internal run cannot turn missing observations into success."""
    result = new_result("trial", REPO_ROOT)
    assert len(result["tasks"]) == 40
    assert result["tasks"]["KA-01"]["seq"] is None
    assert result["tasks"]["KA-01"]["nasa_tlx"] is None
    path = tmp_path / "result.json"
    save_result(path, result)
    assert path.with_suffix(".csv").is_file()
    assert "not_run" in path.with_suffix(".md").read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["archive"]["sha256"]
    result["tasks"]["KA-01"].update(completion="success", correctness=None, notes="ok")
    with pytest.raises(ValueError, match="verified correctness"):
        validate_result(result)


def test_run_path_is_confined() -> None:
    """Traversal and absolute paths cannot reach real worlds."""
    with pytest.raises(ValueError):
        run_root("../worlds")
    with pytest.raises(ValueError):
        run_root("C:\\Users\\chris")
    assert run_root("ux-20260929").is_relative_to(REPO_ROOT / "tmp" / "ux")


def test_inspector_counts_composite_control_once(qapp: object, tmp_path: Path) -> None:
    """The editable combo's private line edit is not a second user control."""
    root = QWidget()
    layout = QVBoxLayout(root)
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItem("First")
    layout.addWidget(combo)
    layout.addWidget(QLineEdit())
    layout.addWidget(QPushButton("Save"))
    root.show()
    result = inspect_widget(root)
    assert result["visible_enabled_controls"] == 3
    assert result["tree"]["children"]
    assert capture_widget(root, tmp_path / "widget.png").is_file()
    root.close()
