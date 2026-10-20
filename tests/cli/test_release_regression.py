"""Adversarial release evidence tests, including real disposable subprocesses."""

import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_test_policy
from scripts.release_regression import aggregation, common, execution, planner, remote
from scripts.release_regression.__main__ import main

pytestmark = pytest.mark.ci_fast


def native_interpreter():
    """Exercise native containment without a Store broker in disposable probes."""
    if sys.platform != "win32":
        return sys.executable
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        wintypes.DWORD,
    ]
    kernel.GetModuleFileNameW.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    assert kernel.GetModuleFileNameW(None, buffer, len(buffer))
    return buffer.value


def make_plan(nodes=None, shards=2):
    if nodes is None:
        nodes = [f"tests/test_{index}.py::test_ok" for index in range(6)]
    items = [
        SimpleNamespace(nodeid=node, get_closest_marker=lambda _: None)
        for node in nodes
    ]
    return planner.build(
        check_test_policy.snapshot(items),
        nodes,
        sha="a" * 40,
        environment={"test": "environment"},
        run="123",
        durations={},
        shards=shards,
    )


def reseal(plan):
    return common.seal({key: value for key, value in plan.items() if key != "digest"})


def test_planner_exact_once_deterministic_and_automatically_includes_additions():
    plan = make_plan()
    assert plan == make_plan()
    nodes = plan["order"] + ["tests/new/test_added.py::test_new"]
    added = make_plan(nodes)
    assigned = [
        node
        for group in added["shards"]
        for module in group
        for node in added["modules"][module]
    ]
    assert set(assigned) == set(nodes)
    assert len(assigned) == len(nodes)
    assert "tests/new/test_added.py" in added["unknown_durations"]


@pytest.mark.parametrize(
    "corruption", ["missing", "duplicate", "empty", "stale", "path"]
)
def test_planner_rejects_bad_assignment_even_with_new_digest(corruption):
    plan = make_plan()
    if corruption == "missing":
        plan["shards"][0].pop()
    elif corruption == "duplicate":
        plan["shards"][0].append(plan["shards"][1][0])
    elif corruption == "empty":
        plan["shards"][0] = []
    elif corruption == "stale":
        plan["order"].append("tests/test_new.py::test_new")
    else:
        plan["order"][0] = "tests/../outside.py::test_bad"
    with pytest.raises(ValueError):
        planner.validate(reseal(plan))


def test_inventory_rejects_duplicates_before_dictionary_conversion():
    item = SimpleNamespace(
        nodeid="tests/test_a.py::test_a", get_closest_marker=lambda _: None
    )
    with pytest.raises(ValueError, match="Duplicate"):
        check_test_policy.snapshot([item, item])


def test_case_sensitive_nodeids_and_collected_parameter_order_are_preserved():
    nodes = [
        "tests/test_a.py::test_a[z]",
        "tests/test_a.py::test_a[A]",
        "tests/test_a.py::test_a[a]",
    ]
    plan = make_plan(nodes, shards=1)
    assert plan["modules"]["tests/test_a.py"] == nodes


def test_log_duration_estimates_omit_the_incomplete_last_module():
    content = (
        "2026-10-20T12:00:00Z tests/test_a.py::test_one PASSED\n"
        "2026-10-20T12:00:03Z tests/test_a.py::test_two PASSED\n"
        "2026-10-20T12:00:08Z tests/test_b.py::test_three PASSED\n"
    )
    assert planner.durations_from_log(content) == {"tests/test_a.py": 8}


@pytest.fixture
def disposable_suite(tmp_path, monkeypatch):
    """Use real Python/pytest/coverage with no application fixtures or user data."""
    repository = common.ROOT
    dependencies = [path for path in sys.path if Path(path).name == "site-packages"]
    interpreter = native_interpreter()
    root = tmp_path / "fixture repository with spaces"
    (root / "tests").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src/__init__.py").write_text("")
    (root / "src/probe.py").write_text("VALUE = 42\n")
    (root / "pytest.ini").write_text("[pytest]\n")
    config = root / "scripts/release_regression/coverage.ini"
    config.parent.mkdir(parents=True)
    config.write_text(
        (repository / "scripts/release_regression/coverage.ini").read_text()
    )
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "environment", lambda: {"test": "environment"})
    monkeypatch.setattr(common, "source_sha", lambda: "a" * 40)
    monkeypatch.setattr(common, "configuration", lambda: {})
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(root), str(repository), *dependencies])
    )
    monkeypatch.setattr(sys, "executable", interpreter)

    def prepare(modules):
        nodes = []
        for name, body in modules.items():
            (root / f"tests/test_{name}.py").write_text(
                "from src.probe import VALUE\n" + body, encoding="utf-8"
            )
            nodes.append(f"tests/test_{name}.py::test_probe")
        return root, make_plan(nodes, shards=1)

    return prepare


def test_failure_abort_and_timeout_preserve_later_module_results(disposable_suite):
    root, plan = disposable_suite(
        {
            "a_assert": "def test_probe():\n    assert VALUE == 0\n",
            "b_abort": "def test_probe():\n    import os\n    os._exit(134)\n",
            "c_timeout": "def test_probe():\n    import time\n    time.sleep(60)\n",
            "d_pass": "def test_probe():\n    assert VALUE == 42\n",
        }
    )
    directory = execution.run_shard(
        plan, 0, root / "evidence", module_timeout=5, shard_timeout=45
    )
    report = common.read(directory / "shard.json")
    assert [item["status"] for item in report["modules"]] == [
        "test_failure",
        "crash",
        "timeout",
        "passed",
    ]
    assert report["status"] == "failed"
    assert "test_probe" in (directory / "1/progress.jsonl").read_text()
    summary = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert summary["status"] == "failed"
    assert not (root / "aggregate/coverage.xml").exists()


@pytest.fixture
def successful_evidence(disposable_suite):
    root, plan = disposable_suite({"ok": "def test_probe():\n    assert VALUE == 42\n"})
    directory = execution.run_shard(plan, 0, root / "evidence", module_timeout=15)
    assert common.read(directory / "shard.json")["status"] == "passed"
    return root, plan, directory


def test_complete_evidence_combines_coverage_and_verifies_release(successful_evidence):
    root, plan, _ = successful_evidence
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "passed", result["errors"]
    assert (root / "aggregate/coverage.xml").is_file()
    remote.verify_summary(root / "aggregate", plan["sha"], {"id": 123})


def test_separate_runner_image_retains_provenance_without_blocking_shard(
    disposable_suite, monkeypatch
):
    root, plan = disposable_suite({"ok": "def test_probe():\n    assert VALUE == 42\n"})
    plan["environment"] = {"image": "planner-image"}
    plan = reseal(plan)
    monkeypatch.setattr(common, "environment", lambda: {"image": "shard-image"})
    directory = execution.run_shard(plan, 0, root / "evidence", module_timeout=15)
    assert common.read(directory / "shard.json")["environment"] == {
        "image": "shard-image"
    }
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "passed", result["errors"]
    assert result["shards"][0]["runner_image"] == "shard-image"


def test_recovery_rejects_runner_image_drift(disposable_suite, monkeypatch):
    root, plan = disposable_suite({"ok": "def test_probe():\n    assert VALUE == 42\n"})
    monkeypatch.setattr(common, "environment", lambda: {"image": "first-image"})
    execution.run_shard(plan, 0, root / "evidence", module_timeout=15)
    monkeypatch.setattr(common, "environment", lambda: {"image": "new-image"})
    execution.run_shard(plan, 0, root / "evidence", attempt=2, module_timeout=15)
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "failed"
    assert "mismatched provenance" in result["errors"][0]
    assert not (root / "aggregate/coverage.xml").exists()


@pytest.mark.parametrize("missing", ["junit.xml", "coverage.data", "progress.jsonl"])
def test_missing_artifacts_fail_closed(successful_evidence, missing):
    root, plan, directory = successful_evidence
    (directory / "0" / missing).unlink()
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "failed"
    assert not (root / "aggregate/coverage.xml").exists()


def test_later_incomplete_attempt_never_falls_back_to_previous_pass(
    successful_evidence,
):
    root, plan, _ = successful_evidence
    (root / "evidence/shard-0-attempt-2").mkdir()
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "failed"
    assert result["ledger"][0]["selected"] == "shard-0-attempt-2"


def test_recovery_requires_bound_review_and_retains_attempt_ledger(successful_evidence):
    root, plan, _ = successful_evidence
    execution.run_shard(plan, 0, root / "evidence", attempt=2, module_timeout=15)
    denied = aggregation.aggregate(plan, root / "evidence", root / "denied")
    assert denied["status"] == "failed"
    review = {
        "sha": plan["sha"],
        "run": plan["run"],
        "attempt": 2,
        "reviewer": "operator",
        "explanation": "Reviewed disposable infrastructure failure",
    }
    accepted = aggregation.aggregate(plan, root / "evidence", root / "accepted", review)
    assert accepted["status"] == "passed", accepted["errors"]
    assert len(accepted["ledger"][0]["attempts"]) == 2


def test_environment_or_sha_drift_prevents_execution(successful_evidence, monkeypatch):
    root, plan, _ = successful_evidence
    monkeypatch.setattr(common, "environment", lambda: {"changed": True})
    with pytest.raises(ValueError, match="fresh complete run"):
        common.provenance(plan, expected_environment={"test": "environment"})
    monkeypatch.setattr(common, "source_sha", lambda: "b" * 40)
    result = aggregation.aggregate(plan, root / "evidence", root / "wrong-source")
    assert result["status"] == "failed"
    assert not (root / "wrong-source/coverage.xml").exists()


def test_teardown_failure_is_not_a_passing_case():
    parts = [
        {"phase": phase, "outcome": outcome, "xfail": False}
        for phase, outcome in [
            ("setup", "passed"),
            ("call", "passed"),
            ("teardown", "failed"),
        ]
    ]
    assert execution.case_outcome(parts) == "failed"


def test_cross_host_artifact_redirect_strips_authorization():
    request = urllib.request.Request(
        "https://api.github.com/artifact", headers={"Authorization": "Bearer private"}
    )
    redirected = remote.SafeRedirect().redirect_request(
        request, None, 302, "Found", {}, "https://storage.example.invalid/file"
    )
    assert not redirected.has_header("Authorization")


def test_artifact_path_traversal_rejected(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../outside", "bad")
    with pytest.raises(ValueError, match="unsafe path"):
        remote.extract(stream.getvalue(), tmp_path)


def test_json_duplicate_keys_rejected(tmp_path):
    path = tmp_path / "ambiguous.json"
    path.write_text('{"status":"failed","status":"passed"}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        common.read(path)


def test_store_python_is_rejected_before_certifying_isolation(monkeypatch):
    from scripts.release_regression.process_tree import ensure_runtime

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        sys, "_base_executable", "C:/Users/test/Microsoft/WindowsApps/python.exe"
    )
    with pytest.raises(ValueError, match="non-WindowsApps Python 3.13"):
        ensure_runtime()


def test_plain_smoke_success_cannot_certify_release(monkeypatch):
    with pytest.raises(ValueError, match="manual release workflow"):
        remote.verify_run(
            "owner/repo",
            "sha",
            {
                "id": 123,
                "head_sha": "sha",
                "event": "push",
                "path": ".github/workflows/tests.yml",
                "status": "completed",
                "conclusion": "success",
            },
        )


def test_recovery_approval_must_name_current_attempt_and_environment(monkeypatch):
    approval = {
        "state": "approved",
        "comment": "attempt 2: Investigated runner loss",
        "user": {"login": "reviewer"},
        "environments": [{"name": "release-regression-recovery"}],
    }
    monkeypatch.setattr(remote, "api", lambda _: [approval])
    assert remote.github_review("owner/repo", "123", 2, "sha")["reviewer"] == "reviewer"
    with pytest.raises(ValueError):
        remote.github_review("owner/repo", "123", 3, "sha")


def test_verify_cli_does_not_require_pytest_in_packaging_environment(tmp_path):
    """The isolated packaging environment deliberately has no pytest installed."""
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "scripts.release_regression",
            "verify",
            "--sha",
            "x",
            "--repo",
            "owner/repo",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        env={
            key: value
            for key, value in os.environ.items()
            if key not in {"GH_TOKEN", "GITHUB_TOKEN"}
        },
    )
    assert result.returncode == 1
    assert "GH_TOKEN is required" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr


def test_invalid_cli_evidence_is_red(tmp_path):
    assert (
        main(
            [
                "aggregate",
                "--plan",
                str(tmp_path / "missing.json"),
                "--evidence",
                str(tmp_path),
                "--output",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )


@pytest.mark.parametrize("hang", [False, True])
def test_native_descendants_are_killed_on_completion_and_timeout(tmp_path, hang):
    import time

    ready, escaped = tmp_path / "ready", tmp_path / "escaped"
    child = (
        "from pathlib import Path; import time; "
        f"Path({str(ready)!r}).touch(); time.sleep(2); "
        f"Path({str(escaped)!r}).touch()"
    )
    parent = (
        "import subprocess,sys,time; from pathlib import Path; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        f"ready=Path({str(ready)!r})\n"
        "while not ready.exists(): time.sleep(.005)\n"
        + ("time.sleep(60)" if hang else "")
    )
    result = execution.launch(
        [native_interpreter(), "-c", parent], tmp_path, os.environ.copy(), 1
    )
    assert ready.exists()
    assert result["timed_out"] == hang
    assert result.get("error") is None
    time.sleep(2.1)
    assert not escaped.exists()


def test_corrupt_coverage_never_publishes_complete_xml(successful_evidence):
    root, plan, directory = successful_evidence
    coverage = directory / "0/coverage.data"
    coverage.write_bytes(b"not a coverage database")
    report_path = directory / "0/module.json"
    report = common.read(report_path)
    report["files"]["coverage.data"] = common.file_hash(coverage)
    common.write(report_path, reseal(report))
    result = aggregation.aggregate(plan, root / "evidence", root / "aggregate")
    assert result["status"] == "failed"
    assert "Coverage merge failed" in result["errors"][0]
    assert not (root / "aggregate/coverage.xml").exists()


def test_workflow_upload_failure_blocks_otherwise_complete_evidence(
    successful_evidence,
):
    root, plan, _ = successful_evidence
    result = aggregation.aggregate(
        plan, root / "evidence", root / "aggregate", upstream_result="failure"
    )
    assert result["status"] == "failed"
    assert not (root / "aggregate/coverage.xml").exists()
