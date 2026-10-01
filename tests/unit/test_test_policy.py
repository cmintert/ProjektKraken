"""Regression coverage for discovery and critical-suite policy enforcement."""

import json
from types import SimpleNamespace

import pytest

from scripts import check_test_policy as policy

pytestmark = pytest.mark.ci_fast


def test_hidden_tests_include_untracked_files_and_exclude_artifacts(tmp_path):
    for name in (
        "src/test_hidden.py",
        "scripts/test_accidental.py",
        "tests/unit/test_ok.py",
        ".venv/test_vendor.py",
        "node_modules/test_vendor.py",
        "tmp/test_scratch.py",
        "build/test_generated.py",
        "artifacts/windows/test_vendor.py",
        ".git/test_internal.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert policy.hidden_tests(tmp_path) == [
        "scripts/test_accidental.py",
        "src/test_hidden.py",
    ]


@pytest.mark.parametrize("marks", [["smoke"], ["ci_fast"], ["smoke", "ci_fast"]])
def test_deleted_critical_test_fails(marks):
    baseline = {"schema": 1, "tests": {"tests/unit/test_a.py::test_a": marks}}
    assert policy.regressions(baseline, {"tests": {}}) == [
        "Removed test: tests/unit/test_a.py::test_a",
    ]


@pytest.mark.parametrize("suite", ["smoke", "ci_fast"])
def test_lost_critical_marker_fails(suite):
    baseline = {"schema": 1, "tests": {"test_a": [suite]}}
    assert policy.regressions(baseline, {"tests": {"test_a": []}}) == [
        f"Lost {suite} membership: test_a",
    ]


def test_additions_allowed_and_reviewed_rename_updates_baseline():
    old = {"schema": 1, "tests": {"old": ["ci_fast"]}}
    renamed = {"schema": 1, "tests": {"renamed": ["ci_fast"], "new": []}}
    assert policy.regressions(old, renamed) == ["Removed test: old"]
    assert policy.regressions(renamed, renamed) == []
    assert (
        policy.regressions({"schema": 1, "tests": {"renamed": ["ci_fast"]}}, renamed)
        == []
    )


def test_snapshot_records_overlaps_full_only_and_categories():
    def item(nodeid, marks):
        return SimpleNamespace(
            nodeid=nodeid,
            get_closest_marker=lambda name: name if name in marks else None,
        )

    result = policy.snapshot(
        [
            item("tests/unit/test_a.py::test_a", ["smoke", "ci_fast"]),
            item("tests/integration/test_b.py::test_b", ["slow"]),
            item("tests/test_root.py::test_root", []),
        ]
    )
    assert result["counts"] == {
        "full": 3,
        "full_only": 2,
        "smoke": 1,
        "ci_fast": 1,
        "slow": 1,
        "performance": 0,
    }
    assert result["categories"] == {"unit": 1, "integration": 1, "root": 1}


def test_unknown_schema_rejected():
    with pytest.raises(ValueError, match="schema"):
        policy.regressions({"schema": 2}, {})


def test_main_rejects_hidden_test_before_collection(tmp_path, monkeypatch):
    (tmp_path / "test_hidden.py").touch()
    monkeypatch.setattr(policy, "ROOT", tmp_path)
    monkeypatch.setattr(policy.sys, "argv", ["check"])

    def unexpected_collection(*args, **kwargs):
        pytest.fail("Hidden test policy must fail before collection")

    monkeypatch.setattr(policy.pytest, "main", unexpected_collection)
    with pytest.raises(SystemExit) as error:
        policy.main()
    assert error.value.code == 1


@pytest.mark.parametrize("update", [False, True])
def test_collection_errors_never_compare_or_overwrite_baseline(
    tmp_path,
    monkeypatch,
    update,
):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("original")
    monkeypatch.setattr(policy, "ROOT", tmp_path)
    monkeypatch.setattr(policy.pytest, "main", lambda *args, **kwargs: 2)
    monkeypatch.setattr(
        policy.sys,
        "argv",
        ["check", "--baseline", str(baseline)] + (["--update"] if update else []),
    )
    assert policy.main() == 2
    assert baseline.read_text() == "original"


def test_main_forces_full_collection_and_restores_environment(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(policy, "ROOT", tmp_path)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-m smoke -k missing")
    monkeypatch.setattr(
        policy.sys,
        "argv",
        ["check", "--update", "--baseline", str(baseline)],
    )

    def collect(args, plugins):
        assert "PYTEST_ADDOPTS" not in policy.os.environ
        assert args == [
            str(tmp_path / "tests"),
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
        ]
        plugins[0].result = {"schema": 1, "counts": {"full": 1}, "tests": {"a": []}}
        return 0

    monkeypatch.setattr(policy.pytest, "main", collect)
    assert policy.main() == 0
    assert json.loads(baseline.read_text())["counts"]["full"] == 1
    assert policy.os.environ["PYTEST_ADDOPTS"] == "-m smoke -k missing"
