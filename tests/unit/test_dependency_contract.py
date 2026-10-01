"""Regression tests for generated dependency projections and drift detection."""

import shutil
from pathlib import Path

import pytest

from scripts.check_dependencies import ROOT, check

pytestmark = pytest.mark.ci_fast


@pytest.fixture
def dependency_checkout(tmp_path: Path) -> Path:
    for relative in (
        "pyproject.toml",
        "src/app/startup_check.py",
        "packaging/windows/requirements.lock",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    assert check(tmp_path, write=True) == []
    return tmp_path


def test_checked_in_dependency_contract() -> None:
    assert check() == []


def test_stale_projection_is_detected_and_regenerated(dependency_checkout) -> None:
    path = dependency_checkout / "requirements/runtime.txt"
    path.write_text("PySide6\n", encoding="utf-8")
    assert "Stale generated dependency file: requirements/runtime.txt" in check(
        dependency_checkout
    )
    assert check(dependency_checkout, write=True) == []


def test_new_runtime_requires_preflight_and_release_pin(dependency_checkout) -> None:
    path = dependency_checkout / "pyproject.toml"
    path.write_text(
        path.read_text("utf-8").replace(
            "dependencies = [", 'dependencies = [\n    "example-runtime==1.0",', 1
        ),
        encoding="utf-8",
    )
    errors = check(dependency_checkout, write=True)
    assert any("Startup coverage drift" in error for error in errors)
    assert any("example-runtime==1.0" in error for error in errors)


@pytest.mark.parametrize("replacement", ["numpy==1.0.0", "absent-numpy==2.4.2"])
def test_incompatible_or_missing_release_pin_is_detected(
    dependency_checkout, replacement
) -> None:
    path = dependency_checkout / "packaging/windows/requirements.lock"
    path.write_text(
        path.read_text("utf-8").replace("numpy==2.4.2", replacement),
        encoding="utf-8",
    )
    assert any("numpy==2.4.2" in error for error in check(dependency_checkout))


def test_release_pin_requires_hash(dependency_checkout) -> None:
    path = dependency_checkout / "packaging/windows/requirements.lock"
    path.write_text(
        path.read_text("utf-8").replace("--hash=sha256:", "--removed-hash=sha256:"),
        encoding="utf-8",
    )
    assert any("unhashed pin" in error for error in check(dependency_checkout))


def test_optional_embeddings_are_not_required_for_startup() -> None:
    text = (ROOT / "requirements/runtime.txt").read_text("utf-8")
    assert "sentence-transformers" not in text
    assert "sentence-transformers==5.6.0" in (
        ROOT / "packaging/windows/requirements.in"
    ).read_text("utf-8")
